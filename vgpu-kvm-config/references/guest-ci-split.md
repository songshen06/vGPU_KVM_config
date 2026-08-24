# Guest VM CI Split (Phase D)

From within a Linux guest VM, further partition a MIG GPU Instance into multiple compute instances. This delegates fine-grained SM-level resource management to the VM tenant without hypervisor admin involvement.

Source: NVIDIA vGPU User Guide 20.0, Chapter 5, Section 5.4.

## Prerequisites

- Phase B completed: MIG-enabled GPU, vGPU occupying the **entire** GI (max vGPUs per GI = 1)
- **Linux guest VM only** — Windows guests do not support CI modification
- Console VNC must be disabled on the vGPU beforehand

## Step 1: Hypervisor Side — Disable Console VNC

```bash
# On hypervisor, for the target vGPU:
echo "disable_vnc=1" > /sys/bus/mdev/devices/<uuid>/nvidia/vgpu_params
```

## Step 2: Inside Guest VM

### List current GPU instances

```bash
nvidia-smi mig -lgi
# +----------------------------------------------------+
# | GPU instances:                                     |
# | GPU   Name          Profile   Instance   Placement |
# |       ID            ID        Start:Size           |
# |====================================================|
# | 0     MIG 2g.48gb+gfx  32       0          1:0    |
# +----------------------------------------------------+
```

### Delete the default compute instance

```bash
nvidia-smi mig -dci -ci 0 -gi 0
# Successfully destroyed compute instance ID 0 from GPU 0 GPU instance ID 0
```

Note: if the GI is being used by another process, this fails. Stop all processes using the GI first.

### List available CI profiles

```bash
nvidia-smi mig -lcip
# Shows available profiles, e.g.:
# MIG 1c.2g.48gb (ID 0): 2 instances available, 46 SM each
# MIG 2g.48gb    (ID 1): 1 instance  (marked with * if already created)
```

### Create new compute instances

```bash
# Option A: Split into 2 smaller CIs (each 46 SM)
nvidia-smi mig -cci 0 -gi 0    # creates CI 0
nvidia-smi mig -cci 0 -gi 0    # creates CI 1

# Option B: Keep as 1 full CI (94 SM)
nvidia-smi mig -cci 1 -gi 0    # creates CI 0 with full GI resources
```

### Verify

```bash
nvidia-smi
# MIG devices table now shows the new CI configuration
```

## Use Cases

- **Kubernetes GPU node**: VM receives full GI, K8s schedules pods to individual CIs with SM-level isolation
- **Researcher multi-workload**: One VM, split GI into training CI + inference CI, no cross-interference
- **Self-service**: Tenant adjusts CI layout without filing a ticket for hypervisor admin

## Limitations

- CIs created inside a VM are **destroyed on VM shutdown/reboot**. Only 1 default CI remains after guest driver reload
- Only works for vGPUs that occupy the **entire** GI (not time-sliced MIG-backed vGPUs)
- Not supported from Windows guest VMs
- Requires hypervisor-side VNC disable (console VNC and CI modification are incompatible)