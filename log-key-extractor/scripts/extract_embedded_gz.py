#!/usr/bin/env python3
"""Extract binary-embedded .gz files from an nvidia-bug-report.log.

nvidia-bug-report.sh dumps /var/log/libvirt/qemu/*.log-*.gz (and other *.gz)
as RAW binary into the report, delimited by:

    *** /var/log/libvirt/qemu//<name>.log-<date>.<epoch>.gz
    *** ls: -rw------- 1 root root NNN ... <path>.gz
    <binary gzip bytes...>
    ________________________________________________

vgpu_report.py / log_key_extract.py cannot read these; grep treats the report
as binary and silently skips them. This tool recovers the full VM lifecycle
history (rotated libvirt/qemu logs), which is often the ONLY place where
customer operations (live migration, HA restart storms) are recorded.

Usage:
    python3 extract_embedded_gz.py <bug_report.log> --out-dir out/ [--list] [--pattern 'libvirt'] [--flat]
"""
import argparse
import gzip
import os
import re
import sys

SEP = b"____________________________________________"
SECTION_RE = re.compile(rb"\*\*\* ([^\s*]+\.gz)\n\*\*\* ls: [^\n]*\n")
LS_ONLY_RE = re.compile(rb"\*\*\* ([^\s*]+\.gz)\n\*\*\* ls: [^\n]*\n\s*?\n")


def find_sections(src):
    """Yield (name, blob) for every embedded .gz whose binary body decompresses."""
    out = []
    for m in SECTION_RE.finditer(src):
        name = m.group(1).decode("utf-8", "replace")
        start = m.end()
        end = src.find(SEP, start)
        if end < 0:
            continue
        blob = src[start:end].rstrip(b"\n")
        if len(blob) < 32 or blob[:2] != b"\x1f\x8b":
            # not raw gzip (some OEM scripts base64 them instead) -> skip
            continue
        out.append((name, blob))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", help="nvidia-bug-report.log (raw binary content expected)")
    ap.add_argument("--out-dir", default="nr_out/gz", help="output directory (default nr_out/gz)")
    ap.add_argument("--pattern", default=None, help="only extract names matching this substring/regex")
    ap.add_argument("--list", action="store_true", help="only list embedded .gz sections, no extraction")
    ap.add_argument("--flat", action="store_true", help="flatten / in names to _ (needed for some OSes)")
    ap.add_argument("--min-bytes", type=int, default=200, help="skip decompressed outputs smaller than this (default 200)")
    args = ap.parse_args()

    with open(args.input, "rb") as f:
        src = f.read()

    sections = find_sections(src)
    if args.pattern:
        try:
            rx = re.compile(args.pattern)
            sections = [s for s in sections if rx.search(s[0])]
        except re.error:
            sections = [s for s in sections if args.pattern in s[0]]

    if not sections:
        sys.stderr.write("No embedded raw-gzip sections found. Possible causes:\n"
                         "  - OEM script base64-encodes .gz (look for 'base64' section headers instead)\n"
                         "  - report was exported via `more`/terminal and binaries were mangled\n")
        return 1

    if args.list:
        for name, blob in sections:
            try:
                size = len(gzip.decompress(blob))
            except OSError:
                size = -1
            print(f"{size:>12}  {name}")
        return 0

    os.makedirs(args.out_dir, exist_ok=True)
    ok = skipped = failed = 0
    for name, blob in sections:
        safe = name.replace("/", "_") if args.flat else name.lstrip("/")
        gz_path = os.path.join(args.out_dir, safe)
        txt_path = gz_path + ".txt"
        os.makedirs(os.path.dirname(gz_path), exist_ok=True)
        try:
            data = gzip.decompress(blob)
        except OSError as e:
            print(f"FAIL  {name}: {e}", file=sys.stderr)
            failed += 1
            continue
        if len(data) < args.min_bytes:
            skipped += 1
            continue
        with open(gz_path, "wb") as f:
            f.write(blob)
        with open(txt_path, "wb") as f:
            f.write(data)
        ok += 1
        print(f"OK    {name}  ({len(blob)}B gz -> {len(data)}B txt)")
    print(f"\nextracted={ok} skipped(<{args.min_bytes}B)={skipped} failed={failed}")
    print("Grep the *.txt outputs next. High-value patterns for vGPU incident forensics:")
    print("  r'starting up libvirt'        - every VM start (wall-clock ms timestamps)")
    print("  r'\\n-S \\\\'                    - migration-target mode (CPU paused)")
    print("  r'migrate-incoming'           - live migration INTO this host was attempted")
    print("  r'sysfsdev=/sys/bus/mdev/devices/([0-9a-f-]+)' - VM -> vGPU(mdev) mapping")
    print("  r'shutting down, reason=(\\w+)' - how each run ended (failed/destroyed/shutdown)")
    print("  r'error getting device from group' - dirty-mdev ENODEV signature")
    print("  r'Not a migration stream'     - source stream invalid (vGPU migration unsupported)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
