import os
import sqlite3
import uuid

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

DATABASE_PATH = os.path.join(
    PROJECT_ROOT,
    "deal_intelligence.db"
)


ALIASES = [
    ("Checkout.com", "Checkout", "common_name"),
    ("Checkout.com", "Checkout.com Ltd", "legal_name"),

    ("Ramp", "Ramp Financial", "common_name"),

    ("Revolut", "Revolut Ltd", "legal_name"),

    ("Stripe", "Stripe Inc", "legal_name"),
    ("Stripe", "Stripe, Inc.", "legal_name"),
]


def normalize_alias(alias):
    return (
        alias.lower()
        .replace(".", " ")
        .replace(",", " ")
        .strip()
    )


def add_aliases():

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    inserted = 0
    skipped = 0
    missing = 0

    for canonical_name, alias, alias_type in ALIASES:

        cursor.execute(
            """
            SELECT company_id
            FROM companies
            WHERE canonical_name = ?
            """,
            (canonical_name,)
        )

        result = cursor.fetchone()

        if not result:
            print(
                f"Company not found: {canonical_name}"
            )
            missing += 1
            continue

        company_id = result[0]

        normalized_alias = normalize_alias(alias)

        cursor.execute(
            """
            SELECT alias_id
            FROM company_aliases
            WHERE company_id = ?
            AND normalized_alias = ?
            """,
            (
                company_id,
                normalized_alias
            )
        )

        if cursor.fetchone():
            skipped += 1
            continue

        alias_id = "als_" + uuid.uuid4().hex

        cursor.execute(
            """
            INSERT INTO company_aliases (
                alias_id,
                company_id,
                alias,
                normalized_alias,
                alias_type,
                confidence
            )
            VALUES (?, ?, ?, ?, ?, 1.0)
            """,
            (
                alias_id,
                company_id,
                alias,
                normalized_alias,
                alias_type
            )
        )

        inserted += 1

        print(
            f"Added alias: {alias} -> {canonical_name}"
        )

    conn.commit()
    conn.close()

    print("\nAlias load complete")
    print(f"Inserted: {inserted}")
    print(f"Skipped: {skipped}")
    print(f"Missing companies: {missing}")


if __name__ == "__main__":
    add_aliases()
