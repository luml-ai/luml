"""Hybrid retriever: BM25 + character n-gram TF-IDF fused with Reciprocal Rank Fusion.

BM25 excels at exact rare terms (config keys, endpoint paths); character
n-grams tolerate morphological variation between question and document
wording. RRF combines both rankings without score calibration.
"""

import math
import time
from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from rag.text import paragraph_chunks, tokenize

STRATEGY = "hybrid-bm25-rrf"
PARAMS = {
    "chunking": "paragraph",
    "rankers": "bm25 + char-tfidf",
    "fusion": "rrf",
    "rrf_k": 60,
    "bm25_k1": 1.5,
    "bm25_b": 0.75,
}


class BM25:
    def __init__(self, docs_tokens, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.doc_tokens = docs_tokens
        self.doc_freqs = [Counter(tokens) for tokens in docs_tokens]
        self.doc_lens = [len(tokens) for tokens in docs_tokens]
        self.avg_len = sum(self.doc_lens) / len(self.doc_lens)
        df = Counter()
        for freqs in self.doc_freqs:
            df.update(freqs.keys())
        n = len(docs_tokens)
        self.idf = {
            term: math.log(1 + (n - count + 0.5) / (count + 0.5))
            for term, count in df.items()
        }

    def scores(self, query_tokens):
        result = [0.0] * len(self.doc_tokens)
        for term in query_tokens:
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, freqs in enumerate(self.doc_freqs):
                tf = freqs.get(term, 0)
                if not tf:
                    continue
                norm = self.k1 * (1 - self.b + self.b * self.doc_lens[i] / self.avg_len)
                result[i] += idf * tf * (self.k1 + 1) / (tf + norm)
        return result


def _ranks(scores):
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return {idx: rank for rank, idx in enumerate(order, start=1)}


class HybridRetriever:
    def __init__(self, documents):
        self.chunks = []
        self.chunk_doc_ids = []
        for doc in documents:
            for chunk in paragraph_chunks(doc["text"]):
                self.chunks.append(doc["title"] + ". " + chunk)
                self.chunk_doc_ids.append(doc["id"])
        self.bm25 = BM25(
            [tokenize(chunk) for chunk in self.chunks],
            k1=PARAMS["bm25_k1"],
            b=PARAMS["bm25_b"],
        )
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5))
        self.matrix = self.vectorizer.fit_transform(self.chunks)

    def search(self, query, k):
        spans = []

        t0 = time.time_ns()
        bm25_scores = self.bm25.scores(tokenize(query))
        spans.append({
            "name": "bm25.search",
            "start": t0,
            "end": time.time_ns(),
            "attributes": {"ranker": "bm25", "chunks_scored": len(self.chunks)},
        })

        t0 = time.time_ns()
        query_vec = self.vectorizer.transform([query])
        dense_scores = cosine_similarity(query_vec, self.matrix)[0]
        spans.append({
            "name": "chargram.search",
            "start": t0,
            "end": time.time_ns(),
            "attributes": {"ranker": "char-tfidf", "ngrams": "3-5"},
        })

        t0 = time.time_ns()
        rrf_k = PARAMS["rrf_k"]
        bm25_ranks = _ranks(bm25_scores)
        dense_ranks = _ranks(list(dense_scores))
        fused = {
            i: 1.0 / (rrf_k + bm25_ranks[i]) + 1.0 / (rrf_k + dense_ranks[i])
            for i in range(len(self.chunks))
        }
        order = sorted(fused, key=lambda i: fused[i], reverse=True)[:k]
        spans.append({
            "name": "rrf.fuse",
            "start": t0,
            "end": time.time_ns(),
            "attributes": {"fusion": "rrf", "rrf_k": rrf_k},
        })

        candidates = [
            {"doc_id": self.chunk_doc_ids[i], "chunk": self.chunks[i], "score": fused[i]}
            for i in order
        ]
        return candidates, spans


def build_retriever(documents):
    return HybridRetriever(documents)
