
from cryptography.hazmat.primitives import hashes
from text_matcher import separate_sentences
from typing import Tuple, Dict, List
from dataclasses import dataclass
from functools import lru_cache

DP_SEED_CONSTANT = "9ca57ab0545f346b422ebf7fe6be7b9a5e11f214a1e575bfc0db081f4b5fa0ec"

@dataclass
class SignatureStep:
    """Represents one step in the incremental signing process"""
    step_id: int
    content_hash: str
    cumulative_signature: str
    dependencies: List[int]  # Which previous steps this depends on
    metadata: Dict

class DPDocumentSigner:
    """
    Dynamic Programming approach to incremental document signing.
    Each step builds upon previous steps with memoization for efficiency.
    """
    
    def __init__(self, base_seed: str = DP_SEED_CONSTANT):
        self.base_seed = base_seed
        self.signature_cache: Dict[Tuple, str] = {}  # Memoization cache
        self.step_signatures: Dict[int, SignatureStep] = {}  # Store all steps
        
    def _hash_data(self, data: str) -> str:
        """Function to hash data with SHA-256"""
        digest = hashes.Hash(hashes.SHA256())
        digest.update(data.encode('utf-8'))
        return digest.finalize().hex()
    
    @lru_cache(maxsize=None)
    def _compute_base_signature(self, doc_title: str, page_number: int) -> str:
        """
        DP Base Case: Compute the foundational signature for a document page.
        """
        base_data = f"{doc_title}|{page_number}|{self.base_seed}"
        return self._hash_data(base_data)
    
    @lru_cache(maxsize=None)
    def _compute_content_signature(self, content: str) -> str:
        """
        DP Subproblem: Compute signature for content chunks.
        Memoized to handle repeated content patterns efficiently.
        """
        return self._hash_data(content)
    
    def _compute_cumulative_signature(self, 
                                    content_sig: str, 
                                    previous_sigs: Tuple[str, ...], 
                                    step_id: int) -> str:
        """
        DP Recurrence Relation: Compute signature based on current content 
        and all previous signatures this step depends on.
        
        Formula: signature[i] = hash(content[i] + combine(signatures[dependencies]))
        """
        cache_key = (content_sig, previous_sigs, step_id)
        
        if cache_key in self.signature_cache:
            return self.signature_cache[cache_key]
        
        # Combine all dependent signatures
        combined_previous = "|".join(previous_sigs) if previous_sigs else ""
        
        # Create cumulative signature
        cumulative_data = f"{content_sig}|{combined_previous}|step_{step_id}"
        signature = self._hash_data(cumulative_data)
        
        # Memoize result
        self.signature_cache[cache_key] = signature
        return signature
    
    def add_signing_step(self, 
                        step_id: int,
                        content: str,
                        dependencies: List[int] = None,
                        metadata: Dict = None) -> SignatureStep:
        """
        DP Step Addition: Add a new step to the signing process.
        Each step depends on previous steps, creating the DP structure.
        """
        dependencies = dependencies or []
        metadata = metadata or {}
        
        # Store original content for verification
        metadata["original_content"] = content
        
        # Compute content signature (subproblem)
        content_sig = self._compute_content_signature(content)
        
        # Gather signatures from dependencies
        previous_sigs = []
        for dep_id in dependencies:
            if dep_id not in self.step_signatures:
                raise ValueError(f"Dependency step {dep_id} not found")
            previous_sigs.append(self.step_signatures[dep_id].cumulative_signature)
        
        # Compute cumulative signature (recurrence relation)
        cumulative_sig = self._compute_cumulative_signature(
            content_sig, 
            tuple(previous_sigs), 
            step_id
        )
        
        # Store the step
        step = SignatureStep(
            step_id=step_id,
            content_hash=content_sig,
            cumulative_signature=cumulative_sig,
            dependencies=dependencies,
            metadata=metadata
        )
        
        self.step_signatures[step_id] = step
        return step
    
    def verify_signature_integrity(self, step_id: int) -> bool:
        """
        Verify the integrity of a signature step by recomputing it.
        """
        if step_id not in self.step_signatures:
            return False
        
        step = self.step_signatures[step_id]
        
        # Recompute content signature
        original_content = step.metadata.get("original_content", "")
        expected_content_sig = self._compute_content_signature(original_content)
        
        if step.content_hash != expected_content_sig:
            return False
        
        # Gather dependency signatures
        previous_sigs = []
        for dep_id in step.dependencies:
            if dep_id in self.step_signatures:
                previous_sigs.append(self.step_signatures[dep_id].cumulative_signature)
        
        # Recompute cumulative signature
        expected_cumulative = self._compute_cumulative_signature(
            step.content_hash,
            tuple(previous_sigs),
            step_id
        )
        
        return step.cumulative_signature == expected_cumulative
    
    def get_signature_chain(self) -> List[Dict]:
        """
        Return the complete signature chain showing the DP progression.
        Useful for auditing and understanding the incremental process.
        """
        chain = []
        for step_id in sorted(self.step_signatures.keys()):
            step = self.step_signatures[step_id]
            chain.append({
                "step_id": step.step_id,
                "content_hash": step.content_hash[:16] + "...",  # Truncated for display
                "cumulative_signature": step.cumulative_signature[:16] + "...",
                "dependencies": step.dependencies,
                "metadata": step.metadata
            })
        return chain


