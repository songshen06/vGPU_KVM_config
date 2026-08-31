# Tuning

## Typical Profiles

- GPU/Xid heavy logs:
  - `--min-score 7`
  - `--top-templates 20`
  - `--top-events 30`
  - `--context-lines 2`

- Very noisy infra logs:
  - `--min-score 9`
  - `--top-templates 15`
  - `--top-events 20`

- Root cause deep-dive:
  - `--top-events 50`
  - `--context-lines 4`

## Heuristics

- Too many low-value lines in top events:
  - Increase `--min-score` by 1-2.
- Need to focus only on an incident window:
  - Add `--time-start` and `--time-end` with the same format.
- Missing surrounding clues:
  - Increase `--context-lines`.
- Output too large for model context:
  - Reduce `--top-events` first, then `--top-templates`.
