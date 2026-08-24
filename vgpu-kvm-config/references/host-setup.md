# Host Setup & Teardown

One-time preparation and cleanup procedures. Not needed for day-to-day vGPU operations.

## Phase 0: Host Preparation

### P0.1 BIOS Settings

Enable in workstation/server BIOS:

- **SR-IOV** — required for Blackwell vGPU
- **VT-X / AMD-V** — virtualization support
- **VT-D / IOMMU** — `intel_iommu=on` or `amd_iommu=on`
- **ARI** (Alternative Routing ID Interpretation) — required for AMD CPU platforms
- **Above 4G Decoding** — if available

### P0.2 GPU Display Mode: Switch to Compute

Blackwell GPUs ship in **graphics** mode by default. vGPU requires **compute** mode (physical display disabled).

```bash
# Download displaymodeselector from NVIDIA Developer site
# 1. Go to https://developer.nvidia.com/displaymodeselector (v1.75.0+)
# 2. Download the Linux .run package
# 3. Transfer to host and make executable: chmod +x displaymodeselector*.run
# 4. Extract: ./displaymodeselector*.run --target ./dms/
#    (or: sh ./displaymodeselector*.run --tar xvf --keep-newer-files)
# 5. The binary is now at ./dms/displaymodeselector

# Unload any GPU drivers first
systemctl stop nvidia-vgpu-mgr
rmmod nvidia_vgpu_vfio nvidia

# Check current mode
./displaymodeselector --listgpumodes
# Shows: graphics (default)

# Switch to compute mode
./displaymodeselector --gpumode compute

# Reboot required
reboot

# Verify after reboot
./displaymodeselector --listgpumodes
# Should show: Compute (Physical display disabled)
```

Note: If multiple GPUs installed, omit `--auto` and select manually. See displaymodeselector user guide.

### P0.3 OS Preparation (RHEL 9.x example)

```bash
# Disable SELinux
setenforce 0
sed -i 's/=enforcing/=disabled/' /etc/selinux/config

# Disable firewall
systemctl disable firewalld
systemctl stop firewalld

# Disable graphical target
systemctl set-default multi-user
systemctl isolate multi-user.target

# Blacklist nouveau driver
echo "blacklist nouveau" > /etc/modprobe.d/nouv-blacklist.conf
echo "options nouveau modeset=0" >> /etc/modprobe.d/nouv-blacklist.conf

# Kernel boot parameters: IOMMU + disable nouveau
grubby --update-kernel=ALL --args="intel_iommu=on iommu=pt modprobe.blacklist=nouveau nouveau.modeset=0"

# If needed: PCI compatibility
grubby --update-kernel=ALL --args="pci=realloc pci=assign-busses pci=nocrs"

# Rebuild initramfs and grub config
grub2-mkconfig -o /boot/grub2/grub.cfg
dracut /boot/initramfs-$(uname -r).img $(uname -r) --force

# Install KVM virtualization components
dnf install -y '@Dev*' '@Sys*'
dnf install -y sysstat virt-manager virt-install xauth tuned

# Tune for virtualization
tuned-adm profile virtual-host
systemctl enable tuned

reboot
```

### P0.4 Install vGPU Manager

```bash
# Copy vGPU package to host, extract zip
# From Host_Drivers directory:
chmod +x NVIDIA-Linux-x86_64-595.91.04-vgpu-kvm.run
./NVIDIA-Linux-x86_64-595.91.04-vgpu-kvm.run -as   # -as = silent install

# Or for RHEL RPM:
rpm -iv NVIDIA-vGPU-rhel-9.6-595.91.04.x86_64.rpm

reboot
```

### P0.5 Verify Installation & Enable SR-IOV

```bash
# Check kernel modules
lsmod | grep vfio
# Must show: nvidia_vgpu_vfio, nvidia, vfio_mdev, mdev, vfio_iommu_type1, vfio

# Check GPU visible
nvidia-smi

# Enable SR-IOV for all GPUs (add to startup script)
/usr/lib/nvidia/sriov-manage -e all

# Verify VFs exist
ls /sys/class/mdev_bus/
# Should list VF device IDs, e.g. 0000:02:00.2 ... up to 32 VFs for PRO 5000
```

---

## GPU Mixed-Size Mode (Optional, for time-sliced single-GPU)

```bash
nvidia-smi vgpu -i 0 -shm 1
nvidia-smi -q | grep "vGPU Heterogeneous Mode"
```

---

## Phase E: Teardown

### Disable MIG (return to single-instance GPU)

```bash
# Shut down all VMs using the GPU
virsh destroy <vm-name>     # per VM

# Stop and remove all vGPU mdev devices
mdevctl stop --uuid <vgpu-uuid>   # per vGPU

# Destroy all CIs, then GIs
nvidia-smi mig -dci -i 0          # destroy all CIs on GPU 0
nvidia-smi mig -dgi -i 0          # destroy all GIs on GPU 0

# Disable MIG
nvidia-smi -i 0 -mig 0
```

### Delete a Single vGPU

```bash
# Shut down VM using it first
virsh destroy <vm-name>

# Method A: mdevctl (preferred)
mdevctl stop --uuid <uuid>

# Method B: sysfs (if mdevctl unavailable)
cd /sys/class/mdev_bus/<gpu-bdf>/mdev_supported_types
cd $(find . -type d -name <uuid>)
echo "1" > remove
```

### Delete Multiple vGPUs

```bash
# Stop all vGPUs on a GPU
mdevctl list | grep <gpu-bdf> | awk '{print $1}' | xargs -I{} mdevctl stop --uuid {}

# Or destroy all VMs on the GPU, then clean up
virsh destroy <vm1> <vm2> ...
nvidia-smi mig -dci -i 0     # if MIG enabled
nvidia-smi mig -dgi -i 0
```

### Persist vGPUs (optional, for time-sliced non-MIG)

```bash
mdevctl define --auto --uuid <uuid>
```

Or add `sriov-manage -e all` and vGPU creation to a systemd oneshot service for reboot persistence.

### Persist vGPUs (optional, for time-sliced non-MIG)

```bash
echo "frame_rate_limiter=0, disable_vnc=1" > /sys/bus/mdev/devices/<uuid>/nvidia/vgpu_params
```
Common: `frame_rate_limiter=0`, `disable_vnc=1`, `enable_uvm=1`, `enable_debugging=1`, `enable_profiling=1`.