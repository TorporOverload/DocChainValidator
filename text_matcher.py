# Text Comparison using KMP Algorithm for document validation and similarity detection

import difflib
from typing import List, Tuple, Dict, Any

def find_text_matches(
    original: str, 
    modified: str
) -> Tuple[str, float, List[Dict[str, Any]]]:
    """
    Compare two texts using KMP and determine if they are:
    1. Exact match
    2. Modified version
    3. Similar document
    4. Different document
    
    Args:
        original (str): The original text.
        modified (str): The modified text.
    
    Returns a tuple (match_type, similarity, matches) where:
    - match_type: 'exact', 'modified', 'similar', or 'different'
    - similarity: percentage of similarity (0-100)
    - matches: list of matching segments with their positions
    """
    def build_kmp_table(pattern: str) -> List[int]:
        """Build failure function table for KMP algorithm"""
        table: List[int] = [0] * len(pattern)
        j = 0
        
        for i in range(1, len(pattern)):
            while j > 0 and pattern[i] != pattern[j]:
                j = table[j - 1]
            
            if pattern[i] == pattern[j]:
                j += 1
            
            table[i] = j
        
        return table

    def kmp_search(text: str, pattern: str) -> List[int]:
        """KMP string search algorithm"""
        if not pattern:
            return []
        
        failure_table = build_kmp_table(pattern)
        matches = []
        j = 0  # pattern index
        for i in range(len(text)):
            while j > 0 and text[i] != pattern[j]:
                j = failure_table[j - 1]
            
            if text[i] == pattern[j]:
                j += 1
            
            if j == len(pattern):
                matches.append(i - j + 1)
                j = failure_table[j - 1]
        
        return matches

    def find_common_substrings(
        text1: str, text2: str, min_length: int = 10
    ) -> List[Dict[str, Any]]:
        """Find common substrings using the selected algorithm"""
        common_matches: List[Dict[str, Any]] = []
        words1 = text1.split()
        
        # Check individual words first
        for word in words1:
            if len(word) >= 4:
                positions = kmp_search(text2.lower(), word.lower())
                if positions:
                    for pos in positions:
                        common_matches.append({
                            'pattern': word,
                            'text1_pos': text1.lower().find(word.lower()),
                            'text2_pos': pos,
                            'length': len(word),
                            'type': 'word'
                        })
        
        # Check phrases (consecutive words)
        for i in range(len(words1) - 1):
            for phrase_len in range(2, min(6, len(words1) - i + 1)):
                phrase = ' '.join(words1[i:i + phrase_len])
                if len(phrase) >= min_length:
                    positions = kmp_search(text2.lower(), phrase.lower())
                    if positions:
                        for pos in positions:
                            common_matches.append({
                                'pattern': phrase,
                                'text1_pos': text1.lower().find(phrase.lower()),
                                'text2_pos': pos,
                                'length': len(phrase),
                                'type': 'phrase'
                            })
        
        # Remove overlapping matches, keeping longer ones
        common_matches.sort(key=lambda x: -x['length'])
        filtered_matches: List[Dict[str, Any]] = []
        used_ranges_text1 = set()
        used_ranges_text2 = set()
        for match in common_matches:
            text1_range = range(match['text1_pos'], match['text1_pos'] + match['length'])
            text2_range = range(match['text2_pos'], match['text2_pos'] + match['length'])
            if not any(pos in used_ranges_text1 for pos in text1_range) and \
               not any(pos in used_ranges_text2 for pos in text2_range):
                filtered_matches.append(match)
                used_ranges_text1.update(text1_range)
                used_ranges_text2.update(text2_range)
        return filtered_matches

    def calculate_similarity(text1: str, text2: str) -> float:
        """Calculate similarity between two texts"""
        seq = difflib.SequenceMatcher(None, text1.lower(), text2.lower())
        return seq.ratio()
    
    # Normalize whitespace
    original_clean = ' '.join(original.split())
    modified_clean = ' '.join(modified.split())
    
    # Check for exact match
    if original_clean.lower() == modified_clean.lower():
        return ('exact', 100.0, [])
    
    # Find common substrings using the selected algorithm
    matches = find_common_substrings(original_clean, modified_clean)
    
    # Calculate overall similarity
    base_similarity = calculate_similarity(original_clean, modified_clean) * 100
    
    # Enhance similarity score based on pattern matches
    if matches:
        total_matched_chars = sum(match['length'] for match in matches)
        max_length = max(len(original_clean), len(modified_clean))
        pattern_boost = min(20, (total_matched_chars / max_length) * 50)  # Up to 20% boost
        similarity = min(100, base_similarity + pattern_boost)
    else:
        similarity = base_similarity
    
    # Classify based on similarity and matches
    if similarity >= 99.5:  # Allow for tiny rounding differences
        return ('exact', similarity, matches)
    elif similarity >= 75:  # High similarity indicates modification
        return ('modified', similarity, matches)
    elif similarity >= 40 or len(matches) >= 3:  # Moderate similarity or good pattern matches
        return ('similar', similarity, matches)
    else:
        return ('different', similarity, matches)


