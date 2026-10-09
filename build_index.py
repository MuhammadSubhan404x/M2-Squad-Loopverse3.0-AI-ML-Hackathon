"""Build the local SQLite TF-IDF vector index for the supplied documents."""
from __future__ import annotations

import math
import re
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "rag_index.sqlite3"
TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


documents = []
for path in sorted((ROOT / "docs").glob("DOC-*.md")):
    documents.append((path.stem.split("_", 1)[0], path.read_text(encoding="utf-8")))

document_terms = [Counter(tokens(text)) for _, text in documents]
df = Counter()
for term_counts in document_terms:
    df.update(term_counts)
total = len(documents)

connection = sqlite3.connect(INDEX)
connection.executescript(
    """
    DROP TABLE IF EXISTS documents;
    DROP TABLE IF EXISTS vectors;
    CREATE TABLE documents (doc_id TEXT PRIMARY KEY, text TEXT NOT NULL);
    CREATE TABLE vectors (
        doc_id TEXT NOT NULL,
        term TEXT NOT NULL,
        weight REAL NOT NULL,
        PRIMARY KEY (doc_id, term),
        FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
    );
    CREATE INDEX vector_term_idx ON vectors(term);
    """
)
for (doc_id, text), term_counts in zip(documents, document_terms):
    connection.execute("INSERT INTO documents VALUES (?, ?)", (doc_id, text))
    norm = math.sqrt(
        sum(
            (count * (math.log((1 + total) / (1 + df[term])) + 1.0)) ** 2
            for term, count in term_counts.items()
        )
    ) or 1.0
    for term, count in term_counts.items():
        weight = (count * (math.log((1 + total) / (1 + df[term])) + 1.0)) / norm
        connection.execute("INSERT INTO vectors VALUES (?, ?, ?)", (doc_id, term, weight))
connection.commit()
connection.close()
print(f"Built {INDEX.name}: {len(documents)} documents")
