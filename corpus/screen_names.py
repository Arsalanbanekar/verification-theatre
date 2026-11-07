"""Screen invented proper nouns against GeoNames for near-collisions with real places.

Preexisting code: pass 1 written 6 Nov 2026, pass 2 added 8 Nov 2026, both before the
sprint (13-15 Nov 2026).

Rule (PREREGISTRATION.md section 3): an invented name is rejected if any real place name
lies within Levenshtein distance 2 of it (case-insensitive, letters only). Screen the
distinctive element of each name ("Brackenstow", not "Brackenstow Town Council"), since
generic words would dilute the distance. Survivors are then web-searched for companies,
organisations, streams and fictional towns that a gazetteer will not contain.

A name must be CLEAN in both passes:
  Pass 1  GB.txt (feature classes P and A) and cities500.txt (every place with
          population >= 500, worldwide).
  Pass 2  US.txt, CA.txt and AU.txt (feature classes P and A, any population). Added
          because pass 1 misses small places outside Great Britain: "Cedarhollow" is clean
          in pass 1 but an exact match for Cedar Hollow, a US populated place.

Reference data (not committed; GeoNames, CC BY 4.0, https://download.geonames.org/export/dump/):
  GB.zip and cities500.zip downloaded 2026-11-06; US.zip, CA.zip and AU.zip 2026-11-08.
GeoNames updates its dumps daily, so record the download date when re-running.

Usage:
  python -I screen_names.py --gb GB.txt --cities cities500.txt \
      --pass2 US.txt CA.txt AU.txt -- Name1 Name2 ...
"""
import argparse
import re
import sys
from collections import defaultdict

MAX_D = 2
PLACE_CLASSES = {"P", "A"}  # GeoNames feature classes: populated places, admin areas


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


def load_into(index, path, keep_classes=None):
    """Add every name and alternate name in a GeoNames dump to index[len][name]."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) < 15:
                continue
            fclass, fcode, cc, pop = p[6], p[7], p[8], p[14]
            if keep_classes and fclass not in keep_classes:
                continue
            info = (p[1], fcode, cc, int(pop or 0))
            names = {p[1], p[2]} | (set(p[3].split(",")) if p[3] else set())
            for n in names:
                k = norm(n)
                if len(k) < 4:
                    continue
                prev = index[len(k)].get(k)
                if prev is None or info[3] > prev[3]:
                    index[len(k)][k] = info


def hits(c, index):
    out = []
    for L in range(len(c) - MAX_D, len(c) + MAX_D + 1):
        for k, info in index.get(L, {}).items():
            d = bounded_lev(c, k, MAX_D)
            if d <= MAX_D:
                out.append((d, -info[3], k, info))
    return sorted(out)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gb", required=True, help="GeoNames GB.txt")
    ap.add_argument("--cities", required=True, help="GeoNames cities500.txt")
    ap.add_argument("--pass2", nargs="+", required=True, metavar="COUNTRY.txt",
                    help="GeoNames country dumps for pass 2 (US.txt CA.txt AU.txt)")
    ap.add_argument("names", nargs="+")
    a = ap.parse_args()

    pass1, pass2 = defaultdict(dict), defaultdict(dict)
    load_into(pass1, a.gb, PLACE_CLASSES)
    load_into(pass1, a.cities)
    for path in a.pass2:
        load_into(pass2, path, PLACE_CLASSES)

    for cand in a.names:
        c = norm(cand)
        h1, h2 = hits(c, pass1), hits(c, pass2)
        verdict = "CLEAN" if not (h1 or h2) else "REJECT"
        print(f"\n== {cand}: {verdict}  (pass 1 {'clean' if not h1 else 'hit'}, pass 2 {'clean' if not h2 else 'hit'})")
        for tag, hs in (("1", h1), ("2", h2)):
            for d, _, k, (disp, fcode, cc, pop) in hs[:4]:
                print(f"   pass {tag}  d={d}  {disp!r:28} {fcode:6} {cc}  pop={pop}")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
