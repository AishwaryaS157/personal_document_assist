import argparse
import json
import os
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app.services.document_service import search_documents


def run_eval(user_id: str, queries_path: str, ks: list[int]) -> None:
    with open(queries_path) as f:
        queries = json.load(f)

    max_k = max(ks)
    results = []

    print(f"\n{'='*60}")
    print(f"  Hybrid Search Recall Evaluation")
    print(f"  Queries: {len(queries)}  |  K values: {ks}")
    print(f"{'='*60}\n")

    for i, q in enumerate(queries, 1):
        question         = q["question"]
        expected_file    = q["expected_filename"]
        notes            = q.get("notes", "")

        retrieved = search_documents(question, user_id, n_results=max_k)
        retrieved_files = [r["filename"] for r in retrieved]

        hit_at = {}
        for k in ks:
            hit_at[k] = expected_file in retrieved_files[:k]

        results.append({"question": question, "expected": expected_file,
                        "retrieved_files": retrieved_files, "hit_at": hit_at})

        status = "✓" if hit_at[max_k] else "✗"
        print(f"[{i}/{len(queries)}] {status}  {question}")
        print(f"         Expected : {expected_file}")
        print(f"         Retrieved: {retrieved_files[:max_k]}")
        for k in ks:
            mark = "HIT " if hit_at[k] else "MISS"
            print(f"         Recall@{k} : {mark}")
        if notes:
            print(f"         Notes    : {notes}")
        print()

    print(f"{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    for k in ks:
        hits = sum(1 for r in results if r["hit_at"][k])
        recall = hits / len(results)
        bar = "█" * int(recall * 20) + "░" * (20 - int(recall * 20))
        print(f"  Recall@{k}  [{bar}]  {hits}/{len(results)} = {recall:.1%}")

    print()

    failures = [r for r in results if not r["hit_at"][max_k]]
    if failures:
        print(f"  FAILED QUERIES (not in top-{max_k}):")
        for r in failures:
            print(f"    • \"{r['question']}\"")
            print(f"      Expected: {r['expected']}")
            print(f"      Got     : {r['retrieved_files'][:3]}")
    else:
        print(f"  All queries found in top-{max_k}!")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recall@K evaluation")
    parser.add_argument("--user-id",  required=True, help="Supabase user UUID")
    parser.add_argument("--queries",  default=str(Path(__file__).parent / "test_queries.json"),
                        help="Path to test queries JSON")
    parser.add_argument("--k", nargs="+", type=int, default=[1, 3, 5],
                        help="K values to evaluate (default: 1 3 5)")
    args = parser.parse_args()

    run_eval(args.user_id, args.queries, sorted(args.k))
