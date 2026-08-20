"""Recall@K / MRR evaluation for the hybrid retrieval pipeline.

Scores three rankers independently off a single candidate fetch:

    dense  - vector similarity only
    fts    - Postgres full-text only
    rrf    - the two fused with Reciprocal Rank Fusion (what /chat uses)

Reporting all three is the point: a hybrid pipeline is only worth its
complexity if fusion beats both arms on their own, and a fused-only number
cannot show that.

Labels live in test_queries.json:

    {
      "question":          "what is memoization?",
      "expected_filename": "06DynamicProgramming.pdf",   # required
      "expected_snippet":  "storing the results of"      # optional
    }

With expected_snippet the query is scored at PASSAGE level: a retrieved chunk
counts only if it comes from the right file AND contains that text. Without it
the query falls back to DOCUMENT level (right file, any chunk), which is a much
weaker bar. The summary reports how many of each you have, so the numbers are
never stronger than the labels behind them.

Snippets rather than chunk ids: chunk UUIDs are regenerated on every re-ingest,
so id-based labels break as soon as a document is re-uploaded.

    python eval/recall_eval.py --user-id <uuid>
    python eval/recall_eval.py --user-id <uuid> --inspect "what is memoization?"
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.database import get_supabase
from app.services.embedding_service import get_embedding
from app.services.document_service import MAX_RRF_SCORE, search_documents

# Imported, never copied: a hardcoded duplicate would drift the day the real
# threshold is tuned, and the eval would quietly stop describing production.
try:
    from app.services.llm_service import CITATION_THRESHOLD
except Exception as exc:  # llm_service builds its client at import time
    CITATION_THRESHOLD = None
    _THRESHOLD_ERR = exc

ARMS = ("dense", "fts", "rrf")
ARM_LABELS = {"dense": "dense (vector)", "fts": "fts (keyword)", "rrf": "rrf (fused)"}

# Default n_sources on ChatRequest: how many chunks /chat actually considers.
N_SOURCES = 5


def fetch_candidates(question: str, user_id: str, candidate_depth: int) -> list[dict]:
    supabase = get_supabase()
    result = supabase.rpc("search_chunks_eval", {
        "query_embedding": get_embedding(question),
        "query_text": question,
        "user_id_filter": user_id,
        "candidate_depth": candidate_depth,
    }).execute()
    return result.data


PRODUCTION_RRF_K = 60  # the constant hardcoded in search_chunks


def rrf_score(row: dict, k: int) -> float:
    """Reciprocal Rank Fusion, recomputed client-side for an arbitrary k.

    Fusion is a pure function of the two ranks, which search_chunks_eval already
    returns, so k can be swept without touching the database. At k=60 this
    reproduces the rrf_score the SQL computed (asserted by check_rrf_parity).
    """
    score = 0.0
    if row["dense_rank"] is not None:
        score += 1.0 / (k + row["dense_rank"])
    if row["fts_rank"] is not None:
        score += 1.0 / (k + row["fts_rank"])
    return score


def max_rrf_score(k: int) -> float:
    """Ceiling: ranked first by both arms."""
    return 2.0 / (k + 1)


def rank_by_arm(rows: list[dict], arm: str, k: int = PRODUCTION_RRF_K) -> list[dict]:
    """Re-sort the shared candidate pool into one arm's own ranking."""
    if arm == "dense":
        scoped = [r for r in rows if r["dense_rank"] is not None]
        return sorted(scoped, key=lambda r: r["dense_rank"])
    if arm == "fts":
        scoped = [r for r in rows if r["fts_rank"] is not None]
        return sorted(scoped, key=lambda r: r["fts_rank"])
    return sorted(rows, key=lambda r: -rrf_score(r, k))


def check_rrf_parity(rows: list[dict]) -> bool:
    """Confirm the client-side RRF matches what the SQL produced at k=60."""
    return all(
        abs(rrf_score(r, PRODUCTION_RRF_K) - r["rrf_score"]) < 1e-9 for r in rows
    )


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def is_hit(row: dict, label: dict) -> bool:
    if row["filename"] != label["expected_filename"]:
        return False
    snippet = label.get("expected_snippet")
    if snippet:
        return _norm(snippet) in _norm(row["content"])
    return True


