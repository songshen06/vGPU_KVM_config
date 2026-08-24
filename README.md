# vGPU KVM Config · Agent Skills

> NVIDIA vGPU 部署的 AI Agent 技能包。两个独立 skill，覆盖从 GPU 虚拟化到 License 服务的完整链路。

> Agent skill bundle for NVIDIA vGPU deployment on Linux KVM. Two independent skills covering the full pipeline from GPU virtualization to license serving.

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

## 前提条件 Prerequisites

- **GPU**: Ampere+ (SR-IOV) 或 Pascal+ (legacy mdev)；MIG 功能需 Blackwell (RTX PRO 6000/5000/4500)
- **Hypervisor**: Red Hat / Ubuntu KVM，libvirt 已安装
- **Agent 侧**: 能免密 SSH 到 KVM 主机 (`ssh root@<host>`)
- **BIOS**: SR-IOV、VT-d、ARI (AMD)、Above 4G 均已开启
- **vGPU 软件包**: NVIDIA vGPU Manager `.run` 包已下载到主机
- **License 部署**: NVIDIA Licensing Portal 账号 + 有效的 license 授权

---

## 版本 Version

基于 NVIDIA Virtual GPU Software Release 20.0 + NVIDIA License System v3.6.1。针对 Blackwell (RTX PRO 6000) 验证。

Based on NVIDIA Virtual GPU Software Release 20.0 + NVIDIA License System v3.6.1. Validated against Blackwell (RTX PRO 6000).