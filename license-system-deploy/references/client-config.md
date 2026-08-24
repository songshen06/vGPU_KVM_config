# Licensed Client Configuration

## Client Configuration Token

A client configuration token identifies:
- Service instance (CLS or DLS)
- License server(s)
- Fulfillment conditions

**Token lifetime:** 12 years from generation.

One token per combination of license servers + fulfillment conditions. Most deployments need just one default token.

### Generate Token

**CLS:** NVIDIA Licensing Portal → License Server Details → ACTIONS → Generate client config token

**DLS:** `https://<dls-ip>` → License Server Details → ACTIONS → Generate client config token

Select fulfillment conditions (accept defaults for straightforward deployments: one pool, universal match).

### Token File

Downloaded as a `.tok` file (a text configuration token).

## Client Setup

### Linux

```bash
# Create directory if not exists
sudo mkdir -p /etc/nvidia/ClientConfigToken

# Copy token file
sudo cp <token-file> /etc/nvidia/ClientConfigToken/

# Restart NVIDIA Grid driver service
sudo systemctl restart nvidia-gridd

# Verify license status
nvidia-smi -q | grep -A5 "License Status"
# Expected output: "Licensed"
```

**Note:** For node-locked licensing, a separate `.nll` license file is generated instead of a token. The file is placed at the same location.

### Windows

```powershell
# Destination directory:
# C:\Program Files\NVIDIA Corporation\vGPU Licensing\ClientConfigToken\

# Copy token file to that directory

# Restart service (PowerShell as Administrator):
Restart-Service "NVIDIA Display Container LS"
# Or via services.msc GUI

# Verify:
nvidia-smi -q | findstr /C:"License Status"
```

### Verification Commands

```bash
# License status (all clients)
nvidia-smi -q | grep License

# Detailed license info
nvidia-smi -q | grep -A10 "License"

# Check expiry date
nvidia-smi -q | grep "Expiry"

# On grid service (Linux):
systemctl status nvidia-gridd
grep -i license /var/log/messages
```

## License Pools and Fulfillment Conditions

For advanced license management (reserving licenses for specific user groups):

### Default Setup

When a license server is first installed:
- **1 default license pool** containing all allotted licenses
- **1 default fulfillment condition**: Universal Match (serves any client from default pool)

This is sufficient for most deployments. Generate a token without creating additional pools/conditions.

### Advanced Setup

1. **Create license pools** to partition licenses (e.g., "CAD-tools" pool with NVIDIA RTX Virtual Workstation, "Office" pool with GRID Virtual PC)
2. **Create fulfillment conditions** with Reference Match to route specific clients to specific pools
3. Order conditions by priority
4. Generate tokens per condition combination

### Leasing Modes

| Mode | Description |
|---|---|
| **Standard Networked** | Default. No additional config needed. Simplified management. |
| **Advanced Networked** | Requires manual pool + fulfillment condition setup. More control. |
| **Node-Locked** | License file installed locally on client. Cannot be changed later. No token — use `.nll` file instead. |

## Supported Licensed Client Products

NVIDIA License System v3.6.1 supports:
- NVIDIA vGPU software graphics drivers starting with release 13.0
- Node-locked licensing: vGPU 15.0+

## Client Communication Flow

```
Client (nvidia-gridd) ──HTTPS──► DLS/CLS: License request
                              ◄── DLS/CLS: License grant/deny
Client periodic heartbeat to maintain lease
Client returns license on graceful shutdown
```

## Token Renewal

Tokens expire after 12 years. Before expiry:
1. Generate a new token on the license server
2. Distribute new token to all clients
3. Restart nvidia-gridd / NVIDIA Display Container LS on each client

The old and new tokens can coexist briefly during rollout.