def separate_sentences(text: str) -> List[str]:
    """
    Split `text` into individual sentences.
    """
    # Normalize line breaks and whitespace
    text = ' '.join(text.split())
    
    # Common sentence endings
    endings = ['. ', '? ', '! ']
    boundaries: List[int] = []
    i = 0
    while i < len(text):
        found = False
        for ending in endings:
            if text[i:].startswith(ending[0]):
                # Skip any extra whitespace after the punctuation
                next_pos = i + 1
                while next_pos < len(text) and text[next_pos].isspace():
                    next_pos += 1
                boundaries.append(next_pos)
                i = next_pos
                found = True
                break
        if not found:
            i += 1
    
    # If no sentence boundaries found, return whole text
    if not boundaries:
        return [text]
    
    # Create individual sentences
    sentences = []
    start = 0
    for boundary in boundaries:
        sentence = text[start:boundary].strip()
        if sentence:
            sentences.append(sentence)
        start = boundary
    
    # Add any remaining text as the last sentence
    if start < len(text):
        last_sentence = text[start:].strip()
        if last_sentence:
            sentences.append(last_sentence)
    
    return sentences


def show_diff(original: str, modified: str) -> None:
    """
    Show a diff of two strings by comparing them sentence by sentence.
    """
    original_sentences = separate_sentences(original)
    modified_sentences = separate_sentences(modified)
    differ = difflib.Differ()
    
    print("\nComparing by sentences:")
    print("─" * 60)
    for line in differ.compare(original_sentences, modified_sentences):
        if line.startswith('+ '):
            print(f"\033[92m{line}\033[0m")  # additions in green
        elif line.startswith('- '):
            print(f"\033[91m{line}\033[0m")  # removals in red
        else:
            print(f"  {line[2:]}")            # unchanged

# # Example usage and testing
# if __name__ == "__main__":
#     # Test cases
#     # original_text = """RSA encryption, which underpins much of today's secure digital 
#     # communication, relies on the difficulty of factoring large composite numbers into 
#     # their prime components. Classical computers find this task computationally infeasible 
#     # when the numbers involved are sufficiently large—taking an impractical amount of time 
#     # to crack even with advanced algorithms. This is what makes RSA secure in the classical 
#     # computing world: the public key can be shared openly, and only someone with the private 
#     # key (derived from the prime factors) can decrypt the data.

#     # However, quantum computers threaten this security model due to **Shor's algorithm**, 
#     # a quantum algorithm capable of factoring large integers exponentially faster than any known classical method. 
#     # A sufficiently powerful quantum computer could use Shor's algorithm to efficiently factor the RSA modulus 
#     # (the product of two primes), thereby uncovering the private key and breaking the encryption. 
#     # This means that RSA, and other public-key systems based on similar mathematical problems, would become obsolete 
#     # in a post-quantum era unless replaced by **quantum-resistant algorithms**.
#     # """
    
#     # modified_text = """RSA encryption, which underpins much of today's secure digital 
#     # communication, relies on the difficulty of factoring large composite numbers into 
#     # their prime components. Classical computers find this task computationally infeasible 
#     # when the numbers involved are sufficiently large—taking an impractical amount of time 
#     # to crack even with advanced algorithms. This is what makes RSA secure in the classical 
#     # computing world: the public key can be shared openly, and only someone with the private 
#     # key (derived from the prime factors) can decrypt the data. Most of the text remains unchanged.

