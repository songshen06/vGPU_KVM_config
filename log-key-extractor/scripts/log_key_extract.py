#!/usr/bin/env python3
import argparse
import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Set, Tuple

SCHEMA_VERSION = "1.1.0"
TOOL_VERSION = "1.1.0"

# High-confidence failure signals
KEYWORD_WEIGHTS = {
    "xid": 12,
    "failed": 10,
    "error": 8,
    "panic": 10,
    "oom": 9,
    "timeout": 6,
    "timed out": 6,
    "reset": 5,
    "abort": 5,
    "unbind": 5,
    "migration": 4,
    "warn": 2,
}

# Lines that look like static PCI capability/state dump and should not dominate results.
CAPABILITY_NOISE_HINTS = (
    "devctl:",
    "devctl2:",
    "devsta:",
    "devcap2:",
    "bridgectl:",
    "cesta:",
    "cemsk:",
    "status: cap+",
    "l1subctl",
    "l1subcap",
)

# Must-have failure signals for line inclusion (unless score is very high)
PRIMARY_SIGNALS = (
    "failed",
    "error",
    "xid",
    "panic",
    "oom",
    "no such device",
    "operation not supported",
)

NOISE_PATTERNS = [
    re.compile(r"^[A-Za-z0-9+/=]{120,}$"),
    re.compile(r"^\s*$"),
]

TIMESTAMP_PATTERNS = [
    re.compile(r"^\[[0-9]+\.[0-9]+\]\s*"),
    re.compile(r"^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"),
    re.compile(r"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+"),
    re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?\s*"),
]

NORMALIZE_PATTERNS = [
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<UUID>"),
    (re.compile(r"\b[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]\b"), "<BDF>"),
    (re.compile(r"\b0x[0-9a-fA-F]+\b"), "<HEX>"),
    (re.compile(r"\b\d+\.\d+\.\d+\.\d+\b"), "<IPV4>"),
    (re.compile(r"\b\d+\b"), "<NUM>"),
    (re.compile(r"\b/tmp/[^\s]+"), "<TMP_PATH>"),
    (re.compile(r"\b/[A-Za-z0-9_./-]+"), "<PATH>"),
]

SYSLOG_RE = re.compile(
    r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
    r"(\d{1,2})\s+"
    r"(\d{2}):(\d{2}):(\d{2})"
)
ISO_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2}):(\d{2})"
)
BRACKET_TS_RE = re.compile(r"^\[(\d+(?:\.\d+)?)\]")
MONTH_MAP = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


@dataclass
class TemplateStat:
    count: int = 0
    first_line: int = 0
    last_line: int = 0
    score: int = 0
    reasons: Counter = field(default_factory=Counter)
    examples: List[str] = field(default_factory=list)


