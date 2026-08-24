#!/bin/bash
# check_dls_prereqs.sh — Pre-deployment environment check for NVIDIA License System DLS
# Run on the target host (KVM hypervisor or container platform host)

set -e

echo "=== NVIDIA DLS Prerequisites Check ==="
echo

# --- OS detection ---
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "[OK] OS: $NAME $VERSION"
else
    echo "[WARN] Cannot detect OS version"
fi

# --- CPU cores ---
CPU_CORES=$(nproc 2>/dev/null || grep -c ^processor /proc/cpuinfo 2>/dev/null || echo 0)
if [ "$CPU_CORES" -ge 4 ]; then
    echo "[OK] CPU cores: $CPU_CORES (≥4 required)"
else
    echo "[FAIL] CPU cores: $CPU_CORES — need ≥4"
fi

# --- RAM ---
TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}')
TOTAL_MEM_GB=$(( TOTAL_MEM_KB / 1024 / 1024 ))
if [ "$TOTAL_MEM_GB" -ge 8 ]; then
    echo "[OK] RAM: ${TOTAL_MEM_GB} GB (≥8 required)"
else
    echo "[FAIL] RAM: ${TOTAL_MEM_GB} GB — need ≥8"
fi

# --- Disk space in likely paths ---
for DIR in /var/lib/libvirt/images /var/lib/docker / /home; do
    if [ -d "$DIR" ]; then
        AVAIL_GB=$(df -BG "$DIR" 2>/dev/null | tail -1 | awk '{print $4}' | sed 's/G//')
        if [ "${AVAIL_GB:-0}" -ge 15 ]; then
            echo "[OK] Disk available on $DIR: ${AVAIL_GB} GB (≥15 needed)"
        else
            echo "[WARN] Disk available on $DIR: ${AVAIL_GB} GB — need ≥15 for DLS"
        fi
    fi
done

# --- Network: check if host has fixed IP ---
DEFAULT_IFACE=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $5; exit}')
if [ -n "$DEFAULT_IFACE" ]; then
    echo "[INFO] Primary interface: $DEFAULT_IFACE"
    IP_ADDR=$(ip -4 addr show "$DEFAULT_IFACE" 2>/dev/null | grep -oP 'inet \K[\d.]+')
    if [ -n "$IP_ADDR" ]; then
        echo "[OK] IP address: $IP_ADDR (ensure this is fixed/unchanging)"
    else
        echo "[WARN] Could not determine IP on $DEFAULT_IFACE"
    fi
else
    echo "[WARN] Could not determine default network interface"
fi

# --- Outbound HTTPS check to NVIDIA Licensing Portal ---
echo "[INFO] Testing outbound HTTPS to NVIDIA Licensing Portal..."
if curl -sk --connect-timeout 5 https://nvid.nvidia.com >/dev/null 2>&1; then
    echo "[OK] HTTPS outbound to nvid.nvidia.com reachable"
else
    echo "[FAIL] Cannot reach nvid.nvidia.com — check firewall/proxy"
fi

# --- KVM-specific checks ---
if command -v virsh &>/dev/null; then
    echo "[OK] libvirt/virsh: available"
    LIBVIRTD_RUNNING=$(systemctl is-active libvirtd 2>/dev/null || echo "inactive")
    if [ "$LIBVIRTD_RUNNING" = "active" ]; then
        echo "[OK] libvirtd: running"
    else
        echo "[FAIL] libvirtd: $LIBVIRTD_RUNNING"
    fi

    QEMU_VER=$(qemu-system-x86_64 --version 2>/dev/null | head -1 || echo "not found")
    echo "[INFO] QEMU: $QEMU_VER"
else
    echo "[INFO] KVM/virsh not detected (skip if using container deployment)"
fi

# --- Docker checks ---
if command -v docker &>/dev/null; then
    DOCKER_VER=$(docker --version 2>/dev/null)
    echo "[OK] Docker: $DOCKER_VER"
    DOCKER_RUNNING=$(docker info >/dev/null 2>&1 && echo "running" || echo "not running")
    if [ "$DOCKER_RUNNING" = "running" ]; then
        echo "[OK] Docker daemon: running"
    else
        echo "[FAIL] Docker daemon: $DOCKER_RUNNING"
    fi
    if command -v docker-compose &>/dev/null; then
        echo "[OK] docker-compose: available"
    fi
else
    echo "[INFO] Docker not detected (skip if using VM deployment)"
fi

# --- Podman checks ---
if command -v podman &>/dev/null; then
    PODMAN_VER=$(podman --version 2>/dev/null)
    echo "[OK] Podman: $PODMAN_VER"
    if command -v podman-compose &>/dev/null; then
        echo "[OK] podman-compose: available"
    fi
fi

# --- Port availability ---
echo "[INFO] Checking required ports (80, 443, 5671)..."
for PORT in 80 443 5671; do
    if ss -tln | grep -q ":$PORT "; then
        echo "[WARN] Port $PORT: in use (may conflict with DLS)"
    else
        echo "[OK] Port $PORT: free"
    fi
done

# --- NTP ---
if command -v timedatectl &>/dev/null; then
    NTP_STATUS=$(timedatectl show -p NTP 2>/dev/null | cut -d= -f2)
    if [ "$NTP_STATUS" = "yes" ]; then
        echo "[OK] NTP: enabled"
    else
        echo "[WARN] NTP: not enabled (recommended for license validity)"
    fi
elif command -v chronyc &>/dev/null; then
    echo "[INFO] chronyd detected"
else
    echo "[WARN] No NTP service detected — license checks require accurate time"
fi

# --- DNS resolution ---
HOSTNAME_FQDN=$(hostname -f 2>/dev/null || echo "unknown")
echo "[INFO] Hostname (FQDN): $HOSTNAME_FQDN"
if host "$HOSTNAME_FQDN" >/dev/null 2>&1; then
    echo "[OK] DNS forward resolution works for $HOSTNAME_FQDN"
else
    echo "[WARN] DNS forward resolution failed — recommend setting DNS before DLS deploy"
fi

echo
echo "=== Summary ==="
echo "If all checks pass (OK), the host is ready for DLS deployment."
echo "Address any FAIL items before proceeding."
echo "WARN items are advised but not blocking for initial deployment."