#!/usr/bin/env python3
"""Cross-reference flagged code-review files against a code_quality_report.md.

Ranks the files worth fixing first by combining, per file: churn and bug-fix
frequency (git), cyclomatic complexity (radon cc), maintainability (radon mi),
security by severity (bandit), dead code (vulture), types (pyrefly), and how
much the local-model review wrote.

Paths are matched by suffix, so absolute, repo-relative, or cwd-relative report
paths all work and no 'Target:' header line is required.

Usage: python3 cross_reference.py <report.md> <review_dir>
Writes <review_dir>/fix_plan.md and prints a ranked summary.
"""

import os
import re
import sys
from collections import defaultdict

W_CHURN = 3.0
W_BUGFIX = 2.0
CX_WEIGHT = {"C": 2.0, "D": 4.0, "E": 6.0, "F": 8.0}
W_MI_LOW = 2.0
W_SEC = {"High": 6.0, "Medium": 3.0, "Low": 1.0}
W_DEAD, DEAD_CAP = 0.5, 2.0
W_TYPE, TYPE_CAP = 0.5, 2.0
W_BUS = 1.0
W_REVIEW, REVIEW_CAP = 0.02, 3.0
SYNERGY = 4.0
GRADE_RANK = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}


def die(msg):
    sys.stderr.write(msg + "\n")
    sys.exit(1)


def read(path):
    try:
        with open(path, errors="replace") as fh:
            return fh.read()
    except OSError as exc:
        die(f"cannot read {path}: {exc}")


def split_sections(text):
    secs = {}
    parts = re.split(r"^###\s+(.+)$", text, flags=re.M)
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        m = re.search(r"```(?:\w+)?\n(.*?)\n```", body, re.S)
        secs[title] = m.group(1) if m else ""
    return secs


def find_section(secs, needle):
    for title, body in secs.items():
        if needle.lower() in title.lower():
            return body
    return ""


def parse_counts(block):
    out = {}
    for line in block.splitlines():
        m = re.match(r"^\s*(\d+)\s+(\S.*\S|\S)\s*$", line)
        if m:
            out[m.group(2)] = int(m.group(1))
    return out


def parse_bus(block):
    out = set()
    for line in block.splitlines():
        line = line.rstrip()
        if not line or line == "(no output)":
            continue
        out.add(line.split("\t")[-1].strip())
    return out


def parse_radon_cc(block):
    out = {}
    current = None
    for line in block.splitlines():
        if not line.strip() or line.strip() == "(no output)":
            continue
        if not line.startswith((" ", "\t")):
            current = line.strip()
            continue
        m = re.search(r"-\s([A-F])\s\(\d+\)\s*$", line.strip())
        if m and current:
            g = m.group(1)
            if current not in out or GRADE_RANK[g] > GRADE_RANK[out[current]]:
                out[current] = g
    return out


def parse_radon_mi(block):
    out = {}
    for line in block.splitlines():
        m = re.match(r"^(.+?)\s-\s([A-F])\s\([\d.]+\)\s*$", line.strip())
        if m and m.group(2) in ("B", "C", "D", "E", "F"):
            out[m.group(1)] = m.group(2)
    return out


def parse_vulture(block):
    out = defaultdict(int)
    for line in block.splitlines():
        m = re.match(r"^(.+?):\d+:\s", line)
        if m:
            out[m.group(1)] += 1
    return dict(out)


def parse_bandit(block):
    out = defaultdict(lambda: {"High": 0, "Medium": 0, "Low": 0})
    last_sev = None
    for line in block.splitlines():
        s = line.strip()
        m_sev = re.match(r"Severity:\s*(High|Medium|Low)", s)
        if m_sev:
            last_sev = m_sev.group(1)
            continue
        m_loc = re.match(r"Location:\s*(.+?):\d+", s)
        if m_loc and last_sev:
            out[m_loc.group(1)][last_sev] += 1
            last_sev = None
    return {k: v for k, v in out.items()}


