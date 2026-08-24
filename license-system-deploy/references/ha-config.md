# High Availability Cluster Configuration

## Architecture

An HA cluster consists of:
- **1 primary instance**: actively serving licenses
- **1+ secondary instances**: standby, ready to take over on primary failure

Cluster nodes communicate via TLS-encrypted AMQP (port 5671) + management ports 8081/8084.

## Design Constraints

### VM-Based Instances

- Deploy each instance on a **separate physical host** (different KVM/ESXi hosts)
- All instances must have the same DLS version
- All instances must have network connectivity between each other

### Containerized Instances

- Deploy each instance on a **separate Kubernetes cluster** (NOT different worker nodes in same cluster)
- Same port mappings must be exposed on all instances
- Same volume sizes on all instances
- Same environment variables (`DLS_EXPOSED_HTTP_PORT`, `DLS_EXPOSED_HTTPS_PORT`, `DLS_RABBITMQ_SSL_PORT=5671`)

## Setup Procedure

### Step 1: Deploy Two Independent DLS Instances

Deploy each via Phase B (VM) or Phase C (Container). Both must:
- Have the same DLS version
- Be on separate hosts/K8s clusters
- Have network connectivity

### Step 2: Configure Primary

1. Deploy first instance → register dls_admin → complete setup (registration, bind, license install)
2. Verify it serves licenses correctly

### Step 3: Deploy Secondary

1. Deploy second instance → register dls_admin
2. Register with NLP (or use dls_registration tool; bind step will be skipped)
3. **Do NOT install license server on secondary** — it inherits from primary

### Step 4: Add Secondary to Cluster

On primary DLS web UI (`https://<primary-ip>`):
1. Navigate to **Settings** → **High Availability**
2. Click **Add secondary instance**
3. Enter secondary instance IP address
4. Enter secondary dls_admin password
5. System configures replication and AMQP communication

### Step 5: Verify Cluster

Check **Service Instance** page: both nodes listed with health status.

## Cluster Size > 2

Default max cluster size is 2. To expand:

### VM-Based
```bash
# On each instance, as dls_admin:
/etc/adminscripts/enable_ha_max.sh
# Enter desired max cluster size
```

### Containerized
```yaml
# Set environment variable on each instance:
DLS_HA_MAX_CLUSTER_SIZE=3
```

Note: Max cluster size is **permanent** — cannot be changed after setting.

## Failover Behavior

### Heartbeat Mechanism

- Secondary node(s) continuously monitor primary via heartbeat
- If primary becomes unresponsive, secondary initiates failover

### Recovery Actions

1. Primary failure detected (heartbeat timeout)
2. Secondary assumes primary role → starts serving licenses
3. Former primary restarts → becomes secondary (role reversal)
4. Cluster re-syncs databases

### Client Impact During Failover

- **Without Virtual IP:** Clients must be configured with both DLS addresses, or require manual reconfiguration
- **With Virtual IP:** Clients use a single floating IP that migrates to the active node transparently

### Restarting a Failed DLS Appliance

```bash
# VM: restart from hypervisor
virsh reboot <dls-vm-name>

# Docker:
docker-compose restart

# Podman:
podman-compose --file docker-compose.yml down
podman-compose --file docker-compose.yml up -d
```

## Virtual IP Management

Available after HA is configured. A single IP address that always points to the active primary node.

Enable via DLS web UI → Settings → High Availability → Virtual IP Management.

Requires:
- A spare IP address in the same subnet as DLS instances
- Network infrastructure that allows IP failover (VRRP or similar)

## Monitoring HA Status

```bash
# API health check on each node:
curl -k https://<node-ip>/api/v1/health

# Web UI:
https://<node-ip> → Service Instance page
# Shows: node role (primary/secondary), health, sync status

# Logs on each node:
sudo /etc/adminscripts/collect_dls_logs.sh
```

## HA Troubleshooting

| Issue | Resolution |
|---|---|
| HA configuration fails | Ensure ports 5671, 8081, 8084 open between nodes; same DLS version on both; same exposed ports mapped |
| Containerized HA fails | Both on separate K8s clusters (not same cluster); same `DLS_EXPOSED_*` env vars; same volume sizes |
| Node health missing from UI | Check storage volumes not full; force reload page |
| Secondary not syncing | Check RabbitMQ connectivity (port 5671); check DB replication status in logs |
| Failover not triggering | Verify heartbeat interval settings; check network between nodes |

## Removing a Secondary Instance

1. DLS web UI → Settings → High Availability → Actions on secondary → Remove
2. **VM:** Instance is auto-shutdown
3. **Container:** Must manually stop the container (`docker-compose down` / `kubectl delete pod`)