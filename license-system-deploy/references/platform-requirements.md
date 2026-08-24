# Platform Requirements for NVIDIA License System v3.6.1

## Deployment Models

| Type | Form | Platforms |
|---|---|---|
| CLS | Cloud-hosted | NVIDIA Licensing Portal (no on-prem infra) |
| DLS VM | Virtual appliance | KVM, VMware ESXi, Hyper-V, Citrix, RHV |
| DLS Container | Containerized image | Docker, Kubernetes, OpenShift, Podman, Tanzu |
| DLS RHEL | Installable package | RHEL 8/9 (bare-metal or VM) |

## Minimum Resource Requirements

| Resource | Minimum |
|---|---|
| vCPUs | 4 |
| RAM | 8 GB |
| Disk | 15 GB |

**Sizing guidance:** 15 GB covers base installation. For production, monitor disk usage and expand as needed. Logs and database grow over time.

## Network Requirements

### DLS VM / Container

| Port | Protocol | Purpose |
|---|---|---|
| 80 | HTTP | License return endpoint (Windows clients), redirect to 443 |
| 443 | HTTPS | DLS management UI + license serving API |
| 5671 | TLS (AMQP) | HA cluster inter-node communication |
| 8081 | Internal | HA cluster management |
| 8084 | Internal | HA cluster management |
| 8080-8085 | Internal | Container platform service port range |

### Communication Paths

```
Client ──HTTPS(443)──► DLS ──HTTPS(443)──► NVIDIA Licensing Portal
                                                  (one-time registration +
                                                   periodic license updates)
```

### Key Network Requirements

- **Fixed IP address** (constant over lifetime; DHCP is OK as long as address never changes)
- **DNS entries** recommended (forward + reverse) for FQDN-based access
- **NTP** for accurate time (required for license validity checks)
- Outbound HTTPS from DLS to NVIDIA Licensing Portal for registration + license file download

## Supported Platforms (v3.6.1)

### Hypervisors for VM Appliance

- XenServer Hypervisor 8.4
- KVM: qemu-kvm-9.0.0-10.el9_5
- Microsoft Windows Server Hyper-V 2025 Datacenter
- VMware vSphere ESXi 8.0.3, 8.0, 7.0.3, 7.0.2, 7.0.1, 9.0.1
- MS Azure Stack HCI 23H2

### Container Orchestration Platforms

- Docker 28.0.1 + Docker Compose 2.34.0
- Kubernetes 1.32.0
- Red Hat OpenShift 4.18.8 + Kubernetes 1.31.7
- Podman 5.2.2 + Podman Compose 1.0.6
- VMware Tanzu 1.31.4 + Kubernetes 1.29.7

### Bare-Metal / VM OS Install

- Red Hat Enterprise Linux 8 or 9 (any supported release)

## Container Volume Minimum Sizes

| Volume | Minimum Size |
|---|---|
| `postgres-data` | 10 GiB |
| `rabbitmq-data` | 2 GiB |
| `logs` | 500 MiB |
| `configurations` | 1 GiB |

## Web Browser Requirements

Tested with Google Chrome 96+. Modern Chromium-based browsers should work.

## Container Limitations vs VM Appliance

Containerized DLS **cannot** support:
- Log archive settings
- NTP configuration (use container platform)
- Static IP configuration (use container platform)
- DLS diagnostics user configuration
- Disk expansion (use container platform)

Containerized DLS **additional constraints**:
- No online migration from VM to container (offline migration only)
- Secondary node removal in HA does not auto-shutdown container