def parse_types(block):
    out = defaultdict(int)
    for m in re.finditer(r"(\S+\.py):\d+", block):
        out[m.group(1)] += 1
    return dict(out)


def resolve(dct, key):
    if key in dct:
        return dct[key], False
    suf = "/" + key
    best_p, best_v, hits = None, None, 0
    for p, v in dct.items():
        if p.endswith(suf):
            hits += 1
            if best_p is None or len(p) > len(best_p):
                best_p, best_v = p, v
    return best_v, (hits > 1 and "/" not in key)


def load_flagged(review_dir):
    def clean(p):
        return p.strip().lstrip("./")

    words = {}
    for name in os.listdir(review_dir):
        if not name.endswith(".md") or name in ("_flagged.md", "fix_plan.md"):
            continue
        lines = read(os.path.join(review_dir, name)).splitlines()
        m = re.match(r"^#\s*Review:\s*(.+)$", lines[0]) if lines else None
        if not m:
            continue
        words[clean(m.group(1))] = len("\n".join(lines[1:]).split())
    wl = os.path.join(review_dir, "_worklist.txt")
    if os.path.exists(wl):
        flagged = []
        for line in read(wl).splitlines():
            m = re.match(r"^\s*-\s*\[[ x]\]\s*(.+\S)\s*$", line)
            if m:
                flagged.append(clean(m.group(1)))
        return {p: words.get(p, 0) for p in flagged}
    return words


def priority(row):
    if row["sec"]["High"] > 0:
        return "P1"
    if row["churn"] > 0 and row["cx"]:
        return "P1"
    if row["churn"] or row["cx"] or row["mi"] or any(row["sec"].values()):
        return "P2"
    return "P3"


def score(row):
    s = 0.0
    s += W_CHURN * row["churn"]
    s += W_BUGFIX * row["bugfix"]
    if row["cx"]:
        s += CX_WEIGHT.get(row["cx"], 0.0)
    if row["mi"]:
        s += W_MI_LOW
    for sev, n in row["sec"].items():
        s += W_SEC[sev] * n
    s += min(W_DEAD * row["dead"], DEAD_CAP)
    s += min(W_TYPE * row["types"], TYPE_CAP)
    if row["bus"]:
        s += W_BUS
    s += min(W_REVIEW * row["words"], REVIEW_CAP)
    if row["churn"] > 0 and row["cx"]:
        s += SYNERGY
    return round(s, 1)


