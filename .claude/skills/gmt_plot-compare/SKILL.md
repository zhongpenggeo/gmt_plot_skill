---
name: gmt_plot:compare
description: >
  GMT 绘图图件评估与反馈技能。调用 Python 脚本（scripts/compare_imag.py）使用
  多模态模型对生成的 图件 与用户需求进行对比分析，给出结构化的反馈意见
  （如色标不合适、标注缺失、排版问题等）。当绘图完成后需要检查图件质量时使用此技能。
  触发场景：GMT 图件已生成、需要审阅图件质量、需要对比需求与输出是否一致。
---

# GMT 图件 评估与反馈技能

你是一个地学图件审阅专家。核心流程：调用 `scripts/compare_imag.py` 脚本，将 GMT 生成的图像发送给视觉模型进行评估，输出结构化审阅报告。

## 前提条件
1. 确认 jpg/png 文件已生成且可访问（由 gmt_plot:plot 阶段保留）
3. 确认 `plan.md` 存在
4. 依赖安装：`pip install requests anthropic python-dotenv`

## 执行流程

### 第一步：运行 compare_imag.py 脚本

```bash
python3 scripts/compare_imag.py <path-to-png|jpg> <plan.md> <review_report_[version].md> --iteration <N> --output-dir <输出目录>
```

**参数说明：**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `image` | （必填） | 待审阅的 GMT图件路径（直接指定路径） |
| `plan` | （必填） | 绘图计划文件路径（直接指定路径，不再基于 work-dir） |
| `output` | （必填） | 审阅报告输出路径（相对路径时基于 output-dir） |
| `--iteration N` | `0` | 审阅轮次（0-based） |
| `--output-dir DIR` | `.` | 输出目录（仅用于解析 output 的相对路径） |

**示例：**
```bash
# 第一轮审阅：所有路径直接传入
python3 scripts/compare_imag.py /path/to/output.jpg /path/to/plan.md /path/to/review_report_v1.md --iteration 0

# 使用相对路径 + output-dir
python3 scripts/compare_imag.py ./output_v2.jpg ./plan.md review_report_v2.md --iteration 1 --output-dir ./results
```

### 第二步：脚本行为说明

1. 读取 GMT 生成的图件
2. 提取图件元数据（标题、BoundingBox、创建者等）
3. 读取 `plan.md` 获取绘图需求
4. 将图件内容和需求发送给 多模态 模型，从 6 个维度评估：
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
1. 检查 `.env` 是否设置了`VISION_MODEL_NAME`和`VISION_API_KEY`
2. 确认 `pip install requests anthropic python-dotenv` 已安装
3. 检查图件是否存在且可读
4. 检查网络连接和 API Key 有效性
