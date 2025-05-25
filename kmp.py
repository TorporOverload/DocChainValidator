# Implementation of Knuth–Morris–Pratt algorithm for substring search
# Adapted for this project

def calculate_lps(pattern):
    """
    Preprocess the pattern to create the longest prefix-suffix (LPS) array.
    The LPS array is used to skip characters while matching.
    """
    lps = [0] * len(pattern)
    length = 0  # Length of the previous longest prefix suffix
    i = 1

    while i < len(pattern):
        if pattern[i] == pattern[length]:
            length += 1
            lps[i] = length
            i += 1
        else:
            if length != 0:
                length = lps[length - 1]
            else:
                lps[i] = 0
                i += 1

    return lps

def kmp_search(text, pattern):
    """
    KMP string searching algorithm.
    Returns a list of positions where pattern occurs in text.
    """
    txt_len = len(text)
    pat_len = len(pattern)
    result = []
    
    if pat_len == 0 or txt_len == 0: 
        return result
        
    lps = calculate_lps(pattern)
    i = 0  # Index for text
    j = 0  # Index for pattern
    
    while i < txt_len:
        if pattern[j] == text[i]:
            i += 1
            j += 1
        
        if j == pat_len:
            result.append(i - j)
            j = lps[j - 1]
        
        elif i < txt_len and pattern[j] != text[i]:
            if j != 0:
                j = lps[j - 1]
            else:
                i += 1
    
    return result
