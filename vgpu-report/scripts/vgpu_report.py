#!/usr/bin/env python3
"""
NVIDIA vGPU bug-report analyzer.

Parses an nvidia-bug-report.log and produces a structured, LLM-friendly report:

  - GPU inventory        (model / driver / VRAM / VBIOS / BDF / serial)
  - Full vGPU enumeration (EVERY mdev: VM name, vGPU type, guest driver,
                            license, FB usage, utilization)
  - Precise Xid error accounting, grouped by (GPU BDF, Xid number, subtype)
  - VM reboot-loop detection ("Received start call" count + interval per mdev)
  - Host memory pinning failures ("Failed to pin" / "IOCTL failed") per mdev
  - A transparent, rule-based risk assessment (NOT a fake numeric score)

Outputs: vgpu_report.json + vgpu_report.md

Usage:
    python3 vgpu_report.py <input_log> --out-dir nr_out/vgpu
"""

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

TOOL_VERSION = "1.2.0"
SCHEMA_VERSION = "1.2.0"

MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
MONTH_MAP_REV = {v: k for k, v in MONTH_MAP.items()}

SYSLOG_TS_RE = re.compile(
    r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})"
)

GPU_DETAILS_RE = re.compile(
    r"(?:NVIDIA GPU Details\s*\|\s*|\|\s*)(.+?),\s*([0-9.]+),\s*(\d+)\s*MiB,\s*([^,]+),\s*([0-9a-fA-F]+:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]),\s*(\S+)"
)

GPU_SECTION_RE = re.compile(r"^GPU\s+([0-9a-fA-F]+:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7])\s*$")
VGPU_ID_RE = re.compile(r"^vGPU ID\s+:\s*(\S+)")
KV_RE = re.compile(r"^\s*([A-Za-z][A-Za-z ]+?)\s*:\s*(.*?)\s*$")
NESTED_KV_RE = re.compile(r"^\s*([A-Za-z][A-Za-z ]+?)\s*:\s*(.*?)\s*$")

XID_RE = re.compile(r"NVRM: Xid \(PCI:([0-9a-fA-F:]+)\):\s*(\d+),?\s*(.*)$")

START_CALL_RE = re.compile(
    r"Received start call from nvidia-vgpu-vfio module:\s*mdev uuid\s+([0-9a-fA-F-]{36})\s+GPU PCI id\s+([0-9a-fA-F:.]+)\s+config params vgpu_type_id=(\d+)"
)

PIN_FAIL_RE = re.compile(
    r"\[nvidia-vgpu-vfio\]\s+([0-9a-fA-F-]{36}):\s*Failed to pin all\s+(0x[0-9a-fA-F]+)\s+pages,\s*ret:\s*(-?\d+)"
)
IOCTL_FAIL_RE = re.compile(
    r"\[nvidia-vgpu-vfio\]\s+([0-9a-fA-F-]{36}):\s*IOCTL\s+(0x[0-9a-fA-F]+)\s+failed\.\s*(0x[0-9a-fA-F]+)"
)
MIGRATION_RE = re.compile(
    r"\[nvidia-vgpu-vfio\]\s+([0-9a-fA-F-]{36}):\s*vGPU migration enabled"
)
NO_VGPU_DEV_RE = re.compile(r"No vGPU devices found for GPU\s+([0-9a-fA-F:]+(?:\.[0-7])?)")

XID_SEVERITY = {
    13: "critical", 31: "critical", 32: "critical", 69: "critical",
    109: "critical", 43: "critical", 79: "critical", 92: "critical",
    119: "critical", 120: "critical",
    45: "high", 48: "high", 61: "high", 62: "high", 63: "high",
    64: "high", 65: "high", 94: "high", 95: "high", 140: "high",
}


def parse_syslog_ts(line):
    m = SYSLOG_TS_RE.match(line)
    if not m:
        return None
    mon, day, hh, mm, ss = m.groups()
    return (MONTH_MAP[mon], int(day), int(hh), int(mm), int(ss))