def generate_dp_page_signature(page_text: str, doc_title: str, page_number: int) -> str:
    """
    Generates a page signature using True Dynamic Programming and Hashing.
    This replaces the original sequential approach with proper DP structure.
    """
    dp_signer = DPDocumentSigner() # changed to instance variable due to crashes in multi-threaded environments
    
    if not page_text:
        # Handle empty page case
        empty_content = f"{doc_title}|{page_number}|EMPTY_PAGE_PLACEHOLDER"
        return dp_signer._compute_base_signature(doc_title, page_number)
    
    # Clear previous steps for new document
    dp_signer.step_signatures.clear()
    
    # Step 0: Base signature (DP base case)
    base_content = f"{doc_title}|{page_number}"
    dp_signer.add_signing_step(
        step_id=0,
        content=base_content,
        dependencies=[],
        metadata={"type": "base", "doc_title": doc_title, "page": page_number}
    )
    
    # Break text into sentences/chunks
    page_chunks = separate_sentences(page_text)
    
    if not page_chunks:
        # If no chunks after processing, return base signature
        return dp_signer.step_signatures[0].cumulative_signature
    
    # Step 1+: Process each chunk incrementally (DP recurrence)
    for i, chunk in enumerate(page_chunks, 1):
        dependencies = [i-1]  # Each step depends on the previous one
        
        dp_signer.add_signing_step(
            step_id=i,
            content=chunk.strip(),
            dependencies=dependencies,
            metadata={"type": "content", "chunk_index": i-1, "chunk_text": chunk}
        )
    
    # Return final cumulative signature
    final_step_id = len(page_chunks)
    return dp_signer.step_signatures[final_step_id].cumulative_signature

def get_dp_signature_details() -> Dict:
    """
    Get detailed information about the DP signature process.
    Useful for debugging and verification.
    """
    global dp_signer
    return {
        "signature_chain": dp_signer.get_signature_chain(),
        "cache_size": len(dp_signer.signature_cache),
        "total_steps": len(dp_signer.step_signatures),
        "cache_stats": {
            "base_signature_cache": dp_signer._compute_base_signature.cache_info(),
            "content_signature_cache": dp_signer._compute_content_signature.cache_info()
        }
    }

def verify_dp_signature_integrity() -> Dict[int, bool]:
    """
    Verify the integrity of all signature steps in the current document.
    Returns a dictionary mapping step_id to verification result.
    """
    global dp_signer
    results = {}
    for step_id in dp_signer.step_signatures:
        results[step_id] = dp_signer.verify_signature_integrity(step_id)
    return results

