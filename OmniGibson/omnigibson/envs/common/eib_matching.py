"""Fuzzy name matching utilities for object registry lookups."""


def fuzzy_match(query, candidates):
    """Find the best matching candidate for a query string by word overlap.

    Args:
        query: Input name string (e.g. "frozen chicken").
        candidates: Iterable of candidate name strings (e.g. ["chicken", "frying pan"]).

    Returns:
        Best matching candidate string, or None if no words overlap.
    """
    query_words = set(query.lower().split())
    best, best_score = None, 0
    for candidate in candidates:
        candidate_words = set(candidate.lower().split())
        overlap = len(query_words & candidate_words)
        if overlap > best_score:
            best, best_score = candidate, overlap
    return best
