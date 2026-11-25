"""Rebuild the merged open source contributions table in README.md.

Lists every merged pull request by GH_USER in repositories that GH_USER does not
own, groups them by repository, sorts repositories by star count, and replaces
the table between the merged-prs markers. Only the standard library is used.
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request

USER = os.environ.get("GH_USER", "lyn1dev")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = os.environ.get("README_PATH", "README.md")
START = "<!-- merged-prs:start -->"
END = "<!-- merged-prs:end -->"


def api(url):
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "readme-merged-prs",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def merged_prs():
    query = urllib.parse.quote(f"author:{USER} is:pr is:merged")
    prs, page = [], 1
    while True:
        data = api(f"https://api.github.com/search/issues?q={query}&per_page=100&page={page}")
        items = data.get("items", [])
        prs.extend(items)
        if len(items) < 100 or len(prs) >= data.get("total_count", 0):
            return prs
        page += 1


def short_stars(n):
    if n < 1000:
        return str(n)
    return f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "k"


def build_table():
    repos = {}
    for pr in merged_prs():
        repo = pr["repository_url"].split("/repos/", 1)[1]
        if repo.split("/")[0].lower() == USER.lower():
            continue
        repos.setdefault(repo, []).append(pr["number"])

    rows = []
    for repo, numbers in repos.items():
        info = api(f"https://api.github.com/repos/{repo}")
        name = info["full_name"]
        rows.append((info["stargazers_count"], name, info["owner"]["login"], sorted(numbers)))
    rows.sort(key=lambda row: (-row[0], row[1].lower()))

    lines = ["| | Repository | ⭐ Stars | 🔀 Merged PRs |", "|:-:|:--|--:|:--|"]
    for stars, name, owner, numbers in rows:
        avatar = f'<img src="https://github.com/{owner}.png?size=40" width="20" height="20" alt="{owner}">'
        links = " ".join(f"[`#{n}`](https://github.com/{name}/pull/{n})" for n in numbers)
        lines.append(f"| {avatar} | [**{name}**](https://github.com/{name}) | {short_stars(stars)} | {links} |")
    return "\n".join(lines), sum(len(r[3]) for r in rows), len(rows)


SUMMARY_RE = re.compile(
    r"<summary><b>open source contributions(?:\s*\(\d+\s+repos?\s+merged\))?\s*-\s*click to expand</b></summary>"
)


def main():
    table, pr_count, repo_count = build_table()
    with open(README, encoding="utf-8", newline="") as f:
        text = f.read()
    newline = "\r\n" if "\r\n" in text else "\n"
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        sys.exit(f"Markers {START} / {END} not found in {README}")
    block = START + newline + newline + table.replace("\n", newline) + newline + newline + END
    updated = pattern.sub(lambda _: block, text, count=1)
    repo_label = "repo" if repo_count == 1 else "repos"
    summary = f"<summary><b>open source contributions ({repo_count} {repo_label} merged) - click to expand</b></summary>"
    updated = SUMMARY_RE.sub(lambda _: summary, updated, count=1)
    if updated != text:
        with open(README, "w", encoding="utf-8", newline="") as f:
            f.write(updated)
        print(f"README updated: {pr_count} merged PRs across {repo_count} repos")
    else:
        print("README already up to date")


if __name__ == "__main__":
    main()
