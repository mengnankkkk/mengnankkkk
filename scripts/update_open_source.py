"""Update public PR cards: python scripts/update_open_source.py.

Layout inspired by https://github.com/gmjneko/gmjneko.
Uses only the standard library; GITHUB_TOKEN is optional outside Actions.
"""

import json
import os
from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

USER = "mengnankkkk"
ROOT = Path(__file__).resolve().parents[1]
ROW_LIMIT = 9
DOT_LIMIT = 12
MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()


def github(path, **params):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = "https://api.github.com/" + path
    if params:
        url += "?" + urlencode(params)
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return json.load(response)


def fetch_prs():
    items = []
    for page in range(1, 11):
        data = github("search/issues", q=f"is:pr is:public author:{USER} -user:{USER}",
                      per_page=100, page=page, sort="created", order="desc")
        # Search caps results at 1,000: fail instead of publishing partial totals.
        if data["incomplete_results"] or data["total_count"] > 1000:
            raise RuntimeError("Incomplete GitHub search; partition the query before updating cards.")
        items.extend(data["items"])
        if len(items) >= data["total_count"]:
            return items
        if not data["items"]:
            raise RuntimeError("GitHub search ended before all PRs were returned.")
    raise RuntimeError("GitHub search pagination exceeded its limit.")


def group_prs(items):
    groups = defaultdict(list)
    for pr in items:
        if "/pull/" in pr["html_url"]:
            name = pr["html_url"].split("github.com/", 1)[1].split("/pull/", 1)[0]
            if name.split("/")[0].lower() != USER.lower():
                groups[name].append(pr)
    return groups


def status(pr):
    if pr["pull_request"].get("merged_at"):
        return "merged"
    if pr["state"] == "closed":
        return "closed"
    return "draft" if pr.get("draft") else "open"


def stars_label(stars):
    return f"{stars / 1000:.1f}K" if stars >= 1000 else str(stars)


def render(groups, stars, dark=False):
    names = sorted(groups, key=lambda name: (-len(groups[name]), -stars[name], name))
    shown = names[:ROW_LIMIT]
    height = 144 + 26 * max(len(shown), 1)
    bg, border, fg, muted = (("#0d1117", "#30363d", "#e6edf3", "#8b949e") if dark
                              else ("#fff", "#d8dee4", "#24292f", "#66707b"))
    merged, opened, closed, draft = (("#a371f7", "#3fb950", "#f85149", "#8b949e") if dark
                                    else ("#8250df", "#1a7f37", "#cf222e", "#66707b"))
    total = sum(map(len, groups.values()))
    svg = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="840" height="{height}" viewBox="0 0 840 {height}" role="img" aria-label="{USER} open source contributions">
  <title>{USER}: {total} public PRs across {len(groups)} external repositories</title>
  <desc>Repositories ranked by PR count. Each dot is one PR; +N counts additional PRs. Latest is the month the newest PR was opened.</desc>
  <style>
    text{{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,'Liberation Mono',monospace}}
    .panel{{fill:{bg};stroke:{border};stroke-width:1.2}}
    .heading{{fill:{fg};font-size:16px;font-weight:700}}
    .meta{{fill:{muted};font-size:12px;font-weight:600}}
    .name{{fill:{fg};font-size:11px;font-weight:600}}
    .long{{font-size:9.5px}}
    .muted{{fill:{muted};font-size:11px;font-weight:500}}
    .star{{fill:{'#d29922' if dark else '#bf8700'}}}
    .merged{{fill:{merged}}}.open{{fill:{opened}}}.closed{{fill:{closed}}}.draft{{fill:{draft}}}
  </style>
  <rect class="panel" x="1" y="1" width="838" height="{height - 2}" rx="14"/>
  <text class="heading" x="24" y="33">OPEN SOURCE CONTRIBUTIONS</text>
  <text class="meta" x="816" y="33" text-anchor="end">{len(groups)} repositories · {total} PRs</text>
  <text class="meta" x="430" y="62" text-anchor="end">STARS</text>
  <text class="meta" x="476" y="62">PRs</text>
  <text class="meta" x="816" y="62" text-anchor="end">LATEST</text>''']
    for index, name in enumerate(shown):
        prs = sorted(groups[name], key=lambda pr: pr["created_at"], reverse=True)
        latest = datetime.fromisoformat(prs[0]["created_at"].replace("Z", "+00:00"))
        month = f"{MONTHS[latest.month - 1]} {latest.year}"
        y = 91 + index * 26
        css = "name long" if len(name) > 33 else "name"
        svg.append(f'  <g><title>{escape(name)}: {len(prs)} PRs; latest opened {latest.date()}</title>')
        svg.append(f'    <text class="{css}" x="24" y="{y}">{escape(name)}</text>')
        svg.append(f'    <text class="muted" x="430" y="{y}" text-anchor="end">{stars_label(stars[name])} <tspan class="star">★</tspan></text>')
        for dot, pr in enumerate(prs[:DOT_LIMIT]):
            state = status(pr)
            title = escape(f'#{pr["html_url"].rsplit("/", 1)[-1]} · {state}')
            svg.append(f'    <circle class="{state}" cx="{466 + 14 * dot}" cy="{y - 4}" r="4"><title>{title}</title></circle>')
        if len(prs) > DOT_LIMIT:
            svg.append(f'    <text class="muted" x="640" y="{y}">+{len(prs) - DOT_LIMIT}</text>')
        svg.append(f'    <text class="muted" x="816" y="{y}" text-anchor="end">{month}</text></g>')
    if not shown:
        svg.append('  <text class="muted" x="24" y="91">No public external PRs yet.</text>')
    for x, state in [(28, "merged"), (130, "open"), (218, "closed"), (320, "draft")]:
        svg.append(f'  <circle class="{state}" cx="{x}" cy="{height - 49}" r="4"/><text class="muted" x="{x + 12}" y="{height - 45}">{state.title()}</text>')
    omitted = names[ROW_LIMIT:]
    footer = (f'{len(omitted)} more repositories · {sum(len(groups[name]) for name in omitted)} PRs · ' if omitted else '')
    svg.append(f'  <text class="muted" x="24" y="{height - 23}">{footer}Stars and PR data from GitHub public information</text>')
    return "\n".join(svg) + "\n</svg>\n"


def write_cards(groups, stars):
    cards = {"open-source.svg": render(groups, stars),
             "open-source-dark.svg": render(groups, stars, dark=True)}
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    for filename, svg in cards.items():
        (assets / filename).write_text(svg, encoding="utf-8")
    print(f"Updated cards: {len(groups)} repositories, {sum(map(len, groups.values()))} PRs")


if __name__ == "__main__":
    groups = group_prs(fetch_prs())
    stars = {name: github(f"repos/{name}")["stargazers_count"] for name in groups}
    write_cards(groups, stars)
