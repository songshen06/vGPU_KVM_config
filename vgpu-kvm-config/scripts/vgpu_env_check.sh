#!/bin/bash
# vGPU KVM Environment Check Script
# Usage: bash vgpu_env_check.sh
# Exit codes: 0 = all checks pass, non-zero = failures found

set -euo pipefail
FAILS=0

check_module() {
    local label="$1" module="$2"
    echo -n "  [$label] "
    if lsmod 2>/dev/null | awk 'NR > 1 { print $1 }' | grep -Fxq "$module"; then
        echo "OK"
    else
        echo "FAIL"
        FAILS=$((FAILS + 1))
    fi
}

echo "=== NVIDIA vGPU KVM Environment Check ==="
echo ""

echo "--- Kernel Module Checks ---"
check_module "nvidia_vgpu" nvidia_vgpu_vfio
check_module "nvidia"      nvidia
check_module "vfio"        vfio
echo -n "  [VFIO mdev] "
if lsmod 2>/dev/null | awk 'NR > 1 { print $1 }' | grep -Fxq vfio_mdev; then
    echo "OK"
else
    echo "NOT LOADED (required only for the mdev backend)"
fi

echo ""
echo "--- Service Checks ---"
echo -n "  [libvirt daemon] "
if systemctl is-active --quiet libvirtd || systemctl is-active --quiet virtqemud; then
    echo "OK"
else
    echo "FAIL (neither libvirtd nor virtqemud is active)"
    FAILS=$((FAILS + 1))
fi

echo ""
echo "--- GPU Visibility ---"
if nvidia-smi &>/dev/null; then
    echo "  [nvidia-smi] OK"
    GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l | tr -d ' ')
    echo "    GPUs detected: $GPU_COUNT"
    nvidia-smi --query-gpu=index,name,pci.bus_id,mig.mode.current --format=csv 2>/dev/null || true
else
    echo "  [nvidia-smi] FAIL — nvidia-smi not functional"
    FAILS=$((FAILS + 1))
fi

echo ""
echo "--- SR-IOV Support ---"
if [ -f /usr/lib/nvidia/sriov-manage ]; then
    echo "  [sriov-manage] Available at /usr/lib/nvidia/sriov-manage"
else
    echo "  [sriov-manage] Not found (may not be needed for legacy GPUs)"
fi

echo ""
echo "--- mdevctl Availability ---"
if command -v mdevctl &>/dev/null; then
    echo "  [mdevctl] Available ($(mdevctl --version 2>/dev/null || echo 'unknown version'))"
else
    echo "  [mdevctl] Not found — vGPU persistence requires custom scripts"
fi

echo ""
echo "--- NUMA / PCI Topology ---"
nvidia-smi topo -m 2>/dev/null || echo "  Not available"

echo ""
echo "--- Active vGPUs ---"
nvidia-smi vgpu 2>/dev/null || echo "  No active vGPUs"

echo ""
echo "--- Active MIG Instances ---"
nvidia-smi mig -lgi 2>/dev/null || echo "  No MIG instances"

echo ""
echo "=========================================="
if [ "$FAILS" -eq 0 ]; then
    echo "All checks passed. Host is ready for vGPU configuration."
    exit 0
else
    echo "$FAILS check(s) failed. Review failures before proceeding."
    exit 1
fi
