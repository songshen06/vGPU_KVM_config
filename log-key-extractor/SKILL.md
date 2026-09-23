---
name: log-key-extractor
description: "Extract high-signal context from huge logs for LLM analysis, and analyze NVIDIA vGPU bug-report logs (GPU/vGPU inventory, Xid error accounting, reboot-loop detection, memory-pin failures). Also recover binary-embedded rotated libvirt logs from bug reports and run multi-source combined analysis for vGPU incidents where the fault lives in the VM/hypervisor layer: VM start failures (vfio ENODEV / 'error getting device from group'), live-migration attempts on vGPU VMs (migrate-incoming / 'Not a migration stream'), VF FLR close failures, mdev dirty state, and proving which operator/platform action caused it. Use when logs are too large to send directly, when you need template aggregation and failure scoring, when analyzing an nvidia-bug-report.log for vGPU problems, or when vgpu_report.py returns an empty/INFO report but the vGPU host is clearly broken."
---

# Log Key Extractor

Three tools in one skill:

| Tool | Purpose |
|------|---------|
| `log_key_extract.py` | Generic: shrink a huge log into compact LLM context (templates + scored events + host profile). |
| `vgpu_report.py` | NVIDIA vGPU: structured bug-report analysis (inventory + Xid errors + reboot loops + pin failures + risk level). |
| `extract_embedded_gz.py` | Recover the raw-binary-embedded rotated libvirt/qemu logs (*.log-*.gz) inside an nvidia-bug-report.log. |

---

## Tool 1: log_key_extract.py (generic log shrinking)

Use when the user asks to summarize very large logs, keep only key failure signals, or build compact LLM input payloads.
For NVIDIA bug-report scenarios, also use it to extract host hardware/OS summary and focus-object evidence windows.

### Workflow

For generic logs, run the extractor directly. For an NVIDIA vGPU bug report, run Tool 2 (`vgpu_report.py`, below) first to identify suspect GPU BDFs, mdev UUIDs, and VMs, then run this extractor on the same raw log with those values as `--focus-object`. Do not use `vgpu_report.json` as the extractor's log input.

1. Run the extractor script on the raw log.
2. Check `llm_context.md` for quick quality validation.
3. If output is too noisy, increase `--min-score` or reduce `--top-events`.
4. If evidence is too thin, increase `--context-lines`.
5. Feed `llm_context.json`, `event_windows.json`, and the companion `vgpu_report.json` to the LLM.

### Command

```bash
python3 scripts/log_key_extract.py <input_log> \
  --out-dir nr_out/llm \
  --min-score 7 \
  --top-templates 20 \
  --top-events 30 \
  --context-lines 2 \
  --focus-object "<vm_uuid_or_name>" \
  --focus-object "<vgpu_uuid_or_bdf>" \
  --time-start "Feb 10 16:30:00" \
  --time-end "Feb 10 17:30:00"
```

If `--time-start/--time-end` are omitted, the script scans the whole log.
Supported time formats: `YYYY-MM-DD HH:MM:SS`, `YYYY-MM-DDTHH:MM:SS`, `Mon DD HH:MM:SS`, kernel seconds like `3908360.4`.

Optional switches:
- `--focus-object` (repeatable): explicitly track one or more target identifiers and return line hits.
- `--no-system-profile`: disable host hardware/OS extraction (enabled by default).
- `--max-focus-hits-each`: cap evidence lines per focus object (default `20`).
- `--max-host-evidence`: cap evidence lines per host profile section (default `4`).
- `--max-gpu-inventory`: cap host GPU inventory items (default `64`).
- `--validate-schema` / `--schema-path`: JSON schema validation for cross-agent integration.

### Outputs
- `llm_context.json`: structured summary (stats, top templates, top events, inspection_object, host_profile, metadata).
- `llm_context.md`: human-readable summary.
- `event_windows.json`: evidence windows around each top event.

---

## Tool 2: vgpu_report.py (NVIDIA vGPU bug-report analysis)

Use when the user asks to analyze an `nvidia-bug-report.log` for vGPU problems, or wants a health/risk assessment of a vGPU host.

### Command

```bash
python3 scripts/vgpu_report.py <input_log> --out-dir nr_out/vgpu --out-prefix vgpu_report
```

### What it reports (all parsed from the log, not guessed)

