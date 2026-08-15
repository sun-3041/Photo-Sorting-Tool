# PickFrame v1.0.2

PickFrame 是一款本地运行的 Windows 图片筛选工具。本发行版已经封装 Python、Pillow、HEIC/HEIF 和相机 RAW 图片支持，无需安装 Python 或其他依赖。

PickFrame is a local Windows photo filtering tool. This release bundles Python, Pillow, HEIC/HEIF, and camera RAW support, so no Python installation or additional dependencies are required.

## 本次更新 Changes in this release

- 导入图片快捷键改为 `Ctrl+I`。
- 导入文件夹快捷键改为 `Ctrl+O`。
- 两个快捷键均不区分字母大小写，并可在按钮、下拉框、图片列表和查看器获得焦点时使用。
- Changed **Import Files** to `Ctrl+I` and **Import Folder** to `Ctrl+O`.
- Both shortcuts are case-insensitive and work while buttons, comboboxes, the image list, or the viewer has focus.

## 下载版本 Packages

### 单文件版 One-file

文件：`PickFrame-v1.0.2-Windows-x64-OneFile.exe`

- 下载后直接双击运行，只需要保留这一个文件。
- 适合发送给朋友或保存在 U 盘中。
- 每次启动时需要解压到 Windows 临时目录，因此启动速度比文件夹版稍慢。

- Double-click the downloaded file; it is the only file you need to keep.
- Best for sharing or carrying on a USB drive.
- Starts a little slower because it extracts to the Windows temporary folder each time.

### 文件夹版 Portable folder

文件：`PickFrame-v1.0.2-Windows-x64-Portable.zip`

- 先完整解压 ZIP，再双击文件夹内的 `PickFrame.exe`。
- 启动更快，推荐经常使用或需要 HEIC、RAW 格式的用户选择。
- `PickFrame.exe` 依赖同目录中的 `_internal` 文件夹，不能只复制 `.exe`。

- Extract the complete ZIP, then double-click `PickFrame.exe` inside the folder.
- Starts faster and is recommended for frequent use or HEIC/RAW workflows.
- `PickFrame.exe` needs the adjacent `_internal` folder; do not copy the EXE by itself.

## 系统要求 Requirements

- 64 位 Windows 10 或 Windows 11
- 无需安装 Python
- No Python installation required

## 功能 Features

- `←` / `→` 浏览上一张或下一张图片
- `↑` 选中，`↓` 取消选中，`Space` 切换选中状态
- 鼠标滚轮缩放、拖动平移、`F11` 全屏筛选
- 导出前复核已选图片
- 保留原文件名或按 `001`、`002`…顺序编号
- 保持原格式，或转换为 JPEG、PNG、WebP、TIFF、BMP
- 支持常见图片、HEIC/HEIF 和相机 RAW 格式

## 原图与缓存 Source safety and cache

程序只读取导入的原图，导出到另外选择的文件夹，不会移动、修改或覆盖原图。浏览缓存只保存在内存中，清空列表或关闭程序后会自动释放，不会长期占用磁盘空间。

The app only reads imported originals and exports to a separate folder. It never moves, modifies, or overwrites source files. The browsing cache is memory-only and is released when the list is cleared or the app exits.
