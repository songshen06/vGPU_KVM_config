# RTX PRO 6000 Blackwell Server Edition — vGPU Types

Physical GPUs per board: 1. Total frame buffer: ~96 GB. Supports both MIG-backed and time-sliced vGPUs.

Full type names use prefix `NVIDIA RTX PRO 6000 Blackwell`, shortened as `DC-` below.

## GPU Instance Profiles (MIG +gfx only)

| Profile ID | Name | Instances (Free/Total) | Memory GiB | SM | DEC | ENC | JPEG | OFA |
|---|---|---|---|---|---|---|---|---|
| 47 | MIG 1g.24gb+gfx | 4/4 | 23.12 | 46 | 1 | 1 | 1 | 0 |
| 35 | MIG 2g.48gb+gfx | 2/2 | 46.50 | 94 | 2 | 2 | 2 | 0 |
| 32 | MIG 4g.96gb+gfx | 1/1 | 93.38 | 188 | 4 | 4 | 4 | 1 |

Only `+gfx` profiles are supported for NVIDIA vGPU. Non-gfx profiles (e.g., `MIG 1g.24gb+me`, `MIG 2g.48gb-me`) are not usable with vGPU.

---

## MIG-Backed Q-Series (Virtual Workstations, license: vWS)

Each vGPU type maps to exactly one GPU instance profile. **Max vGPUs per GI** = max instances of this type on a single GI. Multiply by the number of matching GI profiles on the GPU for total GPU capacity. Max resolution: 7680×4320.

| vGPU Type | FB (GB) | Max vGPUs per GI | GI Profile | Slices per GI | CIs per vGPU | Displays |
|---|---|---|---|---|---|---|
| DC-4-96Q | 96 | 1 | MIG 4g.96gb+gfx | 4 | 4 | 2×7680×4320 or 4×5120×2880 |
| DC-2-48Q | 48 | 1 | MIG 2g.48gb+gfx | 2 | 2 | 2×7680×4320 or 4×5120×2880 |
| DC-4-48Q | 48 | 2 | MIG 4g.96gb+gfx | 4 | 1 | 2×7680×4320 or 4×5120×2880 |
| DC-4-32Q | 32 | 3 | MIG 4g.96gb+gfx | 4 | 1 | 2×7680×4320 or 4×5120×2880 |
| DC-1-24Q | 24 | 1 | MIG 1g.24gb+gfx | 1 | 1 | 2×7680×4320 or 4×5120×2880 |
| DC-2-24Q | 24 | 2 | MIG 2g.48gb+gfx | 2 | 1 | 2×7680×4320 or 4×5120×2880 |
| DC-4-24Q | 24 | 4 | MIG 4g.96gb+gfx | 4 | 1 | 2×7680×4320 or 4×5120×2880 |
| DC-2-16Q | 16 | 3 | MIG 2g.48gb+gfx | 2 | 1 | 2×7680×4320 or 4×5120×2880 |
| DC-1-12Q | 12 | 2 | MIG 1g.24gb+gfx | 1 | 1 | 2×7680×4320 or 4×5120×2880 |
| DC-2-12Q | 12 | 4 | MIG 2g.48gb+gfx | 2 | 1 | 2×7680×4320 or 4×5120×2880 |
| DC-1-8Q | 8 | 3 | MIG 1g.24gb+gfx | 1 | 1 | 2×7680×4320 or 4×5120×2880 |
| DC-1-6Q | 6 | 4 | MIG 1g.24gb+gfx | 1 | 1 | 1×7680×4320 or 4×5120×2880 |
| DC-1-4Q | 4 | 6 | MIG 1g.24gb+gfx | 1 | 1 | 1×7680×4320 or 4×5120×2880 |
| DC-1-3Q | 3 | 8 | MIG 1g.24gb+gfx | 1 | 1 | 1×7680×4320 or 2×5120×2880 or 4×3840×2400 |
| DC-1-2Q | 2 | 12 | MIG 1g.24gb+gfx | 1 | 1 | 1×7680×4320 or 2×5120×2880 or 4×3840×2400 |

**Key interpretation:** `DC-1-2Q` = 2GB frame buffer, 12 such vGPUs fit across 4× MIG 1g.24gb+gfx instances (3 per GI in mixed-size mode). In pure MIG-backed mode (1 vGPU per GI), total = 4.

---

## Time-Sliced Q-Series on Single-Instance GPU (Virtual Workstations, license: vWS)

No MIG. Entire GPU shared via time-slicing. Max vGPUs shown for both equal-size and mixed-size modes.

| vGPU Type | FB (GB) | Max vGPUs (Equal-Size) | Max vGPUs (Mixed-Size) | Displays |
|---|---|---|---|---|
| DC-96Q | 96 | 1 | 1 | 2×7680×4320 or 4×5120×2880 |
| DC-48Q | 48 | 2 | 2 | 2×7680×4320 or 4×5120×2880 |
| DC-32Q | 32 | 3 | 3 | 2×7680×4320 or 4×5120×2880 |
| DC-24Q | 24 | 4 | 4 | 2×7680×4320 or 4×5120×2880 |
| DC-16Q | 16 | 6 | 6 | 2×7680×4320 or 4×5120×2880 |
| DC-12Q | 12 | 8 | 8 | 2×7680×4320 or 4×5120×2880 |
| DC-8Q | 8 | 12 | 12 | 2×7680×4320 or 4×5120×2880 |
| DC-6Q | 6 | 16 | 16 | 1×7680×4320 or 4×5120×2880 |
| DC-4Q | 4 | 24 | 24 | 1×7680×4320 or 4×5120×2880 |
| DC-3Q | 3 | 32 | 32 | 1×7680×4320 or 2×5120×2880 or 4×3840×2400 |

