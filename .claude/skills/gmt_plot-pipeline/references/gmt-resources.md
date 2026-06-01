# GMT 资源索引

> **数据下载参考**: 具体可用的数据集名称、分辨率和下载方式请查阅下载技能的 `../gmt_plot-download/references/datasets.md`。本文档聚焦 GMT 模块、CPT 和文档资源。

## GMT 官方资源

- **源代码**: https://github.com/genericmappingtools/gmt
- **英文手册**: https://docs.generic-mapping-tools.org/latest/
- **远程数据集**: https://www.generic-mapping-tools.org/remote-datasets/
- **GMT 官方论坛**: https://forum.generic-mapping-tools.org/

## 中文社区资源

- **GMT 中文社区主页**: https://gmt-china.org/
- **GMT 中文手册**: https://docs.gmt-china.org/latest/
- **GMT 中文数据集**: https://docs.gmt-china.org/latest/dataset/
- **GMT 中文社区 GitHub**: https://github.com/gmt-china

## 常用模块速查

| 模块 | 功能 | 常用场景 |
|------|------|----------|
| `basemap` | 底图绘制 | 设置投影、边框、刻度 |
| `coast` | 海岸线 | 添加海岸线、国界、河流 |
| `grdimage` | 网格图像 | 绘制地形/重力等网格数据 |
| `plot` | 点线绘制 | 绘制站点、断层线等 |
| `text` | 文本标注 | 添加标签、标题 |
| `colorbar` | 色标 | 添加颜色标尺 |
| `meca` | 震源机制 | 绘制沙滩球 |
| `psxy` | XY 绘图 | 折线图、散点图 |
| `pscontour` | 等值线 | 绘制等值线图 |
| `grdcontour` | 网格等值线 | 从网格提取等值线 |
| `surface` | 网格化 | 离散点插值为网格 |
| `triangulate` | 三角剖分 | Delaunay 三角剖分 |
| `nearneighbor` | 近邻插值 | 最近邻网格化 |
| `makecpt` | 色标制作 | 生成 CPT 色标文件 |
| `grdview` | 三维视图 | 绘制三维地形图 |
| `subplot` | 子图管理 | 多子图排版 |
| `legend` | 图例 | 添加图例说明 |
| `inset` | 插图 | 添加地理位置插图 |

## CPT (色标) 常用选项

GMT 内置很多 CPT：
- `geo`: 地理地形用色
- `topo`: 地形用色
- `globe`: 全球地形用色
- `relief`: 地形渲染
- `seis`: 地震用色
- `polar`: 两极红蓝色标
- `rainbow`: 彩虹色
- `jet`: Jet 色标
- `hot`: 热度色标
- `cool`: 冷色标
- `haxby`: Haxby 海洋色标
- `no_green`: 无绿色彩

查看所有内置 CPT：`gmt makecpt -C` 然后 Tab 补全

## 获取最新文档

对于 GMT 模块的具体用法和参数，请优先通过以下方式获取最新信息：
1. 使用 Context7 查询 GMT 源码仓库获取 API 文档
2. 使用 web_search 搜索 GMT 官方文档
3. 使用 web_fetch 获取特定页面内容