def granularity(label: dict) -> str:
    return "passage" if label.get("expected_snippet") else "document"


def suppressed_by_threshold(candidates: list[dict], rrf_k: int = PRODUCTION_RRF_K) -> bool:
    """True if /chat would show no citations at all for this query.

    llm_service drops the entire source list when the best normalized score
    falls under CITATION_THRESHOLD, so a chunk that ranks well but scores low
    is retrieved and never delivered. Recall alone cannot see that.
    """
    if CITATION_THRESHOLD is None:
        return False
    top = rank_by_arm(candidates, "rrf", rrf_k)[:N_SOURCES]
    best = max((rrf_score(r, rrf_k) for r in top), default=0.0)
    return min(best / max_rrf_score(rrf_k), 1.0) < CITATION_THRESHOLD


def check_parity(question: str, user_id: str) -> bool:
    """Confirm search_chunks_eval ranks identically to the production path.

    The eval reads its own SQL function, so without this the two could drift
    (a retuned k, a different candidate depth) and the report would describe a
    pipeline that no longer ships.
    """
    prod = [(r["filename"], r["chunk_index"])
            for r in search_documents(question, user_id, n_results=N_SOURCES)]
    mine = [(r["filename"], r["chunk_index"])
            for r in rank_by_arm(fetch_candidates(question, user_id, 50), "rrf")[:N_SOURCES]]
    if not prod and not mine:
        # Both empty means they "agree", but agreeing on nothing is not parity —
        # it means retrieval is returning no rows at all. Treat it as a failure
        # rather than letting the run report a tidy 0% as if it were a result.
        print("  ⚠  Both search paths returned NOTHING for the first query.")
        print("     That is an infrastructure problem, not a retrieval score:")
        print("     empty tables, wrong --user-id, or a broken SQL function.")
        return False
    return prod == mine


def collect_pools(queries, user_id, candidate_depth, quiet=False):
    """One embedding + one RPC per question, reused across every k in a sweep.

    Fusion is computed from the returned ranks, so varying k costs nothing.
    """
    pools = {}
    for i, label in enumerate(queries, 1):
        q = label["question"]
        pools[q] = fetch_candidates(q, user_id, candidate_depth)
        if not quiet:
            print(f"  fetched {i}/{len(queries)}", end="\r")
    if not quiet:
        print(" " * 30, end="\r")
    return pools


def evaluate(queries, user_id, ks, candidate_depth,
             rrf_k=PRODUCTION_RRF_K, pools=None, verbose=True):
    max_k = max(ks)
    totals = {a: {"hits": {k: 0 for k in ks}, "rr": 0.0} for a in ARMS}
    totals["delivered"] = {k: 0 for k in ks}
    details = []

    for i, label in enumerate(queries, 1):
        question = label["question"]
        candidates = (pools[question] if pools is not None
                      else fetch_candidates(question, user_id, candidate_depth))
        record = {"question": question, "granularity": granularity(label), "arms": {}}

        for arm in ARMS:
            ranked = rank_by_arm(candidates, arm, rrf_k)[:max_k]
            flags = [is_hit(r, label) for r in ranked]
            first = next((j + 1 for j, hit in enumerate(flags) if hit), None)

            for k in ks:
                if any(flags[:k]):
                    totals[arm]["hits"][k] += 1
            totals[arm]["rr"] += (1.0 / first) if first else 0.0
            record["arms"][arm] = {"first_hit_rank": first, "top": ranked[:3]}

        # What the user actually receives: a correct chunk that the citation
        # threshold then suppresses counts as a miss.
        record["suppressed"] = suppressed_by_threshold(candidates, rrf_k)
        rrf_first = record["arms"]["rrf"]["first_hit_rank"]
        for k in ks:
            if rrf_first and rrf_first <= k and not record["suppressed"]:
                totals["delivered"][k] += 1

        record["n_candidates"] = len(candidates)
        details.append(record)
        if verbose:
            mark = "✓" if rrf_first else "✗"
            ranks = "  ".join(
                f"{arm}={record['arms'][arm]['first_hit_rank'] or '—'}" for arm in ARMS
            )
            flag = "  [SUPPRESSED by citation threshold]" if record["suppressed"] else ""
            print(f"[{i}/{len(queries)}] {mark} {question}")
            print(f"          {granularity(label):<8} label | first hit: {ranks}{flag}")

    return totals, details


