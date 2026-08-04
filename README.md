# PickFrame 图片筛选器

一个**本地运行**的 Windows 图片筛选工具：导入成百上千张照片，用键盘快速浏览、标记喜欢的，最后按格式与质量一键导出。图片只在电脑本地读取和导出，**不会上传**。

> 适合整理相机/手机导出的海量照片、从旅行/活动中挑出满意的成片、清理相册。

---

## ✨ 功能特性

- **快如键盘**：`←`/`→` 翻页，`↑`/`↓`/`空格` 标记，全程无需鼠标
- **大图体验**：鼠标滚轮缩放、按住拖动平移、双击恢复、`F11` 全屏
- **批量管理**：递归导入文件夹，左侧缩略图列表，已选图片橙色高亮
- **灵活导出**：支持保持原格式 / JPEG / PNG / WebP / TIFF / BMP，可调输出质量
- **导出前复核**：先预览已选图片，`↓` 一键移除不满意的再确认
- **格式广泛**：Pillow 全系格式，可选扩展 HEIC/HEIF 与相机 RAW（DNG、CR2/CR3、NEF 等）
- **绝对安全**：只读取原图，导出到独立目录，绝不移动、覆盖或修改原图

---

## 🖥️ 界面总览

![PickFrame 界面示意图](ui_overview.png)

| 区域 | 说明 |
|------|------|
| ① 工具栏 | 导入图片 / 导入文件夹、清除列表、选择导出格式、开始导出 |
| ② 质量与计数 | 调节 JPEG / WebP 输出质量，查看浏览进度与已选数量 |
| ③ 图片列表 | 所有已导入图片，点击跳转，缩略图预览，已选橙色高亮 |
| ④ 查看器 | 大图浏览区，滚轮缩放、拖动平移、双击恢复适合窗口 |
| ⑤ 控制按钮 | 上一张 / 标记为已选 / 下一张 / 全屏查看 / 适合窗口 |
| ⑥ 状态栏 | 当前启用的格式支持与统计信息 |

---

## 🚀 安装与启动

### 环境要求

