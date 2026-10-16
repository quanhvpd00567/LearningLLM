"""Deterministic character-bounded chunks, without a tokenizer dependency."""
import re

PIPELINE_VERSION = 1


def chunk_text(text: str, max_chars: int = 1400, overlap: int = 160) -> list[str]:
    if max_chars < 1 or not 0 <= overlap < max_chars:
        raise ValueError("Require max_chars > overlap >= 0")
    paragraphs = [" ".join(part.split()) for part in re.split(r"\n\s*\n", text.strip())]
    text = "\n\n".join(part for part in paragraphs if part)
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            minimum = start + max(max_chars // 2, overlap + 1)
            for separator in ["\n\n", ". ", " "]:
                boundary = text.rfind(separator, minimum, end)
                if boundary >= minimum:
                    end = boundary + (1 if separator == ". " else 0)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks
