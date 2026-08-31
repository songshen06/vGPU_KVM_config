---
name: vgpu-kvm-config
description: Configure and monitor NVIDIA vGPU on Linux KVM (Red Hat / Ubuntu). Covers environment checks, vGPU creation (legacy mdev and SR-IOV), MIG mode setup (GPU instance + compute instance creation), MIG-backed vGPU configuration, and time-sliced partitioning on MIG instances. Includes RTX PRO 6000 Blackwell vGPU type tables and monitoring via nvidia-smi. Use when the user needs to set up or inspect vGPU on KVM, configure MIG for vGPU, create MIG-backed or time-sliced vGPUs, check environment prerequisites, or look up supported vGPU types for NVIDIA GPUs.
---

# vGPU KVM Quick Reference

Step-by-step NVIDIA vGPU creation on Linux KVM with Blackwell GPUs.

## Remote Execution

All commands below run on the **KVM host**. If the host is remote, prefix with SSH:

```bash
SSH_HOST="root@<kvm-host-ip>"    # user provides this
ssh $SSH_HOST '<command>'        # agent wraps every command
```

For multi-command sequences, use a heredoc to avoid repeated SSH connections:

```bash
ssh $SSH_HOST << 'ENDSSH'
cd /sys/class/mdev_bus/0000:02:00.2/mdev_supported_types
echo "$(uuidgen)" > nvidia-2289/create
ENDSSH
```

Prerequisite: SSH key-based auth from agent machine to KVM host.

## Quick Decision

```bash
# 1. Quick env check
lsmod | grep vfio && nvidia-smi          # must see nvidia_vgpu_vfio + GPU listed
/usr/lib/nvidia/sriov-manage -e all      # enable VFs
ls /sys/class/mdev_bus/                  # verify VFs present

# 2. Discover your VF PCI addresses (use these instead of the example BDFs below)
ls /sys/class/mdev_bus/
# Example output: 0000:02:00.2  0000:02:00.3  ...  0000:02:00.33
# Pick an unused VF as your target BDF. Each VF holds exactly 1 vGPU.
```

