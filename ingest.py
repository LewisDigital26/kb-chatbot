"""
ingest.py - Step 2: turns the business documents into a searchable knowledge base.

1. Reads every .md file in docs/
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
    title = re.search(r"^# (.+)$", text, re.M).group(1).strip()
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
        intro = re.sub(r"^# .+\n", "", parts[0]).strip()
        if intro:
            chunks.append(("Overview", intro))
        for part in parts[1:]:
            heading = part.splitlines()[0].lstrip("# ").strip()
            chunks.append((heading, part.strip()))

    # Each chunk carries its document title and section, so it makes sense on its own
    return [{"source": path.name, "section": heading,
             "text": f"{title} - {heading}\n\n{body}"} for heading, body in chunks]


def main():
    chunks = []
    for path in sorted(DOCS.glob("*.md")):
        found = split_into_chunks(path)
        print(f"{path.name}: {len(found)} chunks")
        chunks.extend(found)

    print(f"\nCreating embeddings for {len(chunks)} chunks...")
    vectors = embed([c["text"] for c in chunks], task="RETRIEVAL_DOCUMENT")
    for chunk, vector in zip(chunks, vectors):
        chunk["embedding"] = vector

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(chunks), encoding="utf-8")
    print(f"Saved {len(chunks)} chunks to {OUT.relative_to(OUT.parent.parent)}")


if __name__ == "__main__":
    main()
