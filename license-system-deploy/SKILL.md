---
name: license-system-deploy
description: Deploy NVIDIA License System (DLS/CLS) v3.6.1. Covers DLS virtual appliance on KVM, containerized DLS (Docker/K8s/Podman), DLS Appliance Setup Tool automation, HA cluster, and licensed client configuration. Use when the user needs to set up an NVIDIA license server to serve licenses to vGPU clients.
---

# NVIDIA License System Deployment

## Who Does What

This skill mixes portal (GUI) and CLI steps. Here is the split:

| Who | Tasks |
|-----|-------|
| **Human** | Portal + Web UI operations. Follow `references/human-operations-guide.md` step-by-step — every click is documented with exact button names and field labels. |
| **Agent** | CLI operations: deploy VM/containers, run `dls_registration` tool, set static IP, copy tokens to clients, verify licenses, collect logs |

**Remote execution:** Agent runs commands on the KVM host via SSH. For multi-step sequences, use heredoc:

```bash
SSH_HOST="root@<kvm-host-ip>"
ssh $SSH_HOST << 'ENDSSH'
# commands here
ENDSSH
```

---

## 🧑 Human Prerequisites (Do These First)

Before the agent can deploy anything, the human must complete these steps on the NVIDIA Licensing Portal:

### P1. Create a License Server

Go to https://nvid.nvidia.com → **NVIDIA Licensing Portal** → **LICENSE SERVER** → **CREATE SERVER**:

1. **Step 1 — Identification:** Name (e.g. "vGPU-Production") + Description
2. **Step 2 — Features:** Select license products + quantities from entitlements
3. **Step 3 — Environment:** Choose **On-Premises (DLS)** (or **Cloud (CLS)** for fully cloud)
4. **Step 4 — Configuration:** Choose **Standard Networked Licensing** (default)
5. Click **CREATE SERVER**

Note the **License Server ID** from the resulting License Server Details page (visible in URL or page header).

### P2. Generate an NLP API Key

Portal → click your avatar (top-right) → **My Info** → **API Keys** → **Create New Key** → Type: **DlsInstallAutomation**

Save the key immediately — it is shown only once. This key lets the `dls_registration` tool automate registration.

### P3. Provide Deployment Context to Agent

Tell the agent:
- **KVM host IP** (where DLS VM will run)
- **DLS appliance image path** (QCOW2 file location)
- **NLP organization name** and **virtual group ID** (from portal)
- The **License Server ID** and **NLP API key** from P1/P2 above
- **Network info:** interface name, desired static IP (if not DHCP)

---

## Quick Decision