def classify_xid_subtype(xid, rest):
    r = rest.lower()
    if xid == 13:
        if "illegal instruction" in r:
            return "illegal_instruction_encoding"
        if "mmu fault" in r:
            return "mmu_fault"
        if "multiple warp errors" in r:
            return "multiple_warp_errors"
        if "esr" in r:
            return "esr_register_dump"
        if "mismatch" in r:
            return "class_subchannel_mismatch"
        if "missing_macro" in r or "missing macro" in r:
            return "missing_macro_data"
        return "graphics_exception"
    if xid == 109:
        return "ctx_switch_timeout"
    if xid == 32:
        return "paging_fault"
    if xid == 69:
        return "class_error"
    if xid == 31:
        return "gpu_memory_page_fault"
    if xid == 43:
        return "stop_processing"
    if xid == 79:
        return "fallen_off_bus"
    return "other"


def extract_channel(rest):
    m = re.search(r"(?<![A-Za-z])channel\s+(0x[0-9a-fA-F]+)", rest, re.IGNORECASE)
    return m.group(1) if m else None


def extract_pid_name(rest):
    pid = re.search(r"pid=(\d+)", rest)
    name = re.search(r"name=([A-Za-z0-9_.+-]+)", rest)
    return (pid.group(1) if pid else None, name.group(1) if name else None)


def fmt_ts(ts):
    if not ts:
        return "?"
    mon, day, hh, mm, ss = ts
    return MONTH_MAP_REV.get(mon, str(mon)) + " " + str(day).zfill(2) + " " + str(hh).zfill(2) + ":" + str(mm).zfill(2) + ":" + str(ss).zfill(2)


