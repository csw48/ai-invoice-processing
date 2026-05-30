"""Probe Supabase anon access for app-owned tables.

This is a black-box check: it verifies that the browser anon key cannot read
rows from sensitive tables. It does not replace the SQL migration that enables
RLS/revokes grants, but it catches the dangerous symptom from outside Postgres.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


APP_TABLES = ("clients", "invoices", "vendors", "processing_logs", "client_configs")


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _request_json(url: str, anon_key: str) -> tuple[int, object]:
    request = urllib.request.Request(
        url,
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode()
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            return exc.code, json.loads(body) if body else None
        except json.JSONDecodeError:
            return exc.code, body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", default="../../apps/web/.env.local")
    parser.add_argument("--supabase-url", default=os.getenv("NEXT_PUBLIC_SUPABASE_URL", ""))
    parser.add_argument("--anon-key", default=os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", ""))
    args = parser.parse_args()

    env_values = _load_env_file(Path(args.env_file))
    supabase_url = args.supabase_url or env_values.get("NEXT_PUBLIC_SUPABASE_URL", "")
    anon_key = args.anon_key or env_values.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")

    if not supabase_url or not anon_key:
        print("Missing NEXT_PUBLIC_SUPABASE_URL or NEXT_PUBLIC_SUPABASE_ANON_KEY", file=sys.stderr)
        return 2

    failed = False
    for table in APP_TABLES:
        query = urllib.parse.urlencode({"select": "*", "limit": "1"})
        status, payload = _request_json(f"{supabase_url.rstrip('/')}/rest/v1/{table}?{query}", anon_key)
        if status == 200 and isinstance(payload, list) and payload:
            failed = True
            print(f"FAIL {table}: anon key can read rows")
        elif status == 200:
            print(f"OK   {table}: anon key returned no rows")
        elif status in {401, 403, 404}:
            print(f"OK   {table}: anon key blocked with HTTP {status}")
        else:
            failed = True
            print(f"FAIL {table}: unexpected HTTP {status}: {payload}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