| Mode | When to use | Section |
|---|---|---|
| **CLS** (Cloud) | No on-prem infra wanted | [Phase A](#phase-a-cls-cloud-only) |
| **DLS VM** on KVM | Existing KVM host, full control | [Phase B](#phase-b-dls-vm-on-kvm-agent) |
| **DLS Container** (Docker) | Container infra, lighter footprint | [Phase C](#phase-c-dls-container-agent) |
| **HA Cluster** | Production resilience | [Phase D](#phase-d-ha-cluster) |
| **Client Config** | After server is serving licenses | [Phase E](#phase-e-client-config-agent) |

---

## Phase A: CLS (Cloud-Only)

> Almost entirely **human** work in the portal. Agent has nothing to deploy.

Express installation: After creating the license server with **Cloud (CLS)** + **Express installation** at Step 3, the portal automatically creates a CLS instance, binds the server, and installs licenses. The instance is ready immediately.

Human then generates a client token (see [Phase E](#phase-e-client-config-agent)) and hands it to the agent for distribution to clients.

---

## Phase B: DLS VM on KVM [AGENT]

### B.1 Run Environment Check

```bash
# On KVM host:
bash scripts/check_dls_prereqs.sh
```

Fix any FAIL items before proceeding.

### B.2 Deploy the VM

```bash
# Copy QCOW2 image to libvirt directory
cp <dls-appliance>.qcow2 /var/lib/libvirt/images/

# Create the VM
virt-install \
  --name <dls-vm-name> \
  --vcpus=4 \
  --memory 8192 \
  --disk /var/lib/libvirt/images/<dls-appliance>.qcow2,bus=virtio \
  --network type=direct,source=<interface> \
  --network=default \
  --os-variant ubuntu22.04 \
  --import \
  --noautoconsole \
  --boot uefi \
  --graphics vga
```

Minimum: 4 vCPUs, 8 GB RAM, 15 GB disk.

### B.3 Wait for Initialization + Get IP

The DLS appliance takes ~15 minutes on first boot to initialize its internal Docker containers.

```bash
# Wait, then get IP:
virsh domifaddr <dls-vm-name>

# Or log in via console (user: dls_admin, password: welcome) and check:
ssh -o StrictHostKeyChecking=no dls_admin@<dls-ip> 'ip addr show'
```

### B.4 (Optional) Set Static IP

If DHCP isn't suitable, set a static IP from the hypervisor console:

```bash
# As rsu_admin on DLS VM:
sudo nmcli conn edit "Wired connection 1" ipv4.method manual
sudo nmcli conn edit "Wired connection 1" +ipv4.addresses <ip>/<prefix>
sudo nmcli conn edit "Wired connection 1" +ipv4.gateway <gateway>
sudo nmcli conn edit "Wired connection 1" +ipv4.dns <dns-server>
sudo nmcli networking off && sudo nmcli networking on
```

### B.5 Human: Register dls_admin in Browser

Agent pauses here. Tell the human to:

> Open `https://<dls-ip>` in a browser. The DLS will prompt to register the `dls_admin` user. Enter an email address, name, and set a new password. Share this password with the agent for subsequent steps.

### B.6 Run DLS Registration Tool [AGENT]

Once the human provides the dls_admin password, API key, and License Server ID:

```bash
ssh dls_admin@<dls-ip> << 'ENDSSH'
cd /home/dls_admin

# Extract and run registration tool
tar -xzf dls_registration-*.tar.gz
./dls_registration \
    --nlp-url https://nvid.nvidia.com \
    --org "<org-name>" \
    --vg-id "<vg-id>" \
    --verbose
# Prompts: DLS URL (auto-detected), NLP API key, License Server ID
# Prompts for dls_admin password (enter the one human set in B.5)

# Optional: configure NTP, TLS, LDAP
tar -xzf dls_configuration-*.tar.gz
./dls_configuration --verbose
ENDSSH
```

**Save the generated/set password** — needed later for HA setup and administration.

The DLS is now registered, bound, and has licenses installed. Ready to serve.

### B.7 Human: Generate Client Configuration Token

Agent pauses again. Tell the human to:

> Open `https://<dls-ip>`, log in as dls_admin, go to **License Server Details** → **ACTIONS** → **Generate client configuration token**. Accept the default fulfillment condition. Download the `.tok` file and provide it to the agent.

Proceed to [Phase E](#phase-e-client-config-agent) for client distribution.

---

## Phase C: DLS Container [AGENT]

### C.1 Docker

```bash
ssh root@<docker-host> << 'ENDSSH'
# Load images
docker load --input dls_appliance_3.6.1.tar.gz
docker load --input dls_pgsql_3.6.1.tar.gz

# Set env vars (in .env or docker-compose.yml):
export DLS_PUBLIC_IP=<host-ip>
export FQDN=<dls-fqdn>
export DLS_EXPOSED_HTTP_PORT=80
export DLS_EXPOSED_HTTPS_PORT=443

# Start
cd /path/to/dls-deployment
docker-compose up -d
ENDSSH
```

### C.2 Kubernetes

```bash
# Adjust deployment YAML env vars first, then:
kubectl apply -f nls-si-0-deployment.yaml
kubectl apply -f nls-si-0-service.yaml
```

Ensure ports 80, 443, 5671, 8080–8085 are open on worker nodes. Minimum volumes: `postgres-data` (10 GiB), `rabbitmq-data` (2 GiB), `logs` (500 MiB), `configurations` (1 GiB).

### C.3 Podman

```bash
podman-compose --file docker-compose.yml up -d
```

### C.4 Post-Deployment

Same as B.5–B.7: human registers dls_admin → agent runs `dls_registration` from a Unix host with network access to both DLS and NLP → human generates token → agent distributes.

---

## Phase D: HA Cluster

### D.1 Agent: Deploy Two Instances

Repeat Phase B or C on two separate physical hosts (or separate K8s clusters for containerized). Both must have same DLS version and network connectivity.

### D.2 Agent: Enable Cluster Size > 2 (Optional)

Default max is 2 nodes. To allow more:

```bash
# VM-based:
ssh dls_admin@<node-ip> '/etc/adminscripts/enable_ha_max.sh'
# Enter desired max cluster size

# Containerized: set env var DLS_HA_MAX_CLUSTER_SIZE=3 on each node
```

This change is **permanent** — cannot be reverted.

### D.3 Human: Configure Cluster in Web UI

Agent pauses. Tell the human to:

> On the primary DLS web UI (`https://<primary-ip>`), go to **Settings** → **High Availability**. Click **Add secondary instance**. Enter the secondary instance IP and its dls_admin password. Verify both nodes appear healthy on the **Service Instance** page.

### D.4 Human: Enable Virtual IP (Optional)

> In **Settings** → **High Availability** → **Virtual IP Management**, configure a floating IP for transparent failover. Requires a spare IP in the same subnet.

### D.5 Agent: Verify Cluster Health

```bash
curl -sk https://<primary-ip>/api/v1/health
curl -sk https://<secondary-ip>/api/v1/health

# Both should return healthy status
```

---

## Phase E: Client Config [AGENT]

The human generates a `.tok` file from the license server web UI and provides it. Then:

### E.1 Linux Clients

```bash
ssh root@<client-ip> << 'ENDSSH'
mkdir -p /etc/nvidia/ClientConfigToken
# Human provides the token file path — agent copies it:
cp <token-file> /etc/nvidia/ClientConfigToken/
systemctl restart nvidia-gridd
nvidia-smi -q | grep -A5 "License Status"
ENDSSH
```

### E.2 Windows Clients

```powershell
# Copy .tok to:
# C:\Program Files\NVIDIA Corporation\vGPU Licensing\ClientConfigToken\
# Restart: Restart-Service "NVIDIA Display Container LS"
# Verify: nvidia-smi -q | findstr License
```

### E.3 Multi-Client Bulk Distribution

```bash
TOKEN_FILE="/path/to/client_config_token.tok"

for CLIENT_IP in <ip1> <ip2> <ip3>; do
    scp "$TOKEN_FILE" root@$CLIENT_IP:/etc/nvidia/ClientConfigToken/
    ssh root@$CLIENT_IP 'systemctl restart nvidia-gridd'
done
```

---

## Monitoring [AGENT]

```bash
# DLS health endpoint:
curl -sk https://<dls-ip>/api/v1/health

# Collect DLS logs for troubleshooting:
ssh dls_admin@<dls-ip> 'sudo /etc/adminscripts/collect_dls_logs.sh'

# Check license status on any client:
ssh root@<client-ip> 'nvidia-smi -q | grep License'
```

---

## End-to-End Walkthrough (DLS VM on KVM)

```
HUMAN: Create license server on portal + get API key + License Server ID
   ↓
AGENT: check_dls_prereqs.sh → virt-install DLS VM → get IP
   ↓
HUMAN: Open https://<dls-ip> → register dls_admin → give password to agent
   ↓
AGENT: SSH dls_admin@<dls-ip> → run dls_registration (registration+bind+license install)
   ↓
HUMAN: Web UI → Generate client configuration token → give .tok file to agent
   ↓
AGENT: scp token → all vGPU clients → restart nvidia-gridd → verify license status
```

---

## References

| File | Content |
|---|---|
| **`references/human-operations-guide.md`** | **🧑 Step-by-step portal/Web UI guide. Every click, field label, and button name documented for the human operator.** |
| `references/platform-requirements.md` | Host requirements, ports, sizing, supported platforms |
| `references/dls-setup-tool.md` | DLS Appliance Setup Tool detailed usage and troubleshooting |
| `references/client-config.md` | Token generation details, fulfillment conditions, license pools |
| `references/ha-config.md` | HA cluster setup, failover, heartbeat, virtual IP |
| `references/troubleshooting.md` | Common issues and resolutions |
| `scripts/check_dls_prereqs.sh` | Pre-deployment environment check |