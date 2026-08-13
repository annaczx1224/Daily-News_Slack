import os
import sys


PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

sys.path.append(
    os.path.join(
        PROJECT_ROOT,
        "src"
    )
)


from entity_resolution import (
    load_companies_from_db,
    load_aliases_from_db,
    match_company,
)


DATABASE_PATH = os.path.join(
    PROJECT_ROOT,
    "deal_intelligence.db"
)


companies = load_companies_from_db(
    DATABASE_PATH
)

aliases = load_aliases_from_db(
    DATABASE_PATH
)


TESTS = [
    "Stripe",
    "Stripe Inc.",
    "Checkout",
    "Checkout.com",
    "Revolut Ltd",
    "Ramp",
    "Zeal",
    "Able",
]


for mention in TESTS:

    result = match_company(
        mention,
        companies,
        aliases
    )

    print("\n-------------------------")
    print(f"INPUT: {mention}")
    print("-------------------------")

    print(result)
