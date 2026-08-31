# AGENTS.md — Agent 自安装说明 Self-Install Guide

> 当人类把这个仓库链接丢给你时，你的任务是：**把这 4 个 skill 安装到你的 skills 目录**，然后告诉人类装好了。
> When a human hands you this repo link, your task is: **install these 4 skills into your skills directory**, then report back.

---

## 仓库里有什么 What's in this repo

4 个 NVIDIA vGPU 相关 skill（每个都是「目录源码」+「.skill 压缩包」两种形态）：

| Skill | 用途 Purpose | 触发关键词 Trigger keywords |
|---|---|---|
| `vgpu-kvm-config` | vGPU 创建/管理：BIOS→驱动→SR-IOV→MIG→vGPU→VM 挂载 | 配 vGPU / MIG vGPU / RTX PRO 6000 vGPU / nvidia-smi vgpu |
| `license-system-deploy` | NVIDIA License System 部署：DLS→注册→绑定→客户端授权 | 部署 DLS / license server / 授权服务器 |
| `log-key-extractor` | 大日志压缩成 LLM 上下文（模板聚合 + 打分事件 + host 画像） | 日志太大 / 提取关键日志 / 日志摘要 |
| `vgpu-report` | nvidia-bug-report 结构化分析（Xid 计数、崩溃循环、pin 失败、风险分级） | 分析 vGPU 日志 / Xid 分析 / bug report 分析 |

---

## 安装步骤 Install steps

### Step 1 — 克隆仓库

```bash
git clone --depth 1 https://github.com/songshen06/vGPU_KVM_config /tmp/vgpu-kvm-config
```

### Step 2 — 确定 skills 目录

按顺序探测，用**第一个已存在**的目录；都不存在就创建 `~/.agents/skills`：

```bash
for d in ~/.agents/skills ~/.claude/skills ~/.opencode/skills ~/.dsh/skills; do
  [ -d "$d" ] && { SKILLS_DIR="$d"; break; }
done
[ -z "$SKILLS_DIR" ] && SKILLS_DIR=~/.agents/skills
mkdir -p "$SKILLS_DIR"
echo "skills dir: $SKILLS_DIR"
```

### Step 3 — 安装（二选一）

**方式 A：符号链接（推荐）** — 跟随仓库更新，不用重复拷贝：

```bash
for s in vgpu-kvm-config license-system-deploy log-key-extractor vgpu-report; do
  ln -sfn "/tmp/vgpu-kvm-config/$s" "$SKILLS_DIR/$s"
done
```

**方式 B：解压 .skill 包** — 独立副本，脱离仓库：

```bash
for f in /tmp/vgpu-kvm-config/*.skill; do unzip -o "$f" -d "$SKILLS_DIR/"; done
```

### Step 4 — 验证

```bash
ls "$SKILLS_DIR" | grep -E 'vgpu-kvm-config|license-system-deploy|log-key-extractor|vgpu-report'
# 每个目录里都必须有 SKILL.md（含 YAML frontmatter 的 name + description）
```

装完后向人类报告：装到了哪个目录、共几个 skill、每个 skill 的触发关键词。

---

## 注意事项 Notes

- 框架靠每个 skill 目录里的 `SKILL.md`（YAML frontmatter 的 `name` + `description`）来发现 skill。目录名必须与 `name` 一致（kebab-case）。
- 符号链接方式下，skill 目录名要和 `SKILL.md` 里的 `name` 严格一致，否则框架可能识别不到。
- 安装后通常**无需重启**，下次对话提及触发关键词即可生效。
- 如果框架扫描的是项目级目录（如 `<project>/.agents/skills`），把 `$SKILLS_DIR` 换成对应项目目录即可。
