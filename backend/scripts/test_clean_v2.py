import re


def _clean_extracted_text(text: str) -> str:
    # 1. Normalize headers
    text = re.sub(r'^[ \t]*#{3,}', '###', text, flags=re.MULTILINE)
    # 2. Remove ANY hashtags that are NOT at the start of a line
    text = re.sub(r'(?<!\n)[ \t]*#+', ' ', text)
    # 3. Clean up broken table pipes '|'
    text = re.sub(r'(?<=\w)[ \t]*\|[ \t]*(?=\w)', ' ', text)
    text = re.sub(r'^[ \t]*\|', '', text, flags=re.MULTILINE)
    text = re.sub(r'\|[ \t]*$', '', text, flags=re.MULTILINE)
    # 4. Collapse spaces
    text = re.sub(r'[ \t]+', ' ', text)
    # 5. Collapse newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

if __name__ == "__main__":
    sample = """
# Header
RAG # Middle Hashtag
|5|Vector DBs|3-4 weeks|
| |Building app|
    """
    cleaned = _clean_extracted_text(sample)
    print("Original:")
    print(sample)
    print("-" * 20)
    print("Cleaned:")
    print(cleaned)
