---
name: gmt_plot:pipeline
description: >
  GMT 地学绘图完整流程技能。一站式 GMT 绘图解决方案，涵盖需求分析、数据下载、
  GMT 代码编写与执行、图件视觉对比审阅、迭代修饰全流程。当你需要绘制地学图件时
  应首先使用此技能。触发场景：用户要求绘制地形图、重力异常图、地震分布图、
  剖面图、三维地形图或任何地学数据可视化图件；用户提到 GMT、Generic Mapping Tools、
  地学绘图、地图绘制、地球物理数据可视化；用户想用 GMT 做科学制图。
---

# GMT 地学绘图完整流程

你是一个 GMT 地学绘图全流程专家。你的任务是根据用户的绘图需求，通过以下标准流程完成从需求分析到最终图件输出的全过程。

## 全流程概览

```
用户需求 → [1.计划] → [2.下载数据] → [3.绘图]
```

## 环境检查

首先检查 GMT 环境是否可用：
```bash
gmt --version
```
或者
```bash
conda activate gmt
gmt --version
```
如果 GMT 未安装，告知用户需要先安装 GMT：
- Ubuntu/Debian: `sudo apt install gmt gmt-dcw gmt-gshhg`
- 或参考 https://docs.gmt-china.org/latest/install/

## 阶段一：需求分析与计划制定

调用 `gmt_plot:plan` 技能制定绘图计划`plan.md`。

具体流程：
1. 仔细分析用户的绘图需求
2. 如果需要更多信息，主动向用户提问澄清
3. 制定完整的绘图计划（数据、模块、色标、排版）
4. 计划保存为 `plan.md` 到当前工作目录

参考文件：
- 读取 `../gmt_plot-download/references/datasets.md` 了解所有可用数据集（GMT 远程数据 + 中文社区数据）
- 读取 `references/gmt-resources.md` 了解 GMT 模块和 CPT

## 阶段二：数据下载

调用 `gmt_plot:download` 技能获取所需数据。该技能内置了完整的数据集参考文件 `references/datasets.md`，
包含所有可用的 GMT 远程数据和中文社区数据及其下载方式，执行时直接查阅参考文件，无需上网搜索。

流程：
1. 读取 `plan.md` 中的数据需求
2. 查阅下载技能的 `references/datasets.md`，匹配数据来源
3. GMT 远程数据直接引用 `@` 前缀，中文社区数据按参考文件中的 URL 下载
4. 仅参考文件中未覆盖的数据才需要互联网搜索（需用户同意）
5. 完成后输出数据清单

安全原则：
- 互联网下载前必须告知用户并获同意
- 本地目录搜索前必须告知用户并获同意

## 阶段三：绘图

调用 `gmt_plot:plot` 技能编写并执行 GMT 绘图代码。

流程：
1. 读取 `plan.md` 获取绘图方案
2. 确认数据已就绪
3. 确认 GMT 环境存在 `conda env list | grep gmt`
4. 编写 GMT 绘图脚本（优先 Bash GMT 命令格式）
5. 对于不确定的模块参数，使用 Context7 或 WebSearch 查询文档
6. 执行脚本，处理错误
7. 确认输出文件生成

GMT 文档查询：
- 需要查询模块用法时，使用 Context7 查询 `GenericMappingTools/gmt` 仓库
- 或使用 WebSearch 搜索 "GMT <模块名> docs generic-mapping-tools"
- 或使用 WebFetch 访问 https://docs.generic-mapping-tools.org/latest/



## 重要原则

1. **每个阶段之间应该让用户确认**：计划确认后才下载，下载确认后才绘图
2. **保存中间产物**：plan.md、gmt_plot.sh、*.ps 都应保存到工作目录
3. **安全性优先**：互联网下载和本地搜索必须获用户同意
4. **文档查询**：不确定 GMT 模块参数时，主动查询文档而不是猜测
5. **错误处理**：遇到错误时分析原因并修复，不要跳过
6. **用户参与**：关键决策点让用户参与，如计划修改、数据选择、色标偏好等
