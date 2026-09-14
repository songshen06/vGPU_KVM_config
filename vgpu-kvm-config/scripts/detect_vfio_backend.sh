#!/bin/bash
# Detect the vGPU VFIO backend from the interfaces exposed by sysfs.
# Usage: bash detect_vfio_backend.sh [VF-BDF]

set -euo pipefail

SYSFS_ROOT="${VGPU_SYSFS_ROOT:-/sys}"
VF_BDF="${1:-}"

detect_bdf() {
    local bdf="$1"

    if [ -f "$SYSFS_ROOT/bus/pci/devices/$bdf/nvidia/creatable_vgpu_types" ]; then
        printf '%s vendor-specific\n' "$bdf"
        return 0
    fi

    if [ -d "$SYSFS_ROOT/class/mdev_bus/$bdf/mdev_supported_types" ]; then
        printf '%s mdev\n' "$bdf"
        return 0
    fi

    printf '%s unsupported\n' "$bdf"
    return 1
}

if [ -n "$VF_BDF" ]; then
    if [[ ! "$VF_BDF" =~ ^[[:xdigit:]]{4}:[[:xdigit:]]{2}:[[:xdigit:]]{2}\.[0-7]$ ]]; then
        echo "Invalid VF BDF: $VF_BDF" >&2
        exit 2
    fi
    detect_bdf "$VF_BDF"
    exit $?
fi

FOUND=0
for path in "$SYSFS_ROOT"/bus/pci/devices/*/nvidia/creatable_vgpu_types; do
    [ -f "$path" ] || continue
    bdf="${path%/nvidia/creatable_vgpu_types}"
    printf '%s vendor-specific\n' "${bdf##*/}"
    FOUND=1
done

for path in "$SYSFS_ROOT"/class/mdev_bus/*/mdev_supported_types; do
    [ -d "$path" ] || continue
    bdf="${path%/mdev_supported_types}"
    printf '%s mdev\n' "${bdf##*/}"
    FOUND=1
done

if [ "$FOUND" -eq 0 ]; then
    echo "No supported NVIDIA vGPU VFIO interface found." >&2
    exit 1
fi
