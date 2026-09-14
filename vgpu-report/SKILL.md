---
name: vgpu-report
description: "Analyze NVIDIA vGPU bug-report logs. Produces a structured report: GPU/vGPU inventory, precise Xid error accounting, VM reboot-loop detection, memory-pin failures, and a transparent rule-based risk level. Use when analyzing an nvidia-bug-report.log for vGPU problems or when you need a health/risk assessment of a vGPU host."
---

# vGPU Bug-Report Analyzer

Use this skill when the user asks to analyze an `nvidia-bug-report.log` for vGPU problems, or wants a risk assessment of a vGPU host.

## Command

```bash
python3 skills/vgpu-report/scripts/vgpu_report.py <input_log> --out-dir nr_out/vgpu --out-prefix vgpu_report
```

For a large bug report that also needs focused raw evidence, run the unified workflow. It runs this report first, selects suspect mdev UUIDs and GPU BDFs, then runs `log-key-extractor` on the same input:

```bash
python3 skills/vgpu-report/scripts/analyze_vgpu_bundle.py <input_log> \
  --out-dir nr_out/vgpu-bundle
```

This command requires the `log-key-extractor` skill directory beside `vgpu-report` in the same skills directory.

## What it reports (all parsed from the log, not guessed)

1. **GPU inventory** — every physical GPU: model, driver, VRAM, VBIOS, BDF, serial (from `NVIDIA GPU Details`).
2. **vGPU inventory** — EVERY mdev/vGPU on the host (not just the ones you name): VM name, vGPU profile/type, guest driver, license, FB usage, GPU utilization, MDEV UUID.
3. **Xid errors** — precise counts grouped by (GPU, Xid number), with subtype / channel / process breakdown.
4. **Reboot / crash loop** — `Received start call` count per mdev (separate from total mdev references), with first/last timestamp. A vGPU with >=10 start calls is flagged as a crash loop.
5. **Memory pin / IOCTL failures** — `Failed to pin` / `IOCTL failed` aggregated per mdev, revealing host-wide vfio pinning issues.
6. **Risk level** — transparent, rule-based (CRITICAL / HIGH / WARNING / INFO), NOT a fake numeric score.

## Risk rules (transparent)

- Critical Xid (13/31/32/43/69/79/109/119/120...) or a crash loop => **CRITICAL**
- High Xid (45/48/61-65/94/95/140...) or pin failures => **HIGH**
- Any Xid => **WARNING**
- Otherwise => **INFO**

## Outputs

- `vgpu_report.json`: full structured report.
- `vgpu_report.md`: human-readable report with tables.

## Design notes

- Guest vs host driver version differences are **normal** and reported as neutral inventory, never flagged as a problem.
- Xid counts are exact per (BDF, Xid); no cross-contamination between Xid types.
- Every mdev is enumerated, so the report cannot silently miss vGPUs.

## Related

Use `log-key-extractor` as the second-stage evidence collector, not as a replacement for this report. Both tools read the same raw log: this skill identifies affected objects and risk, while the extractor returns scored events and context windows around those objects.
