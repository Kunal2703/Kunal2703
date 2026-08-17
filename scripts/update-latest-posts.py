#!/usr/bin/env python3
"""Refresh the "Latest writing" block in README.md from Hashnode.

The README keeps two marker comments:

    <!-- BLOG:START -->
    ...generated rows...
    <!-- BLOG:END -->

Only the text between them is replaced, so the rest of the README is never
touched. Fails safe: on any network or parsing error the script exits non-zero
without writing, leaving the previous list in place.

Usage:
    python3 scripts/update-latest-posts.py [--count 5] [--check]

    --check   render what would be written and diff it, without saving
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

HOST = "kunaltheengineer.hashnode.dev"
README = Path(__file__).resolve().parent.parent / "README.md"
START, END = "<!-- BLOG:START -->", "<!-- BLOG:END -->"

QUERY = """
query Latest($host: String!, $count: Int!) {
  publication(host: $host) {
    posts(first: $count) {
      edges {
        node {
          title
          slug
          publishedAt
          readTimeInMinutes
        }
      }
    }
  }
}
"""


def fetch(count: int) -> list[dict]:
    body = json.dumps(
        {"query": QUERY, "variables": {"host": HOST, "count": count}}
    ).encode()
    req = urllib.request.Request(
        "https://gql.hashnode.com",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "profile-readme-bot"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        status = resp.status
        ctype = resp.headers.get("Content-Type", "?")
        raw = resp.read()

    try:
        payload = json.loads(raw)
    except ValueError:
        # "Expecting value: line 1 column 1" on its own says nothing about why.
        # A 200 carrying HTML means the endpoint moved or a proxy answered.
        head = raw[:200].decode("utf-8", "replace").replace("\n", " ")
        raise RuntimeError(
            f"response was not JSON (HTTP {status}, Content-Type {ctype}): {head!r}"
        ) from None

    if payload.get("errors"):
        raise RuntimeError(payload["errors"][0].get("message", "GraphQL error"))

    pub = (payload.get("data") or {}).get("publication")
    if not pub:
        raise RuntimeError(f"publication not found for host {HOST}")

    posts = [e["node"] for e in pub["posts"]["edges"]]
    if not posts:
        raise RuntimeError("publication returned zero posts")
    return posts


def render(posts: list[dict]) -> str:
    rows = ["| Article | Published | Read |", "| :--- | :--- | :--- |"]
    for p in posts:
        title = p["title"].replace("|", "\\|").strip()
        date = p["publishedAt"][:10]
        mins = p.get("readTimeInMinutes") or 5
        rows.append(
            f"| **[{title}](https://{HOST}/{p['slug']})** | {date} | {mins} min |"
        )
    return "\n".join(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--check", action="store_true", help="print the block, do not write")
    args = ap.parse_args()

    text = README.read_text(encoding="utf-8")
    if START not in text or END not in text:
        print(f"error: markers {START} / {END} not found in README.md", file=sys.stderr)
        return 1

    try:
        block = render(fetch(args.count))
    except (urllib.error.URLError, OSError, RuntimeError, KeyError, ValueError) as exc:
        # fail safe — keep whatever is already in the README
        print(f"error: could not refresh posts ({exc}); README left unchanged", file=sys.stderr)
        return 1

    updated = re.sub(
        rf"{re.escape(START)}.*?{re.escape(END)}",
        f"{START}\n{block}\n{END}",
        text,
        flags=re.S,
    )

    if args.check:
        print(block)
        print("\n-- unchanged --" if updated == text else "\n-- would change README --", file=sys.stderr)
        return 0

    if updated == text:
        print("no change")
        return 0

    README.write_text(updated, encoding="utf-8")
    print(f"updated {len(block.splitlines()) - 2} article rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
