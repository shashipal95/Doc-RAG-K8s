import re


def _clean_extracted_text(text: str) -> str:
    # 1. Replace 3 or more hashtags at the start of a line with just '###'
    text = re.sub(r'^#{3,}', '###', text, flags=re.MULTILINE)
    # 2. Remove hashtags that appear in the middle of text (not at start of line)
    text = re.sub(r'(?<!\n)#+', ' ', text)
    # 3. Collapse multiple spaces
    text = re.sub(r' +', ' ', text)
    # 4. Collapse multiple newlines (max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

if __name__ == "__main__":
    sample = """
# Complete RAG Roadmap ###### From Python Basics
###### Total Time Estimate
#### Section 1
This is a test # with hashtags in middle.
    """
    cleaned = _clean_extracted_text(sample)
    print("Original:")
    print(sample)
    print("-" * 20)
    print("Cleaned:")
    print(cleaned)
