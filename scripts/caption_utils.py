def build_caption_chunks(words: list[str]) -> list[list[str]]:
    """
    Split a list of words into chunks of 1-4 words.
    Prefers splitting at punctuation boundaries within a 4-5 word window.
    Hard split at 4 words if no punctuation found.
    """
    chunks = []
    current_chunk = []
    
    for i, word in enumerate(words):
        current_chunk.append(word)
        
        has_punctuation = any(p in word for p in ".,!?;:")
        is_max_length = len(current_chunk) >= 4
        is_last_word = i == len(words) - 1
        
        # If we hit punctuation and we have at least 1 word, or we hit max length, or it's the end
        if (has_punctuation and len(current_chunk) >= 1) or is_max_length or is_last_word:
            chunks.append(current_chunk)
            current_chunk = []
            
    return chunks
