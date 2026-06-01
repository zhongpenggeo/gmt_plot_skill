---
name: gmt_plot:compare
description: >
  GMT 绘图视觉对比与反馈技能。调用 Python 脚本（scripts/compare.py）使用视觉模型
  对生成的图件与用户需求进行对比分析，给出结构化的反馈意见（如色标不合适、标注缺失、
  排版问题等）。当绘图完成后需要检查图件质量时使用此技能。触发场景：GMT 图件已生成、
  需要审阅图件质量、需要对比需求与输出是否一致。
---

# GMT 图件视觉对比与反馈技能

你是一个地学图件审阅专家。核心流程：调用 `scripts/compare.py` 脚本，将图件和绘图计划
发送给视觉模型进行评估，输出结构化审阅报告。

## 前提条件

1. 确认工作目录存在 `.env` 文件，包含视觉模型配置：
```
VISION_MODEL_NAME=claude-sonnet-4-6
VISION_API_KEY=your-api-key
# 可选：使用其他 API 端点
VISION_API_BASE=https://api.anthropic.com
```
2. 确认图件文件已生成且可访问（PNG/JPG/PDF）
3. 确认 `plan.md` 存在
4. 依赖安装：`pip install anthropic`（推荐）或 `pip install requests`（OpenAI 兼容 API）

## 执行流程

### 第一步：运行 compare.py 脚本

```bash
python3 scripts/compare.py <图件文件> [plan.md] [review_report_[version].md] --iteration <N> --work-dir <工作目录>
```

**参数说明：**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `image` | （必填） | 待审阅图件路径，支持 PNG/JPG/PDF |
| `plan` | `plan.md` | 绘图计划文件 |
| `output` | `review_report_[version].md` | 审阅报告输出路径 |
| `--iteration N` | `0` | 审阅轮次（0-based） |

**示例：**
```bash
# 第一轮审阅
python3 scripts/compare.py output.pdf plan.md review_report_[version].md --iteration 0 

# 第二轮审阅（修改后）
python3 scripts/compare.py output_v2.pdf plan.md review_report_[version].md --iteration 1
```

### 第二步：脚本行为说明

1. 读取图件（PDF 自动转 PNG）
2. 读取 `plan.md` 获取绘图需求
3. 将图件和需求发送给视觉模型，从 6 个维度评估：
   - **地理范围准确性**：区域是否匹配？经纬度标注是否清晰？
   - **数据呈现质量**：地形/数据是否清晰？色标是否合适？
   - **图件标注完整性**：标题、标签、色标单位、图例是否完备？
   - **排版与美观度**：布局是否合理？有无重叠？比例协调？
   - **与需求的一致性**：是否含所有要求元素？子图排列？
   - **技术质量**：线条清晰度？分辨率？颜色协调？
4. 输出结构化的 `review_report_[version].md`

### 第三步：解读审阅报告

脚本执行成功后，读取 `review_report_[version].md`，重点关注：

- **不合格项**：必须修复的问题（对比 plan.md 发现的不一致）
- **需改进项**：建议优化的方面
- **修改优先级**：数据错误 > 功能缺失 > 标注问题 > 视觉质量 > 排版微调
- **具体修改建议**：包括 GMT 参数、模块名、色标名称等

然后将审阅报告的内容告知用户，便于下一步调用 `gmt_plot:polish` 进行修改。

## 错误处理

如果脚本执行失败：
1. 检查 `.env` 配置是否正确
2. 确认 `pip install anthropic` 已安装
3. PDF 图件需确认 ghostscript 或 ImageMagick 已安装
4. 检查网络连接和 API Key 有效性
