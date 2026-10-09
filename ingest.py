"""
ingest.py - Step 2: turns the business documents into a searchable knowledge base.

1. Reads every .md and .txt file in docs/
2. Splits each one into small chunks (one section or one FAQ answer each)
3. Turns each chunk into an embedding with Gemini
4. Saves the chunks and embeddings to vectordb/index.json

Run it again whenever the documents change.
"""
import json
import re
from pathlib import Path

from ai_client import embed

DOCS = Path(__file__).with_name("docs")
OUT = Path(__file__).with_name("vectordb") / "index.json"


def split_into_chunks(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    found_title = re.search(r"^# (.+)$", text, re.M)
    # Documents uploaded by the owner might not have a "# Title", so fall back to the file name
    title = found_title.group(1).strip() if found_title else path.stem.replace("_", " ").replace("-", " ").title()
    chunks = []

    # FAQ files: one chunk per question (lines starting with **Question?**)
    if re.search(r"^\*\*.+\?\*\*\s*$", text, re.M):
        parts = re.split(r"(?m)^(?=\*\*.+\?\*\*\s*$)", text)
        for part in parts[1:]:
            heading = part.splitlines()[0].strip("* ").strip()
            chunks.append((heading, part.strip()))
    else:
        # Other files: one chunk per "## " section, plus the intro before the first section
        parts = re.split(r"(?m)^(?=## )", text)
        intro = re.sub(r"^# .+\n?", "", parts[0]).strip()
        if intro:
            chunks.append(("Overview", intro))
        for part in parts[1:]:
            heading = part.splitlines()[0].lstrip("# ").strip()
            chunks.append((heading, part.strip()))

    # Very long sections (e.g. a plain .txt file) are split by paragraph into ~1,200-character pieces
    sized = []
    for heading, body in chunks:
        if len(body) <= 1500:
            sized.append((heading, body))
            continue
        piece, part_no = "", 1
        for para in re.split(r"\n\s*\n", body):
            if piece and len(piece) + len(para) > 1200:
                sized.append((f"{heading} (part {part_no})", piece.strip()))
                piece, part_no = "", part_no + 1
            piece += para + "\n\n"
        if piece.strip():
            sized.append((f"{heading} (part {part_no})" if part_no > 1 else heading, piece.strip()))
    chunks = sized

    # Each chunk carries its document title and section, so it makes sense on its own
    return [{"source": path.name, "section": heading,
             "text": f"{title} - {heading}\n\n{body}"} for heading, body in chunks]


def main():
    chunks = []
    paths = sorted(list(DOCS.glob("*.md")) + list(DOCS.glob("*.txt")))
    for path in paths:
        found = split_into_chunks(path)
        print(f"{path.name}: {len(found)} chunks")
        chunks.extend(found)

    print(f"\nCreating embeddings for {len(chunks)} chunks...")
    vectors = embed([c["text"] for c in chunks], task="RETRIEVAL_DOCUMENT")
    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector

    OUT.parent.mkdir(exist_ok=True)
    temp = OUT.with_suffix(".tmp")  # write to a temp file first, so a crash never leaves a half-written index
    temp.write_text(json.dumps(chunks), encoding="utf-8")
    temp.replace(OUT)
    return len(chunks)
    print(f"Saved {len(chunks)} chunks to {OUT.relative_to(OUT.parent.parent)}")


if __name__ == "__main__":
    main()
