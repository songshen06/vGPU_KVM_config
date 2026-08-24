# DLS Appliance Setup Tool (v3.6.1)

New in v3.6.1: standalone Unix binaries that automate DLS setup without requiring Python.

## Overview

Two tools are bundled in `/home/dls_admin/` on the DLS VM appliance:

| Tool | Purpose |
|---|---|
| `dls_registration` | Register DLS with NLP, bind to license server, install license file |
| `dls_configuration` | Set NTP, NFS, TLS certificate, TLS ciphers, lease return port, LDAP |

## Prerequisites

- Unix system with network access to both DLS appliance and NVIDIA Licensing Portal
- License server created on NVIDIA Licensing Portal (choose **On-Premises (DLS)** at Environment step)
- NLP API key of type `DlsInstallAutomation` (generated from portal: My Info → API Keys)
- Tools are in `/home/dls_admin/` on VM; copy to external Unix host if running remotely

## dls_registration

### What It Does

1. Prompts for or generates `dls_admin` password
2. Registers DLS service instance on NLP (or skips if already registered)
3. Prompts for License Server ID
4. Binds service instance to license server
5. Downloads license file from NLP and installs it on DLS

### Basic Usage

```bash
cd /home/dls_admin
tar -xzf dls_registration-<version>.tar.gz
./dls_registration --nlp-url https://<nlp-portal-url> \
                   --org <your-org-name> \
                   --vg-id <virtual-group-id> \
                   --verbose
```

Prompts interactively for: DLS URL, NLP API key, License Server ID, dls_admin password.

### Command-Line Options

```
./dls_registration [--dls-url URL] [--nlp-url URL] [--org ORG] [--vg-id VG_ID] [--verbose]
```

### Environment Variables

| Variable | Equivalent Option |
|---|---|
| `DLS_BASE_URL` | `--dls-url` |
| `NLP_BASE_URL` | `--nlp-url` |
| `NLP_ORG` | `--org` |
| `NLP_VG_ID` | `--vg-id` |

### Example Run

```
$ PYINSTALLER_RUNTIME_TMPDIR=${TMPDIR} ./dls_registration \
    --nlp-url https://nvid.nvidia.com \
    --org my-organization \
    --vg-id vg-12345 \
    --verbose

Enter DLS base URL (e.g. https://dls-ip): https://10.0.0.50
Enter NLP API key (from NVIDIA Licensing Portal): <paste-key>
INFO: DLS health check passed.
Enter dls_admin password (from a previous run), or press Enter to generate:
--- Save this password for future runs ---
dls_admin password: <generated-password>
--- ------------------------------------ ---
INFO: CA registration and login completed.
INFO: DLS service instance xid: <si-xid>
INFO: Uploaded SIIT to NLP.
INFO: SI registration on NLP complete.
Enter License Server ID (created on NLP portal): <license-server-id>
INFO: Bound SI <si-xid> to LS <license-server-id>.
INFO: Downloaded license file from NLP.
INFO: License file installed on DLS.
INFO: DLS Registration Complete — ready to serve licenses.
--- Save this password for future runs ---
dls_admin password: <generated-password>
--- ------------------------------------ ---
```

**Important:** Save the generated password. It is needed for future runs, HA setup, and other operations.

### Re-running

Re-running is safe — already-completed steps (registration, bind) are skipped. Use the saved password from the previous run.

### TMPDIR Note

If `/tmp` or `/var/tmp` is mounted `noexec`, set `TMPDIR` to a writable+executable directory:

```bash
export TMPDIR=/home/dls_admin/tmp
mkdir -p $TMPDIR
```

## dls_configuration

### What It Does

Configures:
- NTP servers
- NFS mount points (filesystem integration)
- TLS server certificate
- TLS cipher suites
- Lease shutdown (return) port
- LDAP integration

### Basic Usage

```bash
tar -xzf dls_configuration-<version>.tar.gz
./dls_configuration --dls-url https://<dls-ip>
```

### Command-Line Options

```
./dls_configuration [--dls-url URL] [--verbose]
```

### Environment Variables

| Variable | Equivalent Option |
|---|---|
| `DLS_BASE_URL` | `--dls-url` |

## Step-by-Step Full Setup with Tools

### 1. Create License Server on Portal

In NVIDIA Licensing Portal:
- CREATE SERVER → Name, Description, Features
- Environment: **On-Premises (DLS)**
- Configuration: **Standard Networked Licensing**
- Note the **License Server ID** (shown on License Server details page)

### 2. Generate NLP API Key

Portal → My Info → API Keys → Create new key → Type: `DlsInstallAutomation`

Save the key — it is shown only once.

### 3. Deploy DLS Appliance

Deploy VM or container per Phase B or C of SKILL.md.

### 4. Run dls_registration

```bash
cd /home/dls_admin
tar -xzf dls_registration-*.tar.gz
./dls_registration --verbose
# Enter: DLS URL, NLP API key, License Server ID
# Save the generated dls_admin password!
```

### 5. Run dls_configuration (Optional)

```bash
tar -xzf dls_configuration-*.tar.gz
./dls_configuration --verbose
# Configure NTP, TLS, LDAP as needed
```

### 6. Generate Client Configuration Token

Portal → License Server Details → ACTIONS → Generate client config token.

### 7. Configure Clients

Copy token to clients → Phase E.

## Troubleshooting

| Issue | Resolution |
|---|---|
| Tool executable permission denied | `chmod +x dls_registration` or `chmod +x dls_configuration` |
| TMPDIR noexec | Set `TMPDIR` to writable+executable directory |
| NLP API key invalid | Ensure key type is `DlsInstallAutomation`, not expired |
| DLS health check fails | Wait for DLS appliance to fully start (~15 min after boot), check `https://<dls-ip>/api/v1/health` |
| License server ID not found | Verify ID from License Server Details page on portal |
| Password mismatch on re-run | Use exact password saved from initial run |