def main():
    if len(sys.argv) != 3:
        die("usage: python3 cross_reference.py <report.md> <review_dir>")
    report_path, review_dir = sys.argv[1], sys.argv[2]
    if not os.path.isfile(report_path):
        die(f"no such report: {report_path}")
    if not os.path.isdir(review_dir):
        die(f"no such review dir: {review_dir}")

    secs = split_sections(read(report_path))
    churn = parse_counts(find_section(secs, "Churn"))
    bugfix = parse_counts(find_section(secs, "Bug-fix"))
    bus = parse_bus(find_section(secs, "Bus factor"))
    cx = parse_radon_cc(find_section(secs, "cyclomatic"))
    mi = parse_radon_mi(find_section(secs, "maintainability"))
    dead = parse_vulture(find_section(secs, "Vulture"))
    sec = parse_bandit(find_section(secs, "Bandit"))
    types = parse_types(find_section(secs, "Pyrefly"))
    bus_map = {p: True for p in bus}

    flagged = load_flagged(review_dir)
    if not flagged:
        die(f"no flagged files found in {review_dir} (need _worklist.txt or review *.md)")

    ambiguous = set()
    rows = []
    for path, words in flagged.items():
        vals = {}
        flags = []
        for name, dct in (
            ("churn", churn),
            ("bugfix", bugfix),
            ("cx", cx),
            ("mi", mi),
            ("dead", dead),
            ("sec", sec),
            ("types", types),
            ("bus", bus_map),
        ):
            v, amb = resolve(dct, path)
            vals[name] = v
            flags.append(amb)
        if any(flags):
            ambiguous.add(path)
        row = {
            "path": path,
            "churn": vals["churn"] or 0,
            "bugfix": vals["bugfix"] or 0,
            "cx": vals["cx"] or "",
            "mi": vals["mi"] or "",
            "sec": vals["sec"] or {"High": 0, "Medium": 0, "Low": 0},
            "dead": vals["dead"] or 0,
            "types": vals["types"] or 0,
            "bus": bool(vals["bus"]),
            "words": words,
        }
        row["score"] = score(row)
        row["prio"] = priority(row)
        rows.append(row)

    rows.sort(key=lambda r: (r["score"], r["churn"]), reverse=True)

    signalled = sum(
        1
        for r in rows
        if r["churn"]
        or r["cx"]
        or r["mi"]
        or any(r["sec"].values())
        or r["dead"]
        or r["types"]
        or r["bus"]
    )
    report_signal_files = len(
        set(churn) | set(bugfix) | set(cx) | set(mi) | set(dead) | set(sec) | set(types) | bus
    )

    def sec_cell(d):
        return f"{d['High']}/{d['Medium']}/{d['Low']}" if any(d.values()) else "-"

    def fmt_rows(rs):
        out = [
            "| # | Prio | File | Churn | Fixes | Cx | MI | Sec H/M/L | Dead | Types "
            "| Bus | Words | Score |",
            "|--:|:--|:--|--:|--:|:-:|:-:|:-:|--:|--:|:-:|--:|--:|",
        ]
        for i, r in enumerate(rs, 1):
            out.append(
                f"| {i} | {r['prio']} | {r['path']} | {r['churn'] or ''} | "
                f"{r['bugfix'] or ''} | {r['cx'] or '-'} | {r['mi'] or '-'} | "
                f"{sec_cell(r['sec'])} | {r['dead'] or ''} | {r['types'] or ''} | "
                f"{'Y' if r['bus'] else ''} | {r['words'] or ''} | {r['score']} |"
            )
        return "\n".join(out)

    counts = defaultdict(int)
    for r in rows:
        counts[r["prio"]] += 1

    header = (
        "# Fix Plan\n\n"
        f"- Report: `{report_path}`\n- Flagged files: {len(rows)}\n"
        f"- With report signals: {signalled}  "
        f"(no signal beyond the review: {len(rows) - signalled})\n"
        f"- Distinct files carrying any report signal: {report_signal_files}\n"
        f"- Priority split: P1 {counts['P1']}, P2 {counts['P2']}, P3 {counts['P3']}\n\n"
        "Priority rule: **P1** = security-High, or churn crossed with complexity. "
        "**P2** = any churn, complexity, maintainability, or security signal. "
        "**P3** = flagged by the review only, no corroborating report signal.\n\n"
        "Raw signal columns are shown so you can re-sort. `Cx` is the worst radon "
        "cyclomatic grade (C-F), `MI` a low maintainability grade (B-F), `Sec` is "
        "bandit High/Medium/Low counts, `Words` is how much the review wrote.\n\n"
    )

    p1p2 = [r for r in rows if r["prio"] in ("P1", "P2")]
    body = "## P1 and P2 (fix these first)\n\n" + fmt_rows(p1p2) + "\n\n"
    body += "## Full ranking\n\n" + fmt_rows(rows) + "\n"

    plan_path = os.path.join(review_dir, "fix_plan.md")
    with open(plan_path, "w") as fh:
        fh.write(header + body)

    print(header + "## Top 30\n\n" + fmt_rows(rows[:30]))
    if signalled == 0 and report_signal_files > 0:
        print(
            f"\nWARNING: report has signals for {report_signal_files} files but none "
            "matched your flagged paths; send a few lines of the Radon and Bandit sections."
        )
    if ambiguous:
        shown = ", ".join(sorted(ambiguous)[:5])
        more = " ..." if len(ambiguous) > 5 else ""
        print(f"\nAmbiguous single-name matches (verify): {shown}{more}")
    print(f"\nWrote {plan_path}")


if __name__ == "__main__":
    main()