def analyze(path):
    gpus = {}
    gpu_order = []
    vgpus = []
    xids = []
    start_calls = []
    pin_fails = []
    migrations = Counter()
    no_vgpu_dev = Counter()

    cur_gpu = None
    cur_vgpu = None
    cur_section = None

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.rstrip("\n")
            stripped = line.strip()

            m = GPU_DETAILS_RE.search(stripped)
            if m:
                name, driver, vram, vbios, bdf, serial = m.groups()
                bdf = bdf.lower()
                if bdf not in gpus:
                    gpus[bdf] = {
                        "bdf": bdf, "name": name.strip(),
                        "driver_version": driver, "vram_mib": int(vram),
                        "vbios": vbios.strip(), "serial": serial,
                    }
                    gpu_order.append(bdf)

            m = GPU_SECTION_RE.match(stripped)
            if m:
                cur_gpu = m.group(1).lower()
                cur_vgpu = None
                cur_section = None
                continue

            if cur_gpu is not None:
                m = VGPU_ID_RE.match(stripped)
                if m:
                    cur_vgpu = {
                        "gpu": cur_gpu, "vgpu_id": m.group(1),
                        "vm_uuid": None, "vm_name": None,
                        "vgpu_name": None, "vgpu_type": None,
                        "vgpu_uuid": None, "mdev_uuid": None,
                        "guest_driver_version": None, "license_status": None,
                        "placement_id": None, "pci_bus_id": None,
                        "fb_total": None, "fb_used": None, "fb_free": None,
                        "gpu_util": None, "mem_util": None,
                        "enc_util": None, "dec_util": None,
                    }
                    vgpus.append(cur_vgpu)
                    cur_section = None
                    continue

                if cur_vgpu is not None:
                    if re.match(r"^\s*PCI\s*$", stripped):
                        cur_section = "pci"
                        continue
                    if re.match(r"^\s*FB Memory Usage\s*$", stripped):
                        cur_section = "fb"
                        continue
                    if re.match(r"^\s*Utilization\s*$", stripped):
                        cur_section = "util"
                        continue
                    if re.match(r"^\s*(Encoder Stats|FBC Stats)\s*$", stripped):
                        cur_section = None
                        continue

                    m = KV_RE.match(stripped)
                    if m:
                        key, val = m.group(1).strip(), m.group(2).strip()
                        kmap = {
                            "VM UUID": "vm_uuid", "VM Name": "vm_name",
                            "vGPU Name": "vgpu_name", "vGPU Type": "vgpu_type",
                            "vGPU UUID": "vgpu_uuid", "MDEV UUID": "mdev_uuid",
                            "Guest Driver Version": "guest_driver_version",
                            "License Status": "license_status",
                            "Placement ID": "placement_id",
                        }
                        if key in kmap:
                            cur_vgpu[kmap[key]] = val
                            continue

                    if cur_section:
                        m = NESTED_KV_RE.match(stripped)
                        if m:
                            key, val = m.group(1).strip(), m.group(2).strip()
                            if cur_section == "pci" and key == "Bus Id":
                                cur_vgpu["pci_bus_id"] = val
                            elif cur_section == "fb":
                                if key == "Total":
                                    cur_vgpu["fb_total"] = val
                                elif key == "Used":
                                    cur_vgpu["fb_used"] = val
                                elif key == "Free":
                                    cur_vgpu["fb_free"] = val
                            elif cur_section == "util":
                                if key == "GPU":
                                    cur_vgpu["gpu_util"] = val
                                elif key == "Memory":
                                    cur_vgpu["mem_util"] = val
                                elif key == "Encoder":
                                    cur_vgpu["enc_util"] = val
                                elif key == "Decoder":
                                    cur_vgpu["dec_util"] = val

            m = XID_RE.search(stripped)
            if m:
                bdf = m.group(1).lower()
                xid = int(m.group(2))
                rest = m.group(3)
                pid, name = extract_pid_name(rest)
                xids.append({
                    "line": lineno, "bdf": bdf, "xid": xid,
                    "subtype": classify_xid_subtype(xid, rest),
                    "channel": extract_channel(rest),
                    "pid": pid, "process": name,
                    "ts": parse_syslog_ts(line), "raw": stripped[:400],
                })

            m = START_CALL_RE.search(stripped)
            if m:
                uuid, bdf, type_id = m.groups()
                start_calls.append({
                    "line": lineno, "mdev_uuid": uuid, "bdf": bdf.lower(),
                    "vgpu_type_id": type_id, "ts": parse_syslog_ts(line),
                })

            m = PIN_FAIL_RE.search(stripped)
            if m:
                uuid, pages, ret = m.groups()
                pin_fails.append({
                    "line": lineno, "mdev_uuid": uuid, "kind": "pin",
                    "pages": pages, "ret": ret, "ts": parse_syslog_ts(line),
                })
            m = IOCTL_FAIL_RE.search(stripped)
            if m:
                uuid, ioctl, code = m.groups()
                pin_fails.append({
                    "line": lineno, "mdev_uuid": uuid, "kind": "ioctl",
                    "ioctl": ioctl, "code": code, "ts": parse_syslog_ts(line),
                })

            m = MIGRATION_RE.search(stripped)
            if m:
                migrations[m.group(1)] += 1

            m = NO_VGPU_DEV_RE.search(stripped)
            if m:
                no_vgpu_dev[m.group(1).lower()] += 1

    xid_agg = defaultdict(lambda: {
        "count": 0, "subtypes": Counter(), "channels": Counter(),
        "processes": Counter(), "first_line": None, "last_line": None,
        "first_ts": None, "last_ts": None,
    })
    for e in xids:
        a = xid_agg[(e["bdf"], e["xid"])]
        a["count"] += 1
        a["subtypes"][e["subtype"]] += 1
        if e["channel"]:
            a["channels"][e["channel"]] += 1
        if e["process"]:
            a["processes"][e["process"]] += 1
        if a["first_line"] is None:
            a["first_line"] = e["line"]
        a["last_line"] = e["line"]
        if a["first_ts"] is None:
            a["first_ts"] = e["ts"]
        a["last_ts"] = e["ts"]

    reboot = defaultdict(lambda: {"count": 0, "first_ts": None, "last_ts": None, "bdf": None, "vgpu_type_id": None})
    for e in start_calls:
        r = reboot[e["mdev_uuid"]]
        r["count"] += 1
        r["bdf"] = e["bdf"]
        r["vgpu_type_id"] = e["vgpu_type_id"]
        if r["first_ts"] is None:
            r["first_ts"] = e["ts"]
        r["last_ts"] = e["ts"]

    pin_agg = defaultdict(lambda: {"pin": 0, "ioctl": 0, "rets": Counter(), "codes": Counter()})
    for e in pin_fails:
        p = pin_agg[e["mdev_uuid"]]
        if e["kind"] == "pin":
            p["pin"] += 1
            p["rets"][e["ret"]] += 1
        else:
            p["ioctl"] += 1
            p["codes"][e["code"]] += 1

    return {
        "gpus": [gpus[b] for b in gpu_order],
        "vgpus": vgpus,
        "xid": {
            "total": len(xids),
            "by_gpu_xid": [
                {
                    "bdf": bdf, "xid": xid, "count": a["count"],
                    "severity": XID_SEVERITY.get(xid, "medium"),
                    "subtypes": dict(a["subtypes"]),
                    "channels": dict(a["channels"]),
                    "processes": dict(a["processes"]),
                    "first_line": a["first_line"], "last_line": a["last_line"],
                    "first_ts": a["first_ts"], "last_ts": a["last_ts"],
                }
                for (bdf, xid), a in sorted(xid_agg.items())
            ],
        },
        "reboot_loop": {
            "total_start_calls": len(start_calls),
            "per_mdev": [
                {"mdev_uuid": u, "bdf": r["bdf"], "vgpu_type_id": r["vgpu_type_id"],
                 "start_calls": r["count"], "first_ts": r["first_ts"], "last_ts": r["last_ts"]}
                for u, r in sorted(reboot.items(), key=lambda kv: -kv[1]["count"])
            ],
        },
        "pin_failures": {
            "total": len(pin_fails),
            "per_mdev": [
                {"mdev_uuid": u, "pin": p["pin"], "ioctl": p["ioctl"],
                 "rets": dict(p["rets"]), "codes": dict(p["codes"])}
                for u, p in sorted(pin_agg.items(), key=lambda kv: -(kv[1]["pin"] + kv[1]["ioctl"]))
            ],
        },
        "signals": {
            "migration_enabled_per_mdev": dict(migrations),
            "no_vgpu_devices_per_gpu": dict(no_vgpu_dev),
        },
    }