1. **GPU inventory** — every physical GPU: model, driver, VRAM, VBIOS, BDF, serial (from `NVIDIA GPU Details`).
2. **vGPU inventory** — EVERY mdev/vGPU on the host (not just the ones you name): VM name, vGPU profile/type, guest driver, license, FB usage, GPU utilization, MDEV UUID. This catches vGPUs the previous reports missed.
3. **Xid errors** — precise counts grouped by (GPU, Xid number), with subtype / channel / process breakdown. Fixes the counting bugs (Xid 13 vs 32 confusion, channel distribution, missing ESR lines).
4. **Reboot / crash loop** — `Received start call` count per mdev (separate from total mdev references), with first/last timestamp. A vGPU with >=10 start calls is flagged as a crash loop.
5. **Memory pin / IOCTL failures** — `Failed to pin` / `IOCTL failed` aggregated per mdev, revealing host-wide vfio pinning issues (not single-VM).
6. **Risk level** — transparent, rule-based (CRITICAL / HIGH / WARNING / INFO), NOT a fake numeric score. Rules: critical Xid (13/31/32/43/69/79/109/119/120...) or crash loop => CRITICAL; high Xid or pin failures => HIGH; any Xid => WARNING.

### Outputs
- `vgpu_report.json`: full structured report.
- `vgpu_report.md`: human-readable report with tables.

### Design notes (what was fixed vs the old "vm_state" tool)
- Guest vs host driver version differences are **normal** and are reported as neutral inventory, never flagged as a problem.
- Xid counts are exact per (BDF, Xid); no cross-contamination between Xid types.
- Every mdev is enumerated, so the report can't silently miss vGPUs.

---

## Tool 3: extract_embedded_gz.py (recover embedded rotated logs)

nvidia-bug-report.sh dumps `/var/log/libvirt/qemu/*.log-*.gz` as RAW BINARY into the
report. grep/other tools treat the report as binary and silently skip these sections —
but they often hold the ONLY record of customer/platform operations (live migration,
HA restart storms) because the current `.log` files have already been logrotated.

### Command

```bash
python3 scripts/extract_embedded_gz.py <bug_report.log> --out-dir nr_out/gz --flat
python3 scripts/extract_embedded_gz.py <bug_report.log> --list            # inventory only
python3 scripts/extract_embedded_gz.py <bug_report.log> --pattern 'libvirt' --out-dir nr_out/gz
```

Outputs `<name>.gz` + decompressed `<name>.gz.txt` per section, then prints the
high-value grep patterns for vGPU incident forensics (`starting up libvirt`,
`migrate-incoming`, `sysfsdev=/sys/bus/mdev/devices/...`, `shutting down, reason=`,
`error getting device from group`, `Not a migration stream`).

Exit hint: if it finds nothing, the report was likely mangled (exported via `more`) or
the OEM script base64-encodes .gz — do not conclude "no logs exist".

---

## Combined vGPU analysis (multi-source cross-correlation)

When `vgpu_report.py` returns a near-empty/INFO report but the vGPU host is clearly
broken (VM start failures, migration failures, "cannot open device", no Xid/ECC), the
fault is in the VM/hypervisor layer, not the GPU layer. Read
`references/combined-vgpu-analysis.md` BEFORE continuing. It contains:

- the 5 evidence sources inside one bug report and what each proves;
- the live-migration-target signature triad (`-S` + `migrate-incoming` + `MIGRATION active`);
- dirty-mdev discrimination: ENODEV ≠ EBUSY, sysfs-present-but-unopenable, `VF FLR failed during close -25`;
- 6 red herrings to not chase (e.g. `Attached GPUs: 1` on mdev hosts is normal);
- data-quality traps (`more`-mangled reports, `/dev/kmsg buffer overrun`);
- the 6-step workflow (order matters: extract gz → VM↔mdev map → lifecycle timeline → operator actions → time alignment → root cause).

---

## Tuning Guide

Read `references/tuning.md` when you need profile-specific tuning.

## Related

`vgpu_report.py` is bundled here as Tool 2. The standalone `vgpu-report` skill (same analyzer plus `analyze_vgpu_bundle.py`) can still be used as a unified entry point that runs both tools on one `nvidia-bug-report.log` and emits a `bundle_manifest.json` linking the outputs:

```bash
python3 vgpu-report/scripts/analyze_vgpu_bundle.py <nvidia-bug-report.log> --out-dir nr_out/vgpu-bundle
```
