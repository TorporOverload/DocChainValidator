from .config import logger, CHUNK_SIZE, MAX_REWIND_DEPTH 
from .protocol import send_message
from blockchain import Block, Blockchain
from typing import Any

def handle_blocks(sock: Any, blockchain: Blockchain, payload: dict[str, Any], peer_id: str) -> None:
    """Handle received blocks from peer, with logic to resolve chain forks and continue syncing."""
    if not isinstance(payload, dict) or 'blocks' not in payload:
        logger.error(f"Invalid blocks payload from peer {peer_id}")
        return

    blocks_data = payload.get('blocks', [])
    if not blocks_data:
        return

    logger.info(f"Received {len(blocks_data)} blocks from {peer_id} for syncing.")
    with blockchain.lock:
        latest_block = blockchain.get_latest_block()
        received_block = Block.from_dict(blocks_data[0])

        # Special case: If our chain is empty, accept blocks starting from genesis
        if not latest_block:
            if received_block.index == 0:  # This is a genesis block
                logger.info("Chain is empty, accepting genesis block from peer")
                blockchain.chain = []
                newly_added_blocks = 0
                for block_dict in blocks_data:
                    block_to_add = Block.from_dict(block_dict)
                    blockchain.chain.append(block_to_add)
                    blockchain.add_block_to_index(block_to_add)
                    newly_added_blocks += 1
                    
                if newly_added_blocks > 0:
                    logger.info(f"Successfully added {newly_added_blocks} blocks starting with genesis")
                    blockchain.save_chain()
                return

            logger.error("Chain is empty but received non-genesis blocks. Requesting complete chain.")
            request = {"type": "GET_BLOCKS", "payload": {"start": 0}}
            send_message(sock, request)
            return

        # Scenario 1: Blocks are sequential and valid. Append them.
        if received_block.index == latest_block.index + 1 and received_block.previous_hash == latest_block.current_hash:
            newly_added_blocks = 0
            for block_dict in blocks_data:
                block_to_add = Block.from_dict(block_dict)
                if any(b.index == block_to_add.index for b in blockchain.chain):
                    continue # Skip blocks we already have
                if blockchain.is_new_block_valid(block_to_add, blockchain.get_latest_block()):
                    blockchain.chain.append(block_to_add)
                    blockchain.add_block_to_index(block_to_add)
                    newly_added_blocks += 1
                else:
                    logger.error(f"Validation failed mid-batch at block {block_to_add.index}. Stopping sync.")
                    return 
            
            if newly_added_blocks > 0:
                logger.info(f"Successfully appended {newly_added_blocks} new blocks.")
                blockchain.save_chain()

            if len(blocks_data) >= CHUNK_SIZE:
                new_height = len(blockchain.chain)
                logger.info(f"Continuing sync. Requesting blocks from new height: {new_height}")
                request = {"type": "GET_BLOCKS", "payload": {"start": new_height}}
                send_message(sock, request)
            else:
                logger.info("Sync complete. Received a partial batch, now fully synced with peer.")
                # Notify connection manager that sync is complete
                if hasattr(blockchain, 'node') and hasattr(blockchain.node, 'connection_manager'):
                    blockchain.node.connection_manager.sync_complete()
                elif hasattr(blockchain, 'connection_manager'):
                    blockchain.connection_manager.sync_complete()
 
        elif received_block.index > latest_block.index + 1:
            # Scenario 2: Gap detected. We are behind the peer.
            logger.info(
                f"Gap detected. Our chain height is {latest_block.index}, but peer "
                f"sent blocks starting from {received_block.index}. Requesting missing blocks."
            )
            request = {"type": "GET_BLOCKS", "payload": {"start": latest_block.index + 1}}
            send_message(sock, request)

        else:
            # Scenario 3: Fork detected. Our chain conflicts with the peer's chain.
            our_latest_block = blockchain.get_latest_block()
            logger.warning(
                f"Fork detected! Our block at index {our_latest_block.index} (hash "
                f"{our_latest_block.current_hash[:8]}..) conflicts with peer's chain "
                f"starting at block {received_block.index} (prev_hash {received_block.previous_hash[:8]}..)."
            )

            # We need to rewind to find a common ancestor.
            rewind_target_index = our_latest_block.index - 1
            
            # Safety check to prevent rewinding past the genesis block.
            if rewind_target_index < 0:
                logger.error("Cannot rewind past genesis block. Requesting full chain sync.")
                request = {"type": "GET_BLOCKS", "payload": {"start": 0}}
                send_message(sock, request)
                return

            logger.info(f"Attempting to resolve fork by rewinding to index {rewind_target_index}.")
            if blockchain.rewind_to_index(rewind_target_index):
                # After rewinding, request blocks again from our new height.
                new_height = len(blockchain.chain)
                logger.info(f"Requesting blocks from new height {new_height} to find common root.")
                request = {"type": "GET_BLOCKS", "payload": {"start": new_height}}
                send_message(sock, request)
            else:
                # If rewind fails, fall back to a full sync.
                logger.error("Failed to rewind chain, requesting full chain sync.")
                request = {"type": "GET_BLOCKS", "payload": {"start": 0}}
                send_message(sock, request)
