# 地学数据集完整目录

本文档汇总了所有可用于 GMT 绘图的数据集，包括 GMT 远程数据和 GMT 中文社区数据。
执行下载任务时，直接查阅本文档获取数据来源和下载方式，无需上网搜索。

---

## 一、GMT 内置远程数据

GMT 远程数据通过 `@` 前缀引用，首次使用时自动下载并缓存。使用 `gmt grdinfo @数据集名` 查看数据信息。
完整列表：https://www.generic-mapping-tools.org/remote-datasets/

### 1.1 地球地形/高程数据

| 数据集名称 | 数据源 | 可用分辨率 | 说明 |
|-----------|--------|-----------|------|
| `@earth_relief` | GEBCO / SRTM15+V2.4 | 01m, 02m, 03m, 04m, 05m, 06m, 10m, 15m, 20m, 30m | 全球陆地+海洋地形 |
| `@srtm_relief` | NASA SRTM | 01m, 03m | 仅陆地区域地形 |

**使用示例：**
```bash
gmt grdimage @earth_relief_01m -R70/140/15/55 -JM15c -Cgeo -I+d
```

### 1.2 地球重力/大地水准面数据

| 数据集名称 | 数据源 | 可用分辨率 | 说明 |
|-----------|--------|-----------|------|
| `@earth_faa` | IGPP | 01m, 02m, 03m, 04m, 05m | 自由空气重力异常 |
| `@earth_faaerror` | IGPP | 01m | 自由空气重力异常误差 |
| `@earth_geoid` | EGM2008 | 01m, 02m, 03m, 04m, 05m | 大地水准面 |
| `@earth_vgg` | IGPP | 01m, 02m, 03m, 04m, 05m | 垂直重力梯度 |
| `@earth_edefl` | IGPP | 01m | 东西方向垂线偏差 |
| `@earth_ndefl` | IGPP | 01m | 南北方向垂线偏差 |
| `@earth_wdmam` | WDMAM | 01m, 02m, 03m, 04m, 05m | 世界数字磁异常图 |

**使用示例：**
```bash
gmt grdimage @earth_faa_01m -R70/140/15/55 -JM15c -Cpolar
```

### 1.3 地球磁异常数据

| 数据集名称 | 数据源 | 可用分辨率 | 说明 |
|-----------|--------|-----------|------|
| `@earth_mag` | EMAG2 | 01m, 02m, 03m, 04m, 05m | 地球磁异常 |
| `@earth_mag4km` | EMAG2 | 01m, 02m, 03m, 04m, 05m | 4km 高度磁异常 |

### 1.4 地壳年龄数据

| 数据集名称 | 数据源 | 可用分辨率 | 说明 |
|-----------|--------|-----------|------|
| `@earth_age` | EarthByte | 01m, 02m, 03m, 04m, 05m, 06m | 海洋地壳年龄 |

### 1.5 掩膜与距离数据

| 数据集名称 | 数据源 | 可用分辨率 | 说明 |
|-----------|--------|-----------|------|
| `@earth_mask` | GSHHG | 01m, 02m, 03m, 04m, 05m | 陆地/海洋/湖泊掩膜 |
| `@earth_dist` | GSHHG | 01m | 到海岸线距离（球面） |
| `@earth_cdist` | GSHHG | 01m | 到海岸线距离（笛卡尔） |

### 1.6 卫星影像数据

| 数据集名称 | 数据源 | 可用分辨率 | 说明 |
|-----------|--------|-----------|------|
| `@earth_day` | NASA | 01m, 02m, 03m, 04m, 05m | 白天卫星影像 |
| `@earth_night` | NASA | 01m, 02m, 03m, 04m, 05m | 夜间灯光影像 |

### 1.7 海洋数据

| 数据集名称 | 数据源 | 可用分辨率 | 说明 |
|-----------|--------|-----------|------|
| `@earth_mss` | CNES | 01m | 平均海面高度 |
| `@earth_mdt` | CNES | 01m | 平均动力地形 |

### 1.8 其他行星地形

| 数据集名称 | 数据源 | 可用分辨率 | 说明 |
|-----------|--------|-----------|------|
| `@mars_relief` | NASA | 01m, 02m, 03m, 04m, 05m, 06m, 10m, 15m, 20m, 30m | 火星地形 |
| `@moon_relief` | USGS | 01m, 02m, 03m, 04m, 05m, 06m, 10m, 15m, 20m, 30m | 月球地形 |
| `@mercury_relief` | USGS | 01m, 02m, 03m, 04m, 05m, 06m, 10m, 15m, 20m, 30m | 水星地形 |
| `@venus_relief` | NASA | 01m, 02m, 03m, 04m, 05m, 06m, 10m, 15m, 20m, 30m | 金星地形 |
| `@pluto_relief` | USGS | 01m, 02m, 03m, 04m, 05m, 06m, 10m, 15m, 20m, 30m | 冥王星地形 |

