import hashlib
import re


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def make_chunk_id(doc_id: str, chunk_index: int, text: str) -> str:
    raw = f"{doc_id}:{chunk_index}:{text}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()