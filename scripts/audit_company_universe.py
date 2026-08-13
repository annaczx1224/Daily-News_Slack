import os
import sqlite3
from collections import defaultdict


PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

DATABASE_PATH = os.path.join(
    PROJECT_ROOT,
    "deal_intelligence.db"
)


def audit_companies():

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            company_id,
            canonical_name,
            normalized_name
        FROM companies
        ORDER BY normalized_name
        """
    )

    companies = cursor.fetchall()

    normalized_groups = defaultdict(list)

    for company_id, canonical_name, normalized_name in companies:
        normalized_groups[normalized_name].append(
            {
                "company_id": company_id,
                "canonical_name": canonical_name
            }
        )

    collisions = {
        name: records
        for name, records in normalized_groups.items()
        if len(records) > 1
    }

    print("--------------------------------")
    print("Company universe audit")
    print("--------------------------------")

    print(f"Total companies: {len(companies)}")
    print(f"Unique normalized names: {len(normalized_groups)}")
    print(f"Normalized-name collisions: {len(collisions)}")

    if collisions:

        print("\nPotential collisions:\n")

        for normalized_name, records in collisions.items():

            print(f"NORMALIZED: {normalized_name}")

            for record in records:
                print(
                    f"  - {record['canonical_name']}"
                    f" [{record['company_id']}]"
                )

            print()

    conn.close()


if __name__ == "__main__":
    audit_companies()
