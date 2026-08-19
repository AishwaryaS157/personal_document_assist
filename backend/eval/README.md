# Retrieval evaluation

Scores the retrieval pipeline with Recall@K and MRR, reporting the **dense**,
**fts**, and **rrf** rankers separately so fusion can be shown to beat (or not
beat) either arm on its own.

## Why there is a fixture corpus

This app is bring-your-own-documents, so retrieval scores depend entirely on
which files an account happens to hold. Evaluating against a personal account
makes the numbers unreproducible — nobody else can rerun them, and they move
whenever you upload or delete something.

`corpus/` holds five short documents that are committed with the repo, and
`test_queries.json` labels 32 questions against them. Seeding them into a
dedicated account makes a score mean the same thing on every machine and across
commits, so a regression is visible as a regression rather than as noise.

The corpus is written for the job: adjacent, genuinely confusable topics, and a
deliberate mix of question types so the ranker comparison is informative.

| kind | count | what it tests |
|---|---|---|
| lexical | 13 | question shares vocabulary with the passage — keyword arm should do well |
| paraphrase | 13 | question shares almost no vocabulary — dense arm should do well |
| confusable | 6 | the giveaway phrase also appears in another document |

If fusion is doing its job, `rrf` beats both `dense` and `fts` overall, even
though each arm wins its own family.

## Setup

1. `search_chunks_eval` must exist in the database — apply it from
   `supabase/schema.sql` (additive; `search_chunks` is unchanged and no tables
   are touched, so nothing is dropped).

2. Seed the corpus into its own account:

```bash
python eval/seed_corpus.py            # dry run, shows what it would do
python eval/seed_corpus.py --apply    # create the account and ingest
```

Ingestion goes through the production `ingest_document()`, so the eval exercises
the real chunker and embedding model rather than a reimplementation. The script
only ever touches the eval account. It prints the user id to use next.

## Run

```bash
python eval/recall_eval.py --user-id <eval-user-uuid> --check-labels
python eval/recall_eval.py --user-id <eval-user-uuid>
```

To evaluate your own uploads instead, point `--queries` at a separate label file
and pass your own `--user-id`.

```
  ranker                R@1      R@3      R@5      MRR
  ----------------------------------------------------
  dense (vector)      0.0%   100.0%   100.0%    0.417
  fts (keyword)      50.0%    50.0%    50.0%    0.500
  rrf (fused)        50.0%   100.0%   100.0%    0.750

  delivered          50.0%   100.0%   100.0%        —

  MRR delta vs best single arm: +0.250  ->  fusion beats both arms
```

**`delivered`** is the row that matters for user-facing quality. `llm_service`
drops the entire citation list when the best normalized score falls under
`CITATION_THRESHOLD`, so a query can retrieve the right passage and still show
"I couldn't find any relevant information." Recall counts that as a hit;
delivered does not. A gap between the two rows means the threshold is costing
you answers you successfully retrieved.

The threshold and the RRF ceiling are **imported** from the application, never
copied — a duplicated constant would drift the day either is tuned.

Before scoring, the harness also checks that `search_chunks_eval` ranks
identically to the production `search_documents` path, and warns loudly if the
two SQL functions have diverged. Without that, the report could describe a
pipeline that no longer ships.

## Label format

`test_queries.json` is a list of:

```json
{
  "question":          "what is memoization?",
  "expected_filename": "06DynamicProgramming.pdf",
  "expected_snippet":  "storing the results of expensive function calls"
}
```

`expected_snippet` is optional and decides how strictly the query is scored:

| label | hit means | proves |
|---|---|---|
| filename only | any chunk from that file was retrieved | **document**-level retrieval |
| + snippet | a chunk from that file *containing that text* was retrieved | **passage**-level retrieval |

Only passage-level labels support describing these as *question–source pairs*.
The summary prints the split, so the report never overstates the labels.

Snippets rather than chunk ids: chunk UUIDs are regenerated on every re-ingest,
so id-based labels break the first time a document is re-uploaded. Matching is
case- and whitespace-insensitive, so copy freely across line breaks.

## Authoring snippets

```bash
python eval/recall_eval.py --user-id <uuid> --inspect "what is memoization?"
```

Prints the top chunks verbatim with their per-arm ranks. Find the one that
genuinely answers the question, copy a distinctive phrase out of it, and paste
that into `expected_snippet`. Then verify:

```bash
python eval/recall_eval.py --user-id <uuid> --check-labels
```

This searches every chunk in the corpus and reports whether each snippet is
unique, missing, ambiguous, or in the wrong file. Run it before every scoring
run — a typo'd snippet matches nothing, scores 0%, and looks exactly like a
retrieval regression.

### Rules for a good snippet

- **Copy from `--inspect`, not from the PDF.** What is stored is pdfplumber's
  extraction; hyphenation, ligatures, and column order can differ from what a
  PDF viewer shows. Matching normalizes case and whitespace, nothing else.
- **Pick the passage that *answers*, not one that *mentions*.** "dynamic
  programming" appears on every slide of a DP deck; only one chunk defines it.
- **Keep it to one clause, roughly 5–12 words.** Longer spans risk straddling a
  chunk boundary and matching neither side.
- **Avoid titles, headers, and footers** — they repeat into many chunks.
- **Avoid the question's own wording.** A snippet that is just the query terms
  hands the keyword arm a free hit and biases the dense-vs-fts comparison. The
  point is to find the passage a good retriever *should* return, not the one
  that shares the most words with the question.

If `--inspect` does not surface the right passage at all, that is a finding
worth keeping: label it from the source document anyway (`--check-labels`
searches the whole corpus, not just what was retrieved) so the eval records a
genuine miss rather than hiding it.

## Sample size

The harness warns below 30 queries or 5 documents. With two documents a
retriever gets a coin-flip hit at K=5, so a high score measures the corpus
rather than the pipeline. Grow the corpus before quoting the numbers anywhere.