---

## MIG-Backed B-Series (Virtual Desktops, license: vPC or vWS)

| vGPU Type | FB (GB) | Max vGPUs per GI | GI Profile | Slices per GI | Displays |
|---|---|---|---|---|---|
| DC-1-3B | 3 | 8 | MIG 1g.24gb+gfx | 1 | 1×5120×2880 or 2×3840×2400/2160 or 4×2560×1600 |
| DC-1-2B | 2 | 12 | MIG 1g.24gb+gfx | 1 | 1×5120×2880 or 2×3840×2400/2160 or 4×2560×1600 |

---

## Time-Sliced B-Series on Single-Instance GPU (Virtual Desktops, license: vPC or vWS)

| vGPU Type | FB (GB) | Max vGPUs (Equal-Size) | Max vGPUs (Mixed-Size) | Displays |
|---|---|---|---|---|
| DC-3B | 3 | 32 | 32 | 1×5120×2880 or 2×3840×2400/2160 or 4×2560×1600 |
| DC-2B | 2 | 32 | 32 | 1×5120×2880 or 2×3840×2400/2160 or 4×2560×1600 |

---

## MIG-Backed A-Series (Virtual Applications, license: vApps)

Single display, fixed max resolution 1280×1024.

| vGPU Type | FB (GB) | Max vGPUs per GI | GI Profile | Slices per GI | CIs per vGPU |
|---|---|---|---|---|---|
| DC-4-96A | 96 | 1 | MIG 4g.96gb+gfx | 4 | 4 |
| DC-2-48A | 48 | 1 | MIG 2g.48gb+gfx | 2 | 2 |
| DC-4-48A | 48 | 2 | MIG 4g.96gb+gfx | 4 | 1 |
| DC-4-32A | 32 | 3 | MIG 4g.96gb+gfx | 4 | 1 |
| DC-1-24A | 24 | 1 | MIG 1g.24gb+gfx | 1 | 1 |
| DC-2-24A | 24 | 2 | MIG 2g.48gb+gfx | 2 | 1 |
| DC-4-24A | 24 | 4 | MIG 4g.96gb+gfx | 2 | 1 |
| DC-2-16A | 16 | 3 | MIG 2g.48gb+gfx | 2 | 1 |
| DC-1-12A | 12 | 2 | MIG 1g.24gb+gfx | 1 | 1 |
| DC-2-12A | 12 | 4 | MIG 2g.48gb+gfx | 2 | 1 |
| DC-1-8A | 8 | 3 | MIG 1g.24gb+gfx | 1 | 1 |
| DC-1-6A | 6 | 4 | MIG 1g.24gb+gfx | 1 | 1 |
| DC-1-4A | 4 | 6 | MIG 1g.24gb+gfx | 1 | 1 |
| DC-1-3A | 3 | 8 | MIG 1g.24gb+gfx | 1 | 1 |
| DC-1-2A | 2 | 12 | MIG 1g.24gb+gfx | 1 | 1 |

---

## Time-Sliced A-Series on Single-Instance GPU (Virtual Applications, license: vApps)

Single display, fixed max resolution 1280×1024.

| vGPU Type | FB (GB) | Max vGPUs (Equal-Size) | Max vGPUs (Mixed-Size) |
|---|---|---|---|
| DC-96A | 96 | 1 | 1 |
| DC-48A | 48 | 2 | 2 |
| DC-32A | 32 | 3 | 3 |
| DC-24A | 24 | 4 | 4 |
| DC-16A | 16 | 6 | 6 |
| DC-12A | 12 | 8 | 8 |
| DC-8A | 8 | 12 | 12 |
| DC-6A | 6 | 16 | 16 |
| DC-4A | 4 | 24 | 24 |
| DC-3A | 3 | 32 | 32 |

---

## Typology Summary

| Configuration | Isolation | GPU Instance | vGPUs per GI | Use Case |
|---|---|---|---|---|
| Time-sliced (single-instance GPU) | None (shared) | N/A | N/A | Max density, bursty workloads |
| MIG-backed (one vGPU per GI) | Full (dedicated GI) | 1 vGPU = 1 GI | 1 | QoS isolation, predictable perf |
| Time-sliced MIG-backed | Partial (shared GI, isolated from other GIs) | Multiple vGPUs / GI | 2–12 depending on FB size | Balanced density + isolation |

## Typical RTX PRO 6000 Configuration Examples

### Max Density (time-sliced, single GPU)
- 32× DC-3Q = 32 users, 3GB each, time-sliced

### MIG + Time-Sliced Hybrid
- 2× MIG 2g.48gb+gfx instances × 4× DC-2-12Q each = 8 users @ 12GB, isolated between the two GIs, time-sliced within each GI
- 1× MIG 4g.96gb+gfx × 1× DC-4-96Q (dedicated heavy user) + 1× MIG 1g.24gb+gfx × 3× DC-1-8Q (light users, time-sliced)

### Pure MIG-Backed (no time-slicing within GI)
- 4× MIG 1g.24gb+gfx × 1× DC-1-24Q each = 4 isolated users @ 24GB each