"""Create a persisted semantic FAISS index from the supplied documents."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import faiss
import numpy as np
from openai import OpenAI

ROOT = Path(__file__).resolve().parent
INDEX_DIR = ROOT / "rag_index"
MODEL = "text-embedding-3-small"
CHUNK_WORDS = 180
OVERLAP_WORDS = 30


def chunks(text: str) -> list[str]:
    words = text.split()
    result = []
    step = CHUNK_WORDS - OVERLAP_WORDS
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + CHUNK_WORDS]).strip()
        if chunk:
            result.append(chunk)
    return result


def main() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set; export it before building the FAISS index")
    records = []
    for path in sorted((ROOT / "docs").glob("DOC-*.md")):
        doc_id = path.stem.split("_", 1)[0]
        for chunk_id, text in enumerate(chunks(path.read_text(encoding="utf-8"))):
            records.append(
                {"doc_id": doc_id, "chunk_id": chunk_id, "source": path.name, "text": text}
            )
    client = OpenAI()
    response = client.embeddings.create(
        model=MODEL,
        input=[record["text"] for record in records],
    )
    vectors = np.asarray([item.embedding for item in response.data], dtype="float32")
    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    INDEX_DIR.mkdir(exist_ok=True)
    faiss.write_index(index, str(INDEX_DIR / "index.faiss"))
    (INDEX_DIR / "metadata.json").write_text(
        json.dumps({"model": MODEL, "records": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Indexed {len(records)} chunks from 13 documents using {MODEL}")


if __name__ == "__main__":
    main()