def sweep(queries, user_id, ks, candidate_depth, k_values):
    """Score every k against one fetch, so the fusion constant can be tuned.

    k=60 comes from the original RRF paper, tuned on runs of ~1000 candidates.
    On a small corpus 1/(k+rank) barely varies with rank, so fusion degenerates
    into counting how many arms found each chunk and discards their confidence.
    """
    print(f"\n{'=' * 68}")
    print("  RRF k SWEEP")
    print(f"{'=' * 68}")
    pools = collect_pools(queries, user_id, candidate_depth)

    if not check_rrf_parity(next(iter(pools.values()))):
        print("  ⚠  client-side RRF disagrees with the SQL at k=60; the sweep")
        print("     is not comparable to what production computes.\n")

    n = len(queries)
    max_k = max(ks)
    dense_mrr = fts_mrr = None
    rows = []
    for rk in k_values:
        totals, _ = evaluate(queries, user_id, ks, candidate_depth,
                             rrf_k=rk, pools=pools, verbose=False)
        dense_mrr = totals["dense"]["rr"] / n
        fts_mrr = totals["fts"]["rr"] / n
        rows.append((rk,
                     totals["rrf"]["hits"][1] / n,
                     totals["rrf"]["hits"][max_k] / n,
                     totals["rrf"]["rr"] / n))

    print(f"  Single arms (independent of k):  dense MRR {dense_mrr:.3f}   "
          f"fts MRR {fts_mrr:.3f}")
    print(f"\n  {'k':>5}  {'rrf R@1':>9}  {'rrf R@' + str(max_k):>9}  "
          f"{'rrf MRR':>9}  {'vs best arm':>12}")
    print(f"  {'-' * 54}")
    best_single = max(dense_mrr, fts_mrr)
    for rk, r1, rmax, mrr in rows:
        delta = mrr - best_single
        flag = "  <-- beats both" if delta > 0 else ""
        star = " *" if rk == PRODUCTION_RRF_K else "  "
        print(f"  {rk:>5}{star}{r1:>8.1%}  {rmax:>9.1%}  {mrr:>9.3f}  {delta:>+12.3f}{flag}")

    winners = [r for r in rows if r[3] > best_single]
    print()
    if winners:
        best = max(winners, key=lambda r: r[3])
        print(f"  Best k = {best[0]} (MRR {best[3]:.3f}, "
              f"{best[3] - best_single:+.3f} over the best single arm).")
        print(f"  To adopt it, change the two `60`s in search_chunks in schema.sql")
        print(f"  to {best[0]} and re-apply that function.")
    else:
        print("  No k makes fusion beat the best single arm on this corpus.")
        print("  That is a real result: keyword and vector search are finding")
        print("  the same passages, so fusing them adds nothing to recover.")
    print(f"\n  * = the value currently hardcoded in search_chunks")
    print(f"{'=' * 68}\n")