> **注意**：火星、水星、月球和冥王星的最高分辨率数据需要 GMT 6.5 或更高版本。

---

## 二、GMT 中文社区数据集

以下数据集由 GMT 中文社区收集和维护，需手动下载。
整理页面：https://docs.gmt-china.org/latest/dataset/

### 2.1 CN-border：中国国界省界数据

- **说明**：符合中国领土主张的国界、省界、十段线及南海诸岛数据
- **下载地址**：https://github.com/gmt-china/china-geospatial-data/releases
- **文件选择**：Linux/macOS 下载 `china-geospatial-data-UTF8.zip`；Windows 下载 `china-geospatial-data-GB2312.zip`
- **数据文件**：
  - `CN-border-La.gmt`：中国国界、省界、十段线以及南海诸岛
  - `CN-border-L1.gmt`：中国国界、十段线以及南海诸岛（不含省界）
  - `ten-dash-line.gmt`：仅十段线
- **下载命令**：
```bash
wget https://github.com/gmt-china/china-geospatial-data/releases/latest/download/china-geospatial-data-UTF8.zip
unzip china-geospatial-data-UTF8.zip
```
- **用法示例**：`gmt plot CN-border-La.gmt -W0.1p`
- **注意事项**：正式出版刊物中使用需要审图；科研用途可直接使用

### 2.2 CN-faults：中国断层数据

- **说明**：来自中国活断层数据库 (CAFDv2023)，包含中国及邻区主要活动断层
- **下载地址**：https://github.com/gmt-china/china-geospatial-data/releases
- **数据文件**：`CN-faults.gmt`
- **数据属性**：`FN_Ch`(中文断层名)、`FN_En`(英文断层名)、`FZN_Ch`(断裂带中文名)、`AGE`(活动时代)、`RefE`(参考文献)
- **用法示例**：`gmt plot CN-faults.gmt -W1p,red`
- **按属性筛选**：`gmt convert CN-faults.gmt -S"FN_Ch=红河断裂" | gmt plot`

### 2.3 CN-block：中国大陆活动地块数据

- **说明**：中国大陆及周边活动地块划分（王辉等，2003）
- **下载地址**：https://github.com/gmt-china/china-geospatial-data/releases
- **数据文件**：
  - `CN-block-L1.gmt`：一级地块边界
  - `CN-block-L1-deduced.gmt`：一级地块推断边界
  - `CN-block-L2.gmt`：二级地块边界

### 2.4 geo3al：中国及邻区地质图数据

