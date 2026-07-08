"""Query-expansion retriever: synonym expansion in front of the TF-IDF baseline.

User questions rarely reuse the documentation's vocabulary; expanding the
query with domain synonyms bridges that gap before scoring.
"""

import time

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from rag.text import fixed_chunks, tokenize

STRATEGY = "tfidf-query-expansion"
PARAMS = {
    "chunking": "fixed",
    "chunk_size": 200,
    "vectorizer": "word-tfidf",
    "expansion": "synonym-dict",
}

SYNONYMS = {
    # question vocabulary -> documentation vocabulary
    "keep": ["retained", "retention"],
    "keeps": ["retained", "retention"],
    "disappears": ["deleted", "archived"],
    "notified": ["notification", "alerted"],
    "visit": ["session", "sessions"],
    "fresh": ["new", "session"],
    "spot": ["anomaly", "detection"],
    "unusual": ["anomaly", "baseline"],
    "spikes": ["anomaly", "deviations"],
    "rewind": ["replay", "backfill"],
    "replay": ["backfill", "ingestion"],
    "browsing": ["session", "inactivity"],
    "period": ["timeout", "inactivity"],
    "goes": ["fires", "firing"],
    "subscribe": ["subscription", "webhook"],
    "protected": ["signed", "signing"],
    "streams": ["stream", "realtime"],
    "history": ["audit", "log"],
    "merge": ["sync", "merges"],
    "failing": ["failed", "paused"],
}


class QueryExpansionRetriever:
    def __init__(self, documents):
        self.chunks = []
        self.chunk_doc_ids = []
        for doc in documents:
            for chunk in fixed_chunks(doc["title"] + ". " + doc["text"], PARAMS["chunk_size"]):
                self.chunks.append(chunk)
                self.chunk_doc_ids.append(doc["id"])
        self.vectorizer = TfidfVectorizer(stop_words="english", sublinear_tf=True)
        self.matrix = self.vectorizer.fit_transform(self.chunks)
        vocab = self.vectorizer.vocabulary_
        self.idf = {term: self.vectorizer.idf_[idx] for term, idx in vocab.items()}

    def expand(self, query):
        spans = []
        t0 = time.time_ns()
        expansion_terms = []
        for token in tokenize(query):
            for synonym in SYNONYMS.get(token, []):
                # Weight expansions by corpus IDF so rare terms dominate.
                # Synonyms absent from the corpus vocabulary carry no signal.
                weight = self.idf.get(synonym)
                if weight is None:
                    continue
                repeats = 3 if weight > 3.0 else 1
                expansion_terms.extend([synonym] * repeats)
        expanded = query + " " + " ".join(expansion_terms)
        spans.append({
            "name": "query.expand",
            "start": t0,
            "end": time.time_ns(),
            "attributes": {"added_terms": len(expansion_terms)},
        })
        return expanded, spans

    def search(self, query, k):
        expanded, spans = self.expand(query)
        t0 = time.time_ns()
        query_vec = self.vectorizer.transform([expanded])
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
    return QueryExpansionRetriever(documents)
