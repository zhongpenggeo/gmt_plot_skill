---
name: gmt_plot:compare
description: >
  GMT 绘图 PS 文件评估与反馈技能。调用 Python 脚本（scripts/compare_ps.py）使用
  deepseek-v4-pro 模型对生成的 PS 文件与用户需求进行对比分析，给出结构化的反馈意见
  （如色标不合适、标注缺失、排版问题等）。当绘图完成后需要检查图件质量时使用此技能。
  触发场景：GMT 图件已生成、PS 文件已保留、需要审阅图件质量、需要对比需求与输出是否一致。
---

# GMT 图件 PS 文件评估与反馈技能

你是一个地学图件审阅专家。核心流程：调用 `scripts/compare_ps.py` 脚本，将 GMT 生成的
PS 文件（矢量文本格式）和绘图计划发送给 deepseek-v4-pro 模型进行评估，输出结构化审阅报告。

## 前提条件

1. 确认环境变量 `DEEPSEEK_API_KEY` 已设置：
```bash
export DEEPSEEK_API_KEY=your-deepseek-api-key
```
可选环境变量：
- `DEEPSEEK_API_BASE`：自定义 API 地址（默认 `https://api.deepseek.com`）
- `DEEPSEEK_TIMEOUT`：请求超时秒数（默认 600）
- `DEEPSEEK_MAX_CHARS`：发送 PS 文件的最大字符数（默认 200000）

2. 确认 PS 文件已生成且可访问（由 gmt_plot:plot 阶段保留）
3. 确认 `plan.md` 存在
4. 依赖安装：`pip install requests`

## 执行流程

### 第一步：运行 compare_ps.py 脚本

```bash
python3 scripts/compare_ps.py <PS文件> [plan.md] [review_report_[version].md] --iteration <N> --work-dir <工作目录>
```

**参数说明：**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `ps_file` | （必填） | 待审阅的 GMT PS 文件路径 |
| `plan` | `plan.md` | 绘图计划文件 |
| `output` | `review_report_[version].md` | 审阅报告输出路径 |
| `--iteration N` | `0` | 审阅轮次（0-based） |
| `--work-dir DIR` | `.` | 工作目录 |

**示例：**
```bash
# 第一轮审阅
python3 scripts/compare_ps.py output.ps plan.md review_report_v1.md --iteration 0

# 第二轮审阅（修改后）
python3 scripts/compare_ps.py output_v2.ps plan.md review_report_v2.md --iteration 1
```

### 第二步：脚本行为说明

1. 读取 GMT 生成的 PS 文件（PostScript 文本格式，包含所有矢量绘图命令和文本标注）
2. 提取 PS 文件元数据（标题、BoundingBox、创建者等）
3. 读取 `plan.md` 获取绘图需求
4. 将 PS 文件内容和需求发送给 deepseek-v4-pro 模型，从 6 个维度评估：
   - **地理范围准确性**：坐标范围是否匹配？经纬度标注是否清晰？
   - **数据呈现质量**：色标定义是否合理？是否应用了正确的渲染？
   - **图件标注完整性**：标题、标签、色标单位、图例是否完备？
   - **排版与美观度**：布局是否合理？元素位置是否协调？
   - **与需求的一致性**：是否含所有要求元素？子图排列是否匹配？
   - **技术质量**：线宽、字号、分辨率参数是否合适？
5. 输出结构化的 `review_report_[version].md`

### 第三步：解读审阅报告

脚本执行成功后，读取 `review_report_[version].md`，重点关注：

- **不合格项**：必须修复的问题（对比 plan.md 发现的不一致）
- **需改进项**：建议优化的方面
- **修改优先级**：数据错误 > 功能缺失 > 标注问题 > 视觉质量 > 排版微调
- **具体修改建议**：包括 GMT 参数、模块名、色标名称等

然后将审阅报告的内容告知用户，便于下一步调用 `gmt_plot:polish` 进行修改。

## 错误处理

如果脚本执行失败：
1. 检查 `DEEPSEEK_API_KEY` 环境变量是否正确设置
2. 确认 `pip install requests` 已安装
3. 检查 PS 文件是否存在且可读
4. 检查网络连接和 API Key 有效性
5. 如果 PS 文件过大（>200KB），可通过 `DEEPSEEK_MAX_CHARS` 调整截断阈值