def _type_matches(value, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _validate_schema_subset(instance, schema: Dict, path: str, errors: List[str]) -> None:
    expected_type = schema.get("type")
    if expected_type and not _type_matches(instance, expected_type):
        errors.append(f"{path}: expected type '{expected_type}', got '{type(instance).__name__}'")
        return

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value '{instance}' is not in enum {schema['enum']}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: value {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: value {instance} > maximum {schema['maximum']}")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{path}: missing required key '{key}'")
        props = schema.get("properties", {})
        for key, sub_schema in props.items():
            if key in instance and isinstance(sub_schema, dict):
                _validate_schema_subset(instance[key], sub_schema, f"{path}.{key}", errors)

    if isinstance(instance, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(instance):
                _validate_schema_subset(item, item_schema, f"{path}[{idx}]", errors)


def validate_against_schema(report: Dict, schema_path: str) -> None:
    if not os.path.exists(schema_path):
        raise ValueError(f"Schema file not found: {schema_path}")
    with open(schema_path, "r", encoding="utf-8") as sf:
        schema = json.load(sf)
    errors: List[str] = []
    _validate_schema_subset(report, schema, "$", errors)
    if errors:
        preview = "\n".join(f"- {e}" for e in errors[:20])
        more = "" if len(errors) <= 20 else f"\n- ... and {len(errors) - 20} more"
        raise ValueError(f"Schema validation failed ({len(errors)} errors):\n{preview}{more}")


def strip_prefix(line: str) -> str:
    s = line.rstrip("\n")
    for p in TIMESTAMP_PATTERNS:
        s = p.sub("", s)
    return s.strip()


def is_noise(line: str) -> bool:
    return any(p.match(line) for p in NOISE_PATTERNS)


def looks_like_capability_dump(line: str) -> bool:
    low = line.lower()
    return any(hint in low for hint in CAPABILITY_NOISE_HINTS)


def normalize_line(line: str) -> str:
    s = strip_prefix(line)
    for pattern, repl in NORMALIZE_PATTERNS:
        s = pattern.sub(repl, s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def score_line(line: str) -> Tuple[int, List[str]]:
    lower = line.lower()
    score = 0
    reasons = []
    for kw, w in KEYWORD_WEIGHTS.items():
        if kw in lower:
            score += w
            reasons.append(kw)
    return score, reasons


def has_primary_signal(line: str) -> bool:
    lower = line.lower()
    return any(sig in lower for sig in PRIMARY_SIGNALS)


def parse_time_arg(raw: str):
    raw = raw.strip()
    if not raw:
        return None
    # Numeric range for kernel bracket timestamps, e.g. 3900000.0
    if re.fullmatch(r"\d+(?:\.\d+)?", raw):
        return ("kernel", float(raw))
    # Absolute datetime range, e.g. 2026-02-10 17:00:00
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return ("datetime", datetime.strptime(raw, fmt))
        except ValueError:
            pass
    # Syslog-like time range, e.g. Feb 10 17:00:00
    m = SYSLOG_RE.match(raw)
    if m:
        mon, day, hh, mm, ss = m.groups()
        return ("syslog", (MONTH_MAP[mon], int(day), int(hh), int(mm), int(ss)))
    raise ValueError(
        "Unsupported time format. Use 'YYYY-MM-DD HH:MM:SS', "
        "'YYYY-MM-DDTHH:MM:SS', 'Mon DD HH:MM:SS', or kernel seconds like '3908360.4'."
    )


def extract_time_value(raw_line: str):
    # Kernel relative seconds: [3908360.467646]
    mk = BRACKET_TS_RE.match(raw_line)
    if mk:
        return ("kernel", float(mk.group(1)))
    # ISO datetime: 2026-02-10 17:00:00
    mi = ISO_RE.match(raw_line)
    if mi:
        date_s, hh, mm, ss = mi.groups()
        try:
            dt = datetime.strptime(f"{date_s} {hh}:{mm}:{ss}", "%Y-%m-%d %H:%M:%S")
            return ("datetime", dt)
        except ValueError:
            pass
    # Syslog: Feb 10 17:00:00
    ms = SYSLOG_RE.match(raw_line)
    if ms:
        mon, day, hh, mm, ss = ms.groups()
        return ("syslog", (MONTH_MAP[mon], int(day), int(hh), int(mm), int(ss)))
    return None


def in_time_range(raw_line: str, time_start, time_end) -> bool:
    if time_start is None and time_end is None:
        return True
    tv = extract_time_value(raw_line)
    if tv is None:
        return False
    t_type, t_val = tv
    if time_start is not None:
        s_type, s_val = time_start
        if t_type != s_type:
            return False
        if t_val < s_val:
            return False
    if time_end is not None:
        e_type, e_val = time_end
        if t_type != e_type:
            return False
        if t_val > e_val:
            return False
    return True


def extract_system_profile(path: str, max_host_evidence: int = 4, max_gpu_inventory: int = 64) -> Dict:
    uname_re = re.compile(r"^Linux\s+(\S+)\s+(\S+).*?\b(x86_64|aarch64|arm64)\b")
    syslog_host_re = re.compile(
        r"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+(\S+)\s+"
    )
    pretty_name_re = re.compile(r'^PRETTY_NAME="?([^"\n]+)"?$')
    os_version_re = re.compile(r'^(?:VERSION|VERSION_ID)="?([^"\n]+)"?$')
    cpu_re = re.compile(r"^model name\s*:\s*(.+)$", re.IGNORECASE)
    processor_re = re.compile(r"^processor\s*:\s*\d+$", re.IGNORECASE)
    mem_re = re.compile(r"^MemTotal:\s*(\d+)\s*kB$", re.IGNORECASE)
    gpu_re = re.compile(r"^GPU\s+(\d+):\s*(.+?)\s+\(UUID:\s*([^)]+)\)")
    driver_re = re.compile(r"Driver Version:\s*([0-9.]+)")
    cuda_re = re.compile(r"CUDA Version:\s*([0-9.]+)")

    profile = {
        "hostname": None,
        "kernel_version": None,
        "architecture": None,
        "os_pretty_name": None,
        "os_version": None,
        "cpu_model": None,
        "cpu_count": 0,
        "memory_total_kib": None,
        "nvidia_driver_version": None,
        "cuda_version": None,
        "gpu_inventory": [],
    }
    evidence = {"os": [], "cpu": [], "memory": [], "nvidia": []}
    gpu_seen = set()
    cpu_count = 0

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.rstrip("\n")
            stripped = line.strip()
            if not stripped:
                continue

            m = uname_re.match(stripped)
            if m:
                uname_host = m.group(1)
                if uname_host.lower() != "version":
                    profile["hostname"] = profile["hostname"] or uname_host
                profile["kernel_version"] = profile["kernel_version"] or m.group(2)
                profile["architecture"] = profile["architecture"] or m.group(3)
                if len(evidence["os"]) < max_host_evidence:
                    evidence["os"].append(stripped)

            m = syslog_host_re.match(stripped)
            if m and profile["hostname"] is None:
                profile["hostname"] = m.group(1)
                if len(evidence["os"]) < max_host_evidence:
                    evidence["os"].append(stripped)

            m = pretty_name_re.match(stripped)
            if m and profile["os_pretty_name"] is None:
                profile["os_pretty_name"] = m.group(1)
                if len(evidence["os"]) < max_host_evidence:
                    evidence["os"].append(stripped)

            m = os_version_re.match(stripped)
            if m and profile["os_version"] is None:
                profile["os_version"] = m.group(1)
                if len(evidence["os"]) < max_host_evidence:
                    evidence["os"].append(stripped)

            m = cpu_re.match(stripped)
            if m and profile["cpu_model"] is None:
                profile["cpu_model"] = m.group(1)
                if len(evidence["cpu"]) < max_host_evidence:
                    evidence["cpu"].append(stripped)
            if processor_re.match(stripped):
                cpu_count += 1

            m = mem_re.match(stripped)
            if m and profile["memory_total_kib"] is None:
                profile["memory_total_kib"] = int(m.group(1))
                if len(evidence["memory"]) < max_host_evidence:
                    evidence["memory"].append(stripped)

            m = gpu_re.match(stripped)
            if m:
                key = (m.group(1), m.group(3))
                if key not in gpu_seen:
                    gpu_seen.add(key)
                    if len(profile["gpu_inventory"]) < max_gpu_inventory:
                        profile["gpu_inventory"].append(
                            {"index": m.group(1), "name": m.group(2).strip(), "uuid": m.group(3).strip()}
                        )
                if len(evidence["nvidia"]) < max_host_evidence:
                    evidence["nvidia"].append(stripped)

            m = driver_re.search(stripped)
            if m and profile["nvidia_driver_version"] is None:
                profile["nvidia_driver_version"] = m.group(1)
                if len(evidence["nvidia"]) < max_host_evidence:
                    evidence["nvidia"].append(stripped)

            m = cuda_re.search(stripped)
            if m and profile["cuda_version"] is None:
                profile["cuda_version"] = m.group(1)
                if len(evidence["nvidia"]) < max_host_evidence:
                    evidence["nvidia"].append(stripped)

    profile["cpu_count"] = cpu_count if cpu_count > 0 else None
    return {
        "summary": profile,
        "evidence": evidence,
        "truncated": {
            "gpu_inventory": len(gpu_seen) > max_gpu_inventory,
        },
        "counts": {
            "gpu_inventory_total_seen": len(gpu_seen),
        },
    }


def collect_focus_object_hits(path: str, focus_objects: List[str], max_hits_each: int = 20) -> Dict:
    if not focus_objects:
        return {"focus_objects": [], "hit_counts": {}, "hits": {}}

    lowered = {o: o.lower() for o in focus_objects if o}
    hits = {o: [] for o in lowered.keys()}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.rstrip("\n")
            lo = line.lower()
            for obj, obj_low in lowered.items():
                if len(hits[obj]) >= max_hits_each:
                    continue
                if obj_low in lo:
                    hits[obj].append({"line": lineno, "text": line[:500]})
    return {
        "focus_objects": list(lowered.keys()),
        "hit_counts": {k: len(v) for k, v in hits.items()},
        "hits": hits,
    }


def analyze_file(
    path: str,
    min_score: int,
    top_templates: int,
    top_events: int,
    time_start,
    time_end,
    focus_objects: List[str],
    include_system_profile: bool,
    max_focus_hits_each: int,
    max_host_evidence: int,
    max_gpu_inventory: int,
) -> Dict:
    templates: Dict[str, TemplateStat] = {}
    total_lines = 0
    kept_lines = 0
    noisy_lines = 0
    capability_filtered = 0
    time_filtered = 0
    scored_events = []

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for lineno, raw in enumerate(f, start=1):
            total_lines += 1
            if not in_time_range(raw, time_start, time_end):
                time_filtered += 1
                continue
            stripped = strip_prefix(raw)
            if is_noise(stripped):
                noisy_lines += 1
                continue
            if looks_like_capability_dump(stripped):
                capability_filtered += 1
                continue

            s, reasons = score_line(stripped)
            # Keep only meaningful failures/signals unless extremely high score.
            if not has_primary_signal(stripped) and s < (min_score + 5):
                continue

            template = normalize_line(raw)
            if not template:
                continue

            kept_lines += 1
            stat = templates.get(template)
            if stat is None:
                stat = TemplateStat(count=0, first_line=lineno, last_line=lineno)
                templates[template] = stat

            stat.count += 1
            stat.last_line = lineno
            stat.score += s
            stat.reasons.update(reasons)
            if len(stat.examples) < 2:
                stat.examples.append(raw.rstrip("\n"))

            if s >= min_score:
                scored_events.append({
                    "line": lineno,
                    "score": s,
                    "reasons": sorted(set(reasons)),
                    "raw": raw.rstrip("\n")[:500],
                    "template": template,
                })

    ranked_templates = sorted(
        templates.items(),
        key=lambda kv: (kv[1].score + kv[1].count * 2, kv[1].count),
        reverse=True,
    )

    top_template_items = []
    for i, (template, stat) in enumerate(ranked_templates[:top_templates], start=1):
        top_template_items.append({
            "rank": i,
            "template": template,
            "count": stat.count,
            "first_line": stat.first_line,
            "last_line": stat.last_line,
            "score": stat.score,
            "reasons": stat.reasons.most_common(5),
            "examples": stat.examples,
        })

    top_events_list = sorted(scored_events, key=lambda x: (x["score"], x["line"]), reverse=True)[:top_events]

    result = {
        "input_file": path,
            "stats": {
                "total_lines": total_lines,
                "time_filtered_lines": time_filtered,
                "noisy_lines": noisy_lines,
                "capability_filtered": capability_filtered,
                "kept_lines": kept_lines,
            "template_count": len(templates),
        },
            "selection_policy": {
                "min_score": min_score,
                "top_templates": top_templates,
                "top_events": top_events,
                "time_start": None if time_start is None else str(time_start[1]),
                "time_end": None if time_end is None else str(time_end[1]),
                "keywords": KEYWORD_WEIGHTS,
                "primary_signals": list(PRIMARY_SIGNALS),
            },
        "top_templates": top_template_items,
        "top_events": top_events_list,
    }
    result["inspection_object"] = collect_focus_object_hits(path, focus_objects, max_hits_each=max_focus_hits_each)
    if include_system_profile:
        result["host_profile"] = extract_system_profile(
            path,
            max_host_evidence=max_host_evidence,
            max_gpu_inventory=max_gpu_inventory,
        )
    return result


def build_windows(path: str, top_events: List[Dict], context_lines: int) -> List[Dict]:
    wanted: Set[int] = set()
    for e in top_events:
        line = e["line"]
        start = max(1, line - context_lines)
        end = line + context_lines
        for i in range(start, end + 1):
            wanted.add(i)

    lines_map: Dict[int, str] = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for idx, raw in enumerate(f, start=1):
            if idx in wanted:
                lines_map[idx] = raw.rstrip("\n")

    windows = []
    for e in top_events:
        line = e["line"]
        start = max(1, line - context_lines)
        end = line + context_lines
        snippet = []
        for i in range(start, end + 1):
            if i in lines_map:
                snippet.append({"line": i, "text": lines_map[i][:500]})
        windows.append(
            {
                "event_line": line,
                "event_score": e["score"],
                "event_reasons": e["reasons"],
                "event_template": e["template"],
                "window_start": start,
                "window_end": end,
                "snippet": snippet,
            }
        )
    return windows


def render_markdown(summary: Dict) -> str:
    lines = []
    stats = summary["stats"]
    lines.append("# Log Key Extraction Summary")
    lines.append("")
    lines.append(f"- Schema Version: `{summary.get('schema_version')}`")
    lines.append(f"- Tool Version: `{summary.get('tool_version')}`")
    lines.append(f"- Parse Mode: `{summary.get('parse_mode')}`")
    lines.append(f"- Confidence: `{summary.get('confidence')}`")
    lines.append(f"- Input: `{summary['input_file']}`")
    lines.append(f"- Total lines: {stats['total_lines']}")
    lines.append(f"- Time-filtered lines: {stats['time_filtered_lines']}")
    lines.append(f"- Noisy lines filtered: {stats['noisy_lines']}")
    lines.append(f"- Capability-dump lines filtered: {stats['capability_filtered']}")
    lines.append(f"- Kept candidate lines: {stats['kept_lines']}")
    lines.append(f"- Unique templates: {stats['template_count']}")
    lines.append("")

    lines.append("## Inspection Object")
    inspect = summary.get("inspection_object", {})
    lines.append(f"- Focus Objects: `{inspect.get('focus_objects', [])}`")
    lines.append(f"- Hit Counts: `{inspect.get('hit_counts', {})}`")
    lines.append("")

    host = summary.get("host_profile", {}).get("summary", {})
    if host:
        lines.append("## Host Hardware / OS")
        lines.append(f"- Hostname: `{host.get('hostname')}`")
        lines.append(f"- OS: `{host.get('os_pretty_name') or host.get('os_version')}`")
        lines.append(f"- Kernel: `{host.get('kernel_version')}`")
        lines.append(f"- Architecture: `{host.get('architecture')}`")
        lines.append(f"- CPU Model: `{host.get('cpu_model')}`")
        lines.append(f"- CPU Count: `{host.get('cpu_count')}`")
        lines.append(f"- Memory Total KiB: `{host.get('memory_total_kib')}`")
        lines.append(f"- NVIDIA Driver: `{host.get('nvidia_driver_version')}`")
        lines.append(f"- CUDA Version: `{host.get('cuda_version')}`")
        lines.append(
            f"- GPU Inventory: `count={summary.get('host_profile', {}).get('counts', {}).get('gpu_inventory_total_seen')}`"
        )
        lines.append(f"- GPU Inventory (sample): `{host.get('gpu_inventory')}`")
        lines.append("")

    lines.append("## Top Templates")
    lines.append("")
    for t in summary["top_templates"]:
        reasons = ", ".join(f"{k}:{v}" for k, v in t["reasons"]) if t["reasons"] else "none"
        lines.append(f"### {t['rank']}. count={t['count']} score={t['score']}")
        lines.append(f"- Template: `{t['template']}`")
        lines.append(f"- Lines: {t['first_line']} -> {t['last_line']}")
        lines.append(f"- Reasons: {reasons}")
        for ex in t["examples"]:
            lines.append(f"- Example: `{ex[:220]}`")
        lines.append("")

    lines.append("## Top Events")
    lines.append("")
    for e in summary["top_events"]:
        lines.append(f"- line={e['line']} score={e['score']} reasons={','.join(e['reasons'])}")
        lines.append(f"  - `{e['raw']}`")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract key log information for LLM-friendly analysis.")
    parser.add_argument("input", help="Path to input log file")
    parser.add_argument("--out-dir", default="nr_out/llm", help="Output directory")
    parser.add_argument("--min-score", type=int, default=7, help="Minimum event score to keep as top event")
    parser.add_argument("--top-templates", type=int, default=25, help="How many templates to keep")
    parser.add_argument("--top-events", type=int, default=50, help="How many scored raw events to keep")
    parser.add_argument("--context-lines", type=int, default=2, help="How many lines around each top event to keep")
    parser.add_argument(
        "--time-start",
        default=None,
        help="Time window start. Format: 'YYYY-MM-DD HH:MM:SS', 'Mon DD HH:MM:SS', or kernel seconds like '3908360.4'.",
    )
    parser.add_argument(
        "--time-end",
        default=None,
        help="Time window end. Format: 'YYYY-MM-DD HH:MM:SS', 'Mon DD HH:MM:SS', or kernel seconds like '3909000.0'.",
    )
    parser.add_argument(
        "--focus-object",
        action="append",
        default=[],
        help="Object identifier to inspect explicitly (repeatable), e.g. VM UUID / vGPU UUID / GPU BDF.",
    )
    parser.add_argument(
        "--no-system-profile",
        action="store_true",
        help="Disable host hardware/OS extraction from the log.",
    )
    parser.add_argument("--max-focus-hits-each", type=int, default=20, help="Max evidence lines per focus object.")
    parser.add_argument("--max-host-evidence", type=int, default=4, help="Max evidence lines per host profile section.")
    parser.add_argument("--max-gpu-inventory", type=int, default=64, help="Max GPU inventory items kept in host profile.")
    parser.add_argument("--validate-schema", action="store_true", help="Validate output JSON against the built-in schema.")
    parser.add_argument(
        "--schema-path",
        default=None,
        help="Optional custom schema path. Defaults to ../schemas/llm_context.schema.json",
    )
    args = parser.parse_args()

    time_start = parse_time_arg(args.time_start) if args.time_start else None
    time_end = parse_time_arg(args.time_end) if args.time_end else None
    if time_start and time_end and time_start[0] != time_end[0]:
        raise ValueError("time-start and time-end must use the same timestamp format.")

    os.makedirs(args.out_dir, exist_ok=True)
    summary = analyze_file(
        args.input,
        args.min_score,
        args.top_templates,
        args.top_events,
        time_start,
        time_end,
        args.focus_object,
        not args.no_system_profile,
        args.max_focus_hits_each,
        args.max_host_evidence,
        args.max_gpu_inventory,
    )
    summary["schema_version"] = SCHEMA_VERSION
    summary["tool_version"] = TOOL_VERSION
    summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    summary["parse_mode"] = "scored_templates"
    summary["confidence"] = "high" if summary["stats"]["kept_lines"] >= 100 else ("medium" if summary["stats"]["kept_lines"] > 0 else "low")
    if args.validate_schema:
        default_schema = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schemas", "llm_context.schema.json")
        validate_against_schema(summary, args.schema_path or default_schema)

    json_path = os.path.join(args.out_dir, "llm_context.json")
    md_path = os.path.join(args.out_dir, "llm_context.md")
    windows_path = os.path.join(args.out_dir, "event_windows.json")

    windows = build_windows(args.input, summary["top_events"], args.context_lines)

    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(summary, jf, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as mf:
        mf.write(render_markdown(summary))

    with open(windows_path, "w", encoding="utf-8") as wf:
        json.dump(
            {
                "input_file": args.input,
                "context_lines": args.context_lines,
                "windows": windows,
            },
            wf,
            ensure_ascii=False,
            indent=2,
        )

    print(f"Wrote: {json_path}")
    print(f"Wrote: {md_path}")
    print(f"Wrote: {windows_path}")


if __name__ == "__main__":
    main()
