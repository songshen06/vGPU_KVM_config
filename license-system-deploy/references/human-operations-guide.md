# 🧑 Human Operations Guide — NVIDIA License System Portal & Web UI

This document is the **human-side cheatsheet** for every portal and web UI click required during NVIDIA License System deployment. Follow each section exactly. After completing a section, provide the recorded values to the agent so it can proceed.

---

## Section 1: Create a License Server on the Portal

**URL:** https://nvid.nvidia.com

**Time:** ~5 minutes. **Critical:** do NOT skip the Express installation option if using CLS.

### 1.1 Log In

1. Open browser, go to **https://nvid.nvidia.com**
2. Click **NVIDIA Enterprise Application Hub** → sign in with your NVIDIA enterprise account
3. On the Enterprise Application Hub dashboard, click the tile labeled **NVIDIA LICENSING PORTAL**
4. The NVIDIA Licensing Portal dashboard opens

> **If you belong to multiple virtual groups:** Click the avatar/gear icon at top right → **View settings** → **My Info** window opens → select the correct **Virtual Group** from the drop-down → close the window. All subsequent steps operate within this virtual group.

### 1.2 Start the Create License Server Wizard

5. In the **left navigation pane**, find **LICENSE SERVER** (it's a collapsible section)
6. Click to **expand** it if collapsed
7. Click **CREATE SERVER**

> If no license servers exist yet for your org/virtual group, the dashboard will also show a banner: *"You don't have any license servers yet. Create one now?"* — clicking that banner also works.

The **Create License Server** wizard opens, showing Step 1.

### 1.3 Step 1 — Identification

8. **Name field** — enter a name for this license server. Use something descriptive and permanent. Examples:
   - `vGPU-Production`
   - `DLS-Primary`
   - `Engineering-VWS-Licenses`
   > This name appears in the portal list and on the DLS web UI. Choose carefully — it cannot be changed after certain operations.

9. **Description field** — enter a short description. This field is **required**. Examples:
   - `Primary production license server for vGPU workloads`
   - `DLS instance serving NVIDIA RTX Virtual Workstation licenses`

10. Click **NEXT STEP** (button at bottom-right)

### 1.4 Step 2 — Features

11. You see a list of licensed products from your entitlements. Each row shows:
    - Product name (e.g., "NVIDIA RTX Virtual Workstation", "GRID Virtual PC")
    - **AVAILABLE** column — total licenses you own
    - **ADDED** column — a text-entry field (initially 0)

12. For each product you want to serve from this license server:
    - Find the product row
    - Click the text-entry field in the **ADDED** column
    - Type the **number of licenses** to allot to this server
    > You can split licenses across multiple servers. Example: if you own 100 NVIDIA RTX vWS licenses, you could allot 50 to this server and 50 to another later.

13. After setting quantities for all desired products, click **NEXT STEP**

### 1.5 Step 3 — Environment

**This is the critical fork in the road.** Choose carefully:

14. Select ONE of these radio buttons:

| Option | What it means | Use when |
|---|---|---|
| **Cloud (CLS)** | License server hosted by NVIDIA cloud. Zero on-prem infrastructure. | No on-prem server wanted; clients have outbound internet |
| **On-Premises (DLS)** | License server runs on YOUR hardware (VM or container). | You control the infra; air-gapped or restricted networks |
| **Deferred** | Choose later. Server created but environment not set. | Still deciding; can be changed later |

> **For CLS (Cloud):** After selecting "Cloud (CLS)", an **Express installation** checkbox appears below. **Leave it checked** unless you specifically need a custom CLS instance. Express installation auto-creates the CLS instance, binds the server, and installs licenses — no further work needed.
>
> **For DLS (On-Premises):** No Express option. You will deploy the server yourself (the agent handles this).

15. Click **NEXT STEP**

### 1.6 Step 4 — Configuration

16. **Leasing mode** drop-down — select one:

| Mode | Use when |
|---|---|
| **Standard Networked Licensing** | **(Recommended)** Default. No additional config required. |
| **Advanced Networked Licensing** | Need to partition licenses into pools with specific fulfillment rules per user group |
| **Node-Locked Licensing** | Clients have NO network connection to license server; license file installed locally on each client |

> ⚠️ **WARNING:** If you select **Node-Locked Licensing**, this choice is **PERMANENT** — the license server's mode cannot be changed later. Only choose this if you are absolutely sure clients cannot reach a license server over the network.

17. Click **REVIEW SUMMARY**

### 1.7 Review and Create

18. The **Server Summary** page shows all your selections. Verify:
    - Name and Description are correct
    - Features/quantities are correct
    - Environment (Cloud or On-Premises) is correct
    - Leasing mode is correct

19. Click **CREATE SERVER** (button at bottom or in Step 4 menu)

20. The server is created. You are taken to the **License Server Details** page.

### 1.8 Record These Values for the Agent

From the License Server Details page, copy/screenshot and save:

| Value | Where to find it | Example |
|---|---|---|
| **License Server ID** | URL bar: `.../license-server/<id>` or displayed on the page header | `ls-abc123def456` |
| **Server Name** | Top of the page | `vGPU-Production` |
| **Status** | Overview tab, status badge | Should be "Not Installed" initially |

Share these with the agent immediately.

**If you chose CLS + Express installation:** The status should show "Installed" and the server is ready. Skip to [Section 4](#section-4-generate-client-configuration-token).

**If you chose DLS:** Status shows "Not Installed." Proceed to [Section 2](#section-2-generate-nlp-api-key-for-dls-automation).

---

## Section 2: Generate NLP API Key for DLS Automation

**Where:** NVIDIA Licensing Portal → My Info

**Time:** ~2 minutes. **Critical:** save the key immediately; it is displayed only once.

### 2.1 Open My Info

1. On the NVIDIA Licensing Portal, click your **avatar/initials** at the top-right corner
2. Click **View settings** (or the gear icon)
3. The **My Info** window opens

### 2.2 Navigate to API Keys

4. In the My Info window, find and click the **API Keys** tab (or section)
5. Click the button: **Create New Key** (or **Generate API Key**)

### 2.3 Select Key Type

6. A **key type** drop-down or selection menu appears. Choose:

   > **DlsInstallAutomation**

   This is the ONLY key type that works with the `dls_registration` tool. Other key types (like `User`) will NOT work.

7. Optionally enter a **key name/label** (e.g., "dls-setup-key")

8. Click **Create** or **Generate**

### 2.4 Save the Key

9. The key is displayed once in a pop-up or text field. It looks like a long alphanumeric string, possibly with dots or dashes. Example format: `eyJh...very-long-string...XjPs`

10. **COPY the entire key immediately.** Paste it into:
    - A secure note/ password manager
    - A text file you will share with the agent
    - Your clipboard for immediate use

> ⚠️ If you close the pop-up without copying, the key is **lost forever**. You must create a new one.

11. Record for the agent:
    - The **full API key string**
    - The **key type**: `DlsInstallAutomation`

**Also verify you have these values from Section 1 ready:**
- License Server ID
- Organization name (visible in My Info or URL)
- Virtual Group ID (visible in My Info under Virtual Group drop-down)

---

## Section 3: Register dls_admin on the DLS Appliance

**When:** After the agent deploys the DLS VM and gives you the IP address.

**URL:** `https://<dls-ip>` (replace `<dls-ip>` with the actual IP)

**Time:** ~3 minutes. **Critical:** the password you set is used by the agent for `dls_registration` and HA setup. Do not lose it.

### 3.1 Open the DLS Web UI

1. The agent will tell you: *"DLS appliance is ready at https://10.0.0.50"* (example IP)
2. Open a browser and navigate to `https://<dls-ip>`
3. Your browser will show a **certificate warning** (self-signed certificate). Click **Advanced** → **Proceed to <ip> (unsafe)** or **Accept the Risk and Continue**. This is normal for first boot.

### 3.2 First-Time Registration Page

4. If this is a fresh deployment, you see a **registration page** (NOT a login page). It prompts you to register the `dls_admin` user. The page typically has fields:

| Field | What to enter | Notes |
|---|---|---|
| **Email Address** | Your email or admin email | Used for password recovery |
| **Full Name / Display Name** | Your name or admin name | Displayed in the UI |
| **Password** | A strong password | ⚠️ Save this — agent needs it |
| **Confirm Password** | Same password again | Must match |

5. Fill in all fields, click **Register** or **Create Account**

6. After registration, you are redirected to the **login page**. Log in with:
    - Username: `dls_admin`
    - Password: the one you just set

7. You should now see the DLS **dashboard** or **License Server Details** page.

### 3.3 Record and Share

| Value | For the agent |
|---|---|
| **DLS IP address** | Already known, but confirm it's correct |
| **dls_admin password** | The agent needs this to SSH and run `dls_registration` |

> ⚠️ The initial console login (before web registration) uses `dls_admin` / `welcome`. After web registration, the console password is also updated to what you set.

---

## Section 4: Generate Client Configuration Token

**When:** After the license server is installed on the service instance (status shows "Enabled" or "Installed").

**Where:**
- **DLS:** `https://<dls-ip>` → log in as `dls_admin`
- **CLS:** NVIDIA Licensing Portal → navigate to the License Server

**Time:** ~2 minutes per token.

### 4.1 Navigate to License Server Details

1. Log in to the appropriate interface (DLS web UI or Portal)
2. You should land on the License Server Details page. If not:
   - **DLS:** The dashboard should show your license server directly
   - **Portal:** Left nav → **LICENSE SERVER** → **LIST SERVERS** → click your server name

3. Verify the server status badge shows **"Enabled"** or **"Installed"**. If it shows "Not Installed", the agent hasn't completed the previous step — do not proceed.

### 4.2 Generate the Token

4. Find the **ACTIONS** button/menu (typically top-right of the page)
5. Click **ACTIONS** → from the drop-down menu, select **Generate client configuration token**

6. A wizard or pop-up opens. It may show:
   - A list of **fulfillment conditions** (for most setups, there is just one: the default Universal Match)
   - A checkbox or selection list

7. **Select the fulfillment condition(s)** to include in this token:
   - For **Standard Networked Licensing** (default): select the default condition (usually "Universal Match" or auto-selected)
   - For **Advanced Networked Licensing**: you may need to select one specific condition per token
   - **Most deployments:** just accept the default/auto-selected condition

8. Click **Generate** or **Download**

9. A `.tok` file is downloaded to your browser's default download location. The filename is typically something like `client_configuration_token_<timestamp>.tok` or based on the server name.

### 4.3 Provide to Agent

10. Note the file path (e.g., `~/Downloads/client_configuration_token_xxx.tok`)
11. Share this file with the agent:
    - If agent is on same machine: note the full path
    - If agent is remote: transfer via scp, shared drive, or copy-paste the content

> **Token lifetime:** 12 years from generation date. Store a backup copy.

### 4.4 One Token vs Multiple Tokens

| Scenario | How many tokens |
|---|---|
| All clients get same license type, single license pool | **One token** — distribute to all clients |
| Different client groups need different license pools | **One token per group** — each token encodes different fulfillment conditions |
| Multiple license servers | **One token per server** (or one token referencing multiple servers) |

For the simple case (one server, Standard Networked Licensing, one pool): generate **one token** and copy it to every client.

---

## Section 5: Configure HA Cluster (Optional)

**When:** Two DLS instances are deployed and both have license servers installed.

**Where:** `https://<primary-ip>` — the primary DLS web UI

**Time:** ~5 minutes.

### 5.1 Prerequisites Checklist

Before starting, confirm with the agent:
- [ ] Two DLS instances deployed (primary + secondary)
- [ ] Both have different IP addresses, on separate physical hosts
- [ ] Both have same DLS version
- [ ] Both have the dls_admin password saved and accessible
- [ ] Ports 5671, 8081, 8084 are open between the two hosts
- [ ] Agent confirms both `/api/v1/health` endpoints return healthy

### 5.2 Open HA Settings

1. Log in to the **primary** DLS web UI (`https://<primary-ip>`)
2. Navigate to **Settings** (typically in left navigation or top menu)
3. Find the **High Availability** section or tab

### 5.3 Add Secondary Instance

4. In the High Availability section, click **Add secondary instance** (or similar button, e.g., "Configure HA" / "Add Node")

5. A form appears with fields:

| Field | What to enter |
|---|---|
| **Secondary Instance IP / Hostname** | The IP address of the second DLS instance (e.g., `10.0.0.51`) |
| **Admin Username** | `dls_admin` (pre-filled or type it) |
| **Admin Password** | The dls_admin password set on the **secondary** instance |

6. Click **Add** or **Configure**

7. The system will:
   - Connect to the secondary instance
   - Set up database replication
   - Configure RabbitMQ communication (port 5671)
   - Synchronize license data

8. Wait for the process to complete (progress indicator may show). This can take 1–3 minutes.

### 5.4 Verify

9. Navigate to **Service Instance** page (left nav or dashboard link)
10. You should see **two nodes** listed:
    - Node 1: Role = **Primary**, Status = **Healthy/Online**
    - Node 2: Role = **Secondary**, Status = **Healthy/Online**

11. If the secondary shows "Unhealthy" or "Unknown", wait 2–3 minutes and refresh. If still unhealthy, have the agent check port connectivity and logs.

### 5.5 Enable Virtual IP (Optional)

12. In **Settings** → **High Availability**, find the **Virtual IP Management** section
13. Click **Enable** or **Configure**
14. Enter:

| Field | What to enter |
|---|---|
| **Virtual IP Address** | A spare IP in the same subnet as the DLS instances |
| **Subnet Mask / Prefix** | CIDR prefix (e.g., `24` for 255.255.255.0) |

15. Click **Save**. The virtual IP now floats between nodes. Licensed clients should use this IP instead of individual node IPs.

### 5.6 Record for Agent

| Value |
|---|
| Virtual IP address (if configured) |
| Confirmation that both nodes show Healthy |

---

## Section 6: Add More Cluster Nodes (Beyond 2)

If you need 3 or more nodes:

1. The agent must first run `/etc/adminscripts/enable_ha_max.sh` on each existing node (sets max cluster size permanently)
2. Then repeat [Section 5](#section-5-configure-ha-cluster-optional) steps 5.3 for each additional node, adding it to the primary

---

## Section 7: Generate Node-Locked Licenses (Alternative to Token)

**Only if** you selected **Node-Locked Licensing** in Section 1.6.

### 7.1 Per-Client License File

1. On License Server Details page → **ACTIONS** → **Generate node-locked license**
2. Enter the client's **MAC address** (or other identifier)
3. Download the `.nll` file
4. Provide it to the agent → agent places it at:
   - Linux: `/etc/nvidia/ClientConfigToken/`
   - Windows: `C:\Program Files\NVIDIA Corporation\vGPU Licensing\ClientConfigToken\`

> ⚠️ Node-locked: each client needs its own `.nll` file. Licenses must be manually returned on the portal before the client is decommissioned.

---

## Quick Reference Card

### What the Agent Needs From You, by Phase

| Phase | Values to provide | Format |
|---|---|---|
| **After Section 1** | License Server ID, Server Name, Org name, VG ID | Text strings |
| **After Section 2** | NLP API key (full string) | Long alphanumeric token |
| **After Section 3** | dls_admin password | Plain text |
| **After Section 4** | Path to downloaded `.tok` file | File path |
| **Throughout** | DLS IP address(es) | IP like `10.0.0.50` |

### Portal URLs

| What | URL |
|---|---|
| NVIDIA Enterprise Application Hub | `https://nvid.nvidia.com` |
| DLS Web UI (on-prem) | `https://<dls-ip>` (agent provides IP) |

### Common Mistakes

| Mistake | Fix |
|---|---|
| Forgot to copy API key | Generate a new one — old one is unrecoverable |
| Chose wrong virtual group | Click View settings → switch VG → re-check server list |
| Selected Node-Locked by accident | **Cannot undo.** Create a new license server with correct mode |
| Forgot CLS Express checkbox | Server created but not installed. Either delete and recreate, or manually create CLS instance + bind + install |
| Lost dls_admin password | On VM: log in as `rsu_admin` via hypervisor console to reset. On container: redeploy |
| Token file lost | Generate a new one (old token continues to work; new one is additive) |
| Secondary node shows Unhealthy in HA | Wait 2–3 min; check agent has verified port connectivity between nodes |