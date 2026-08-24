# vGPU KVM Config Skill · 使用指南

> 一份给 AI Agent 用的 NVIDIA vGPU KVM 配置手册。把 BIOS → 驱动 → SR-IOV → MIG → vGPU 完整链路压缩为可分步执行的指令集。Agent 按 Phase 顺序走，用户只需提供 KVM 主机地址和目标场景。

> A consumable instruction set for AI agents to configure NVIDIA vGPU on Linux KVM. Compresses the full BIOS → Driver → SR-IOV → MIG → vGPU pipeline into phased, executable steps. The agent walks through phases; you just give it your KVM host address and goal.

---

## 这是什么？ What is this?

`vgpu-kvm-config` 是一个 **Agent Skill** — 它不是给人逐行阅读的手册，而是给 Claude/OpenCode 等 AI Agent 吃的结构化知识包。Agent 加载后能：

- 远程 SSH 到你的 KVM 主机执行配置命令
- 根据你的需求（密度优先 / 隔离优先 / 混合）自动选择正确的配置路径
- 查阅 GPU 型号对应的 vGPU 类型表，告诉你最多能开几个虚拟机

`vgpu-kvm-config` is an **Agent Skill** — not a manual for humans to read line by line, but a structured knowledge package consumed by AI agents (Claude, OpenCode, etc.). Once loaded, the agent can:

- SSH into your KVM host and run configuration commands remotely
- Pick the correct configuration path based on your goal (density / isolation / hybrid)
- Look up vGPU type tables for your GPU model and tell you max VM count

---

## 能做什么？ Capabilities

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

---

## 怎么触发？ How to trigger

把这个 `.skill` 文件放到 Agent 的 skills 目录，然后对话中提及以下任意关键词即可触发：

Place the `.skill` file in your agent's skills directory, then mention any of these keywords in conversation:

> vGPU KVM 配置 / vGPU setup / MIG vGPU / 配 vGPU / RTX PRO 6000 vGPU / Blackwell vGPU / nvidia-smi vgpu / SR-IOV vGPU / time-sliced vGPU / MIG-backed vGPU / guest CI split / configure vGPU on KVM / vGPU environment check

你也可以直接说：

Or just say:

> "用 vgpu-kvm-config skill 帮我在 10.0.0.5 上配 4 个 MIG 隔离 vGPU"
> "Use the vgpu-kvm-config skill to set up 4 MIG-isolated vGPUs on 10.0.0.5"

---

## 文件结构 File structure

```
vgpu-kvm-config.skill          ← 打包的 skill 文件 (zip)
├── SKILL.md                   ← 主流程：Phase 0 Quick Decision → A B C
├── scripts/
│   └── vgpu_env_check.sh      ← 一键环境体检脚本
└── references/
    ├── host-setup.md          ← Phase 0 (BIOS/OS/驱动) + Phase E (Teardown)
    ├── vgpu-types-rtx-pro-6000.md  ← RTX PRO 6000 Q/B/A 类型全表
    ├── troubleshooting.md     ← 7 类常见故障 + 文件系统路径速查
    └── guest-ci-split.md      ← Phase D: VM 内二次切分 CI
```

---

## Phase 路线图 Phase roadmap

```
Phase 0 ─── 一次性主机准备 (BIOS → display mode → OS → driver → SR-IOV)
   │
   ├── Phase A ─── 纯时间分片 (MIG OFF, 最高密度, 无隔离)
   │
   ├── Phase B ─── MIG 硬件隔离 (Blackwell only, 1 vGPU = 1 GI, QoS 保证)
   │
   ├── Phase C ─── MIG + TimeSlice (GI 间隔离, GI 内分片, 部门共享)
   │
   ├── Phase D ─── Guest CI Split (Phase B 得到的 GI 在 VM 内再拆 CI)
   │
   └── Phase E ─── 全拆清理 (删 vGPU → 销毁 CI/GI → 关闭 MIG)
```

---

## 前提条件 Prerequisites

- **GPU**: Ampere+ (SR-IOV) 或 Pascal+ (legacy mdev)；MIG 功能需 Blackwell (RTX PRO 6000/5000/4500)
- **Hypervisor**: Red Hat / Ubuntu KVM，libvirt 已安装
- **Agent 侧**: 能免密 SSH 到 KVM 主机 (`ssh root@<host>`)
- **BIOS**: SR-IOV、VT-d、ARI (AMD)、Above 4G 均已开启
- **vGPU 软件包**: NVIDIA vGPU Manager `.run` 包已下载到主机

---

## 典型对话示例 Example conversations

### 示例 1：全新部署 Example 1: Fresh deployment

> **用户**: 帮我在 192.168.1.100 上配置 vGPU，GPU 是 RTX PRO 6000，要 8 个 Windows 虚拟机做 VDI。
>
> **Agent**: [加载 skill → Quick Decision 判定走 Phase A 纯时分 → SSH 到主机 → Phase 0 检查环境 → Phase A 创建 vGPU → 输出结果]

### 示例 2：MIG 隔离 Example 2: MIG isolation

> **用户**: 我有 RTX PRO 6000，4 个用户每人需要 24GB 显存，不能互相干扰。
>
> **Agent**: [加载 skill → 查类型表: 4× DC-1-24Q → Quick Decision 判定 Phase B → 开启 MIG → 创建 4 个 1g.24gb+gfx GI → 每个 GI 上建一个 vGPU → 完成]

### 示例 3：排障 Example 3: Troubleshooting

> **用户**: vGPU 授权不生效，Windows VM 里 nvidia-smi 显示 Unlicensed。
>
> **Agent**: [加载 skill → 查 troubleshooting → 定位: token 路径或服务未重启 → 给出 Windows 路径和重启服务命令]

---

## 与 HTML 参考页的关系 Relation to HTML reference

项目里还有一个 `vgpu-kvm-reference.html` — 这是给人看的可视化参考页面（流程卡片 + 场景对比 + 决策矩阵），可以在浏览器打开。Skill 是给 AI 执行的指令集，HTML 是给人理解的速查图。两者内容同源，功能互补。

The project also includes `vgpu-kvm-reference.html` — a visual reference page for humans (flow cards + scenario comparison + decision matrix), openable in a browser. The Skill is the executable instruction set for AI; the HTML is the quick-reference diagram for people. Same source material, complementary roles.

---

## 版本 Version

基于 NVIDIA Virtual GPU Software User Guide Release 20.0。针对 Blackwell (RTX PRO 6000) 验证。
Based on NVIDIA Virtual GPU Software User Guide Release 20.0. Validated against Blackwell (RTX PRO 6000).