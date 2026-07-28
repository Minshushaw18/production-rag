from typing import List
import re
import logfire


def chunk_text(
    text: str,
    chunk_size: int = 1500,
    overlap: int = 200,
) -> List[str]:
    """
    Production-friendly paragraph-aware chunker.

    Features:
    - Preserves paragraph boundaries when possible.
    - Handles paragraphs larger than chunk_size.
    - Splits oversized paragraphs by sentences first.
    - Falls back to word/character splitting for very large sentences.
    - Adds overlap for ieval quality.
    - Guarantees chunks do not exceed chunk_size.
    - Returns List[str] to avoid breaking existing consumers.
    """

    with logfire.span(
        "✂️ Text Chunking",
        text_length=len(text) if text else 0,
        chunk_size=chunk_size,
        overlap=overlap,
    ):
        if not text or not text.strip():
            return []

        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than 0")

        # Prevent overlap from causing infinite loops or oversized chunks
        overlap = max(0, min(overlap, chunk_size - 1))

        chunks: List[str] = []
        current_parts: List[str] = []
        current_length = 0
        pending_overlap = ""

        def get_overlap_text(chunk: str) -> str:
            """
            Returns overlap text from the end of a chunk.
            Tries not to start from the middle of a word when possible.
            """
            if overlap <= 0 or not chunk:
                return ""

            tail = chunk[-overlap:]

            # Avoid starting overlap from middle of a word when possible
            if len(chunk) > overlap:
                first_space = tail.find(" ")
                if first_space != -1:
                    tail = tail[first_space + 1:]

            return tail.strip()

        def flush_chunk() -> None:
            """
            Saves the current chunk and prepares overlap for the next chunk.
            """
            nonlocal current_parts, current_length, pending_overlap

            if not current_parts:
                return

            chunk = "\n\n".join(current_parts).strip()

            if chunk:
                chunks.append(chunk)
                pending_overlap = get_overlap_text(chunk)

            current_parts = []
            current_length = 0

        def start_new_chunk_with(value: str) -> None:
            """
            Starts a new chunk with optional pending overlap.
            Ensures the final chunk does not exceed chunk_size.
            """
            nonlocal current_parts, current_length, pending_overlap

            value = value.strip()
            if not value:
                return

            if pending_overlap:
                separator_length = 2  # for "\n\n"
                available_overlap = chunk_size - len(value) - separator_length

                if available_overlap > 0:
                    overlap_text = pending_overlap[-available_overlap:].strip()

                    if overlap_text:
                        current_parts = [overlap_text, value]
                        current_length = (
                            len(overlap_text)
                            + separator_length
                            + len(value)
                        )
                    else:
                        current_parts = [value]
                        current_length = len(value)
                else:
                    # Paragraph itself is near chunk_size, so drop overlap
                    current_parts = [value]
                    current_length = len(value)

                pending_overlap = ""
            else:
                current_parts = [value]
                current_length = len(value)

        def split_by_char_window(value: str) -> List[str]:
            """
            Last-resort splitter.
            Used when a single word or long sequence exceeds chunk_size.
            """
            pieces: List[str] = []
            step = chunk_size - overlap if overlap > 0 else chunk_size
            step = max(1, step)

            start = 0
            while start < len(value):
                end = start + chunk_size
                piece = value[start:end].strip()

                if piece:
                    pieces.append(piece)

                start += step

            return pieces

        def split_long_sentence(sentence: str) -> List[str]:
            """
            Splits a sentence that is bigger than chunk_size.
            Tries word-based splitting first, then character window fallback.
            """
            words = sentence.split()

            if not words:
                return []

            result: List[str] = []
            buffer: List[str] = []
            buffer_length = 0

            for word in words:
                # If one word itself is too large, use char fallback
                if len(word) > chunk_size:
                    if buffer:
                        result.append(" ".join(buffer).strip())
                        buffer = []
                        buffer_length = 0
                    result.extend(split_by_char_window(word))
                    continue

                projected_length = buffer_length + len(word) + (1 if buffer else 0)

                if projected_length <= chunk_size:
                    buffer.append(word)
                    buffer_length = projected_length
                else:
                    chunk = " ".join(buffer).strip()
                    if chunk:
                        result.append(chunk)

                    overlap_text = get_overlap_text(chunk)

                    if overlap_text:
                        projected_with_overlap = (
                            len(overlap_text) + 1 + len(word)
                        )

                        if projected_with_overlap <= chunk_size:
                            buffer = [overlap_text, word]
                            buffer_length = projected_with_overlap
                        else:
                            buffer = [word]
                            buffer_length = len(word)
                    else:
                        buffer = [word]
                        buffer_length = len(word)

            if buffer:
                result.append(" ".join(buffer).strip())

            return [r for r in result if r.strip()]

        def split_long_paragraph(paragraph: str) -> List[str]:
            """
            Splits oversized paragraph into sentence-sized chunks first.
            Falls back to word/char splitting only when required.
            """
            sentences = re.split(r"(?<=[.!?])\s+", paragraph.strip())

            result: List[str] = []
            buffer: List[str] = []
            buffer_length = 0

            for sentence in sentences:
                sentence = sentence.strip()

                if not sentence:
                    continue

                if len(sentence) > chunk_size:
                    if buffer:
                        result.append(" ".join(buffer).strip())
                        buffer = []
                        buffer_length = 0

                    result.extend(split_long_sentence(sentence))
                    continue

                projected_length = buffer_length + len(sentence) + (1 if buffer else 0)

                if projected_length <= chunk_size:
                    buffer.append(sentence)
                    buffer_length = projected_length
                else:
                    chunk = " ".join(buffer).strip()
                    if chunk:
                        result.append(chunk)

                    overlap_text = get_overlap_text(chunk)

                    if overlap_text:
                        projected_with_overlap = (
                            len(overlap_text) + 1 + len(sentence)
                        )

                        if projected_with_overlap <= chunk_size:
                            buffer = [overlap_text, sentence]
                            buffer_length = projected_with_overlap
                        else:
                            buffer = [sentence]
                            buffer_length = len(sentence)
                    else:
                        buffer = [sentence]
                        buffer_length = len(sentence)

            if buffer:
                result.append(" ".join(buffer).strip())

            return [r for r in result if r.strip()]

        paragraphs = [
            p.strip()
            for p in text.split("\n\n")
            if p.strip()
        ]

        for paragraph in paragraphs:
            # Edge case: paragraph itself is bigger than chunk_size
            if len(paragraph) > chunk_size:
                flush_chunk()

                paragraph_chunks = split_long_paragraph(paragraph)

                for paragraph_chunk in paragraph_chunks:
                    if len(paragraph_chunk) <= chunk_size:
                        chunks.append(paragraph_chunk)
                    else:
                        # Extra safety fallback
                        chunks.extend(split_by_char_window(paragraph_chunk))

                pending_overlap = (
                    get_overlap_text(chunks[-1])
                    if chunks
                    else ""
                )
                continue

            projected_size = (
                current_length
                + len(paragraph)
                + (2 if current_parts else 0)
            )

            if projected_size <= chunk_size:
                if current_parts:
                    current_parts.append(paragraph)
                    current_length = projected_size
                else:
                    start_new_chunk_with(paragraph)
            else:
                flush_chunk()
                start_new_chunk_with(paragraph)

        flush_chunk()

        valid_chunks = [
            chunk
            for chunk in chunks
            if chunk.strip()
        ]

        logfire.info(
            "✅ Generated chunks",
            chunk_count=len(valid_chunks),
            avg_chunk_size=(
                sum(len(c) for c in valid_chunks) / len(valid_chunks)
                if valid_chunks else 0
            ),
            max_chunk_size=(
                max(len(c) for c in valid_chunks)
                if valid_chunks else 0
            ),
        )

        return valid_chunks