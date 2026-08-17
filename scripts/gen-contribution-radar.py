#!/usr/bin/env python3
"""Render the GitHub "Activity overview" radar as a standalone SVG.

GitHub draws this chart client-side on the profile page, so it cannot be
embedded in a README. This rebuilds it from the same numbers via the GraphQL
API and writes assets/contribution-radar.svg.

Usage:
    GITHUB_TOKEN=$(gh auth token) python3 scripts/gen-contribution-radar.py

The token must belong to the profile owner and carry `read:user` (plus
`read:org` for private repos owned by an organisation), otherwise private-repo
contributions collapse into restrictedContributionsCount and the breakdown only
reflects public activity. `repo` is not the scope that unlocks this.
"""

import json
import os
import sys
import urllib.request

USER = os.environ.get("GITHUB_USER", "Kunal2703")
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "contribution-radar.svg")

QUERY = """
query($login: String!) {
  viewer { login }
  user(login: $login) {
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      restrictedContributionsCount
      contributionCalendar { totalContributions }
    }
  }
}
"""

# canvas
W, H = 560, 440
CX, CY = 280, 220
R = 125           # radius of a 100%-of-max spoke
AXIS = 145        # drawn length of each axis line

BG, BORDER = "#0d1117", "#30363d"
LINE, FILL, DOT = "#3fb950", "#2ea043", "#e6ffec"
PCT_COLOR, LABEL_COLOR = "#f0f6fc", "#c9d1d9"
FONT = "-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif"


def fetch():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{USER}-profile-radar",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            # A traceback here reads like a bug in this script; it is almost
            # always a mangled secret. Report the length so a truncated or
            # whitespace-padded paste is obvious - a classic PAT is 40 chars
            # after the `ghp_` prefix.
            sys.exit(
                f"HTTP 401: GitHub rejected the token (length {len(token)}). "
                "The value is wrong, revoked or expired - not a scope problem. "
                "A classic PAT is 44 characters and starts `ghp_`; anything "
                "else means the secret was set from the wrong text."
            )
        sys.exit(f"HTTP {exc.code}: {exc.reason}")
    if "errors" in body:
        sys.exit(f"GraphQL error: {body['errors']}")

    # Guard: only the profile owner's own token can see the private breakdown.
    # Anything else (notably Actions' built-in GITHUB_TOKEN, which runs as
    # github-actions[bot]) silently returns public-only counts and would redraw
    # the chart with the wrong shape.
    viewer = body["data"]["viewer"]["login"]
    if viewer.lower() != USER.lower():
        sys.exit(
            f"token belongs to '{viewer}', not '{USER}'. Private contributions "
            "would be omitted - use a PAT owned by the profile owner."
        )

    c = body["data"]["user"]["contributionsCollection"]

    # Owning the token is not enough - it must also carry `read:user`. Without
    # it the API still answers, but every private contribution collapses into
    # restrictedContributionsCount and the breakdown silently becomes
    # public-only (90/10/0/0 here instead of 61/17/17/5).
    #
    # `repo` is the intuitive guess and it is wrong: a classic PAT with `repo`
    # and even `admin:org` still reports the public-only split. Contributions
    # to private repos are gated on `read:user`, per
    # https://docs.github.com/en/graphql/reference/objects#contributionscollection
    #
    # Do NOT try to detect this from contributionCalendar.totalContributions:
    # with "Include private contributions on my profile" enabled that figure
    # reports the full count to *any* viewer, so it looks correct either way.
    # restrictedContributionsCount is the honest signal - it is the number of
    # contributions this token is being denied.
    restricted = c["restrictedContributionsCount"]
    if restricted:
        sys.exit(
            f"token cannot see {restricted} private contributions, so the chart "
            "would be drawn from public activity only. The scope that unlocks "
            "them is `read:user` - NOT `repo`, which grants repository access "
            "but leaves the contribution breakdown public-only. Private repos "
            "owned by an organisation additionally need `read:org`. Classic "
            "tokens only; fine-grained tokens never expose this data."
        )
    return c


def build(c):
    counts = [
        ("Code review", c["totalPullRequestReviewContributions"]),
        ("Issues", c["totalIssueContributions"]),
        ("Pull requests", c["totalPullRequestContributions"]),
        ("Commits", c["totalCommitContributions"]),
    ]
    total = sum(n for _, n in counts) or 1
    top = max(n for _, n in counts) or 1

    # GitHub scales each spoke against the LARGEST category, not against 100%.
    pts, labels = [], []
    for i, (name, n) in enumerate(counts):
        r = R * n / top
        pct = round(100 * n / total)
        # order above is up, right, down, left
        dx, dy = [(0, -1), (1, 0), (0, 1), (-1, 0)][i]
        pts.append((CX + dx * r, CY + dy * r))
        labels.append((name, pct, i))

    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    dots = "".join(
        f'\n    <circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{DOT}" stroke="{LINE}" stroke-width="1.5"/>'
        for x, y in pts
    )

    # label anchors: above / right / below / left of the axis tips
    anchors = [
        (CX, 38, CX, 62, "middle"),
        (CX + AXIS + 10, 212, CX + AXIS + 10, 236, "start"),
        (CX, 398, CX, 422, "middle"),
        (CX - AXIS - 10, 212, CX - AXIS - 10, 236, "end"),
    ]
    text = ""
    for name, pct, i in labels:
        px, py, lx, ly, anchor = anchors[i]
        text += (
            f'\n    <text x="{px}" y="{py}" text-anchor="{anchor}" fill="{PCT_COLOR}" '
            f'font-family="{FONT}" font-size="22" font-weight="600">{pct}%</text>'
            f'\n    <text x="{lx}" y="{ly}" text-anchor="{anchor}" fill="{LABEL_COLOR}" '
            f'font-family="{FONT}" font-size="17">{name}</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Contribution breakdown for {USER}">
    <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>
    <line x1="{CX}" y1="{CY - AXIS}" x2="{CX}" y2="{CY + AXIS}" stroke="{LINE}" stroke-width="2"/>
    <line x1="{CX - AXIS}" y1="{CY}" x2="{CX + AXIS}" y2="{CY}" stroke="{LINE}" stroke-width="2"/>
    <polygon points="{poly}" fill="{FILL}" fill-opacity="0.55" stroke="{LINE}" stroke-width="2" stroke-linejoin="round"/>{dots}{text}
</svg>
"""


if __name__ == "__main__":
    collection = fetch()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        fh.write(build(collection))
    # Print the breakdown, not just the calendar total - the total is the one
    # number that looks the same whether or not private data was visible.
    rows = [
        ("commits", collection["totalCommitContributions"]),
        ("pull requests", collection["totalPullRequestContributions"]),
        ("code review", collection["totalPullRequestReviewContributions"]),
        ("issues", collection["totalIssueContributions"]),
    ]
    total = sum(n for _, n in rows) or 1
    print("wrote", os.path.relpath(OUT))
    for name, n in rows:
        print(f"  {name:<14}{n:>5}  {round(100 * n / total):>3}%")
    print(
        f"  {'':<14}{total:>5}  scored;",
        collection["contributionCalendar"]["totalContributions"],
        "on the calendar",
    )
