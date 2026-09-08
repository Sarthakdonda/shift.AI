import re
from app.core.config import get_settings
from app.repositories.store import serialize


def retrieve(store, ai, pid, query, limit=14):
    warnings = []
    s = get_settings()
    if s.vector_search_enabled:
        try:
            vector = ai.embed(query)
            chunks = list(store.db.document_chunks.aggregate([{'$vectorSearch': {'index': s.vector_index_name, 'path': 'embedding', 'queryVector': vector, 'numCandidates': 100, 'limit': limit, 'filter': {'project_id': pid}}}, {'$project': {'embedding': 0}}]))
            if chunks:
                return serialize(chunks), warnings
            warnings.append('Vector search returned no matches; keyword retrieval was used.')
        except Exception:
            warnings.append('Vector search is unavailable; keyword retrieval was used.')
    chunks = list(store.db.document_chunks.find({'project_id': pid}, {'embedding': 0}))
    terms = set(re.findall(r'\w{3,}', query.lower()))
    chunks.sort(key=lambda c: sum(c['text'].lower().count(t) for t in terms), reverse=True)
    return serialize(chunks[:limit]), warnings
