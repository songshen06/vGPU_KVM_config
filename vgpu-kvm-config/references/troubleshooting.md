# Troubleshooting & Filesystem Reference

## Common Issues

| Symptom | Likely Cause | Check |
|---|---|---|
| GPU not in nvidia-smi | Mixed GPU architectures on same host | Don't mix old GPUs (e.g. T4) with Blackwell. Driver may bind to wrong arch. Remove old GPUs. |
| SR-IOV VFs not appearing | BIOS or kernel config | BIOS: SR-IOV, VT-d enabled. Kernel: `cat /proc/cmdline` — must have `intel_iommu=on`. Run `/usr/lib/nvidia/sriov-manage -e all`. |
| `sriov-manage` fails | IOMMU kernel params missing | `dmesg \| grep -i iommu` for errors. Add `intel_iommu=on iommu=pt` to kernel params. |
| MIG creation fails | GPU still in use | Stop all VMs first. Check `nvidia-smi` for active processes. |
| vGPU `available_instances = 0` | VF already occupied, or MIG mode mismatch | VF can only hold 1 vGPU. When MIG enabled, time-sliced types show 0; when MIG disabled, MIG-backed types show 0. |
| Guest driver won't load | Incompatible guest driver | Guest and host driver versions need not be identical, but must be from a compatible release. Check the vGPU release notes for the supported guest driver for your vGPU Manager version. |
| License not acquired | Token path or service not restarted | Linux: `/etc/nvidia/ClientConfigToken/`. Windows: `C:\Program Files\NVIDIA Corporation\vGPU Licensing\ClientConfigToken\`. Restart `nvidia-gridd` (Linux) or "NVIDIA Display Container LS" (Windows). |
| MIG GI/CI lost after reboot | MIG non-persistent by design | Add `nvidia-smi -mig 1` and `mig -cgi ...` to system startup script or systemd oneshot service. |
| Mixed-size mode lost after reboot | Non-persistent | Re-run `nvidia-smi vgpu -i <id> -gi <id> -shm 1` after each reboot. |

---

## Filesystem Reference

| Path | What |
|---|---|
| `/sys/class/mdev_bus/<bdf>/mdev_supported_types/` | VF's supported vGPU types |
| `/sys/class/mdev_bus/<bdf>/mdev_supported_types/nvidia-*/name` | vGPU type name string |
| `/sys/class/mdev_bus/<bdf>/mdev_supported_types/nvidia-*/available_instances` | 1 = can create, 0 = occupied or unavailable |
| `/sys/class/mdev_bus/<bdf>/mdev_supported_types/nvidia-*/create` | Write UUID to create vGPU mdev |
| `/sys/bus/mdev/devices/<uuid>/` | Created vGPU mdev device directory |
| `/sys/bus/mdev/devices/<uuid>/nvidia/vgpu_params` | Plugin parameters (FRL, VNC, UVM, debug, profiler) |
| `/sys/bus/mdev/devices/<uuid>/nvidia/gpu_instance_id` | GI anchor target (MIG-backed vGPUs) |
| `/sys/bus/mdev/devices/<uuid>/nvidia/gpu_instance_id/placement_id` | Placement slot within GI (time-sliced MIG) |
| `/usr/lib/nvidia/sriov-manage` | SR-IOV virtual function enable/disable script |

---

## Key Commands Cheat Sheet

```bash
# ── MIG ──
nvidia-smi -i 0 -mig 1                              # enable MIG
nvidia-smi -i 0 -mig 0                              # disable MIG
nvidia-smi mig -lgip                                 # list GI profiles
nvidia-smi mig -cgi 38,38                            # create GIs
nvidia-smi mig -cci                                  # create default CIs for all GIs
nvidia-smi mig -cci 0 -gi 0                          # create CI profile 0 on GI 0
nvidia-smi mig -dci -ci 0 -gi 0                     # destroy CI 0 on GI 0
nvidia-smi mig -dci -i 0                             # destroy all CIs on GPU 0
nvidia-smi mig -dgi -i 0                             # destroy all GIs on GPU 0
nvidia-smi mig -lgi                                  # list created GIs
nvidia-smi mig -lci                                  # list created CIs
nvidia-smi mig -lcip -gi 0                           # list CI profiles available on GI 0

# ── vGPU Creation ──
mdevctl list                                         # list all mdev vGPU devices
mdevctl start -p <bdf> -u <uuid> -t nvidia-XXX      # create vGPU via mdevctl
mdevctl stop --uuid <uuid>                           # stop/remove vGPU
mdevctl define --auto --uuid <uuid>                  # persist vGPU across reboots

# ── Mixed-Size / Placement ──
nvidia-smi vgpu -i 0 -shm 1                         # GPU to mixed-size mode
nvidia-smi vgpu -i 0 -gi 0 -shm 1                   # GI to mixed-size mode
nvidia-smi vgpu -i 0 -gi 0 -ghm                     # check GI heterogeneous mode
nvidia-smi vgpu -i 0 -gi 0 -c -v                    # list GI placement IDs
nvidia-smi vgpu -s -v                                # list all supported placement IDs

# ── Monitoring ──
nvidia-smi                                           # GPU summary
nvidia-smi vgpu                                      # vGPU summary
nvidia-smi -q                                        # detailed GPU info
nvidia-smi vgpu -q -i 0                              # detailed vGPU info
nvidia-smi vgpu -q -gi 0 -i 0                        # vGPU details on GI 0
nvidia-smi -q | grep "Heterogeneous Time-Slice Sizes" # check mixed-size support
nvidia-smi -q | grep License                         # license status
nvidia-smi --query-gpu=index,name,pci.bus_id,mig.mode.current --format=csv
nvidia-smi topo -m                                   # NUMA/PCI topology

# ── SR-IOV ──
/usr/lib/nvidia/sriov-manage -e all                  # enable all VFs
/usr/lib/nvidia/sriov-manage -e <bdf>                # enable VFs for specific GPU
ls -l /sys/bus/pci/devices/<bdf>/ | grep virtfn      # list virtual functions

# ── VM ──
virsh attach-device <vm> vgpu.xml --config           # add vGPU to VM config
virsh destroy <vm>                                   # force-stop VM
virsh start <vm>                                     # start VM
```