def assess_risk(data):
    reasons = []
    critical = 0
    high = 0
    for x in data["xid"]["by_gpu_xid"]:
        if x["severity"] == "critical":
            critical += x["count"]
        elif x["severity"] == "high":
            high += x["count"]

    if critical > 0:
        reasons.append(str(critical) + " critical-severity Xid error(s)")
    if high > 0:
        reasons.append(str(high) + " high-severity Xid error(s)")

    crash_loops = [r for r in data["reboot_loop"]["per_mdev"] if r["start_calls"] >= 10]
    if crash_loops:
        loop_desc = ", ".join(r["mdev_uuid"][:8] + " (" + str(r["start_calls"]) + "x)" for r in crash_loops[:4])
        reasons.append(str(len(crash_loops)) + " vGPU(s) in reboot/crash loop (" + loop_desc + ")")

    if data["pin_failures"]["total"] > 0:
        reasons.append(str(data["pin_failures"]["total"]) + " memory-pin/IOCTL failure(s) across " + str(len(data["pin_failures"]["per_mdev"])) + " mdev(s)")

    if critical > 0 or crash_loops:
        level = "CRITICAL"
    elif high > 0 or data["pin_failures"]["total"] > 0:
        level = "HIGH"
    elif data["xid"]["total"] > 0:
        level = "WARNING"
    else:
        level = "INFO"
    return level, reasons


