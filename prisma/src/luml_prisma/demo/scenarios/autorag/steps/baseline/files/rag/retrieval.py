"""Baseline retriever: word-level TF-IDF over fixed-width character chunks."""

import time

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from rag.text import fixed_chunks

STRATEGY = "tfidf-fixed-chunks"
PARAMS = {
    "chunking": "fixed",
    "chunk_size": 200,
    "vectorizer": "word-tfidf",
}


class TfidfRetriever:
    def __init__(self, documents):
        self.chunks = []
        self.chunk_doc_ids = []
        for doc in documents:
            for chunk in fixed_chunks(doc["title"] + ". " + doc["text"], PARAMS["chunk_size"]):
                self.chunks.append(chunk)
                self.chunk_doc_ids.append(doc["id"])
        self.vectorizer = TfidfVectorizer(stop_words="english", sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform(self.chunks)

    def search(self, query, k):
        """Return (candidates, spans): top-k chunks and trace span records."""
        spans = []
        t0 = time.time_ns()
        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.matrix)[0]
        order = scores.argsort()[::-1][:k]
        spans.append({
            "name": "tfidf.search",
            "start": t0,
            "end": time.time_ns(),
            "attributes": {"vectorizer": PARAMS["vectorizer"], "chunks_scored": len(self.chunks)},
        })
        candidates = [
            {"doc_id": self.chunk_doc_ids[i], "chunk": self.chunks[i], "score": float(scores[i])}
            for i in order
        ]
        return candidates, spans


def build_retriever(documents):
    return TfidfRetriever(documents)
