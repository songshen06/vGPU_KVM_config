#!/usr/bin/env python3
"""Run vgpu-report first, then focus log-key-extractor on its suspects."""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def default_extractor_script() -> Path:
    skills_root = Path(__file__).resolve().parents[2]
    return skills_root / "log-key-extractor" / "scripts" / "log_key_extract.py"


def add_focus(store, value, reason):
    if value and value not in ("?", "N/A"):
        store[str(value)].add(reason)


def select_focus_objects(report, limit):
    focus = defaultdict(set)

    for item in report.get("reboot_loop", {}).get("per_mdev", []):
        if item.get("start_calls", 0) >= 10:
            add_focus(focus, item.get("mdev_uuid"), "crash-loop")
            add_focus(focus, item.get("bdf"), "crash-loop-gpu")

    for item in report.get("pin_failures", {}).get("per_mdev", []):
        if item.get("pin", 0) or item.get("ioctl", 0):
            add_focus(focus, item.get("mdev_uuid"), "pin-or-ioctl-failure")

    severity_rank = {"critical": 0, "high": 1, "medium": 2, "warning": 2}
    xid_items = sorted(
        report.get("xid", {}).get("by_gpu_xid", []),
        key=lambda item: (
            severity_rank.get(item.get("severity"), 3),
            -item.get("count", 0),
        ),
    )
    for item in xid_items:
        add_focus(focus, item.get("bdf"), "xid-" + str(item.get("xid", "unknown")))

    selected_mdevs = {
        value
        for value, reasons in focus.items()
        if "crash-loop" in reasons or "pin-or-ioctl-failure" in reasons
    }
    for vgpu in report.get("vgpus", []):
        if vgpu.get("mdev_uuid") not in selected_mdevs:
            continue
        add_focus(focus, vgpu.get("vm_name"), "affected-vm")
        add_focus(focus, vgpu.get("vm_uuid"), "affected-vm")
        add_focus(focus, vgpu.get("vgpu_uuid"), "affected-vgpu")

    return [
        {"value": value, "reasons": sorted(reasons)}
        for value, reasons in list(focus.items())[:limit]
    ]


def run(command):
    print("Running:", " ".join(str(part) for part in command), flush=True)
    subprocess.run([str(part) for part in command], check=True)


def main():
    parser = argparse.ArgumentParser(
        description="Create a vGPU structural report and focused evidence bundle from one raw bug report."
    )
    parser.add_argument("input", help="Path to nvidia-bug-report.log")
    parser.add_argument("--out-dir", default="nr_out/vgpu-bundle", help="Bundle output directory")
    parser.add_argument("--max-focus-objects", type=int, default=12)
    parser.add_argument("--min-score", type=int, default=7)
    parser.add_argument("--top-templates", type=int, default=20)
    parser.add_argument("--top-events", type=int, default=30)
    parser.add_argument("--context-lines", type=int, default=3)
    parser.add_argument("--extractor-script", default=str(default_extractor_script()))
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    out_dir = Path(args.out_dir).resolve()
    report_dir = out_dir / "report"
    evidence_dir = out_dir / "evidence"
    report_script = Path(__file__).resolve().with_name("vgpu_report.py")
    extractor_script = Path(args.extractor_script).resolve()

    if not input_path.is_file():
        parser.error("input log does not exist: " + str(input_path))
    if not extractor_script.is_file():
        parser.error(
            "log-key-extractor companion script not found: "
            + str(extractor_script)
            + ". Install both skill source directories together or pass --extractor-script."
        )

    report_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    run([
        sys.executable,
        report_script,
        input_path,
        "--out-dir",
        report_dir,
        "--out-prefix",
        "vgpu_report",
    ])

    report_path = report_dir / "vgpu_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    focus_objects = select_focus_objects(report, args.max_focus_objects)

    extractor_command = [
        sys.executable,
        extractor_script,
        input_path,
        "--out-dir",
        evidence_dir,
        "--min-score",
        args.min_score,
        "--top-templates",
        args.top_templates,
        "--top-events",
        args.top_events,
        "--context-lines",
        args.context_lines,
        "--validate-schema",
    ]
    for item in focus_objects:
        extractor_command.extend(["--focus-object", item["value"]])
    run(extractor_command)

    manifest = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_file": str(input_path),
        "risk": report.get("risk", {}),
        "focus_objects": focus_objects,
        "artifacts": {
            "vgpu_report_json": str(report_path),
            "vgpu_report_markdown": str(report_dir / "vgpu_report.md"),
            "llm_context_json": str(evidence_dir / "llm_context.json"),
            "llm_context_markdown": str(evidence_dir / "llm_context.md"),
            "event_windows_json": str(evidence_dir / "event_windows.json"),
        },
    }
    manifest_path = out_dir / "bundle_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Risk level:", manifest["risk"].get("level", "UNKNOWN"))
    print("Focus objects:", len(focus_objects))
    print("Wrote:", manifest_path)


if __name__ == "__main__":
    main()
