"""Screen invented proper nouns against GeoNames for near-collisions with real places.

Preexisting code: written 6 Nov 2026, before the sprint (13-15 Nov 2026).

Rule (PREREGISTRATION.md section 3): an invented name is rejected if any real place name
lies within Levenshtein distance 2 of it (case-insensitive, letters only). Screen the
distinctive element of each name ("Brackenstow", not "Brackenstow Town Council"), since
generic words would dilute the distance. Survivors are then web-searched for companies,
organisations and fictional towns that a gazetteer will not contain.

Reference data (not committed; GeoNames, CC BY 4.0), downloaded 2026-11-06:
  https://download.geonames.org/export/dump/GB.zip          -- feature classes P and A
  https://download.geonames.org/export/dump/cities500.zip   -- all places, pop >= 500
GeoNames updates its dumps daily, so record the download date when re-running.

Usage:
  python -I screen_names.py <GB.txt> <cities500.txt> Name1 Name2 ...
"""
import re
import sys
from collections import defaultdict

MAX_D = 2


def norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def bounded_lev(a: str, b: str, k: int) -> int:
    """Levenshtein distance, or k+1 if it exceeds k."""
    if abs(len(a) - len(b)) > k:
        return k + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        row_min = cur[0]
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            row_min = min(row_min, cur[j])
        if row_min > k:
            return k + 1
        prev = cur
    return prev[-1]


def load(path: str, keep_classes=None):
    """Map normalised name -> (display name, feature code, country, population), by length."""
    by_len = defaultdict(dict)
    with open(path, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 15:
                continue
            fclass, fcode, cc, pop = p[6], p[7], p[8], p[14]
            if keep_classes and fclass not in keep_classes:
                continue
            names = {p[1], p[2]} | (set(p[3].split(",")) if p[3] else set())
            for n in names:
                k = norm(n)
                if len(k) < 4:
                    continue
                prev = by_len[len(k)].get(k)
                info = (p[1], fcode, cc, int(pop or 0))
                if prev is None or info[3] > prev[3]:
                    by_len[len(k)][k] = info
    return by_len


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    gb_path, c500_path, *cands = sys.argv[1:]
    index = defaultdict(dict)
    for path, classes in ((gb_path, {"P", "A"}), (c500_path, None)):
        for L, d in load(path, classes).items():
            for k, info in d.items():
                if k not in index[L] or info[3] > index[L][k][3]:
                    index[L][k] = info
    for cand in cands:
        c = norm(cand)
        hits = []
        for L in range(len(c) - MAX_D, len(c) + MAX_D + 1):
            for k, info in index.get(L, {}).items():
                d = bounded_lev(c, k, MAX_D)
                if d <= MAX_D:
                    hits.append((d, -info[3], k, info))
        hits.sort()
        print(f"\n== {cand}: {'REJECT' if hits else 'CLEAN'}")
        for d, _, k, (disp, fcode, cc, pop) in hits[:8]:
            print(f"   d={d}  {disp!r:28} {fcode:6} {cc}  pop={pop}")


if __name__ == "__main__":
    main()