- Windows 10 / 11
- Python 3.10+（[python.org](https://www.python.org/downloads/) 安装时勾选 *Add Python to PATH*）

### 方法一：一键脚本（推荐）

双击依次运行：

1. `install_dependencies.bat` — 安装基础依赖（Pillow）
2. `start.bat` — 启动程序

> 提示：如需 HEIC/HEIF 与相机 RAW 支持，再双击一次 `install_optional_formats.bat`。

### 方法二：命令行

```bat
cd /d F:\photos_split
py -3 -m pip install -r requirements.txt
py -3 photo_selector.py
```

### 可选格式安装

```bat
install_optional_formats.bat
```

会安装 `pillow-heif`（HEIC/HEIF/AVIF）与 `rawpy`（相机 RAW）。

---

## 📖 使用说明

![PickFrame 操作流程图](workflow.png)

### 1. 导入图片

- 点击工具栏「**导入图片**」选择多个文件，或按 `Ctrl+O`
- 点击「**导入文件夹**」递归导入文件夹及子文件夹内全部图片，或按 `Ctrl+Shift+O`

### 2. 浏览照片

- 按 `←` / `→`（或底部按钮）翻页浏览
- 在图片上**滚动鼠标滚轮**缩放，**按住左键拖动**平移，**双击**恢复适合窗口
- `F11` 进入全屏，全屏下所有筛选操作不变，`Esc` 或 `F11` 退出

### 3. 标记喜欢的

- `↑` 标记当前图片为已选，`↓` 取消标记，`空格` 切换标记状态
- 底部「标记为已选」按钮可点击标记
- 已选图片在左侧列表中以橙色高亮显示，数量实时更新

### 4. 设置格式与质量并导出

- 工具栏选择**导出格式**（保持原格式 / JPEG / PNG / WebP / TIFF / BMP）
- 「输出质量」滑条调节 JPEG / WebP 压缩质量（1–100，默认 92）
- 点击「**导出已选**」或按 `Ctrl+E` 进入复核

### 5. 复核已选

- 在复核界面用方向键逐张检查已选图片
- `↓` 移除不满意的图片，确认无误后点击「**确认导出**」

### 6. 选择目标文件夹

- 选择导出目录完成导出
- 导出目录**不能**与任一原图所在目录相同，程序只会复制或转换到单独目录

---

## ⌨️ 快捷键一览

| 快捷键 | 功能 |
|--------|------|
| `←` / `→` | 上一张 / 下一张 |
| `↑` | 标记当前图片为已选 |
| `↓` | 取消标记（复核界面中为移除该图片） |
| `空格` | 切换标记状态 |
| `Home` | 跳转到第一张 |
| `End` | 跳转到最后一张 |
| `Esc` | 普通窗口：恢复适合窗口；全屏：退出全屏 |
| `Ctrl+O` | 导入图片 |
| `Ctrl+Shift+O` | 导入文件夹 |
| `Ctrl+E` | 导出已选（进入复核） |
| `F11` | 切换全屏查看 |

---

## 🖼️ 支持的格式

### 默认支持（Pillow 可解码）

JPEG/JFIF、PNG、WebP、AVIF、TIFF、BMP、GIF、ICO、PSD、PNM/PPM/PBM/PGM、PCX、QOI 等。动图导入后显示首帧。

### 可选扩展（需运行 `install_optional_formats.bat`）

- **HEIC / HEIF**（iPhone / 现代手机默认格式）
- **相机 RAW**：DNG、CR2/CR3（佳能）、NEF（尼康）、ARW（索尼）、RAF（富士）、RW2（松下）等

### 导出格式

| 格式 | 说明 |
|------|------|
| 保持原格式 | 复制原图，不转换 |
| JPEG / PNG / WebP / TIFF / BMP | 转换导出，质量可调 |

> JPEG / BMP 不支持透明通道，透明区域会使用白色背景填充。

---

## 📤 导出说明

- **原图安全**：程序只会复制或转换到单独目录，绝不会移动、覆盖或修改原图
- **防覆盖**：导出时不会覆盖已有文件；同名文件自动追加 `_2`、`_3` 等编号
- **目录限制**：导出目录不能与任一原图所在目录相同，防止误操作

---

## 📁 项目结构

```
photos_split/
├── photo_selector.py          # 主程序（Tkinter 界面 + 核心逻辑）
├── test_photo_selector.py     # 单元测试（unittest）
├── requirements.txt           # 基础依赖（Pillow）
├── requirements-optional.txt  # 可选依赖（HEIC/RAW）
├── install_dependencies.bat   # 一键安装基础依赖
├── install_optional_formats.bat # 一键安装可选格式支持
├── start.bat                  # 一键启动
├── ui_overview.png            # 界面示意图
└── workflow.png               # 操作流程图
```

---

## 🧪 测试

项目内置单元测试（`unittest`）：

```bat
py -3 -m unittest test_photo_selector
```

覆盖自然排序、递归发现图片、导出路径去重、原图安全校验等核心逻辑。

---

## 🔒 隐私声明

程序**没有任何网络上传逻辑**。图片仅在本地读取与导出。唯一联网场景是执行依赖安装脚本时连接 Python 软件包源下载依赖。

---

## 🛠️ 技术栈

- Python 3 + [Tkinter](https://docs.python.org/3/library/tkinter.html)（界面）
- [Pillow](https://python-pillow.org/)（图片解码 / 转换）
- 可选：[pillow-heif](https://github.com/strukturag/libheif) / [rawpy](https://github.com/letmaik/rawpy)（HEIC / RAW）

---

## 📜 许可

本项目为个人工具，目前未指定开源许可。如需开源发布，建议补充 `LICENSE` 文件后使用。
