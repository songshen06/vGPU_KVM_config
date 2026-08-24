# vGPU KVM Config · Agent Skills

> NVIDIA vGPU 部署的 AI Agent 技能包。两个独立 skill，覆盖从 GPU 虚拟化到 License 服务的完整链路。

> Agent skill bundle for NVIDIA vGPU deployment on Linux KVM. Two independent skills covering the full pipeline from GPU virtualization to license serving.

---

## 🗺️ 总流程 End-to-End Flow

从零开始到 GPU 虚拟机拿到 License 授权的完整路径。标注每一步由哪个 skill 负责、谁来执行。

```
🧑 前置准备
  │
  ├─ 提供 SSH 凭据 (KVM 主机 IP + root 密码/SSH key)         🧑 Human
  ├─ 下载 vGPU Manager .run 包 + DLS QCOW2 镜像               🧑 Human
  ├─ 登录 nvid.nvidia.com → 建 License Server → 记下 ID       🧑 Human
  └─ Portal → My Info → 生成 DlsInstallAutomation API Key      🧑 Human
         │
         ▼
┌─────────────────────── vgpu-kvm-config ─────────────────────┐
│                                                              │
│  Phase 0: 主机准备                                           │
│    ├─ BIOS 验证 (SR-IOV, VT-d, Above 4G)         🤖 Agent   │
│    ├─ 安装 vGPU Manager .run                      🤖 Agent   │
│    └─ 启用 SR-IOV VFs                             🤖 Agent   │
│                                                              │
│  Phase A/B/C/D: 创建 vGPU                                   │
│    ├─ Quick Decision → 选模式 (时分/MIG/混合)     🤖 Agent   │
│    ├─ mdevctl / nvidia-smi 创建 vGPU              🤖 Agent   │
│    ├─ virt-install 创建 VM + virsh 挂载 vGPU      🤖 Agent   │
│    └─ VM 内安装 NVIDIA GRID 驱动                  🤖 Agent   │
│                                                              │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼  VM 已有 GPU，但没有 License
                               │
┌──────────────────── license-system-deploy ───────────────────┐
│                                                              │
│  Phase B/C: 部署 DLS License 服务器                          │
│    ├─ check_dls_prereqs.sh 环境预检               🤖 Agent   │
│    ├─ virt-install 创建 DLS VM (4 vCPU, 8GB)      🤖 Agent   │
│    └─ 获取 IP，等待 15min 初始化                   🤖 Agent   │
│                                                              │
│  🧑 Human 介入 (参照 human-operations-guide.md)              │
│    ├─ 打开 https://<dls-ip> → 注册 dls_admin       🧑 Human  │
│    └─ 把 dls_admin 密码交给 Agent                            │
│                                                              │
│  Phase B.6: dls_registration 自动化                          │
│    ├─ SSH dls_admin@<dls-ip>                       🤖 Agent   │
│    └─ 运行 dls_registration (注册+绑定+安装License) 🤖 Agent  │
│                                                              │
│  🧑 Human 介入                                               │
│    └─ DLS Web UI → Generate Client Token → .tok     🧑 Human  │
│                                                              │
│  Phase E: 客户端授权                                         │
│    ├─ scp .tok → 所有 VM (ClientConfigToken 目录)   🤖 Agent  │
│    ├─ systemctl restart nvidia-gridd               🤖 Agent   │
│    └─ nvidia-smi -q | grep License → Licensed ✅   🤖 Agent   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                               │
                               ▼
                      ✅ 所有 vGPU VM 已授权
```

**关键路径：** 🧑 人做 6 次操作（每次 ≤5 分钟，有分步手册） → 🤖 Agent 执行所有 CLI。总耗时约 30-60 分钟（含 DLS 初始化 15 分钟等待）。

---

## Skills

| Skill | 用途 Purpose | 文件 File |
|---|---|---|
| **vgpu-kvm-config** | vGPU 创建与管理：BIOS → 驱动 → SR-IOV → MIG → vGPU → VM 挂载 | `vgpu-kvm-config.skill` |
| **license-system-deploy** | NVIDIA License System 部署：DLS/CLS → 注册 → 绑定 → License 安装 → 客户端配置 | `license-system-deploy.skill` |

两者互补：`vgpu-kvm-config` 把 GPU 切成 vGPU 分给 VM，`license-system-deploy` 部署 License 服务器让 VM 里的 GPU 驱动能拿到授权。

These two skills complement each other: `vgpu-kvm-config` partitions GPUs into vGPUs and assigns them to VMs; `license-system-deploy` sets up the license server so the GPU drivers inside VMs can obtain licenses.

---

## vgpu-kvm-config

### 能做什么？ Capabilities