- **说明**：USGS 提供的 1:5,000,000 中国及邻区地质图
- **下载地址**：https://github.com/gmt-china/china-geospatial-data/releases
- **数据文件**：`geo3al.gmt`
- **数据属性**：`TYPE`(岩性)、`GLG`(地质年代)、`GEN_GLG`(计算后的地质年代)
- **推荐色标**：[geoage.cpt](https://docs.gmt-china.org/latest/_downloads/a897756861bc97cf016e193de18e8b53/geoage.cpt)
- **用法示例**：`gmt plot geo3al.gmt -Cgeoage.cpt -aZ="GEN_GLG" -G+z`

### 2.5 PB2002：全球板块边界数据

- **说明**：包含 14 个大板块和 38 个小板块，共 52 个板块的全球板块边界
- **官方网站**：http://peterbird.name/publications/2003_PB2002/2003_PB2002.htm
- **下载方式一（平台边界）**：
  - `wget https://docs.gmt-china.org/latest/_downloads/e53c0ab92a657b49852ac4c3519375c5/PB2002_plates.dig.txt`
- **下载方式二（分段边界）**：
  - `wget https://docs.gmt-china.org/latest/_downloads/75a2dd8fb85f0e6980091005c8f6f06f/PB2002_boundaries.dig.txt`
- **说明**：`plates` 版分 52 段（每板块一边界），`boundaries` 版分 229 段（每板块对一边界）。绘图等效。
- **用法示例**：`gmt plot PB2002_boundaries.dig.txt -W0.5p,red`
- **引用**：Bird, P. (2003). GGG, 4(3). https://doi.org/10.1029/2001GC000252

### 2.6 global_tectonics：全球地质构造数据

- **说明**：包含板块边界、板块、地质块体、海陆边界四种数据
- **官方网站**：https://github.com/dhasterok/global_tectonics
- **数据文件及下载**：
  - 板块边界：`wget https://raw.githubusercontent.com/dhasterok/global_tectonics/master/plates%26provinces/gmt/boundaries.gmt`
  - 板块数据：`wget https://raw.githubusercontent.com/dhasterok/global_tectonics/master/plates%26provinces/gmt/plates.gmt`
  - 地质块体：`wget https://raw.githubusercontent.com/dhasterok/global_tectonics/master/plates%26provinces/gmt/global_gprv.gmt`
  - 海陆边界：`wget https://raw.githubusercontent.com/dhasterok/global_tectonics/master/plates%26provinces/gmt/oc_boundaries.gmt`
- **板块边界类型**：spreading center(扩张中心)、extension zone(拉张带)、subduction zone(俯冲带)、collision zone(碰撞带)、dextral transform(右旋转换)、sinistral transform(左旋转换)、inferred(推断)
- **用法示例**：
```bash
gmt convert boundaries.gmt -S"type=subduction zone" | gmt plot -W0.5p,black
```

### 2.7 GADM：全球行政区划数据库

- **说明**：全球所有国家和地区的国界、省界、市界、区界等多级行政区划
- **主页**：https://gadm.org/
- **下载方式**：
  - 全球数据：https://gadm.org/download_world.html
  - 按国家下载（推荐）：https://gadm.org/download_country_v3.html
- **格式转换**（Shapefile → GMT）：
```bash
ogr2ogr -f OGR_GMT output.gmt input.shp
```
- **注意事项**：
  - 中国数据需下载 China、Hong Kong、Macao、Taiwan 四个地区
  - GADM 的中国国界不符合中国领土主张，正式发表需谨慎
  - 需要 GMT 已链接 GDAL 库

### 2.8 WSM_2025：全球地应力数据

- **说明**：World Stress Map Database Release 2025，包含 100842 条全球地壳应力记录
- **官方网站**：https://www.world-stress-map.org/
- **数据下载**：https://datapub.gfz.de/download/10.5880.WSM.2025.001-Scbwez/
- **数据文件**：`WSM_Database_2025.csv` 和 `WSM_Database_2025.xlsx`
- **格式说明**：https://doi.org/10.48440/wsm.2025.001
- **注意事项**：原始数据含引号包裹的逗号，需预处理后再使用

### 2.9 GSHHG：全球高分辨率海岸线

- **说明**：GMT 内置的全球海岸线数据（也会在 `gmt coast` 中使用）
- **文档**：https://docs.gmt-china.org/latest/dataset/gshhg/
- **使用**：通过 `gmt coast` 的 `-D` 选项选择精度（f/h/i/l/c）

### 2.10 DCW：世界数字图表

- **说明**：Digital Chart of the World，GMT 内置的国界/州界等数据
- **文档**：https://docs.gmt-china.org/latest/dataset/dcw/
- **使用**：通过 `gmt coast` 的 `-E` 选项按国家代码提取国界

---

## 三、其他未整理的地学数据集

以下数据可从原始来源下载，使用 GDAL 的 `ogr2ogr` 或 `gdal_translate` 转换为 GMT 格式。

| 数据集 | 下载地址 | 说明 |
|--------|---------|------|
| 中国区域地表热流 | https://doi.org/10.1016/j.tecto.2019.01.006 | 中国热流数据 |
| 1:100万全国基础地理数据 | https://gmt-china.org/blog/national-geographic-database/ | 全国标准基础地理数据 |
| 美国地质图 | https://mrdata.usgs.gov/geology/state/ | USGS 美国各州地质图 |
| 全球布格重力异常 | https://bgi.obs-mip.fr/grids-and-models-2/ | BGI 布格重力数据 |

---

## 四、数据下载工具参考

### 4.1 使用 wget 下载

```bash
wget <URL> -O <目标文件名>
wget --progress=bar <URL>  # 显示进度条
```

### 4.2 使用 curl 下载

```bash
curl -L <URL> -o <目标文件名>
```

### 4.3 解压文件

```bash
unzip <zip文件>
tar -xzf <tar.gz文件>
```

### 4.4 GDAL 格式转换

Shapefile 转 GMT：
```bash
ogr2ogr -f OGR_GMT output.gmt input.shp
```

GeoTIFF 转 GMT 网格：
```bash
gdal_translate -of GMT input.tif output.grd
```

### 4.5 GMT 数据库目录配置

将自定义数据放入目录（如 `~/GMTDB`），设置环境变量：
```bash
export GMT_DATADIR=~/GMTDB
# 多个目录
export GMT_DATADIR=~/GMTDB/data1,~/GMTDB/data2
# 递归搜索（仅 Linux/macOS）
export GMT_DATADIR=~/GMTDB/
```
