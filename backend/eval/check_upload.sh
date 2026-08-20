#!/usr/bin/env bash
# Diagnose an upload against the live backend, with real HTTP status codes.
# Prompts for credentials; nothing is echoed, stored, or written to shell history.
set -u
API="${API:-https://personal-doc-assistant-api-h6x4.onrender.com}"
PDF="${1:?usage: check_upload.sh /path/to/file.pdf}"
JAR="$(mktemp)"; trap 'rm -f "$JAR"' EXIT

read -r -p "email: " EMAIL
read -r -s -p "password: " PASSWORD; echo

echo
echo "--- warming instance (free tier sleeps) ---"
curl -s -m 120 -o /dev/null -w "  /health  HTTP %{http_code}  %{time_total}s\n" "$API/health"

echo "--- login ---"
CODE=$(curl -s -m 120 -c "$JAR" -o /tmp/login.out -w '%{http_code}' \
  -X POST "$API/auth/login" -H 'Content-Type: application/json' \
  --data-binary @<(printf '{"email":%s,"password":%s}' \
      "$(printf '%s' "$EMAIL" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))')" \
      "$(printf '%s' "$PASSWORD" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))')"))
echo "  HTTP $CODE  $(cat /tmp/login.out)"
[ "$CODE" = "200" ] || { echo "  login failed - stopping"; exit 1; }

echo "--- upload: $(basename "$PDF") ($(du -h "$PDF" | cut -f1)) ---"
curl -s -m 600 -b "$JAR" -o /tmp/upload.out \
  -w "  HTTP %{http_code}   %{time_total}s total\n" \
  -X POST "$API/documents/upload" -F "file=@$PDF"
echo "  response: $(cat /tmp/upload.out)"

echo "--- documents now on the account ---"
curl -s -m 120 -b "$JAR" "$API/documents" | python3 -m json.tool 2>/dev/null | grep -E 'filename|chunk_count' || true
