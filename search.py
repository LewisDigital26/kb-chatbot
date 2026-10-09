"""
search.py - finds the chunks most relevant to a question.

It turns the question into an embedding and compares it with every stored chunk
using cosine similarity (how closely the two "point in the same direction").
This is exactly what a vector database does; with a small knowledge base,
a few lines of numpy are fast and easy to understand.
"""
import json
from pathlib import Path

import numpy as np

from ai_client import embed

INDEX = Path(__file__).with_name("vectordb") / "index.json"


class KnowledgeBase:
    def __init__(self):
        if not INDEX.exists():
            raise FileNotFoundError("No knowledge base yet. Run ingest.py first.")
        self.chunks = json.loads(INDEX.read_text(encoding="utf-8"))
        matrix = np.array([c["embedding"] for c in self.chunks], dtype=np.float32)
        self.matrix = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)

    def search(self, question: str, top_k: int = 4) -> list[dict]:
        q = np.array(embed([question], task="RETRIEVAL_QUERY")[0], dtype=np.float32)
        q /= np.linalg.norm(q)
        scores = self.matrix @ q
        best = np.argsort(scores)[::-1][:top_k]
        return [{**self.chunks[i], "score": float(scores[i])} for i in best]


if __name__ == "__main__":
    kb = KnowledgeBase()
    questions = [
        "Are you open on Mondays?",
        "How much does balayage cost?",
        "Can my 14 year old get her hair dyed?",
        "What happens if I cancel the day before?",
        "Do I get loyalty points when I buy shampoo?",
    ]
    for question in questions:
        print(f"\nQ: {question}")
        for r in kb.search(question, top_k=2):
            print(f"   {r['score']:.2f}  {r['source']} > {r['section']}")
