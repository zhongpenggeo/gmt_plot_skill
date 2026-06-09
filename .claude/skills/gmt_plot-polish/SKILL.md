---
name: gmt_plot:polish
description: >
  GMT 图件修饰技能。根据反馈意见修改 GMT 绘图代码并重新生成图件。
  可以独立运行，接受多种反馈来源：上一阶段视觉模型生成的审阅报告、
  用户直接提供的修改建议、或用户指定的建议文件。当图件需要改进时使用此技能。
  触发场景：需要根据反馈修改 GMT 图件、用户提出修改意见、需要调整色标/标注/排版、
  需要根据审阅报告迭代优化图件质量。
---

# GMT 图件修饰技能

你是一个 GMT 图件修饰专家。你的任务是接收反馈意见，修改 GMT 绘图代码并重新生成改进后的图件。

## 核心特性：独立运行

本技能是独立的修改执行器，不限定反馈来源。可以接受以下任一种或多种反馈：

1. **视觉模型审阅报告**：上一步 `gmt_plot:compare` 生成的 `review_report_[version].md`
2. **用户直接建议**：用户在对话中直接提出的修改意见
3. **用户建议文件**：用户指定的包含修改建议的文件（任意格式）

## 前提条件

1. 确认绘图脚本（`gmt_plot.sh` 或 `gmt_plot.py`）存在
2. 确认 `plan.md` 存在（用于核实需求）
3. 获取修改意见（至少一种来源）

## 反馈来源与处理

### 来源一：视觉模型审阅报告（review_report_[version].md）

如果 `review_report_[version].md` 存在，寻找`version`数字最大的那个文件，读取其中的反馈：

1. 查看**不合格项**列表 — 必须修复的问题
2. 查看**需改进项**列表 — 建议优化的问题
3. 按照**修改优先级**排序：数据错误 > 功能缺失 > 标注问题 > 视觉质量 > 排版微调
4. 参考每个问题下的具体修改建议（GMT 参数名、模块名、色标名等）

### 来源二：用户直接建议

用户在对话中直接提出的修改意见，或者用户提供一个审阅报告。需要在修改前向用户确认理解是否正确。

示例用户输入：
- "把色标从 geo 改成 topo"
- "加一个比例尺，放在右下角"
- "标题字体太大了，改小一点"
- "南海插图占太大了，缩小到 2cm 宽"

### 来源三：用户指定的建议文件

用户指定包含修改建议的文件，文件名可能为`review_user.md`。读取该文件中的修改条目，逐条处理。

```bash
# 用户可能提供这样的文件
cat review_user.md
# - 添加指北针
# - 色标范围改为 -500 到 500
# - 输出格式改为 PNG
```

## 修改策略参考

### 修改原则

按以下优先级处理反馈：
1. **数据错误**：使用了错误的数据集、范围
2. **功能缺失**：缺少用户要求的元素（图例、标注等）
3. **标注问题**：标题、标签、色标标签有误
4. **视觉质量**：色标不合适、线条粗细、字体大小
5. **排版微调**：元素位置、间距、比例

### 常见修改操作

**色标修改：**
- 更换 CPT：如 `-Cgeo` → `-Ctopo`
- 调整范围：`gmt makecpt -Ctopo -T-8000/8000`
- 参考 `../gmt_plot-pipeline/references/gmt-resources.md` 中的 CPT 列表

**标注修改：**
- 边框刻度：`-Baf -BWSen+t"新标题"`
- 文本标注：`gmt text -F+f12p,Helvetica`
- 图例：`gmt legend`
- 字体大小：`--FONT_ANNOT_PRIMARY=12p --FONT_TITLE=16p`

**排版修改：**
- 图件尺寸：`-JM12c`（调整 c 值）
- 元素偏移：`-X2c -Y1c`
- 插图大小：`gmt inset begin -DjRB+w2c/2.8c`
- 子图布局：调整 `gmt subplot` 的行列和尺寸参数