| 场景 Scenario | 你只需说 You just say | Agent 会走 Phase |
|---|---|---|
| 全新部署 vGPU | "帮我在 192.168.1.10 上配好 vGPU，要 8 个轻量 VDI" | 0 → A |
| 硬件隔离场景 | "给这台 RTX PRO 6000 配 MIG vGPU，4 个用户互不干扰" | 0 → B |
| 部门级分层 | "工程部 4 人共享半个 GPU，数据部 2 人独占另半个" | 0 → B → C |
| 租户自助切分 | "给研究员一台 VM，让他在 VM 里自己拆 MIG" | 0 → B → D |
| 环境体检 | "检查一下 KVM 主机 vGPU 环境是否就绪" | 运行 env_check 脚本 |
| 查 vGPU 类型 | "RTX PRO 6000 最多能开几个 DC-3Q？" | 查类型表 |
| 排障 | "vGPU 创建失败、授权不对、MIG 丢失..." | 查 troubleshooting |
| 全拆清理 | "把 GPU 恢复成普通单卡模式，删掉所有 vGPU" | E |

### 触发关键词 Trigger keywords

> vGPU KVM 配置 / vGPU setup / MIG vGPU / 配 vGPU / RTX PRO 6000 vGPU / Blackwell vGPU / nvidia-smi vgpu / SR-IOV vGPU / time-sliced vGPU / MIG-backed vGPU / guest CI split / configure vGPU on KVM / vGPU environment check

### 文件结构 File structure

```
vgpu-kvm-config.skill
├── SKILL.md                   ← 主流程：Phase 0/Quick Decision → A B C D E
├── scripts/
│   └── vgpu_env_check.sh      ← 一键环境体检脚本
└── references/
    ├── host-setup.md          ← Phase 0 (BIOS/OS/驱动) + Phase E (Teardown)
    ├── vgpu-types-rtx-pro-6000.md  ← RTX PRO 6000 Q/B/A 类型全表
    ├── troubleshooting.md     ← 7 类常见故障 + 文件系统路径速查
    └── guest-ci-split.md      ← Phase D: VM 内二次切分 CI
```

---

## license-system-deploy

### 能做什么？ Capabilities

| 场景 Scenario | 你只需说 You just say | Agent 会走 Phase |
|---|---|---|
| 部署 DLS VM | "帮我在 KVM 主机上部署 DLS license 服务器" | 环境预检 → B |
| 部署 DLS 容器 | "用 Docker 部署 DLS license 服务器" | C |
| DLS 自动化注册 | "用 dls_registration 工具注册 DLS、绑定、安装 license" | B.6 |
| 客户端批量授权 | "把 token 分发到所有 GPU VM，重启 grid 服务" | E |
| License 排障 | "VM 里 nvidia-smi 显示 Unlicensed" | troubleshooting |
| HA 集群扩容 | "把 DLS 集群从 2 节点扩到 3 节点" | D.2 |
| License 服务体检 | "检查 DLS 健康状态" | Monitoring |

### Human + Agent 协作模式

这个 skill 明确区分了 portal/Web UI（人操作）和 CLI（Agent 操作）：

```
Human(Portal 建 License Server + 拿 API Key)
   ↓
Agent(SSH → virt-install 部署 DLS VM → 运行 dls_registration)
   ↓
Human(打开 https://<dls-ip> 注册 admin → 生成 client token)
   ↓
Agent(scp token → 所有 VM → 重启 nvidia-gridd → 验证)
```

Human 操作指南（每个按钮、字段、下拉选项精确标注）在 `references/human-operations-guide.md`。

### 触发关键词 Trigger keywords

> DLS 部署 / license server / NVIDIA License System / license-system-deploy / 部署 license 服务器 / CLS 配置 / DLS 虚拟设备 / dls_registration / license client token / 授权服务器 / vGPU license / nvidia-gridd license

### 文件结构 File structure

```
license-system-deploy.skill
├── SKILL.md                        ← 主流程：Human Prerequisites → Phase A B C D E
├── scripts/
│   └── check_dls_prereqs.sh        ← DLS 环境预检脚本
└── references/
    ├── human-operations-guide.md   ← 🧑 Portal/Web UI 详细操作手册
    ├── platform-requirements.md    ← 硬件要求、端口、支持平台
    ├── dls-setup-tool.md           ← dls_registration/dls_configuration 工具用法
    ├── client-config.md            ← Token 生成 + Linux/Windows 客户端配置
    ├── ha-config.md                ← HA 集群、故障转移、虚拟 IP
    └── troubleshooting.md          ← 常见问题排障
```

---

## 怎么触发？ How to trigger

把 `.skill` 文件放到 Agent 的 skills 目录，对话中提及对应关键词即可触发。

Place the `.skill` file in your agent's skills directory, then mention any trigger keyword in conversation.

