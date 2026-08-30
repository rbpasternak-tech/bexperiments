"""Entry point for the clause remediation demo.

Loads environment, then runs the orchestrator with a sample
arbitration clause update scenario.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from orchestrator import run_remediation


def main():
    """Run the AAA arbitration clause remediation demo."""
    print("=" * 60)
    print("  CLAUSE REMEDIATION APP")
    print("  Clause Remediation Workflow")
    print("=" * 60)
    print()
    print("Scenario: Update arbitration clauses from AAA 2013 rules")
    print("          to AAA 2024 rules across the document portfolio.")
    print()

    results = run_remediation(
        clause_type="arbitration",
        old_standard="AAA Commercial Arbitration Rules (2013)",
        new_standard="AAA Commercial Arbitration Rules (2024)",
        category_filter="Services & Commercial",
    )

    print()
    print("=" * 60)
    print(f"  Workflow returned: {results['updated']}/{results['searched']} documents updated")
    print(f"  QA approved: {results.get('qa_approved', 0)}")
    print(f"  Total time: {results['elapsed_seconds']:.1f}s")
    print("=" * 60)

    return results


if __name__ == "__main__":
    main()