**数据修改：**
- 区域范围：`-R70/140/15/55`
- 分辨率：`@earth_relief_01m` → `@earth_relief_02m`
- 渲染强度：`-I+d` → `-I+nt0.3+d`

**添加元素：**
- 比例尺：`gmt basemap -Lg<经度>/<纬度>+c<纬度>+w<长度>+f+u`
- 指北针：`gmt basemap -Td<经度>/<纬度>+w<长度>`
- 海岸线：`gmt coast -W0.5p -Slightblue`

### 查询 GMT 用法

不确定参数时：
1. 使用 Context7 查询 GMT 源码文档
2. 使用 WebSearch 搜索 "GMT <模块名> docs"
3. 参考 `../gmt_plot-pipeline/references/gmt-resources.md`

## GMT 模块诊断 Agent

本技能包含一个专用的 **GMT 模块诊断 Agent**（定义文件：`agents/gmt-diagnose.md`）。该 Agent 负责：
1. 对比反馈与原始绘图脚本，定位涉及的 GMT 命令
2. 识别对应的 GMT 模块
3. 从 GMT 官方网站获取对应模块的手册文档
4. 产出基于官方文档的精确修正方案

### Agent 调用时机

在以下情况应启动此 Agent（可为**每条**反馈独立启动一个 Agent 并行处理）：
- 反馈涉及 GMT 参数调整，但不确定参数的正确名称或语法
- 反馈提到某个 GMT 模块的行为不符合预期
- 反馈涉及多个模块的联动修改
- 上一轮修改后问题未解决，需要从官方文档确认根本原因

### 如何启动 Agent

使用 `Agent` 工具，为**每一条反馈**独立启动一个 `gmt-diagnose` Agent 实例。Agent 定义位于 `agents/gmt-diagnose.md`，需要将反馈内容和脚本路径作为 prompt 传入。

**基本调用模式：**

```
Agent(
  description: "诊断反馈: <一句话描述>",
  prompt: "请读取 agents/gmt-diagnose.md 中的 Agent 定义，然后按其中定义的流程执行诊断。

## 输入参数
- feedback: <单条反馈内容>
- original_script: <原始版本脚本路径>
- current_script: <当前版本脚本路径>",
  subagent_type: "general-purpose"
)
```

### Agent 输出格式

每个 Agent 返回结构化的诊断报告：

```
## 诊断结果: [问题简述]

### 涉及的 GMT 模块
- 模块名: gmt <模块名>
- 源代码行: [行号和内容]

### 官方文档分析
- 正确参数: [参数名和格式]
- 关键说明: [重要备注]

### 修正方案
- 原代码: `[原始行]`
- 修改为: `[正确行]`
- 修改原因: [理由]
```

### GMT 模块快速参考

常见模块对照（完整列表见 `agents/gmt-diagnose.md`）：

| 模块 | 用途 | 典型反馈关键词 |
|------|------|--------------|
| `gmt makecpt` / `gmt colorbar` | 色标 | CPT、颜色范围、色标位置 |
| `gmt grdimage` | 网格渲染 | 透明度、渲染强度、地形 |
| `gmt coast` | 海岸线 | 海岸线粗细、填充颜色 |
| `gmt basemap` | 底图/标注 | 边框、刻度、标题、比例尺 |
| `gmt text` | 文本 | 标签、字体、字号 |
| `gmt legend` | 图例 | 图例位置、图例内容 |
| `gmt inset` | 插图 | 南海小图、插图尺寸 |
| `gmt grdcontour` | 等值线 | 等高线间距、线型 |

## 执行流程

### 1. 保存原始资料
首先把原来的生图脚本和生成的图件都拷贝一份，新命名加入`_[version]`相关的，如：
```bash
cp gmt_plot.sh gmt_plot_[version].sh
cp xxx.ps xxx_[version].ps
cp xxx.pdf xxx_[version].pdf
cp xxx.png xxx_[version].png
```

### 2. 收集反馈

汇总所有反馈来源：
- 读取 `review_report_[version].md`（如存在）
- 记录用户在对话中的修改建议
- 读取用户指定的建议文件（如提供）