---

## Phase 路线图 Phase roadmap (vgpu-kvm-config)

```
Phase 0 ─── 一次性主机准备 (BIOS → display mode → OS → driver → SR-IOV)
   │
   ├── Phase A ─── 纯时间分片 (MIG OFF, 最高密度, 无隔离)
   ├── Phase B ─── MIG 硬件隔离 (Blackwell only, 1 vGPU = 1 GI, QoS 保证)
   ├── Phase C ─── MIG + TimeSlice (GI 间隔离, GI 内分片, 部门共享)
   ├── Phase D ─── Guest CI Split (Phase B 得到的 GI 在 VM 内再拆 CI)
   └── Phase E ─── 全拆清理
```

---

## ⚠️ 前置条件 Prerequisites — 使用前必读

### 🔴 硬性前提 Must Have

> 这些缺一不可。没有的话 Agent 无法工作。

| # | 条件 | 适用 Skill | 说明 |
|---|---|---|---|
| 1 | **SSH 免密登录** | 两个都需要 | Agent 通过 `ssh root@<kvm-host>` 执行所有命令。你的 Agent 运行环境必须能免密 SSH 到目标 KVM 主机 |
| 2 | **NVIDIA 企业账号** | 两个都需要 | 用于下载 vGPU 软件包 + 登录 NVIDIA Licensing Portal。通过 `nvid.nvidia.com` 访问 |
| 3 | **有效的 License Entitlements** | license-system-deploy | Portal 里必须有已购买的 vGPU license 授权（如 NVIDIA RTX vWS、GRID Virtual PC 等） |
| 4 | **NVIDIA GPU 硬件** | vgpu-kvm-config | Ampere+ (SR-IOV) 或 Pascal+ (legacy mdev)；MIG 功能需 Blackwell (RTX PRO 6000/5000/4500) |
| 5 | **KVM Hypervisor** | vgpu-kvm-config | Red Hat 或 Ubuntu，libvirt 已安装、libvirtd 已运行 |
| 6 | **BIOS 虚拟化支持** | vgpu-kvm-config | SR-IOV、VT-d/AMD-Vi、ARI (AMD)、Above 4G Decoding 均已开启 |
| 7 | **vGPU Manager 软件包** | vgpu-kvm-config | `NVIDIA-Linux-x86_64-<ver>-vgpu-kvm.run` 已从 NVIDIA 下载到 KVM 主机 |
| 8 | **DLS 镜像文件** | license-system-deploy | QCOW2 虚拟机镜像（KVM 部署）或 tar.gz 容器镜像（Docker/K8s 部署） |
| 9 | **网络连通性** | license-system-deploy | DLS 能 HTTPS 出站到 `nvid.nvidia.com`；客户端能 HTTPS 访问 DLS 的 443 端口 |

### 🟡 你需要会做的 What You Need to Know

> Agent 会给你精确到按钮名称的操作指南（`references/human-operations-guide.md`）。

| 操作 | 耗时 | 说明 |
|---|---|---|
| **提供 SSH 凭据** | 1 分钟 | 告诉 Agent："KVM 主机 IP 是 10.0.0.5，root 密码是 xxx" 或配置好 SSH key |
| **Portal 上建 License Server** | 5 分钟 | 打开 `nvid.nvidia.com` → 跟着手册 Section 1 一步步点击 |
| **Portal 上拿 API Key** | 2 分钟 | 跟着手册 Section 2，点击 5 下，复制一串 key 给 Agent |
| **注册 DLS Admin** | 3 分钟 | Agent 部署完 DLS VM 后，打开 `https://<dls-ip>` 填邮箱+密码 |
| **生成 Client Token** | 2 分钟 | DLS Web UI 上点击 Generate → 下载 `.tok` 文件给 Agent |
| **回答选择题** | 1 分钟 | "要几个 VM？密度优先还是隔离优先？哪种 license？" |

### 🟢 你不需要会的 What You DON'T Need

> Agent 全权负责以下所有命令行操作，你无需了解：

- ❌ KVM/virsh/virt-install 命令
- ❌ nvidia-smi / mdevctl / SR-IOV / MIG 配置
- ❌ Docker / Kubernetes / Podman 部署
- ❌ dls_registration / dls_configuration 自动化工具
- ❌ License 排障 / 日志收集 / 健康检查
- ❌ Linux 网络配置 (nmcli)、systemctl、scp

---

## 版本 Version

基于 NVIDIA Virtual GPU Software Release 20.0 + NVIDIA License System v3.6.1。针对 Blackwell (RTX PRO 6000) 验证。

Based on NVIDIA Virtual GPU Software Release 20.0 + NVIDIA License System v3.6.1. Validated against Blackwell (RTX PRO 6000).