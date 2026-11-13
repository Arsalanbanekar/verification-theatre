# Pilot report

Generated 2026-11-11 10:37 UTC. Pilot data lives in `C:\Users\banek\Desktop\AI x Epistemics Research Sprint\data\pilot` and is excluded from analysis.

## Study calls

| model | condition | interpreter | attempt | status | result | in tok | out tok | $ | s |
|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b | C0 | no | 1 | ok | accept=true conf=95 | 508 | 159 | 0.00017 | 0.8 |
| gpt-oss-120b | C1 | no | 1 | ok | accept=true conf=95 | 1522 | 154 | 0.00032 | 0.5 |
| gpt-oss-120b | C2 | no | 1 | ok | accept=uncertain conf=60 | 1712 | 154 | 0.00035 | 0.6 |
| gpt-oss-120b | C5 | no | 1 | ok | accept=true conf=90 | 1754 | 138 | 0.00035 | 0.5 |
| gpt-oss-120b | C2 | yes | 1 | ok | accept=uncertain conf=45 | 1866 | 127 | 0.00036 | 0.8 |
| gpt-oss-20b | C0 | no | 1 | ok | accept=true conf=95 | 508 | 130 | 0.00008 | 0.6 |
| gpt-oss-20b | C1 | no | 1 | ok | accept=true conf=95 | 1522 | 253 | 0.00019 | 0.5 |
| gpt-oss-20b | C2 | no | 1 | ok | accept=true conf=90 | 1712 | 155 | 0.00017 | 0.5 |
| gpt-oss-20b | C5 | no | 1 | ok | accept=true conf=95 | 1754 | 129 | 0.00017 | 0.4 |
| gpt-oss-20b | C2 | yes | 1 | ok | accept=uncertain conf=30 | 1866 | 139 | 0.00018 | 0.3 |
| qwen3.8-27b | C0 | no | 1 | ok | accept=true conf=100 | 363 | 64 | 0.00055 | 0.6 |
| qwen3.8-27b | C1 | no | 1 | ok | accept=uncertain conf=10 | 1556 | 133 | 0.00178 | 0.5 |
| qwen3.8-27b | C2 | no | 1 | parse_retry | PARSE FAIL: HTTP 400 json_validate_failed; invalid J | 1554 | 129 | 0.00176 | 0.7 |
| qwen3.8-27b | C2 | no | 2 | parse_failed | PARSE FAIL: HTTP 400 json_validate_failed; invalid J | 1554 | 4 | 0.00126 | 0.4 |
| qwen3.8-27b | C5 | no | 1 | ok | accept=uncertain conf=90 | 1823 | 137 | 0.00201 | 0.7 |
| qwen3.8-27b | C2 | yes | 1 | ok | accept=uncertain conf=95 | 1943 | 99 | 0.00195 | 0.5 |
| gemini-3.5-flash-lite | C0 | no | 1 | ok | accept=true conf=100 | 348 | 99 | 0.00000 | 13.0 |
| gemini-3.5-flash-lite | C1 | no | 1 | ok | accept=true conf=95 | 1560 | 112 | 0.00000 | 1.5 |
| gemini-3.5-flash-lite | C2 | no | 1 | ok | accept=true conf=95 | 1783 | 100 | 0.00000 | 6.3 |
| gemini-3.5-flash-lite | C5 | no | 1 | ok | accept=true conf=95 | 1834 | 102 | 0.00000 | 23.3 |
| gemini-3.5-flash-lite | C4 | no | 1 | ok | accept=true conf=95 | 1565 | 99 | 0.00000 | 1.5 |

21 study responses; 20 of 20 pilot cells done; pilot spend $0.0116.

## Judge check

Skipped (`--skip-judge`): no judge call was made. Once the main judge is chosen and set in `models.yaml` (RUNBOOK.md section 9), run `python src/runner.py --pilot` again: it repeats no study call and makes the 10 judge calls.


## Projected full run (calibrated on the pilot's measured tokens)

| model | calls left | input tok/call | output tok/call | projected $ |
|---|---|---|---|---|
| gpt-oss-120b | 960 | 1518 | 146 | 0.303 |
| gpt-oss-20b | 960 | 1518 | 161 | 0.156 |
| qwen3.8-27b | 960 | 1471 | 94 | 1.492 |
| gemini-3.5-flash-lite | 720 | 1465 | 102 | 0.000 |

Projected total including spend so far: **$1.96** (hard stop $4.50). Judge costs are separate (OpenRouter credit).