def report(totals, details, queries, ks):
    n = len(queries)
    passage = sum(1 for q in queries if granularity(q) == "passage")

    # A uniform 0% is almost never a retrieval result — it means nothing came
    # back at all. Say so plainly instead of printing a table of zeroes that
    # reads like a measurement.
    if all(d.get("n_candidates", 0) == 0 for d in details):
        print(f"\n{'=' * 68}")
        print("  NO RESULTS — THIS IS NOT A SCORE")
        print(f"{'=' * 68}")
        print(f"  Retrieval returned zero candidates for all {n} queries.")
        print("  Nothing was measured. Likely causes, in order:")
        print("    1. document_chunks is empty for this user — check with")
        print("       --check-labels, which reads the table directly")
        print("    2. --user-id does not match the account that holds the corpus")
        print("    3. search_chunks_eval is missing or erroring")
        print(f"{'=' * 68}\n")
        return

    print(f"\n{'=' * 68}")
    print("  SUMMARY")
    print(f"{'=' * 68}")
    header = f"  {'ranker':<16}" + "".join(f"{'R@' + str(k):>9}" for k in ks) + f"{'MRR':>9}"
    print(header)
    print(f"  {'-' * (len(header) - 2)}")
    for arm in ARMS:
        cells = "".join(f"{totals[arm]['hits'][k] / n:>8.1%} " for k in ks)
        print(f"  {ARM_LABELS[arm]:<16}{cells}{totals[arm]['rr'] / n:>8.3f}")

    delivered = "".join(f"{totals['delivered'][k] / n:>8.1%} " for k in ks)
    print(f"  {'delivered':<16}{delivered}{'—':>8}")
    print("  (delivered = rrf hit that also survives the citation threshold,")
    print("   i.e. what the user actually sees cited)")

    # totals[...]["rr"] accumulates reciprocal ranks; divide by n so this is a
    # true MRR difference. Comparing the raw sums overstated it n-fold.
    best_single = max(totals[a]["rr"] for a in ("dense", "fts")) / n
    delta = totals["rrf"]["rr"] / n - best_single
    verdict = "fusion beats both arms" if delta > 0 else "fusion does NOT beat the best single arm"
    print(f"\n  MRR delta vs best single arm: {delta:+.3f}  ->  {verdict}")

    if CITATION_THRESHOLD is None:
        print(f"\n  ⚠  Citation threshold unavailable ({type(_THRESHOLD_ERR).__name__}); "
              "delivered row assumes nothing is suppressed.")
    else:
        gap = totals["rrf"]["hits"][max(ks)] - totals["delivered"][max(ks)]
        if gap:
            print(f"\n  ⚠  {gap} query(s) retrieved the right passage but had every citation")
            print(f"     suppressed by CITATION_THRESHOLD={CITATION_THRESHOLD}. Recall")
            print("     overstates delivered quality by that much.")

    print(f"\n  Labels: {passage}/{n} passage-level, {n - passage}/{n} document-level")
    if passage < n:
        print("  Document-level labels only prove the right FILE was retrieved.")
        print("  Add \"expected_snippet\" to score actual passages (--inspect helps).")

    docs = {q["expected_filename"] for q in queries}
    if n < 30 or len(docs) < 5:
        print(f"\n  ⚠  {n} queries over {len(docs)} documents is a weak sample.")
        print("     With few documents a hit is likely by chance; aim for 30+ queries")
        print("     across 5+ documents before quoting these numbers.")

    failed = [d for d in details if not d["arms"]["rrf"]["first_hit_rank"]]
    if failed:
        print(f"\n  MISSED by rrf (top-{max(ks)}):")
        for d in failed:
            got = ", ".join(f"{r['filename']}#{r['chunk_index']}" for r in d["arms"]["rrf"]["top"])
            print(f"    • {d['question']}\n      got: {got or '(nothing)'}")
    print(f"{'=' * 68}\n")


def check_labels(queries: list[dict], user_id: str) -> int:
    """Validate authored snippets against the corpus before scoring anything.

    A snippet with a typo, or copied from a PDF viewer rather than from the
    extracted text, matches no chunk. Every query then scores 0% and reads as a
    retrieval regression instead of a labelling mistake. Catch it here.
    """
    supabase = get_supabase()
    rows = (
        supabase.table("document_chunks")
        .select("filename, chunk_index, content")
        .eq("user_id", user_id)
        .limit(5000)
        .execute()
    ).data
    print(f"\nChecking labels against {len(rows)} chunks\n{'=' * 68}")
    if len(rows) >= 5000:
        print("  ⚠  hit the 5000-chunk fetch cap; results may be incomplete\n")

    problems = 0
    for label in queries:
        question = label["question"]
        snippet = label.get("expected_snippet")
        want_file = label["expected_filename"]

        if not snippet:
            print(f"  ○  {question}\n     document-level label (no snippet yet)")
            continue

        matches = [r for r in rows if _norm(snippet) in _norm(r["content"])]
        right = [r for r in matches if r["filename"] == want_file]
        wrong = [r for r in matches if r["filename"] != want_file]

        if not matches:
            problems += 1
            print(f"  ✗  {question}")
            print(f"     snippet matches NO chunk — typo, or copied from the PDF")
            print(f"     rather than the extracted text. Re-copy from --inspect.")
        elif not right:
            problems += 1
            print(f"  ✗  {question}")
            print(f"     snippet only appears in {sorted({r['filename'] for r in wrong})},")
            print(f"     not in the expected {want_file}")
        elif len(right) > 1 or wrong:
            print(f"  ⚠  {question}")
            print(f"     matches {len(right)} chunks in {want_file}"
                  + (f" and {len(wrong)} elsewhere" if wrong else ""))
            print(f"     not distinctive — it will score hits it did not earn")
        else:
            hit = right[0]
            print(f"  ✓  {question}\n     unique -> {hit['filename']} chunk {hit['chunk_index']}")

    labelled = sum(1 for q in queries if q.get("expected_snippet"))
    print(f"\n  {labelled}/{len(queries)} queries have snippets; {problems} broken")
    print(f"{'=' * 68}\n")
    return problems


