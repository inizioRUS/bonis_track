from core.config import settings
from utils.text import normalize_text


class ChunkerService:
    def chunk_text(
        self,
        text: str,
        chunk_size: int = settings.CHUNK_SIZE,
        overlap: int = settings.CHUNK_OVERLAP,
    ) -> list[str]:
        text = normalize_text(text)
        if not text:
            return []

        chunks: list[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk = text[start:end].strip()

            if end < text_len:
                boundary = max(
                    chunk.rfind(". "),
                    chunk.rfind("! "),
                    chunk.rfind("? "),
                    chunk.rfind("\n"),
                )
                if boundary > int(chunk_size * 0.6):
                    chunk = chunk[: boundary + 1].strip()
                    end = start + len(chunk)

            if chunk:
                chunks.append(chunk)

            if end >= text_len:
                break

            start = max(end - overlap, start + 1)

        return chunks

    def build_chunk_window(self, chunks: list[str], index: int, radius: int = 2) -> dict:
        left_items = []
        right_items = []

        left_start = max(0, index - radius)
        left_end = index

        right_start = index + 1
        right_end = min(len(chunks), index + radius + 1)

        for i in range(left_start, left_end):
            left_items.append(
                {
                    "chunk_index": i,
                    "text": chunks[i],
                }
            )

        for i in range(right_start, right_end):
            right_items.append(
                {
                    "chunk_index": i,
                    "text": chunks[i],
                }
            )

        return {
            "center_index": index,
            "left": left_items,
            "center": {
                "chunk_index": index,
                "text": chunks[index],
            },
            "right": right_items,
        }