| Mode | When to use | Section |
|---|---|---|
| **Time-Sliced** (no MIG) | Max density, bursty VDI | [Phase A](#phase-a-time-sliced) |
| **MIG-Backed** (1 vGPU = 1 GI) | Hardware isolation, QoS | [Phase B](#phase-b-mig-backed) |
| **MIG + TimeSlice** (GI 内分片) | Dept isolation + sharing | [Phase C](#phase-c-mig--timeslice) |
| **Guest CI Split** | Tenant self-service | [references/guest-ci-split.md](references/guest-ci-split.md) |
| **Delete vGPU / Disable MIG** | Cleanup, revert to bare GPU | [references/host-setup.md#phase-e-teardown](references/host-setup.md#phase-e-teardown) |

**Architecture note:** MIG-backed vGPU (graphics) requires **Blackwell GPU** (RTX PRO 6000/5000/4500). Ampere/Hopper MIG is compute-only.

For host setup (BIOS, display mode, OS, driver install) and teardown, see `references/host-setup.md`.
For troubleshooting, see `references/troubleshooting.md`.
For RTX PRO 6000 vGPU type tables, see `references/vgpu-types-rtx-pro-6000.md`.

---

## Phase A: Time-Sliced

> **NOTE:** All BDF paths below use `0000:02:00.2` as an example. Replace with the actual unused VF address discovered from `ls /sys/class/mdev_bus/` in the Quick Decision step above. Each VF can hold exactly 1 vGPU; use different VFs for multiple vGPUs.

### A.1 Ensure MIG is OFF

```bash
nvidia-smi -i 0 --query-gpu=mig.mode.current --format=csv,noheader
# Must show: Disabled
# If "Enabled": stop all VMs and vGPUs, then disable MIG — see references/host-setup.md#phase-e-teardown
```

### A.2 List vGPU types on a VF

```bash
cd /sys/class/mdev_bus/0000:02:00.2/mdev_supported_types
for i in * ; do echo "$i : $(cat $i/name) : available=$(cat $i/available_instances)" ; done
```

### A.3 Create vGPU

```bash
# Pick type from listing, e.g. nvidia-2289
echo "$(uuidgen)" > nvidia-2289/create
# or via mdevctl:
mdevctl start -p 0000:02:00.2 -u $(uuidgen) -t nvidia-2289
```

**Rule:** 1 VF = 1 vGPU. For more vGPUs, switch to next unused VF:

```bash
cd /sys/class/mdev_bus/0000:02:00.3/mdev_supported_types
echo "$(uuidgen)" > nvidia-2289/create
```

### A.4 Create VM (if no VM exists yet)

```bash
# Import from existing qcow2 image
virt-install -v \
  --vcpus=8 \
  --memory 8192 \
  --disk /var/lib/libvirt/images/<os>.qcow2 \
  --network type=direct,source=<iface> \
  --network=default \
  --name <vm-name> \
  --os-variant <os-variant> \
  --noautoconsole \
  --import \
  --print-xml > /tmp/<vm-name>.xml

# Inspect XML, then define
virsh define /tmp/<vm-name>.xml
```

Common `--os-variant` values: `win10`, `win11`, `ubuntu22.04`, `ubuntu24.04`, `rhel9`. List all: `virt-install --os-variant list`.

For a fresh install (no qcow2 image), replace `--import` with `--cdrom /path/to/install.iso`.

### A.5 Attach vGPU to VM

```bash
cat > /tmp/vgpu.xml << EOF
<hostdev mode='subsystem' type='mdev' managed='no' model='vfio-pci' display='on'>
  <source><address uuid='<uuid>'/></source>
</hostdev>
EOF
virsh attach-device <vm-name> /tmp/vgpu.xml --config

# Suppress default video device:
cat > /tmp/video.xml << EOF
<video><model type='none'/></video>
EOF
virsh attach-device <vm-name> /tmp/video.xml --config

virsh start <vm-name>
```

To get VM IP (for guest driver install):
```bash
virsh domifaddr <vm-name>   # or: virsh net-dhcp-leases default
```

### A.6 Guest Driver + License

```bash
# Linux VM:
./NVIDIA-Linux-x86_64-595.91.07-grid.run -as
cp <token> /etc/nvidia/ClientConfigToken/
systemctl restart nvidia-gridd

# Windows VM:
# Run .exe installer
# Copy .tok to C:\Program Files\NVIDIA Corporation\vGPU Licensing\ClientConfigToken\
# Restart "NVIDIA Display Container LS" service

# Verify:
nvidia-smi -q | grep License
```

---

## Phase B: MIG-Backed

> **NOTE:** Same as Phase A — replace example BDF `0000:02:00.X` with actual unused VF addresses from `ls /sys/class/mdev_bus/`.

1 vGPU per GPU Instance. Hardware isolation at SM + framebuffer. **Blackwell only.**

### B.1 Enable MIG

```bash
nvidia-smi -i 0 -mig 1
nvidia-smi -i 0 --query-gpu=mig.mode.current --format=csv,noheader  # → Enabled
```

### B.2 Create GPU Instances

```bash
# 1. List available GI profiles — only "+gfx" profiles work for vGPU
nvidia-smi mig -lgip
# RTX PRO 6000 Blackwell (96GB) 只有 3 个 +gfx profile：
#   MIG 1g.24gb+gfx   (id 47)   最多 4 个
#   MIG 2g.48gb+gfx   (id 35)   最多 2 个
#   MIG 4g.96gb+gfx   (id 32)   最多 1 个

# 2. Create GIs by profile id (comma-separated)
nvidia-smi mig -cgi 47,47,47,47        # 4× 1g.24gb+gfx → 4 个隔离用户
nvidia-smi mig -cgi 35,35              # 2× 2g.48gb+gfx
nvidia-smi mig -cgi 32                 # 1× 4g.96gb+gfx（整卡 1 个 GI）

# 3. Create default CI on all GIs
nvidia-smi mig -cci

# 4. Verify GI/CI table
nvidia-smi
```

### B.3 Create MIG-backed vGPUs

Same as A.2–A.3, but MIG-enabled VFs show only MIG-backed types (time-sliced types have `available=0`):

```bash
cd /sys/class/mdev_bus/0000:02:00.2/mdev_supported_types
for i in * ; do echo "$i : $(cat $i/name) : available=$(cat $i/available_instances)" ; done
echo "$(uuidgen)" > nvidia-2275/create   # e.g. Blackwell-1-12Q

# Second vGPU on different VF:
cd /sys/class/mdev_bus/0000:02:00.3/mdev_supported_types
echo "$(uuidgen)" > nvidia-2273/create   # e.g. Blackwell-1-6Q
```

Then attach to VMs per A.5 and install drivers per A.6.

---

## Phase C: MIG + TimeSlice

Multiple vGPUs share one GI via time-slicing. **Prerequisite:** Phase B done.

### C.1 Mixed-Size Mode on GI

```bash
nvidia-smi -q | grep "Heterogeneous Time-Slice Sizes"   # must be: Supported
nvidia-smi vgpu -i 0 -gi 0 -shm 1
nvidia-smi vgpu -i 0 -gi 0 -ghm                          # verify: Enabled
```

### C.2 Create + Place vGPUs

```bash
# View placement slots
nvidia-smi vgpu -i 0 -gi 0 -c -v
# Placement Size: 2    Placement IDs: 0 2 4 6 8 10 ...

# Create vGPUs on different VFs, set placement on same GI:
echo "$uuidA" > .../nvidia-XXX/create
echo 0 > /sys/bus/mdev/devices/$uuidA/nvidia/gpu_instance_id/placement_id

echo "$uuidB" > .../nvidia-XXX/create  # different VF
echo 2 > /sys/bus/mdev/devices/$uuidB/nvidia/gpu_instance_id/placement_id

# Verify after VM boot:
nvidia-smi vgpu -i 0 -gi 0 -q
```

Attach + drivers per A.5–A.6.

---

## Monitoring

```bash
nvidia-smi                              # all GPUs
nvidia-smi vgpu                         # all vGPUs
nvidia-smi -q                           # detailed GPU
nvidia-smi vgpu -q -gi <id> -i <id>    # per-GI vGPU details
nvidia-smi mig -lgi                     # GPU instances
nvidia-smi mig -lci                     # compute instances
nvidia-smi -q | grep License            # license status
```

---

## References

| File | Content |
|---|---|
| `references/vgpu-types-rtx-pro-6000.md` | RTX PRO 6000 GI profiles + Q/B/A type tables + config examples |
| `references/host-setup.md` | One-time: BIOS, display mode switch, OS prep, vGPU Manager install, teardown |
| `references/troubleshooting.md` | 7 common issues: driver bind, SR-IOV BIOS, IOMMU, MIG conflict, version mismatch, license |
| `references/guest-ci-split.md` | Phase D: Guest VM compute instance sub-partitioning (Ch.5 §5.4) |
| `scripts/vgpu_env_check.sh` | One-shot environment check script |