import re
from bs4 import BeautifulSoup


def clean_chapter(raw_text: str) -> str:
    """Strip HTML tags and normalize whitespace from a raw chapter string."""
    # Remove HTML if present
    if "<" in raw_text and ">" in raw_text:
        soup = BeautifulSoup(raw_text, "html.parser")
        text = soup.get_text(separator="\n")
    else:
        text = raw_text

    # Collapse 3+ blank lines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip trailing spaces on each line
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines).strip()

    return text


def clean_file(input_path: str, output_path: str) -> None:
    with open(input_path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()

    cleaned = clean_chapter(raw)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(cleaned)
