"""Ingest the fixture corpus into a dedicated evaluation account.

The app is bring-your-own-documents, so retrieval scores depend entirely on
which files a given account happens to hold. That makes results from a personal
account unreproducible: nobody else can rerun them, and they shift whenever you
upload or delete something. This seeds a known, version-controlled corpus into
a separate account so the numbers mean the same thing on every machine.

Ingestion goes through the production ingest_document(), so the eval measures
the real chunker and the real embedding model, not a reimplementation.

    python eval/seed_corpus.py                 # show what would happen
    python eval/seed_corpus.py --apply         # create account + ingest
    python eval/seed_corpus.py --apply --reset # re-ingest from scratch

Writes to whichever Supabase project your .env points at. It only ever touches
the eval account, never your own documents.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from app.database import get_supabase
from app.services.auth_service import DuplicateEmailError, register_user
from app.services.document_service import delete_document, ingest_document, list_documents

CORPUS_DIR = Path(__file__).parent / "corpus"
EVAL_EMAIL = os.environ.get("EVAL_USER_EMAIL", "eval-corpus@example.invalid")
EVAL_PASSWORD = os.environ.get("EVAL_USER_PASSWORD", "eval-corpus-password")


def get_or_create_user() -> str:
    try:
        user = register_user(EVAL_EMAIL, EVAL_PASSWORD)
        print(f"  created eval account {EVAL_EMAIL}")
        return user["id"]
    except DuplicateEmailError:
        rows = (
            get_supabase().table("users").select("id").eq("email", EVAL_EMAIL).execute()
        ).data
        print(f"  reusing eval account {EVAL_EMAIL}")
        return rows[0]["id"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the fixture corpus for evaluation")
    parser.add_argument("--apply", action="store_true",
                        help="actually write; without it this is a dry run")
    parser.add_argument("--reset", action="store_true",
                        help="delete the eval account's existing documents first")
    args = parser.parse_args()

    files = sorted(CORPUS_DIR.glob("*.md"))
    if not files:
        print(f"No corpus files in {CORPUS_DIR}")
        return 1

    print(f"\nCorpus: {len(files)} documents from {CORPUS_DIR}")
    for f in files:
        print(f"  {f.name:26} {len(f.read_text()):>6} chars")

    if not args.apply:
        print("\nDry run. Re-run with --apply to create the account and ingest.\n")
        return 0

    print()
    user_id = get_or_create_user()

    existing = list_documents(user_id)
    if existing and not args.reset:
        print(f"  {len(existing)} documents already ingested; pass --reset to replace")
        print(f"\n  user id: {user_id}\n")
        return 0

    for doc in existing:
        delete_document(doc["id"], user_id)
    if existing:
        print(f"  removed {len(existing)} previously ingested documents")

    total = 0
    for f in files:
        meta = ingest_document(f.read_bytes(), f.name, user_id)
        total += meta["chunk_count"]
        print(f"  ingested {f.name:26} -> {meta['chunk_count']} chunks")

    print(f"\n  {len(files)} documents, {total} chunks\n")
    # Absolute paths, and the same interpreter that ran this script, so the
    # commands work from any directory rather than only from backend/.
    script = Path(__file__).parent / "recall_eval.py"
    print("Now run:")
    print(f"  {sys.executable} {script} --user-id {user_id} --check-labels")
    print(f"  {sys.executable} {script} --user-id {user_id}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