def inspect(question: str, user_id: str, candidate_depth: int) -> None:
    """Print top chunks verbatim so a gold snippet can be copied out."""
    rows = rank_by_arm(fetch_candidates(question, user_id, candidate_depth), "rrf")
    print(f"\nTop chunks for: {question!r}\n{'=' * 68}")
    for i, r in enumerate(rows[:5], 1):
        body = re.sub(r"\s+", " ", r["content"]).strip()
        print(f"\n[{i}] {r['filename']}  chunk {r['chunk_index']}  "
              f"(dense={r['dense_rank'] or '—'} fts={r['fts_rank'] or '—'})")
        print(f"    {body[:400]}{'…' if len(body) > 400 else ''}")
    print(f"\n{'=' * 68}")
    print('Copy a distinctive phrase from the correct chunk into "expected_snippet".\n')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hybrid retrieval Recall@K / MRR evaluation")
    parser.add_argument("--user-id", required=True, help="Supabase user UUID")
    parser.add_argument("--queries", default=str(Path(__file__).parent / "test_queries.json"))
    parser.add_argument("--k", nargs="+", type=int, default=[1, 3, 5])
    parser.add_argument("--candidate-depth", type=int, default=50,
                        help="Per-arm candidate pool, matches search_chunks (default 50)")
    parser.add_argument("--inspect", metavar="QUESTION",
                        help="Print top chunks for one question, to author a snippet label")
    parser.add_argument("--check-labels", action="store_true",
                        help="Verify authored snippets match exactly one chunk, then exit")
    parser.add_argument("--rrf-k", type=int, default=PRODUCTION_RRF_K,
                        help=f"RRF fusion constant (default {PRODUCTION_RRF_K}, "
                             "matching search_chunks)")
    parser.add_argument("--sweep", nargs="*", type=int, metavar="K",
                        help="Score several RRF k values off one fetch and compare. "
                             "Bare --sweep uses 1 2 3 5 10 20 40 60")
    args = parser.parse_args()

    if args.inspect:
        inspect(args.inspect, args.user_id, args.candidate_depth)
        raise SystemExit(0)

    with open(args.queries) as f:
        queries = json.load(f)

    if args.check_labels:
        raise SystemExit(1 if check_labels(queries, args.user_id) else 0)

    if args.sweep is not None:
        k_values = sorted(args.sweep) if args.sweep else [1, 2, 3, 5, 10, 20, 40, 60]
        sweep(queries, args.user_id, sorted(args.k), args.candidate_depth, k_values)
        raise SystemExit(0)

    ks = sorted(args.k)
    print(f"\n{'=' * 68}")
    print("  Hybrid Retrieval Evaluation")
    print(f"  {len(queries)} queries | K = {ks} | candidate depth = {args.candidate_depth}"
          f" | rrf k = {args.rrf_k}")
    if args.rrf_k != PRODUCTION_RRF_K:
        print(f"  NOTE: rrf k differs from the {PRODUCTION_RRF_K} in search_chunks, so"
              " these numbers")
        print("        describe a candidate tuning, not what /chat currently serves.")
    print(f"{'=' * 68}\n")

    # Parity only means anything at the production constant.
    if args.rrf_k == PRODUCTION_RRF_K and queries and \
            not check_parity(queries[0]["question"], args.user_id):
        print("  ⚠  PARITY FAILED: search_chunks_eval and the production search_documents")
        print("     path returned different top-5 rankings. The two SQL functions have")
        print("     drifted — these numbers no longer describe what /chat serves.\n")

    totals, details = evaluate(queries, args.user_id, ks, args.candidate_depth,
                               rrf_k=args.rrf_k)
    report(totals, details, queries, ks)
