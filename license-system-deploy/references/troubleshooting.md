# Troubleshooting NVIDIA License System

## DLS Appliance Not Starting (VM)

| Symptom | Check | Fix |
|---|---|---|
| VM boots but DLS UI not reachable | Wait 15 minutes for first boot initialization | Patience; DLS containers start inside the VM |
| `https://<ip>` connection refused | Is VM IP correct? | `virsh domifaddr <vm-name>` or console login `ip addr` |
| 502/503 from DLS | DLS containers still initializing | Wait, check `docker ps` inside VM as `dls_admin` |
| VM console shows errors | Disk space, memory | Verify 15 GB disk, 8 GB RAM allocated |

## DLS Appliance Not Starting (Container)

| Symptom | Check | Fix |
|---|---|---|
| Container exits immediately | Docker logs | `docker logs <container-id>` |
| K8s pod CrashLoopBackOff | Pod describe + logs | Check volume permissions, env vars |
| Podman compose fails with "missing networks" | Network config | Remove stale networks: `podman network prune` |
| Data validation errors on K8s | Volume mode | Ensure volumes use `Filesystem` mode, not `Block` |

## Portal Registration Issues

| Symptom | Check | Fix |
|---|---|---|
| Cannot register DLS on portal | DLS can reach internet? | Verify outbound HTTPS from DLS to `nvid.nvidia.com` |
| Registration fails with "unreachable" | Is NLP URL correct? | Use `https://nvid.nvidia.com` for production |
| dls_registration tool fails | TMPDIR noexec? | `export TMPDIR=/home/dls_admin/tmp` |
| API key invalid | Key type + expiry | Must be `DlsInstallAutomation` type |
| License server install fails | Server bound correctly? | Check binding on portal License Server Details page |

## Client License Issues

| Symptom | Check | Fix |
|---|---|---|
| Client shows "Unlicensed" | Token installed correctly? | Verify token file at `/etc/nvidia/ClientConfigToken/` (Linux) or `C:\Program Files\NVIDIA Corporation\vGPU Licensing\ClientConfigToken\` (Windows) |
| Client cannot reach license server | Network/firewall | Client must reach DLS on port 443; check firewall rules |
| License status "Expired" | Token expiry or lease | Generate new token; check license entitlements on portal |
| Windows client cannot return license | Port 80 blocked | Container: set `DLS_EXPOSED_HTTP_PORT=80` |
| Client uses domain name, cannot get license | FQDN env var | Set `FQDN` env var on containerized DLS; verify DNS resolution from client |

## HA Cluster Issues

| Symptom | Check | Fix |
|---|---|---|
| HA config fails | Same version? Network between nodes? | Both instances same DLS version; ports 5671,8081,8084 open |
| Container HA fails | Same K8s cluster? | Must use SEPARATE clusters (not same cluster different workers) |
| Port mapping mismatch | Env vars | Ensure `DLS_EXPOSED_HTTP_PORT`, `DLS_EXPOSED_HTTPS_PORT`, `DLS_RABBITMQ_SSL_PORT=5671` identical on both |
| Volume size mismatch | Storage | Match `rabbitmq-data` (2 GiB), `postgres-data` (10 GiB), `logs` (500 MiB), `configurations` (1 GiB) |
| Node health missing | Storage full? | Resize volumes, restart container |

## Log Gathering

```bash
# On DLS VM, as dls_admin:
sudo /etc/adminscripts/collect_dls_logs.sh

# This script collects:
#   - CPU info (/proc/cpuinfo)
#   - RAM info (/proc/meminfo)
#   - DLS startup log (/var/log/applicationStartup.log)
#   - Appliance ops log (/var/log/applianceOps.log)
#   - IP address log (/var/log/ip_address.log)
#   - Disk usage
#   - Docker logs for both containers
#   - Chrony/timesyncd NTP status
#   - Syslog
#   - Service logs

# Health endpoint:
curl -k https://<dls-ip>/api/v1/health
```

## Common Post-Deployment Steps

```bash
# Verify DLS health:
curl -k https://<dls-ip>/api/v1/health

# Check license server status (DLS web UI):
# https://<dls-ip> → License Server Details → Overview tab
# Expected: "Enabled", with licenses listed

# Test from a client:
nvidia-smi -q | grep -A5 "License Status"
```

## Disk Space

If DLS runs out of disk space:

```bash
# VM: Expand disk from hypervisor, then:
/etc/adminscripts/expand_disk.sh

# Clean up old data:
sudo /etc/dls/scripts/db_data_purge.sh

# Container: Resize volumes in container platform, restart
```