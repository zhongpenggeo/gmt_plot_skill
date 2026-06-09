---
name: gmt_plot:plot
description: >
  GMT 绘图执行技能。根据绘图计划编写 GMT 绘图脚本（Bash GMT 命令或 Python PyGMT），
  执行脚本生成图件。当你需要编写和执行 GMT 绘图代码时使用此技能。
  触发场景：绘图计划已制定、数据已准备好、需要开始编写 GMT 代码绘制图件。
---

# GMT 绘图技能

你是一个 GMT 绘图脚本编写专家。你的任务是根据绘图计划，编写并执行 GMT 绘图代码。

## 前提条件

1. 首先读取当前工作目录下的 `plan.md`，获取绘图计划
2. 确认所有需要的数据已经就绪（如未就绪，建议用户先运行 `gmt_plot:download`）
3. **检查参考脚本**：查看当前目录是否存在 `reference_plot_*.sh` 文件，这些是 `gmt_plot:plan` 阶段从网络博客中提取的参考脚本
4. 确认 GMT 环境可用（运行 `conda activate gmt && gmt --version` 检查）

## 参考脚本利用

在编写绘图代码之前，**必须先读取并学习**当前目录下的参考脚本（`reference_plot_*.sh`）：

```bash
# 列出所有参考脚本
ls reference_plot_*.sh 2>/dev/null

# 逐份读取参考脚本，理解其中的技巧
cat reference_plot_1.sh
cat reference_plot_2.sh
```

**借鉴要点**：
- 模块组合方式：参考脚本中使用了哪些 GMT 模块，调用顺序是怎样的
- 参数配置经验：参数值（如 `-I` 渲染强度、`-W` 线宽、`-B` 刻度间隔）可以直接借鉴
- 色标使用技巧：参考脚本中使用的 CPT 文件和 `makecpt` 参数
- 布局设计：子图排列、色标位置、插图大小等排版方式
- 常见陷阱规避：参考脚本注释中标注的注意事项

**重要**：借鉴不等于照抄。应根据 `plan.md` 中的用户需求调整参数，只借鉴通用的技术手法和最佳实践。

## 代码编写规范

### 代码风格选择

GMT 绘图支持两种方式，优先使用 **Bash GMT 命令**方式（兼容性最好），也可使用 Python PyGMT （根据用户提供的环境自行选择绘图方式）：

**Bash GMT 示例：**
```bash
#!/bin/bash
gmt begin map pdf,png,ps
  gmt basemap -R70/140/15/55 -JM15c -Baf -BWSen+t"标题"
  gmt grdimage @earth_relief_05m -R70/140/15/55 -JM15c -Cgeo -I+d
  gmt coast -R70/140/15/55 -JM15c -W0.5p -N1/0.5p -Slightblue
  gmt colorbar -Cgeo -Baf+l"高程 (m)"
gmt end
```

**Python PyGMT 示例：**
```python
import pygmt
fig = pygmt.Figure()
fig.basemap(region=[70, 140, 15, 55], projection="M15c", frame=["af", "WSen+t标题"])
fig.grdimage("@earth_relief_01m", region=[70, 140, 15, 55], cmap="geo", shading="+d")
fig.coast(region=[70, 140, 15, 55], shorelines="0.5p", borders=["1/0.5p"], water="lightblue")
fig.colorbar(cmap="geo", frame=["af+l高程 (m)"])
fig.savefig("map.pdf")
```

### 编写原则

1. 严格按照 plan.md 中的方案编写代码
2. 使用 GMT 现代模式（`gmt begin` / `gmt end`）或 PyGMT
3. 合理设置 `-R`（区域）和 `-J`（投影）参数
4. 正确使用 `-B` 设置边框和刻度
5. 确保色标（CPT）与数据类型匹配
6. 添加必要的 `-I+d` 做地形渲染（地形图）
7. 添加 `-V` 或 `-Vd` 参数以便调试时查看详细输出
8. **必须保留 PS 文件**：`gmt begin` 的输出格式中必须包含 `ps`（如 `pdf,png,ps`），生成的 PS 文件不要删除，供后续 compare 阶段使用

### 查询 GMT 用法

当不确定某个模块的参数时：

1. 使用 Context7 查询 GMT GitHub 源码仓库获取模块文档：`context7-plugin:context7-mcp` → query `resolve-library-id` with "Generic Mapping Tools" or "GMT"
2. 使用 WebSearch 搜索 GMT 官方文档：搜索 "GMT module_name docs generic-mapping-tools"
3. 使用 WebFetch 获取官方文档页面：https://docs.generic-mapping-tools.org/latest/

### 常用参数参考

- **投影 (-J)**: `-JM15c` (墨卡托), `-JQ15c` (等距圆柱), `-JR15c` (Robinson), `-JN15c` (Lambert)
- **边框 (-B)**: `-Baf` (自动刻度), `-BWSen` (西/南边框标注), `-B+t"标题"` (标题)
- **海岸线 (-W)**: `-W0.5p` (0.5磅线宽)
- **国界 (-N)**: `-N1/0.5p` (一级国界/二级国界)
- **地形渲染 (-I)**: `-I+d` (默认光照), `-I+nt0.5` (强度0.5)

## 执行流程

### 1. 编写脚本

将 GMT 绘图代码写入文件，文件名建议为 `gmt_plot.sh`（Bash GMT）或 `gmt_plot.py`（PyGMT）。

### 2. 检查环境

```bash
# 先激活gmt环境
conda activate gmt
# 检查 GMT 是否安装
gmt --version
# 对于 PyGMT，检查 Python 环境
python3 -c "import pygmt; print(pygmt.__version__)" 2>/dev/null
```

### 3. 执行脚本

Bash GMT:
```bash
chmod +x gmt_plot.sh
bash gmt_plot.sh
```

PyGMT:
```bash
python3 gmt_plot.py
```

### 4. 错误处理

如果执行失败：
1. 仔细阅读错误信息，确定问题所在
2. 检查数据文件路径是否正确
3. 检查 -R 范围是否与数据匹配
4. 使用 `gmt grdinfo <数据文件>` 检查网格数据信息
5. 修正代码后重新执行
6. 最多重试 2 次，如仍有问题，汇总错误信息向用户说明

### 5. 确认输出

执行成功后：
1. 确认输出文件已生成（PS/PDF/PNG/JPG 等）
2. **确认 PS 文件已保留**，不要删除 PS 文件
3. 使用 `ls -lh <输出文件名>` 检查文件大小
4. 如有图片文件，使用 Read 工具查看图片质量
5. 记录输出文件路径

## 输出格式

绘图完成后输出：

```
## 绘图结果

### 参考脚本
- reference_plot_1.sh: [来源URL] — [借鉴了哪些技巧]
- reference_plot_2.sh: [来源URL] — [借鉴了哪些技巧]
（如无参考脚本，标注"无"）

### 执行的脚本
- 脚本文件: [路径]
- 脚本类型: [Bash GMT / PyGMT]

### 输出文件
- 主图件: [文件路径]
- PS 文件: [.ps 文件路径]（保留，供 compare 阶段使用）
- 文件大小: [大小]
- 文件格式: [PS/PDF/PNG/JPG]

### 使用的模块
- [模块1]: [用途]
- [模块2]: [用途]
...

### 遇到的问题和解决方案
- [如有问题，记录在此]
```