#     # However, quantum computers threaten this security model due to **Shor's algorithm**, 
#     # a quantum algorithm capable of factoring large integers exponentially faster than any known classical method. 
#     # A sufficiently powerful quantum computer could use an algorithm to efficiently factor the RSA modulus 
#     # (the product of two primes), thereby uncovering the private key and breaking the encryption. 
#     # This means that RSA, and other public-key systems based on similar mathematical problems, would become obsolete 
#     # in a post-quantum era unless replaced by **quantum-resistant algorithms**. Quantum computing is the future.
#     # """
    
    
#     original_text = """Tutorial 14 - Pattern Matching creationDate: 2025-05-22 14:59 modificationDate: 2025-05-22 20:29 tags: [] Content For the text a pattern string \u2018pattern\u2019 given below. Text: \u201cThe quick brown fox jumps over the lazy dog. The dog barks at the fox. Brown foxes are quick and agile animals.\u201d Pattern: \u201cfox\u201d 1. Using the KMP algorithm, define the longest proper prefix. index 0 1 2 Pattern f o x LPS 0 0 0 2. Using the KMP algorithm show using a diagram how the pattern matching will be carried to find out all the matching patterns. image 3. How many comparisons were made to find all the matching patterns? \u2013 111 comparisons For the text string \u2018text\u2019 and a pattern string \u2018pattern\u2019 given below. Text: \u201cThe quick brown fox jumps over the lazy dog. The dog barks at the fox. Brown foxes are quick and agile animals.\u201d Pattern: \u201cfox\u201d 1. Using the Boyer-Moore algorithm, explain the Bad Character Rule using the given \u2018text\u2019 and \u2018pattern.\u2019 \u2013 When a character in the text does not match any character in the pattern, the character is considered a bad character. When this happens, the pattern will be shifted until the character in the text matches the a character in the pattern. 2. Using the Boyer-Moore algorithm explain the Good Suffix Rule using the given \u2018text\u2019 and \u2018pattern\u2019."""
#     modified_text = """Tutorial 14 - Pattern Matching creationDate: 2025-05-22 14:59 modificationDate: 2025-05-22 20:29 tags: [] Content For the text a pattern string \u2018pattern\u2019 given below. Text: \u201cThe quick brown fox jumps over the lazy dog. The dog barks at the fox. Brown foxes are quick and agile animals.\u201d Pattern: \u201cfox\u201d 1. Using the KMP algorithm, define the longest proper prefix. index 0 1 2 Pattern f o x LPS 0 0 0 2. Using the KMP using a diagram how the pattern matching will be carried to find out all the matching patterns. image 3. How many comparisons were made to find all the matching patterns? \u2013 111 comparisons For the text string \u2018text\u2019 and a pattern string \u2018pattern\u2019 given below. Text: \u201cThe quick brown fox jumps over the lazy dog. The dog barks at the fox. Brown foxes are quick and agile animals.\u201d Pattern: \u201cfox\u201d 1. Using the Boyer-Moore algorithm, explain the Bad Character Rule using the given \u2018text\u2019 and \u2018pattern.\u2019 \u2013 When a character in the text does not match any character in the pattern, the character is considered a bad character. When this happens, the pattern will be shifted until the character in the text matches the a character in the pattern. 2. Using the Boyer-Moore algorithm explain the Good Suffix Rule using the given \u2018text\u2019 and \u2018pattern\u2019."""
    
#     different_text = """
#     Machine learning algorithms have revolutionized data analysis and artificial intelligence.
#     Deep neural networks can process vast amounts of information and identify complex patterns.
#     This technological advancement opens new possibilities for automation and decision-making.
#     """
#     # Test with KMP
#     result = find_text_matches(original_text, modified_text)
#     print(f"Modified test with KMP: {result[0]} ({result[1]:.1f}%) with {len(result[2])} matches")

    
#     # Show diff
#     print("\n" + "="*60)
#     print("SHOWING CHANGES BETWEEN ORIGINAL AND MODIFIED:")
#     show_diff(original_text, modified_text)