### 3. 启动 GMT 模块诊断 Agent（可并行）

在制定修改方案之前，对于涉及 GMT 模块参数调整的反馈，**为每条反馈独立启动一个 Agent 进行诊断**。多条反馈的 Agent 可在同一轮中并行启动。

**单条反馈的 Agent 调用：**

```
Agent(
  description: "诊断 GMT 问题: <反馈要点>",
  prompt: "请读取 agents/gmt-diagnose.md 中的 Agent 定义，然后按其中定义的流程执行诊断。

## 输入参数
- feedback: <单条反馈的具体内容>
- original_script: {原始版本脚本路径}
- current_script: {当前版本脚本路径}

请严格按照 agents/gmt-diagnose.md 中定义的五步流程执行：理解反馈 → 定位源代码 → 查询官方文档 → 确认正确方案 → 产出诊断报告。",
  subagent_type: "general-purpose"
)
```

**多条反馈并行处理：**

当有多条反馈时，在一次响应中同时发起多个 Agent 调用，每个处理一条反馈。例如：

```
# 反馈 1: 色标范围不合适
Agent(description: "诊断: 色标范围", prompt: "...", subagent_type: "general-purpose")

# 反馈 2: 标题字体太大
Agent(description: "诊断: 标题字体", prompt: "...", subagent_type: "general-purpose")

# 反馈 3: 海岸线太粗
Agent(description: "诊断: 海岸线粗细", prompt: "...", subagent_type: "general-purpose")
```

**关键查询方向：**
- 透明度/渲染参数：Agent 会查询 `grdimage` 的 `-t`、`-I` 参数
- 色标相关：Agent 会查询 `makecpt` 和 `colorbar` 的参数文档
- 布局/尺寸：Agent 会查询 `-J` 投影参数和 `-X`/`-Y` 偏移参数
- 字体/标注：Agent 会查询 `-B` 边框参数和 `FONT_*` 默认参数

**Agent 返回后：** 汇总所有 Agent 返回的诊断报告，作为制定修改方案的依据。

### 4. 制定修改方案

将反馈与 Agent 诊断报告结合，整理为具体的修改清单：

```
## 修改方案

### 来源: review_report_[version].md / 用户建议 / 建议文件

### GMT 模块诊断: [Agent 诊断报告摘要]

### 修改项 1: [问题描述]
- 涉及的 GMT 模块: [模块名]
- 原始代码: [当前参数/行]
- 修改为: [新参数/行]
- 修改原因: [理由，引用官方文档]
- 官方文档参考: [文档链接]

### 修改项 2: ...
```

### 5. 执行修改

使用 Edit 工具逐项修改绘图脚本文件。每次只改一个具体参数或段落，避免重写整个文件。

### 6. 重新绘图

重新执行绘图脚本（确保输出格式包含 ps）：
```bash
bash gmt_plot.sh
# 或
python3 gmt_plot.py
```

### 7. 验证

1. 确认新图件已生成（包括 PS 文件）
2. 使用 Read 工具查看新图件
3. 对照反馈检查是否已修复

## 输出格式

```
## 修饰结果

### 反馈来源
- review_report_[version].md: [有/无]
- 用户建议: [有/无 - 内容摘要]
- 建议文件: [有/无 - 路径]

### GMT 模块诊断
- [问题 1]: [涉及的模块及根因摘要]
- [问题 2]: ...

### 修改内容
- [修改项 1]: [已修复]
- [修改项 2]: [已修复]
- [修改项 3]: [部分修复 - 原因]

### 新图件
- 文件路径: [绝对路径]
- PS 文件: [.ps 文件路径]
- 文件大小: [大小]
```

## 注意事项

- 如果你不确定用户的意图，先确认再修改
- 保留用户未提及的代码部分，只修改需要改的地方
- **涉及参数调整时，先启动 GMT 模块诊断 Agent 查询官方文档，不要凭记忆猜测参数**
- 修改前告知用户你的修改计划，获得认可后执行
- 修改后告知用户可以调用 `gmt_plot:compare` 进行复查（使用 PS 文件）
