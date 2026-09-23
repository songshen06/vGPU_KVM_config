# Combined vGPU Log Analysis (multi-source cross-correlation)

Method for root-causing vGPU host incidents when `vgpu_report.py` alone is not enough
(no Xid, no ECC, failures live in the VM/hypervisor layer, not the GPU layer).
Distilled from case 6810090 (33× L40, vGPU 535.288.01, 12× L40-4Q; root cause: live
migration of vGPU VMs corrupted mdev state → 134 VM start failures → host reboot).

## When to read this

- `vgpu_report.py` returns a near-empty / INFO report but the host is clearly broken.
- Symptoms include VM start failures, migration failures, or vGPU "cannot open device".
- You need to prove (not just infer) what operation a customer/platform performed.

## Evidence sources inside one nvidia-bug-report.log (and what each proves)

| Source | In the report as | Proves |
|---|---|---|
| libvirt qemu logs (current + rotated .gz) | `/var/log/libvirt/qemu//<vm>.log` sections; rotated ones embedded as raw binary → recover with `extract_embedded_gz.py` | who did what, when (ms wall-clock): starts, shutdowns, vGPU attach, migration |
| kernel log | `journalctl` / raw `[ secs]` dmesg section | GPU/RM layer errors: Xid, `VF FLR failed`, vfio messages |
| sysfs dump | `*** /sys/class/mdev_bus/...` | which mdevs exist / are created / belong to which GPU BDF |
| lspci -k | `/sbin/lspci -nnDvvvxxxx` | real GPU count + `Kernel driver in use` per BDF |
| nvidia-smi --query/-x | `==============NVSMI LOG==============` | RM-visible GPUs, ECC, remapped rows, virtualization mode |

External inputs worth requesting: separate dmesg file (previous boot), CAS/management-plane
audit logs (who initiated an operation), source-host libvirt logs for migrations.

## Recovery step 0: embedded rotated logs

Run `extract_embedded_gz.py` FIRST on any complete bug report. The rotated
`*.log-*.gz` files hold VM lifecycle history that the current `.log` files have
already logrotated away. This is the only way to see operations from previous days.

## Signature dictionary (grep patterns → meaning)

### Live-migration target (host is the DESTINATION)
```
starting up libvirt ... hostname: <this host>   ← libvirt spawning qemu
-S \                                            ← CPU paused at boot = migration-receive mode
-device vfio-pci,...,sysfsdev=/sys/bus/mdev/devices/<uuid>  ← vGPU opened at start
add qdev vfio-pci:hostdev0 success             ← vGPU mdev now OPEN (occupied)
migrate-incoming {"uri": "tcp:[::]:49152"}     ← INCOMING migration command issued
MIGRATION status: setup → active                ← a real source connected and streamed
Not a migration stream / load of migration failed: Invalid argument ← source stream lacks (vGPU) state
shutting down, reason=failed (within ~2s)       ← VM destroyed; vGPU took an abnormal abort-close path
```
Corroborating triad: `MIGRATION status: active` proves a real peer (not a port scan);
multiple retries ~minutes apart prove a deliberate operator/task; a sibling plain-VM
migration reaching `status: completed` in the same window is the control sample that
exonerates node/network and isolates vGPU as the failure variable.

### Dirty / broken mdev (after an abnormal release)
```
vfio <uuid>: error getting device from group NNN: No such device   ← VFIO_GET_DEVICE_FD = ENODEV
Verify all devices in group NNN are bound to vfio-<bus> or pci-stub and not already in use
[nvidia-vgpu-vfio] <uuid>: VF FLR failed during close -25          ← kernel: FLR reset failed (-ENOTTY)
```
Key discrimination: **ENODEV ≠ EBUSY**. "Already in use" would be EBUSY and recovers
when the holder exits. ENODEV + mdev still listed in sysfs + FLR-close-failure = a
PERSISTENT dirty state that survives process exit; mdev-level repair is ineffective,
only host reboot (or full driver re-init) cleans it. A restart storm cycling through
many different mdevs and failing on all of them is the host-level signature.

## Red herrings (do not chase)

1. `Attached GPUs: 1` while lspci shows many GPUs — NORMAL on mdev vGPU hosts: GPUs
   registered to the mdev module are hidden from host NVML. Cross-check
   `/sys/class/mdev_bus/` and `lspci -k` (`Kernel driver in use: nvidia`) before calling it a GPU drop-off.
2. `vfio <uuid>: Could not enable error recovery for the device` — routine mdev+vfio
   warning, printed on every mdev passthrough.
3. `qemu ... terminating on signal 15 from pid N (/usr/sbin/libvirtd)` — libvirt's own
   orderly stop, not a crash.
4. Short-lived `guestfs-*` VMs — libguestfs disk-inspection appliances, ignore.
5. Host-side noise unrelated to GPU: abrt-dbus segfault, `chbk` storage heartbeats.
6. Guest vs host vGPU driver version mismatch — neutral inventory, never a fault.

## Data-quality traps

- A bug report exported through `more`/terminal copy is MANGLED: long lines wrap,
  binaries lost, only the first seconds of sections survive. Treat such a file as
  evidence of "mdev existed in sysfs at time T" at best; demand a re-collect.
- `/dev/kmsg buffer overrun, some messages lost` in dmesg = earlier kernel evidence
  is gone. Compute wall-clock for `[secs]` lines by back-calculating boot time from
  the last dmesg timestamp vs file mtime (mark it as an estimate, ±minutes).
- kernfs/proc mtimes inside the report are collection-order artifacts; never use them
  as "when the driver registered".

## Workflow (the order matters)

1. `vgpu_report.py` + `extract_embedded_gz.py` on the complete bug report.
2. Build the VM↔mdev mapping: grep `sysfsdev=/sys/bus/mdev/devices/([0-9a-f-]+)` per VM log.
3. Build the VM lifecycle timeline: `starting up`, `shutting down, reason=`, `migrate-incoming`.
4. Identify customer/platform operations: look for the migration-target triad and
   retry cadence; find the control sample (success in same window).
5. Align kernel-time (dmesg `[secs]`) with wall-clock (libvirt ms) via boot-time back-calculation.
6. Only then assign root cause; state which hypothesis each log line kills or confirms.
