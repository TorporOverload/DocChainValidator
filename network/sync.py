from .config import logger, CHUNK_SIZE  # Import CHUNK_SIZE
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

        # Check if the first received block correctly links to our latest block
        if received_block.previous_hash == latest_block.current_hash:
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
 
        else:
            # Fork Detected: Rewind and Retry
            logger.warning(
                f"Fork detected! Our block {latest_block.index} hash "
                f"({latest_block.current_hash[:8]}..) does not match peer's "
                f"previous hash ({received_block.previous_hash[:8]}..)."
            )
            
            rewind_succeeded = blockchain.rewind_to_index(latest_block.index - 1)
            
            if rewind_succeeded:
                new_height = len(blockchain.chain)
                logger.info(f"Requesting blocks again from new height: {new_height}")
                request = {"type": "GET_BLOCKS", "payload": {"start": new_height}}
                send_message(sock, request)
            else:
                logger.error("Failed to rewind chain, cannot resolve fork.")

def handle_new_block(blockchain: Blockchain, payload: dict[str, Any], peer_id: str, broadcast_callback: Any) -> None:
    """Handle a new single block announcement from a peer."""
    if not isinstance(payload, dict) or 'block' not in payload:
        logger.error(f"Invalid new block payload from peer {peer_id}")
        return

    block_dict = payload.get('block')
    if any(b.current_hash == block_dict.get('current_hash') for b in blockchain.chain):
        return

    try:
        new_block = Block.from_dict(block_dict)
        if blockchain.is_new_block_valid(new_block, blockchain.get_latest_block()):
            blockchain.chain.append(new_block)
            blockchain.add_block_to_index(new_block)
            blockchain.save_chain()
            logger.info(f"Accepted and added new block #{new_block.index} from peer {peer_id}")
            broadcast_callback({'type': 'NEW_BLOCK', 'payload': {'block': block_dict}}, exclude_peer=peer_id)
    except Exception as e:
        logger.error(f"Error processing new block from peer {peer_id}: {str(e)}")