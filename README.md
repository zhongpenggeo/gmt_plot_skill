# gmt_plot — GMT Geoscience Plotting Skill Suite

> A Claude Code skill suite for automated geoscience figure plotting using Generic Mapping Tools (GMT).

[中文](#中文) | English

---

## English

### Overview

`gmt_plot` is a skill pipeline for Claude Code that automates the entire workflow of creating geoscience figures with GMT. From requirements analysis, data downloading, GMT code generation, to visual review and iterative refinement — all in one flow.

### Skill Architecture

```
User Input → [1. plan] → [2. download] → [3. plot] → [4. compare] → [5. polish]
                                                            ↑                  |
                                                            └─── up to 3 rounds ←──┘
```

| Skill | Trigger | Purpose |
|-------|---------|---------|
| `gmt_plot:pipeline` | `/gmt_plot:pipeline` | Full workflow orchestrator |
| `gmt_plot:plan` | `/gmt_plot:plan` | Requirement analysis & plan generation |
| `gmt_plot:download` | `/gmt_plot:download` | Data acquisition (GMT remote, China datasets, local) |
| `gmt_plot:plot` | `/gmt_plot:plot` | GMT script writing & execution |
| `gmt_plot:compare` | `/gmt_plot:compare` | Visual review via vision model (calls `scripts/compare.py`) |
| `gmt_plot:polish` | `/gmt_plot:polish` | Code modification based on feedback (standalone) |

### Quick Start

```bash
# 1. Enter the project directory
cd /path/to/gmt_plot_skill

# 2. Create .env with vision model config
cp .env.example .env

# 3. Install and Activate GMT (e.g., conda)
conda install gmt -c conda-forge
conda activate gmt

# 4. Install Python dependencies
conda install anthropic requests

# 5. Start plotting in Claude Code
claude
# /gmt_plot:pipeline plot topography of china sourth sea
```

### Prerequisites

- **GMT 6.x**: `conda install -c conda-forge gmt` or `apt install gmt gmt-dcw gmt-gshhg`
- **Python 3.10+**: with `anthropic` or `requests` for vision model calls
- **Ghostscript** or **ImageMagick**: for PDF-to-PNG conversion during visual review (optional)
- **Vision Model API Key**: at least one of Anthropic / OpenAI / Kimi / Gemini

### Directory Structure

```
gmt_plot_skill/
├── .claude/skills/
│   ├── gmt_plot-pipeline/           # Main orchestrator
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── gmt-resources.md     # GMT modules & CPT reference
│   ├── gmt_plot-plan/
│   │   └── SKILL.md
│   ├── gmt_plot-download/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── datasets.md          # ★ Complete data catalog
│   ├── gmt_plot-plot/
│   │   └── SKILL.md
│   ├── gmt_plot-compare/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── compare.py           # Vision model review script
│   └── gmt_plot-polish/
│       └── SKILL.md
├── .env                             # Vision model config
└── README.md
```

### Supported Vision Models

`scripts/compare.py` auto-detects the provider from model name:

| Model name contains | Provider | Default API URL |
|--------------------|----------|-----------------|
| `claude` | Anthropic | `https://api.anthropic.com` |
| `gpt` / `openai` | OpenAI | `https://api.openai.com/v1` |
| `gemini` | Google | `https://generativelanguage.googleapis.com/v1beta` |
| `kimi` / `moonshot` | Moonshot | `https://api.moonshot.cn/v1` |
| other | OpenAI-compatible | set `VISION_API_BASE` |

Use `VISION_API_BASE` in `.env` to route through a custom proxy/gateway.

### Available Data Sources

- **GMT Remote**: Earth relief, gravity, magnetics, crustal age, masks, satellite imagery, planetary data
- **China Geoscience**: CN-border (boundaries), CN-faults, CN-block (tectonic blocks), geo3al (geological map), PB2002 (plate boundaries), global_tectonics, GADM (admin boundaries), WSM_2025 (stress map)
- **Other**: See `datasets.md` for the full catalog with download URLs

### Workflow Files

Each plotting session creates these intermediate files:

| File | Stage | Description |
|------|-------|-------------|
| `plan.md` | plan | Confirmed plotting plan |
| `gmt_plot.sh` | plot | GMT bash script |
| `output.pdf` / `.png` | plot | Generated figure |
| `review_report.md` | compare | Vision model review |
| `review_report_v1.md` | compare (round 2) | Review after first fix |

---

## 中文

### 概述

`gmt_plot` 是一套 Claude Code 技能流水线，用于利用 GMT (Generic Mapping Tools) 自动化地学图件绘制的全流程：从需求分析、数据下载、GMT 代码生成，到视觉模型审阅和迭代修饰。

### 技能架构

```
用户输入 → [1.plan] → [2.download] → [3.plot] → [4.compare] → [5.polish]
                                                       ↑                  |
                                                       └── 最多 3 轮迭代 ←──┘
```

| 技能 | 触发方式 | 功能 |
|------|----------|------|
| `gmt_plot:pipeline` | `/gmt_plot:pipeline` | 全流程编排器 |
| `gmt_plot:plan` | `/gmt_plot:plan` | 需求分析 & 绘图计划生成 |
| `gmt_plot:download` | `/gmt_plot:download` | 数据获取（GMT 远程、中国数据集、本地） |
| `gmt_plot:plot` | `/gmt_plot:plot` | GMT 脚本编写 & 执行 |
| `gmt_plot:compare` | `/gmt_plot:compare` | 视觉模型审阅（调用 `scripts/compare.py`） |
| `gmt_plot:polish` | `/gmt_plot:polish` | 基于反馈修改代码（可独立运行） |

### 快速开始

```bash
# 1. 进入项目目录
cd /path/to/gmt_plot_skill

# 2. 创建 .env 配置视觉模型
cp .env.example .env
# 在.env中添加自己的api-key

# 3. 安装和激活 GMT 环境 (conda示例)
conda install gmt -c conda-forge
conda activate gmt

# 4. 安装 Python 依赖
conda install anthropic requests

# 5. 在 Claude Code 中开始绘图
claude 
# /gmt_plot:pipeline 绘制中国南海地区的etopo1地形图，要求绘制阴影强度，使用etopo色标，位置在右下角，竖直色标，添加海岸线，非海洋地区设置为白色掩膜
```

### 环境要求

- **GMT 6.x**: `conda install -c conda-forge gmt` 或 `apt install gmt gmt-dcw gmt-gshhg`
- **Python 3.10+**: 安装 `anthropic` 或 `requests`
- **Claude code插件**：context7用于查阅原始github仓库，CC-Web-MCP用于支持deepseek模型完成web_search，参考：https://github.com/JcDizzy/CC-Web-MCP
- **Ghostscript** 或 **ImageMagick**: 视觉审阅时 PDF 转 PNG（可选）
- **视觉模型 API Key**: Anthropic / OpenAI / Kimi / Gemini 任意一个即可

### 目录结构

```
gmt_plot_skill/
├── .claude/skills/
│   ├── gmt_plot-pipeline/           # 主流程编排器
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── gmt-resources.md     # GMT 模块 & CPT 速查
│   ├── gmt_plot-plan/
│   │   └── SKILL.md
│   ├── gmt_plot-download/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── datasets.md          # ★ 完整数据目录
│   ├── gmt_plot-plot/
│   │   └── SKILL.md
│   ├── gmt_plot-compare/
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── compare.py           # 视觉模型审阅脚本
│   └── gmt_plot-polish/
│       └── SKILL.md
├── .env                             # 视觉模型配置
└── README.md
```

### 支持的视觉模型

`scripts/compare.py` 根据模型名自动识别 provider：

| 模型名包含 | 服务商 | 默认 API 地址 |
|-----------|--------|-------------|
| `claude` | Anthropic | `https://api.anthropic.com` |
| `gpt` / `openai` | OpenAI | `https://api.openai.com/v1` |
| `gemini` | Google | `https://generativelanguage.googleapis.com/v1beta` |
| `kimi` / `moonshot` | 月之暗面 | `https://api.moonshot.cn/v1` |
| 其他 | OpenAI 兼容 | 请设置 `VISION_API_BASE` |

在 `.env` 中设置 `VISION_API_BASE` 可走中转站/代理。

### 可用数据源

- **GMT 远程数据**：地形、重力、磁异常、地壳年龄、掩膜、卫星影像、行星数据
- **中国地学数据集**：CN-border 国界、CN-faults 断层、CN-block 地块、geo3al 地质图、PB2002 板块边界、global_tectonics 全球构造、GADM 行政边界、WSM_2025 地应力
- **其他**：详见 `datasets.md` 完整目录（含下载 URL）

### 中间产物

每次绘图会话生成以下中间文件：

| 文件 | 阶段 | 说明 |
|------|------|------|
| `plan.md` | plan | 已确认的绘图计划 |
| `gmt_plot.sh` | plot | GMT 绘图脚本 |
| `output.pdf` / `.png` | plot | 生成的图件 |
| `review_report.md` | compare | 视觉模型审阅报告 |
| `review_report_v1.md` | compare (第2轮) | 修改后的复查报告 |


### version
v0: 初始版本，目前skill全部用中文编写的，便于修改，后期将全部修改为英文

### to do list
[] 测试其他视觉模型(目前只测试过kimi-2.5)
[] 测试更多复杂的案例
[] 测试生图成本（视觉模型还是有点点小贵，一张图大概要1块钱~~~~）
    - 考虑保留ps文件，先校验ps文件？（或者svg？）
    - 把原图分辨率减半用来视觉分析，减少模型调用

