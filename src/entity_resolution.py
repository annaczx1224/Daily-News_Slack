import re
import unicodedata
from difflib import SequenceMatcher


LEGAL_SUFFIXES = {
    "inc",
    "incorporated",
    "llc",
    "ltd",
    "limited",
    "corp",
    "corporation",
    "plc",
    "gmbh",
    "sa",
    "ag",
    "co",
    "company",
    "holdings",
}


def normalize_company_name(name: str) -> str:
    """
    Convert a company name into a standardized matching format.

    Examples:
        Stripe, Inc. -> stripe
        Bolt (Financial Software) -> bolt
        Checkout.com -> checkout com
    """

    if not name:
        return ""

    name = str(name)

    # Normalize accented / Unicode characters
    name = unicodedata.normalize("NFKD", name)

    # Lowercase
    name = name.lower().strip()

    # Normalize ampersands
    name = name.replace("&", " and ")

    # Remove PitchBook-style descriptions in parentheses
    # Bolt (Financial Software) -> Bolt
    name = re.sub(r"\([^)]*\)", " ", name)

    # Replace punctuation with spaces
    name = re.sub(r"[^a-z0-9\s]", " ", name)

    # Remove duplicate whitespace
    parts = name.split()

    # Remove legal suffixes at the end
    while parts and parts[-1] in LEGAL_SUFFIXES:
        parts.pop()

    return " ".join(parts)


def similarity(name_a: str, name_b: str) -> float:
    """
    Return a similarity score between 0 and 1.
    """

    a = normalize_company_name(name_a)
    b = normalize_company_name(name_b)

    if not a or not b:
        return 0.0

    return SequenceMatcher(None, a, b).ratio()


def build_company_index(companies):
    """
    Build a dictionary for fast exact matching.

    Expected input:
    [
        {
            "company_id": "cmp_123",
            "canonical_name": "Stripe"
        }
    ]
    """

    index = {}

    for company in companies:
        normalized = normalize_company_name(
            company["canonical_name"]
        )

        if not normalized:
            continue

        if normalized not in index:
            index[normalized] = []

        index[normalized].append(company)

    return index


def find_fuzzy_matches(
    mention,
    companies,
    threshold=0.85,
    limit=5
):
    """
    Find the closest company names when exact matching fails.
    """

    normalized_mention = normalize_company_name(mention)

    if not normalized_mention:
        return []

    results = []

    for company in companies:
        normalized_company = normalize_company_name(
            company["canonical_name"]
        )

        score = SequenceMatcher(
            None,
            normalized_mention,
            normalized_company
        ).ratio()

        if score >= threshold:
            results.append({
                "company_id": company["company_id"],
                "canonical_name": company["canonical_name"],
                "score": round(score, 4),
                "method": "fuzzy"
            })

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results[:limit]


def match_company(
    mention,
    companies,
    company_index=None
):
    """
    Main matching function.

    Returns the best match and confidence.
    """

    if company_index is None:
        company_index = build_company_index(companies)

    normalized = normalize_company_name(mention)

    # ---------------------------------
    # 1. Exact normalized match
    # ---------------------------------

    exact_matches = company_index.get(normalized, [])

    if len(exact_matches) == 1:
        company = exact_matches[0]

        return {
            "company_id": company["company_id"],
            "canonical_name": company["canonical_name"],
            "confidence": 0.99,
            "method": "exact_normalized",
            "needs_review": False
        }

    # If multiple companies normalize to the same name,
    # don't automatically choose one.
    if len(exact_matches) > 1:
        return {
            "company_id": None,
            "canonical_name": None,
            "confidence": 0.75,
            "method": "ambiguous_exact_match",
            "needs_review": True,
            "candidates": exact_matches
        }

    # ---------------------------------
    # 2. Fuzzy match
    # ---------------------------------

    fuzzy_matches = find_fuzzy_matches(
        mention,
        companies,
        threshold=0.85,
        limit=5
    )

    if not fuzzy_matches:
        return {
            "company_id": None,
            "canonical_name": None,
            "confidence": 0.0,
            "method": "no_match",
            "needs_review": False
        }

    best = fuzzy_matches[0]

    # Very high fuzzy similarity
    if best["score"] >= 0.95:
        return {
            "company_id": best["company_id"],
            "canonical_name": best["canonical_name"],
            "confidence": best["score"],
            "method": "high_confidence_fuzzy",
            "needs_review": False
        }

    # Lower-confidence match:
    # eventually send this to the LLM.
    return {
        "company_id": best["company_id"],
        "canonical_name": best["canonical_name"],
        "confidence": best["score"],
        "method": "fuzzy_review",
        "needs_review": True,
        "candidates": fuzzy_matches
    }