def render_markdown(data, risk_level, risk_reasons):
    L = []
    L.append("# vGPU Bug-Report Analysis")
    L.append("")
    L.append("- Tool Version: `" + TOOL_VERSION + "`")
    L.append("- Risk Level: **" + risk_level + "**")
    for r in risk_reasons:
        L.append("  - " + r)
    L.append("")

    L.append("## GPU Inventory")
    L.append("")
    L.append("| GPU | Model | Driver | VRAM | VBIOS | Serial |")
    L.append("|-----|-------|--------|------|-------|--------|")
    for g in data["gpus"]:
        L.append("| " + g["bdf"] + " | " + g["name"] + " | " + g["driver_version"] + " | " + str(g["vram_mib"]) + " MiB | " + g["vbios"] + " | " + g["serial"] + " |")
    if not data["gpus"]:
        L.append("_(none parsed - no NVIDIA GPU Details lines found)_")
    L.append("")

    L.append("## vGPU Inventory (" + str(len(data["vgpus"])) + " total)")
    L.append("")
    L.append("| GPU | VM Name | vGPU Profile | Type | Guest Driver | License | FB Used/Total | GPU Util | MDEV UUID |")
    L.append("|-----|---------|--------------|------|--------------|---------|---------------|----------|-----------|")
    for v in data["vgpus"]:
        L.append("| " + (v["gpu"] or "?") + " | " + (v["vm_name"] or "?") + " | " + (v["vgpu_name"] or "?") + " | " + (v["vgpu_type"] or "?") + " | " + (v["guest_driver_version"] or "?") + " | " + (v["license_status"] or "?") + " | " + (v["fb_used"] or "?") + "/" + (v["fb_total"] or "?") + " | " + (v["gpu_util"] or "?") + " | " + (v["mdev_uuid"] or "?") + " |")
    if not data["vgpus"]:
        L.append("_(none parsed - no nvidia-smi vgpu --query section found)_")
    L.append("")

    L.append("## Xid Errors (total " + str(data["xid"]["total"]) + ")")
    L.append("")
    if data["xid"]["by_gpu_xid"]:
        L.append("| GPU | Xid | Count | Severity | Subtypes | Channels | Processes |")
        L.append("|-----|-----|-------|----------|----------|----------|-----------|")
        for x in data["xid"]["by_gpu_xid"]:
            sub = ", ".join(k + "x" + str(v) for k, v in sorted(x["subtypes"].items(), key=lambda kv: -kv[1]))
            ch = ", ".join(k + "x" + str(v) for k, v in sorted(x["channels"].items(), key=lambda kv: -kv[1]))
            pr = ", ".join(k + "x" + str(v) for k, v in sorted(x["processes"].items(), key=lambda kv: -kv[1]))
            L.append("| " + x["bdf"] + " | " + str(x["xid"]) + " | " + str(x["count"]) + " | " + x["severity"] + " | " + sub + " | " + ch + " | " + pr + " |")
    else:
        L.append("_(no Xid errors found)_")
    L.append("")

    L.append("## Reboot / Crash Loop (total start calls: " + str(data["reboot_loop"]["total_start_calls"]) + ")")
    L.append("")
    if data["reboot_loop"]["per_mdev"]:
        L.append("| MDEV UUID | GPU | vGPU Type | Start Calls | First | Last |")
        L.append("|-----------|-----|-----------|-------------|-------|------|")
        for r in data["reboot_loop"]["per_mdev"]:
            L.append("| " + r["mdev_uuid"] + " | " + (r["bdf"] or "?") + " | " + (r["vgpu_type_id"] or "?") + " | " + str(r["start_calls"]) + " | " + fmt_ts(r["first_ts"]) + " | " + fmt_ts(r["last_ts"]) + " |")
    else:
        L.append("_(no start calls found)_")
    L.append("")

    L.append("## Memory Pin / IOCTL Failures (total " + str(data["pin_failures"]["total"]) + ")")
    L.append("")
    if data["pin_failures"]["per_mdev"]:
        L.append("| MDEV UUID | Pin | IOCTL | ret | codes |")
        L.append("|-----------|-----|-------|-----|-------|")
        for p in data["pin_failures"]["per_mdev"]:
            L.append("| " + p["mdev_uuid"] + " | " + str(p["pin"]) + " | " + str(p["ioctl"]) + " | " + str(p["rets"]) + " | " + str(p["codes"]) + " |")
    else:
        L.append("_(no pin/IOCTL failures found)_")
    L.append("")

    L.append("## Other Signals")
    L.append("")
    L.append("- vGPU migration enabled (per mdev): `" + str(data["signals"]["migration_enabled_per_mdev"]) + "`")
    L.append("- No vGPU devices found (per GPU): `" + str(data["signals"]["no_vgpu_devices_per_gpu"]) + "`")
    L.append("")
    return "\n".join(L)


def main():
    p = argparse.ArgumentParser(description="Analyze NVIDIA vGPU bug-report log.")
    p.add_argument("input", help="Path to nvidia-bug-report log")
    p.add_argument("--out-dir", default="nr_out/vgpu", help="Output directory")
    p.add_argument("--out-prefix", default="vgpu_report", help="Output file prefix")
    args = p.parse_args()

    data = analyze(args.input)
    risk_level, risk_reasons = assess_risk(data)

    report = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_file": args.input,
        "risk": {"level": risk_level, "reasons": risk_reasons},
    }
    report.update(data)

    os.makedirs(args.out_dir, exist_ok=True)
    json_path = os.path.join(args.out_dir, args.out_prefix + ".json")
    md_path = os.path.join(args.out_dir, args.out_prefix + ".md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_markdown(data, risk_level, risk_reasons))

    print("Risk level: " + risk_level)
    print("Wrote: " + json_path)
    print("Wrote: " + md_path)


if __name__ == "__main__":
    main()
