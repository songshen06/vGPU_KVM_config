---
name: log-key-extractor
description: Extract high-signal context from huge logs for LLM analysis. Use this when logs are too large to send directly and you need template aggregation, failure scoring, and event context windows. For NVIDIA bug-report scenarios, also extracts host hardware/OS summary and focus-object evidence windows.
---

# Log Key Extractor

Use this skill when the user asks to summarize very large logs, keep only key failure signals, or build compact LLM input payloads.
For NVIDIA bug-report scenarios, also use it to extract host hardware/OS summary and focus-object evidence windows.

## Workflow

1. Run the extractor script on the raw log.
2. Check `llm_context.md` for quick quality validation.
3. If output is too noisy, increase `--min-score` or reduce `--top-events`.
4. If evidence is too thin, increase `--context-lines`.
5. Feed `llm_context.json` and `event_windows.json` to the LLM.

## Command

```bash
python3 skills/log-key-extractor/scripts/log_key_extract.py <input_log> \
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
Supported time formats:
- `YYYY-MM-DD HH:MM:SS`
- `YYYY-MM-DDTHH:MM:SS`
- `Mon DD HH:MM:SS` (for syslog-like lines)
- Kernel seconds in brackets domain, e.g. `3908360.4`

Optional switches:
- `--focus-object` (repeatable): explicitly track one or more target identifiers and return line hits.
- `--no-system-profile`: disable host hardware/OS extraction (enabled by default).
- `--max-focus-hits-each`: cap evidence lines per focus object (default `20`).
- `--max-host-evidence`: cap evidence lines per host profile section (default `4`).
- `--max-gpu-inventory`: cap host GPU inventory items (default `64`).
- Schema validation for cross-agent integration:
  - `--validate-schema`
  - `--schema-path` (optional, default `schemas/llm_context.schema.json`)

## Outputs

- `llm_context.json`: structured summary with stats, top templates, top events.
  - includes `inspection_object` (focus object hits).
  - includes `host_profile` (unless `--no-system-profile` is set).
  - includes metadata for cross-agent integration: `schema_version`, `tool_version`, `generated_at`, `parse_mode`, `confidence`.
- `llm_context.md`: human-readable summary.
- `event_windows.json`: evidence windows around each top event.

## Tuning Guide

Read `references/tuning.md` when you need profile-specific tuning.

## Related

For structured NVIDIA vGPU bug-report analysis (GPU/vGPU inventory, Xid accounting, reboot-loop detection, risk level), use the `vgpu-report` skill instead.
