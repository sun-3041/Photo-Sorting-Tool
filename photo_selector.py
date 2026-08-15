from __future__ import annotations

import ctypes
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
import math
import os
import queue
import re
import shutil
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Iterable

from PIL import Image, ImageOps, ImageTk


APP_NAME = "PickFrame 图片筛选器"

STANDARD_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".dib",
    ".gif",
    ".heic",
    ".heif",
    ".ico",
    ".jfif",
    ".jpe",
    ".jpeg",
    ".jpg",
    ".pbm",
    ".pcx",
    ".pgm",
    ".png",
    ".pnm",
    ".ppm",
    ".psd",
    ".qoi",
    ".tif",
    ".tiff",
    ".webp",
}
RAW_EXTENSIONS = {
    ".3fr",
    ".arw",
    ".cr2",
    ".cr3",
    ".dcr",
    ".dng",
    ".erf",
    ".kdc",
    ".mef",
    ".mos",
    ".mrw",
    ".nef",
    ".nrw",
    ".orf",
    ".pef",
    ".raf",
    ".raw",
    ".rw2",
    ".sr2",
    ".srf",
    ".srw",
}
SUPPORTED_EXTENSIONS = STANDARD_EXTENSIONS | RAW_EXTENSIONS

EXPORT_FORMATS = {
    "保持原格式": (None, None),
    "JPEG": (".jpg", "JPEG"),
    "PNG": (".png", "PNG"),
    "WEBP": (".webp", "WEBP"),
    "TIFF": (".tif", "TIFF"),
    "BMP": (".bmp", "BMP"),
}

EXPORT_NAMING_MODES = (
    "保留原文件名",
    "顺序编号 001...",
)

COLORS = {
    "window": "#eef0f3",
    "surface": "#ffffff",
    "surface_alt": "#f6f7f9",
    "toolbar": "#20242b",
    "toolbar_text": "#f8fafc",
    "canvas": "#14171c",
    "canvas_text": "#b9c0ca",
    "text": "#20242b",
    "muted": "#68717d",
    "border": "#d7dbe1",
    "accent": "#2563eb",
    "accent_hover": "#1d4ed8",
    "selected": "#f59e0b",
    "success": "#15803d",
    "danger": "#b42318",
}


def _register_optional_decoders() -> tuple[bool, bool]:
    heif_available = False
    raw_available = False

    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
        if hasattr(pillow_heif, "register_avif_opener"):
            pillow_heif.register_avif_opener()
        heif_available = True
    except (AttributeError, ImportError, RuntimeError):
        pass

    try:
        import rawpy  # noqa: F401

        raw_available = True
    except ImportError:
        pass

    return heif_available, raw_available


HEIF_AVAILABLE, RAW_AVAILABLE = _register_optional_decoders()


def path_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(path))


def natural_sort_key(path: Path) -> list[object]:
    parts = re.split(r"(\d+)", str(path).casefold())
    return [int(part) if part.isdigit() else part for part in parts]


def is_supported_image(path: Path) -> bool:
    return path.is_file() and path.suffix.casefold() in SUPPORTED_EXTENSIONS


def discover_images(folder: Path) -> list[Path]:
    try:
        files = [path for path in folder.rglob("*") if is_supported_image(path)]
    except OSError:
        files = []
    return sorted(files, key=natural_sort_key)


def load_image(path: Path) -> Image.Image:
    if path.suffix.casefold() in RAW_EXTENSIONS:
        if not RAW_AVAILABLE:
            raise RuntimeError("打开相机 RAW 文件需要安装 rawpy")

        import rawpy

        with rawpy.imread(str(path)) as raw:
            array = raw.postprocess(use_camera_wb=True, output_bps=8)
        return Image.fromarray(array, "RGB")

    with Image.open(path) as source:
        try:
            source.seek(0)
        except EOFError:
            pass
        corrected = ImageOps.exif_transpose(source)
        corrected.load()
        result = corrected.copy()
        result.info = corrected.info.copy()
        return result


def _flatten_transparency(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, "white")
    background.alpha_composite(rgba)
    return background.convert("RGB")


def prepare_for_export(image: Image.Image, pil_format: str) -> Image.Image:
    if pil_format in {"JPEG", "BMP"}:
        if image.mode in {"RGBA", "LA"} or (
            image.mode == "P" and "transparency" in image.info
        ):
            return _flatten_transparency(image)
        if image.mode not in {"RGB", "L"}:
            return image.convert("RGB")
    elif pil_format == "WEBP":
        if image.mode in {"RGBA", "LA"} or (
            image.mode == "P" and "transparency" in image.info
        ):
            return image.convert("RGBA")
        if image.mode != "RGB":
            return image.convert("RGB")
    elif pil_format == "PNG" and image.mode == "CMYK":
        return image.convert("RGB")
    return image


def unique_output_path(folder: Path, stem: str, suffix: str) -> Path:
    candidate = folder / f"{stem}{suffix}"
    index = 2
    while candidate.exists():
        candidate = folder / f"{stem}_{index}{suffix}"
        index += 1
    return candidate


def export_stem(source: Path, index: int, naming_mode: str) -> str:
    if naming_mode == "顺序编号 001...":
        return f"{index:03d}"
    return source.stem


def export_destination_matches_source_folder(destination: Path, sources: Iterable[Path]) -> bool:
    return any(path_key(destination) == path_key(source.parent) for source in sources)


def export_image(source: Path, destination: Path, output_format: str, quality: int) -> None:
    if output_format == "保持原格式":
        shutil.copy2(source, destination)
        return

    _, pil_format = EXPORT_FORMATS[output_format]
    if pil_format is None:
        raise ValueError(f"未知导出格式：{output_format}")

    image = load_image(source)
    image = prepare_for_export(image, pil_format)
    save_options: dict[str, object] = {}

    if pil_format == "JPEG":
        save_options.update(quality=quality, optimize=True, progressive=True)
    elif pil_format == "WEBP":
        save_options.update(quality=quality, method=6)
    elif pil_format == "PNG":
        save_options.update(optimize=True)
    elif pil_format == "TIFF":
        save_options.update(compression="tiff_deflate")

    icc_profile = image.info.get("icc_profile")
    if icc_profile and pil_format in {"JPEG", "PNG", "WEBP", "TIFF"}:
        save_options["icc_profile"] = icc_profile

    exif = image.getexif()
    if exif and pil_format in {"JPEG", "WEBP", "TIFF"}:
        save_options["exif"] = exif.tobytes()

    image.save(destination, pil_format, **save_options)


class ExportProgressDialog(tk.Toplevel):
    def __init__(self, parent: tk.Tk, total: int, cancel_event: threading.Event) -> None:
        super().__init__(parent)
        self.cancel_event = cancel_event
        self.title("正在导出")
        self.geometry("440x150")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.cancel)

        container = ttk.Frame(self, padding=20)
        container.pack(fill="both", expand=True)

        self.label = ttk.Label(container, text=f"正在准备导出 0 / {total}")
        self.label.pack(anchor="w", pady=(0, 12))
        self.progress = ttk.Progressbar(container, maximum=max(total, 1), mode="determinate")
        self.progress.pack(fill="x")
        self.cancel_button = ttk.Button(container, text="取消", command=self.cancel)
        self.cancel_button.pack(anchor="e", pady=(14, 0))

        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.grab_set()

    def set_progress(self, done: int, total: int, filename: str) -> None:
        self.progress.configure(value=done, maximum=max(total, 1))
        self.label.configure(text=f"正在导出 {done} / {total}    {filename}")

    def cancel(self) -> None:
        self.cancel_event.set()
        self.cancel_button.configure(text="正在取消…", state="disabled")


class PhotoSelectorApp:
    MIN_SCALE = 0.02
    MAX_SCALE = 16.0
    IMAGE_CACHE_ITEMS = 3
    IMAGE_CACHE_BYTES = 128 * 1024 * 1024
    SHIFT_MASK = 0x0001
    WINDOWS_O_KEYCODE = 0x4F
    IMPORT_FOLDER_SHORTCUTS = (
        "<Control-Shift-KeyPress-o>",
        "<Control-Shift-KeyPress-O>",
    )

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1360x860")
        self.root.minsize(920, 620)
        self.root.configure(bg=COLORS["window"])

        self.paths: list[Path] = []
        self.selected: set[str] = set()
        self.review_mode = False
        self.failed: set[str] = set()
        self.current_index = -1
        self.current_image: Image.Image | None = None
        self.current_photo: ImageTk.PhotoImage | None = None
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.fit_mode = True
        self.is_fullscreen = False
        self._interactive_render_job: str | None = None
        self._quality_render_job: str | None = None
        self._fit_render_job: str | None = None
        self.drag_start: tuple[int, int, float, float] | None = None
        self.export_directory: Path | None = None
        self._tree_syncing = False
        self._canvas_resize_job: str | None = None
        self._export_queue: queue.Queue[tuple] | None = None
        self._export_dialog: ExportProgressDialog | None = None
        self._export_cancel: threading.Event | None = None
        self._option_focus_job: str | None = None
        self._image_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="photo-decode")
        self._image_cache: OrderedDict[str, Image.Image] = OrderedDict()
        self._image_cache_bytes = 0
        self._image_cache_lock = threading.RLock()
        self._pending_image_loads: dict[str, Future[Image.Image]] = {}
        self._image_load_generation = 0
        self._image_queue: queue.Queue[tuple] = queue.Queue()
        self._image_poll_job: str | None = None

        self.export_format = tk.StringVar(value="JPEG")
        self.export_naming = tk.StringVar(value=EXPORT_NAMING_MODES[0])
        self.export_quality = tk.IntVar(value=92)
        self.counter_text = tk.StringVar(value="0 张图片 · 已选 0 张")
        self.image_info_text = tk.StringVar(value="未载入图片")

        self._configure_styles()
        self._build_ui()
        self._bind_events()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._image_poll_job = self.root.after(30, self._poll_image_queue)
        self._update_actions()
        self.root.after_idle(self._draw_empty_state)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        base_font = ("Microsoft YaHei UI", 10)
        self.root.option_add("*Font", base_font)

        style.configure("TFrame", background=COLORS["window"])
        style.configure("Surface.TFrame", background=COLORS["surface"])
        style.configure("Toolbar.TFrame", background=COLORS["toolbar"])
        style.configure(
            "ToolbarTitle.TLabel",
            background=COLORS["toolbar"],
            foreground=COLORS["toolbar_text"],
            font=("Microsoft YaHei UI", 14, "bold"),
        )
        style.configure(
            "ToolbarMeta.TLabel",
            background=COLORS["toolbar"],
            foreground="#c9d0da",
            font=("Microsoft YaHei UI", 9),
        )
        style.configure(
            "SidebarTitle.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            font=("Microsoft YaHei UI", 11, "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background=COLORS["surface"],
            foreground=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
        )
        style.configure(
            "Status.TLabel",
            background=COLORS["surface_alt"],
            foreground=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
        )
        style.configure(
            "TButton",
            padding=(12, 7),
            background="#f4f5f7",
            foreground=COLORS["text"],
            bordercolor=COLORS["border"],
            lightcolor="#f4f5f7",
            darkcolor="#f4f5f7",
        )
        style.map("TButton", background=[("active", "#e7e9ed"), ("disabled", "#f0f1f3")])
        style.configure(
            "Toolbar.TButton",
            padding=(12, 7),
            background="#303640",
            foreground=COLORS["toolbar_text"],
            bordercolor="#454c57",
            lightcolor="#303640",
            darkcolor="#303640",
        )
        style.map(
            "Toolbar.TButton",
            background=[("active", "#3b424e"), ("disabled", "#292e36")],
            foreground=[("disabled", "#7e8794")],
        )
        style.configure(
            "Primary.TButton",
            padding=(15, 8),
            background=COLORS["accent"],
            foreground="white",
            bordercolor=COLORS["accent"],
            lightcolor=COLORS["accent"],
            darkcolor=COLORS["accent"],
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[("active", COLORS["accent_hover"]), ("disabled", "#9aa6b8")],
            foreground=[("disabled", "#e4e7eb")],
        )
        style.configure(
            "Treeview",
            background=COLORS["surface"],
            fieldbackground=COLORS["surface"],
            foreground=COLORS["text"],
            rowheight=32,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=COLORS["surface_alt"],
            foreground=COLORS["muted"],
            font=("Microsoft YaHei UI", 9),
            padding=(6, 7),
            borderwidth=0,
        )
        style.map("Treeview", background=[("selected", "#dbe8ff")], foreground=[("selected", "#173d79")])

    def _build_ui(self) -> None:
        toolbar = ttk.Frame(self.root, style="Toolbar.TFrame", padding=(18, 12))
        self.toolbar = toolbar
        toolbar.pack(side="top", fill="x")

        title_group = ttk.Frame(toolbar, style="Toolbar.TFrame")
        title_group.pack(side="left", padx=(0, 28))
        ttk.Label(title_group, text="PickFrame", style="ToolbarTitle.TLabel").pack(anchor="w")
        ttk.Label(title_group, text="图片筛选器", style="ToolbarMeta.TLabel").pack(anchor="w")

        ttk.Button(toolbar, text="导入图片", style="Toolbar.TButton", command=self.import_files).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(toolbar, text="导入文件夹", style="Toolbar.TButton", command=self.import_folder).pack(
            side="left", padx=(0, 8)
        )
        self.clear_button = ttk.Button(
            toolbar, text="清空列表", style="Toolbar.TButton", command=self.clear_all
        )
        self.clear_button.pack(side="left")

        export_group = ttk.Frame(toolbar, style="Toolbar.TFrame")
        export_group.pack(side="right")
        ttk.Label(export_group, text="导出格式", style="ToolbarMeta.TLabel").pack(
            side="left", padx=(0, 7)
        )
        self.format_combo = ttk.Combobox(
            export_group,
            textvariable=self.export_format,
            values=list(EXPORT_FORMATS),
            state="readonly",
            width=11,
        )
        self.format_combo.pack(side="left", padx=(0, 8))
        self.format_combo.bind("<<ComboboxSelected>>", self._on_export_format_selected)
        self.format_combo.bind("<ButtonPress-1>", self._cancel_option_focus_restore, add="+")
        self.export_button = ttk.Button(
            export_group, text="导出已选", style="Primary.TButton", command=self.start_export
        )
        self.export_button.pack(side="left")

        quality_group = ttk.Frame(self.root, style="Surface.TFrame", padding=(18, 8))
        self.quality_group = quality_group
        quality_group.pack(side="top", fill="x")
        ttk.Label(quality_group, text="输出质量", style="Muted.TLabel").pack(side="left")
        self.quality_scale = ttk.Scale(
            quality_group,
            from_=60,
            to=100,
            variable=self.export_quality,
            orient="horizontal",
            length=150,
            command=self._on_quality_changed,
        )
        self.quality_scale.pack(side="left", padx=(10, 8))
        self.quality_label = ttk.Label(quality_group, text="92", style="Muted.TLabel", width=3)
        self.quality_label.pack(side="left")
        ttk.Separator(quality_group, orient="vertical").pack(side="left", fill="y", padx=18)
        ttk.Label(quality_group, text="命名方式", style="Muted.TLabel").pack(side="left")
        self.naming_combo = ttk.Combobox(
            quality_group,
            textvariable=self.export_naming,
            values=EXPORT_NAMING_MODES,
            state="readonly",
            width=15,
        )
        self.naming_combo.pack(side="left", padx=(10, 0))
        self.naming_combo.bind("<<ComboboxSelected>>", self._on_export_format_selected)
        self.naming_combo.bind("<ButtonPress-1>", self._cancel_option_focus_restore, add="+")
        ttk.Separator(quality_group, orient="vertical").pack(side="left", fill="y", padx=18)
        ttk.Label(quality_group, textvariable=self.counter_text, style="Muted.TLabel").pack(side="left")

        self.review_status = tk.Label(quality_group, text="正在复核已选图片", bg="#fff3d6", fg="#875600", padx=10, pady=4)
        self.exit_review_button = ttk.Button(quality_group, text="退出复核", command=self.exit_review)
        workspace = ttk.Panedwindow(self.root, orient="horizontal")
        self.workspace = workspace
        workspace.pack(fill="both", expand=True)

        sidebar = ttk.Frame(workspace, style="Surface.TFrame", width=300)
        self.sidebar = sidebar
        viewer = ttk.Frame(workspace, style="Surface.TFrame")
        workspace.add(sidebar, weight=0)
        workspace.add(viewer, weight=1)

        sidebar_header = ttk.Frame(sidebar, style="Surface.TFrame", padding=(14, 13, 10, 8))
        sidebar_header.pack(fill="x")
        ttk.Label(sidebar_header, text="图片列表", style="SidebarTitle.TLabel").pack(side="left")
        self.selection_badge = tk.Label(
            sidebar_header,
            text="已选 0",
            bg="#fff3d6",
            fg="#875600",
            padx=8,
            pady=3,
            font=("Microsoft YaHei UI", 9),
        )
        self.selection_badge.pack(side="right")

        tree_frame = ttk.Frame(sidebar, style="Surface.TFrame")
        tree_frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("selected", "folder"),
            show="tree headings",
            selectmode="browse",
        )
        self.tree.heading("#0", text="文件名", anchor="w")
        self.tree.heading("selected", text="状态", anchor="center")
        self.tree.heading("folder", text="来源", anchor="w")
        self.tree.column("#0", minwidth=150, width=175, stretch=True)
        self.tree.column("selected", minwidth=54, width=54, stretch=False, anchor="center")
        self.tree.column("folder", minwidth=70, width=80, stretch=False)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        workspace.sashpos(0, 300)

        canvas_frame = tk.Frame(viewer, bg=COLORS["canvas"], highlightthickness=0)
        canvas_frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(
            canvas_frame,
            bg=COLORS["canvas"],
            highlightthickness=0,
            cursor="arrow",
        )
        self.canvas.pack(fill="both", expand=True)

        controls = ttk.Frame(viewer, style="Surface.TFrame", padding=(14, 10))
        self.controls = controls
        controls.pack(fill="x")
        self.previous_button = ttk.Button(controls, text="←  上一张", command=lambda: self.navigate(-1))
        self.previous_button.pack(side="left")
        self.select_button = ttk.Button(controls, text="标记为已选", command=self.toggle_selected)
        self.select_button.pack(side="left", padx=8)
        self.next_button = ttk.Button(controls, text="下一张  →", command=lambda: self.navigate(1))
        self.next_button.pack(side="left")
        self.fullscreen_button = ttk.Button(controls, text="全屏查看", command=self.toggle_fullscreen)
        self.fullscreen_button.pack(side="right")
        ttk.Button(controls, text="适合窗口", command=self.fit_image).pack(side="right", padx=(0, 8))
        ttk.Label(controls, textvariable=self.image_info_text, style="Muted.TLabel").pack(
            side="right", padx=(0, 12)
        )

        status = ttk.Frame(self.root, style="Surface.TFrame", padding=(14, 7))
        self.status = status
        status.pack(side="bottom", fill="x")
        decoder_parts = ["JPEG / PNG / WebP / AVIF / TIFF / BMP / GIF"]
        decoder_parts.append("HEIC 可用" if HEIF_AVAILABLE else "HEIC 需可选组件")
        decoder_parts.append("RAW 可用" if RAW_AVAILABLE else "RAW 需可选组件")
        ttk.Label(status, text=" · ".join(decoder_parts), style="Status.TLabel").pack(side="left")

    def _bind_events(self) -> None:
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_selected)
        self.tree.bind("<Left>", lambda event: self._keyboard_action(event, lambda: self.navigate(-1)))
        self.tree.bind("<Right>", lambda event: self._keyboard_action(event, lambda: self.navigate(1)))
        self.tree.bind("<Up>", lambda event: self._keyboard_action(event, self.select_current))
        self.tree.bind("<Down>", lambda event: self._keyboard_action(event, self.deselect_current))
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", lambda event: self._zoom_at(event.x, event.y, 1.12))
        self.canvas.bind("<Button-5>", lambda event: self._zoom_at(event.x, event.y, 1 / 1.12))
        self.canvas.bind("<ButtonPress-1>", self._start_pan)
        self.canvas.bind("<B1-Motion>", self._pan)
        self.canvas.bind("<ButtonRelease-1>", self._end_pan)
        self.canvas.bind("<Double-Button-1>", lambda _event: self.fit_image())

        self.root.bind("<Left>", lambda event: self._keyboard_action(event, lambda: self.navigate(-1)))
        self.root.bind("<Right>", lambda event: self._keyboard_action(event, lambda: self.navigate(1)))
        self.root.bind("<Up>", lambda event: self._keyboard_action(event, self.select_current))
        self.root.bind("<Down>", lambda event: self._keyboard_action(event, self.deselect_current))
        self.root.bind("<space>", lambda event: self._keyboard_action(event, self.toggle_selected))
        self.root.bind("<Home>", lambda event: self._keyboard_action(event, lambda: self.set_current(0)))
        self.root.bind(
            "<End>", lambda event: self._keyboard_action(event, lambda: self.set_current(len(self.paths) - 1))
        )
        self.root.bind("<Escape>", lambda event: self._keyboard_action(event, self._handle_escape))
        self.root.bind("<F11>", lambda event: self._keyboard_action(event, self.toggle_fullscreen))
        for sequence in self.IMPORT_FOLDER_SHORTCUTS:
            self.root.bind(sequence, self._on_import_folder_shortcut)
        self.root.bind("<Control-KeyPress>", self._on_import_shortcut)
        self.root.bind("<Control-e>", lambda _event: self.start_export())
        self.root.bind("<Button-1>", self._on_root_click, add="+")
        self._bind_photo_shortcuts_to_controls(self.root)

    def toggle_fullscreen(self) -> None:
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self) -> None:
        if self.is_fullscreen:
            return
        self.is_fullscreen = True
        self.root.attributes("-fullscreen", True)
        self.toolbar.pack_forget()
        self.quality_group.pack_forget()
        self.status.pack_forget()
        self.controls.pack_forget()
        if str(self.sidebar) in self.workspace.panes():
            self.workspace.forget(self.sidebar)
        self.fullscreen_button.configure(text="退出全屏")
        self.root.after_idle(self._finish_fullscreen_layout)

    def exit_fullscreen(self) -> None:
        if not self.is_fullscreen:
            return
        self.is_fullscreen = False
        self.root.attributes("-fullscreen", False)
        self.toolbar.pack(side="top", fill="x", before=self.workspace)
        self.quality_group.pack(side="top", fill="x", before=self.workspace)
        if str(self.sidebar) not in self.workspace.panes():
            self.workspace.insert(0, self.sidebar, weight=0)
        self.controls.pack(fill="x")
        self.status.pack(side="bottom", fill="x")
        self.fullscreen_button.configure(text="全屏查看")
        self.root.after_idle(self._finish_fullscreen_layout)

    def _finish_fullscreen_layout(self) -> None:
        self.root.update_idletasks()
        if not self.is_fullscreen and str(self.sidebar) in self.workspace.panes():
            self.workspace.sashpos(0, 300)
        if self.current_image is not None:
            self.fit_image()
        else:
            self._draw_empty_state()
        self.canvas.focus_set()

    def _handle_escape(self) -> None:
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.fit_image()

    def _keyboard_action(self, event: tk.Event, action) -> str | None:
        action()
        return "break"

    def _on_import_shortcut(self, event: tk.Event) -> str | None:
        if not self._is_import_o_key(event):
            return None
        if event.state & self.SHIFT_MASK:
            return self._on_import_folder_shortcut(event)
        self.import_files()
        return "break"

    def _on_import_folder_shortcut(self, event: tk.Event) -> str | None:
        if not self._is_import_o_key(event):
            return None
        self.import_folder()
        return "break"

    def _is_import_o_key(self, event: tk.Event) -> bool:
        keysym = getattr(event, "keysym", "")
        keycode = getattr(event, "keycode", None)
        return keysym.casefold() == "o" or keycode == self.WINDOWS_O_KEYCODE

    def _bind_photo_shortcuts_to_controls(self, parent: tk.Misc) -> None:
        shortcuts = (
            ("<Left>", lambda: self.navigate(-1)),
            ("<Right>", lambda: self.navigate(1)),
            ("<Up>", self.select_current),
            ("<Down>", self.deselect_current),
            ("<space>", self.toggle_selected),
        )
        for widget in parent.winfo_children():
            for sequence in self.IMPORT_FOLDER_SHORTCUTS:
                widget.bind(sequence, self._on_import_folder_shortcut, add="+")
            widget.bind("<Control-KeyPress>", self._on_import_shortcut, add="+")
            for sequence, action in shortcuts:
                widget.bind(
                    sequence,
                    lambda event, callback=action: self._keyboard_action(event, callback),
                )
            self._bind_photo_shortcuts_to_controls(widget)

    def _on_quality_changed(self, value: str) -> None:
        self.quality_label.configure(text=str(round(float(value))))

    def _on_export_format_selected(self, _event: tk.Event) -> None:
        self._schedule_option_focus_restore(80)

    def _cancel_option_focus_restore(self, _event: tk.Event | None = None) -> None:
        if self._option_focus_job is not None:
            self.root.after_cancel(self._option_focus_job)
            self._option_focus_job = None

    def _schedule_option_focus_restore(self, delay_ms: int = 0) -> None:
        self._cancel_option_focus_restore()
        self._option_focus_job = self.root.after(delay_ms, self._restore_canvas_focus)

    def _restore_canvas_focus(self) -> None:
        self._option_focus_job = None
        self.canvas.focus_force()

    def _on_root_click(self, event: tk.Event) -> None:
        focused = self.root.focus_get()
        option_widgets = (self.format_combo, self.naming_combo)
        if focused not in option_widgets or event.widget in option_widgets:
            return
        self._cancel_option_focus_restore()
        self.canvas.focus_force()

    def import_files(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS))
        names = filedialog.askopenfilenames(
            parent=self.root,
            title="选择图片",
            filetypes=[("支持的图片", patterns), ("所有文件", "*.*")],
        )
        if names:
            self._add_paths(Path(name) for name in names)

    def import_folder(self) -> None:
        folder_name = filedialog.askdirectory(parent=self.root, title="选择图片文件夹")
        if not folder_name:
            return
        folder = Path(folder_name)
        self.root.configure(cursor="watch")
        self.root.update_idletasks()
        images = discover_images(folder)
        self.root.configure(cursor="")
        if not images:
            messagebox.showinfo("未找到图片", "所选文件夹及其子文件夹中没有可导入的图片。", parent=self.root)
            return
        self._add_paths(images)

    def _add_paths(self, paths: Iterable[Path]) -> None:
        existing = {path_key(path) for path in self.paths}
        added: list[Path] = []
        for path in paths:
            try:
                normalized = path.resolve()
            except OSError:
                normalized = path.absolute()
            key = path_key(normalized)
            if key not in existing and normalized.suffix.casefold() in SUPPORTED_EXTENSIONS:
                existing.add(key)
                added.append(normalized)

        if not added:
            return

        previous_path = self.paths[self.current_index] if self.current_index >= 0 else None
        self.paths.extend(added)
        self.paths.sort(key=natural_sort_key)
        self._rebuild_tree()

        target = previous_path if previous_path is not None else added[0]
        try:
            target_index = self.paths.index(target)
        except ValueError:
            target_index = 0
        self.set_current(target_index, force=True)

    def _rebuild_tree(self) -> None:
        self._tree_syncing = True
        self.tree.delete(*self.tree.get_children())
        self.tree.heading("#0", text="已选图片" if self.review_mode else "文件名")
        for index, path in enumerate(self.paths):
            key = path_key(path)
            if self.review_mode and key not in self.selected:
                continue
            if key in self.failed:
                state = "不可读"
            elif key in self.selected:
                state = "已选"
            else:
                state = ""
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                text=path.name,
                values=(state, path.parent.name),
            )
        self._tree_syncing = False
        self._update_actions()

    def _on_tree_selected(self, _event: tk.Event) -> None:
        if self._tree_syncing:
            return
        selection = self.tree.selection()
        if selection:
            self.set_current(int(selection[0]))

    @staticmethod
    def _image_cache_weight(image: Image.Image) -> int:
        return image.width * image.height * max(len(image.getbands()), 1)

    def _get_cached_image(self, key: str) -> Image.Image | None:
        with self._image_cache_lock:
            image = self._image_cache.get(key)
            if image is not None:
                self._image_cache.move_to_end(key)
            return image

    def _cache_image(self, key: str, image: Image.Image) -> None:
        weight = self._image_cache_weight(image)
        if weight > self.IMAGE_CACHE_BYTES:
            return
        with self._image_cache_lock:
            previous = self._image_cache.pop(key, None)
            if previous is not None:
                self._image_cache_bytes -= self._image_cache_weight(previous)
            while self._image_cache and (
                len(self._image_cache) >= self.IMAGE_CACHE_ITEMS
                or self._image_cache_bytes + weight > self.IMAGE_CACHE_BYTES
            ):
                _, removed = self._image_cache.popitem(last=False)
                self._image_cache_bytes -= self._image_cache_weight(removed)
            self._image_cache[key] = image
            self._image_cache_bytes += weight

    def _clear_image_cache(self) -> None:
        with self._image_cache_lock:
            self._image_cache.clear()
            self._image_cache_bytes = 0

    def _neighbor_indices(self, index: int, preferred_direction: int = 1) -> list[int]:
        if not self.paths:
            return []
        if self.review_mode:
            indices = self._selected_indices()
            if index not in indices or len(indices) < 2:
                return []
            position = indices.index(index)
            previous_index = indices[(position - 1) % len(indices)]
            next_index = indices[(position + 1) % len(indices)]
        else:
            if len(self.paths) < 2:
                return []
            previous_index = (index - 1) % len(self.paths)
            next_index = (index + 1) % len(self.paths)
        candidates = (
            (previous_index, next_index) if preferred_direction < 0 else (next_index, previous_index)
        )
        return list(dict.fromkeys(candidate for candidate in candidates if candidate != index))

    def _cancel_stale_image_loads(self, keep_keys: set[str]) -> None:
        for key, future in list(self._pending_image_loads.items()):
            if key in keep_keys:
                continue
            if future.cancel():
                self._pending_image_loads.pop(key, None)

    def _request_image_load(self, path: Path) -> None:
        key = path_key(path)
        if self._get_cached_image(key) is not None:
            return
        pending = self._pending_image_loads.get(key)
        if pending is not None:
            if pending.cancelled():
                self._pending_image_loads.pop(key, None)
            else:
                return
        generation = self._image_load_generation
        future = self._image_executor.submit(load_image, path)
        self._pending_image_loads[key] = future
        future.add_done_callback(
            lambda completed, image_key=key, image_path=path, load_generation=generation: self._deliver_image_load(
                image_key, image_path, load_generation, completed
            )
        )

    def _deliver_image_load(
        self,
        key: str,
        path: Path,
        generation: int,
        future: Future[Image.Image],
    ) -> None:
        self._image_queue.put((key, path, generation, future))

    def _poll_image_queue(self) -> None:
        self._image_poll_job = None
        while True:
            try:
                key, path, generation, future = self._image_queue.get_nowait()
            except queue.Empty:
                break
            self._complete_image_load(key, path, generation, future)
        try:
            self._image_poll_job = self.root.after(30, self._poll_image_queue)
        except tk.TclError:
            self._image_poll_job = None

    def _complete_image_load(
        self,
        key: str,
        path: Path,
        generation: int,
        future: Future[Image.Image],
    ) -> None:
        if self._pending_image_loads.get(key) is future:
            self._pending_image_loads.pop(key, None)
        if generation != self._image_load_generation or future.cancelled():
            return
        try:
            image = future.result()
        except Exception as exc:
            if any(path_key(candidate) == key for candidate in self.paths):
                self.failed.add(key)
            if 0 <= self.current_index < len(self.paths) and path_key(self.paths[self.current_index]) == key:
                self.current_image = None
                self._show_load_error(path, str(exc))
                self._update_actions()
            return

        self._cache_image(key, image)
        self.failed.discard(key)
        if 0 <= self.current_index < len(self.paths) and path_key(self.paths[self.current_index]) == key:
            self.current_image = image
            self.fit_mode = True
            self._schedule_fit_render(fast=True)
            self._refresh_tree_row(self.current_index)
            self._update_actions()

    def _schedule_image_loads(self, index: int, preferred_direction: int = 1) -> None:
        if index < 0 or index >= len(self.paths):
            return
        neighbor_indices = self._neighbor_indices(index, preferred_direction)
        keep_keys = {path_key(self.paths[index])}
        keep_keys.update(path_key(self.paths[neighbor]) for neighbor in neighbor_indices)
        self._cancel_stale_image_loads(keep_keys)
        self._request_image_load(self.paths[index])
        for neighbor in neighbor_indices:
            self._request_image_load(self.paths[neighbor])

    def set_current(self, index: int, force: bool = False, preload_direction: int = 1) -> None:
        if not self.paths:
            return
        index = max(0, min(index, len(self.paths) - 1))
        if index == self.current_index and not force:
            return

        self._cancel_interactive_render()
        self._cancel_scheduled_fit()
        self.current_index = index
        path = self.paths[index]
        key = path_key(path)
        cached = self._get_cached_image(key)
        if cached is not None:
            self.current_image = cached
            self.failed.discard(key)
            self._schedule_fit_render(fast=True)
        else:
            self.current_image = None
            self._show_loading_state(path)

        self._sync_tree_selection()
        self._refresh_tree_row(index)
        self._schedule_image_loads(index, preload_direction)
        self._update_actions()

    def _sync_tree_selection(self) -> None:
        if self.current_index < 0:
            return
        item = str(self.current_index)
        if not self.tree.exists(item):
            return
        self._tree_syncing = True
        self.tree.selection_set(item)
        self.tree.focus(item)
        self.tree.see(item)
        self._tree_syncing = False

    def _refresh_tree_row(self, index: int) -> None:
        if index < 0 or index >= len(self.paths) or not self.tree.exists(str(index)):
            return
        key = path_key(self.paths[index])
        if key in self.failed:
            state = "不可读"
        elif key in self.selected:
            state = "已选"
        else:
            state = ""
        self.tree.set(str(index), "selected", state)

    def _selected_indices(self) -> list[int]:
        return [index for index, path in enumerate(self.paths) if path_key(path) in self.selected]

    def navigate(self, delta: int) -> None:
        if not self.paths:
            return
        if self.review_mode:
            indices = self._selected_indices()
            if not indices:
                return
            position = indices.index(self.current_index) if self.current_index in indices else 0
            self.set_current(indices[(position + delta) % len(indices)], preload_direction=delta)
            return
        self.set_current((self.current_index + delta) % len(self.paths), preload_direction=delta)

    def toggle_selected(self) -> None:
        if self.current_index < 0:
            return
        key = path_key(self.paths[self.current_index])
        if key in self.selected:
            self._set_current_selected(False)
        else:
            self._set_current_selected(True)

    def select_current(self) -> None:
        self._set_current_selected(True)

    def deselect_current(self) -> None:
        self._set_current_selected(False)

    def _set_current_selected(self, is_selected: bool) -> None:
        if self.current_index < 0:
            return
        review_position = 0
        if self.review_mode:
            indices_before = self._selected_indices()
            if self.current_index in indices_before:
                review_position = indices_before.index(self.current_index)
        key = path_key(self.paths[self.current_index])
        if is_selected:
            self.selected.add(key)
        else:
            self.selected.discard(key)
        if self.review_mode and not is_selected:
            remaining = self._selected_indices()
            if not remaining:
                self.exit_review()
                self._render_image()
                return
            next_index = remaining[min(review_position, len(remaining) - 1)]
            self._rebuild_tree()
            self.set_current(next_index, force=True)
            return
        self._refresh_tree_row(self.current_index)
        self._update_actions()
        self._render_image()

    def clear_all(self) -> None:
        if not self.paths:
            return
        if self.selected and not messagebox.askyesno(
            "清空列表", "当前标记会一起清除，确定要清空吗？", parent=self.root
        ):
            return
        self._cancel_interactive_render()
        self._cancel_scheduled_fit()
        self._cancel_all_image_loads()
        self._clear_image_cache()
        self.paths.clear()
        self.selected.clear()
        self.failed.clear()
        self.current_index = -1
        self.current_image = None
        self.current_photo = None
        self.tree.delete(*self.tree.get_children())
        self._draw_empty_state()
        self._update_actions()

    def _cancel_all_image_loads(self) -> None:
        self._image_load_generation += 1
        for future in self._pending_image_loads.values():
            future.cancel()
        self._pending_image_loads.clear()

    def _cancel_scheduled_fit(self) -> None:
        if self._fit_render_job is not None:
            self.root.after_cancel(self._fit_render_job)
            self._fit_render_job = None

    def _schedule_fit_render(self, fast: bool = False) -> None:
        self._cancel_scheduled_fit()
        self._fit_render_job = self.root.after_idle(self._run_scheduled_fit, fast)

    def _run_scheduled_fit(self, fast: bool) -> None:
        self._fit_render_job = None
        self.fit_image(fast=fast)

    def _cancel_interactive_render(self) -> None:
        if self._interactive_render_job is not None:
            self.root.after_cancel(self._interactive_render_job)
            self._interactive_render_job = None
        if self._quality_render_job is not None:
            self.root.after_cancel(self._quality_render_job)
            self._quality_render_job = None

    def _schedule_interactive_render(self) -> None:
        if self._interactive_render_job is None:
            self._interactive_render_job = self.root.after(16, self._render_interactive_frame)
        if self._quality_render_job is not None:
            self.root.after_cancel(self._quality_render_job)
        self._quality_render_job = self.root.after(120, self._finish_interactive_render)

    def _render_interactive_frame(self) -> None:
        self._interactive_render_job = None
        self._render_image(fast=True)

    def _finish_interactive_render(self) -> None:
        self._cancel_interactive_render()
        self._render_image()

    def fit_image(self, fast: bool = False) -> None:
        if self.current_image is None:
            return
        self._cancel_scheduled_fit()
        self._cancel_interactive_render()
        canvas_width = max(self.canvas.winfo_width(), 1)
        canvas_height = max(self.canvas.winfo_height(), 1)
        image_width, image_height = self.current_image.size
        margin = 32
        self.scale = min(
            max((canvas_width - margin * 2) / image_width, self.MIN_SCALE),
            max((canvas_height - margin * 2) / image_height, self.MIN_SCALE),
            4.0,
        )
        self.offset_x = (canvas_width - image_width * self.scale) / 2
        self.offset_y = (canvas_height - image_height * self.scale) / 2
        self.fit_mode = True
        self._render_image(fast=fast)
        if fast:
            self._quality_render_job = self.root.after(120, self._finish_interactive_render)

    def _on_mousewheel(self, event: tk.Event) -> str:
        factor = math.pow(1.001, event.delta)
        self._zoom_at(event.x, event.y, factor)
        return "break"

    def _zoom_at(self, x: int, y: int, factor: float) -> None:
        if self.current_image is None:
            return
        old_scale = self.scale
        new_scale = max(self.MIN_SCALE, min(self.MAX_SCALE, old_scale * factor))
        if math.isclose(old_scale, new_scale):
            return
        source_x = (x - self.offset_x) / old_scale
        source_y = (y - self.offset_y) / old_scale
        self.scale = new_scale
        self.offset_x = x - source_x * new_scale
        self.offset_y = y - source_y * new_scale
        self.fit_mode = False
        self._schedule_interactive_render()

    def _start_pan(self, event: tk.Event) -> None:
        if self.current_image is None:
            return
        self.canvas.focus_force()
        self.drag_start = (event.x, event.y, self.offset_x, self.offset_y)
        self.canvas.configure(cursor="fleur")

    def _pan(self, event: tk.Event) -> None:
        if self.drag_start is None:
            return
        start_x, start_y, original_x, original_y = self.drag_start
        self.offset_x = original_x + event.x - start_x
        self.offset_y = original_y + event.y - start_y
        self.fit_mode = False
        self._schedule_interactive_render()

    def _end_pan(self, _event: tk.Event) -> None:
        self.drag_start = None
        self.canvas.configure(cursor="arrow")
        self._finish_interactive_render()

    def _on_canvas_resize(self, _event: tk.Event) -> None:
        if self._canvas_resize_job is not None:
            self.root.after_cancel(self._canvas_resize_job)
        self._canvas_resize_job = self.root.after(50, self._finish_canvas_resize)

    def _finish_canvas_resize(self) -> None:
        self._canvas_resize_job = None
        if self.fit_mode and self.current_image is not None:
            self.fit_image()
        elif self.current_image is not None:
            self._render_image()
        else:
            self._draw_empty_state()

    def _render_image(self, fast: bool = False) -> None:
        image = self.current_image
        if image is None:
            return

        canvas_width = max(self.canvas.winfo_width(), 1)
        canvas_height = max(self.canvas.winfo_height(), 1)
        image_width, image_height = image.size
        scale = self.scale

        source_left = max(0, math.floor((0 - self.offset_x) / scale))
        source_top = max(0, math.floor((0 - self.offset_y) / scale))
        source_right = min(image_width, math.ceil((canvas_width - self.offset_x) / scale))
        source_bottom = min(image_height, math.ceil((canvas_height - self.offset_y) / scale))

        self.canvas.delete("all")
        if source_right <= source_left or source_bottom <= source_top:
            self.current_photo = None
            self._draw_selection_indicator()
            return

        target_width = max(1, round((source_right - source_left) * scale))
        target_height = max(1, round((source_bottom - source_top) * scale))
        source_box = (source_left, source_top, source_right, source_bottom)
        source_size = (source_right - source_left, source_bottom - source_top)
        if source_size == (target_width, target_height):
            rendered = image.crop(source_box)
        else:
            resample = Image.Resampling.BILINEAR if fast else (Image.Resampling.LANCZOS if scale < 1 else Image.Resampling.BICUBIC)
            reducing_gap = 2.0 if scale < 1 else None
            rendered = image.resize((target_width, target_height), resample, box=source_box, reducing_gap=reducing_gap)
        if rendered.mode not in {"RGB", "RGBA"}:
            rendered = rendered.convert("RGBA" if "transparency" in rendered.info else "RGB")

        self.current_photo = ImageTk.PhotoImage(rendered)
        display_x = round(self.offset_x + source_left * scale)
        display_y = round(self.offset_y + source_top * scale)
        self.canvas.create_image(display_x, display_y, anchor="nw", image=self.current_photo)

        full_left = self.offset_x
        full_top = self.offset_y
        full_right = self.offset_x + image_width * scale
        full_bottom = self.offset_y + image_height * scale
        self.canvas.create_rectangle(
            full_left,
            full_top,
            full_right,
            full_bottom,
            outline="#3a414c",
            width=1,
        )
        self._draw_selection_indicator()
        self._update_image_info()

    def _draw_selection_indicator(self) -> None:
        if self.current_index < 0:
            return
        key = path_key(self.paths[self.current_index])
        if key not in self.selected:
            return
        self.canvas.create_rectangle(3, 3, 118, 40, fill="#8a5a00", outline=COLORS["selected"], width=2)
        self.canvas.create_text(
            60,
            22,
            text="✓  已选择",
            fill="white",
            font=("Microsoft YaHei UI", 11, "bold"),
        )

    def _draw_empty_state(self) -> None:
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self.canvas.create_text(
            width / 2,
            height / 2 - 12,
            text="还没有导入图片",
            fill="#e5e7eb",
            font=("Microsoft YaHei UI", 18, "bold"),
        )
        self.canvas.create_text(
            width / 2,
            height / 2 + 24,
            text="请选择图片或文件夹",
            fill=COLORS["canvas_text"],
            font=("Microsoft YaHei UI", 10),
        )

    def _show_loading_state(self, path: Path) -> None:
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self.canvas.create_text(
            width / 2,
            height / 2 - 12,
            text="正在加载图片",
            fill="#e5e7eb",
            font=("Microsoft YaHei UI", 16, "bold"),
        )
        self.canvas.create_text(
            width / 2,
            height / 2 + 24,
            text=path.name,
            fill=COLORS["canvas_text"],
            font=("Microsoft YaHei UI", 10),
            width=max(width - 120, 200),
        )

    def _show_load_error(self, path: Path, details: str) -> None:
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self.canvas.create_text(
            width / 2,
            height / 2 - 24,
            text="无法打开这张图片",
            fill="#fda4af",
            font=("Microsoft YaHei UI", 16, "bold"),
        )
        self.canvas.create_text(
            width / 2,
            height / 2 + 10,
            text=path.name,
            fill="#e5e7eb",
            font=("Microsoft YaHei UI", 10),
        )
        self.canvas.create_text(
            width / 2,
            height / 2 + 38,
            text=details[:160],
            fill=COLORS["canvas_text"],
            font=("Microsoft YaHei UI", 9),
            width=max(width - 120, 200),
        )

    def _update_image_info(self) -> None:
        if self.current_image is None or self.current_index < 0:
            self.image_info_text.set("未载入图片")
            return
        width, height = self.current_image.size
        if self.review_mode:
            indices = self._selected_indices()
            review_position = indices.index(self.current_index) + 1 if self.current_index in indices else 0
            position_text = f"复核 {review_position} / {len(indices)}"
        else:
            position_text = f"{self.current_index + 1} / {len(self.paths)}"
        self.image_info_text.set(
            f"{position_text}   {width} × {height}   {self.scale * 100:.0f}%"
        )

    def _update_actions(self) -> None:
        has_images = bool(self.paths)
        selected_count = len(self.selected)
        navigable = selected_count > 0 if self.review_mode else has_images
        self.previous_button.configure(state="normal" if navigable else "disabled")
        self.next_button.configure(state="normal" if navigable else "disabled")
        self.select_button.configure(state="normal" if navigable else "disabled")
        self.clear_button.configure(state="normal" if has_images and not self.review_mode else "disabled")
        self.export_button.configure(state="normal" if selected_count else "disabled", text="确认导出" if self.review_mode else "导出已选")
        if self.review_mode:
            self.counter_text.set(f"正在复核 {selected_count} 张已选图片")
            self.review_status.configure(text=f"正在复核 {selected_count} 张已选图片")
        else:
            self.counter_text.set(f"{len(self.paths)} 张图片 · 已选 {selected_count} 张")
        self.selection_badge.configure(text=f"已选 {selected_count}")

        if self.current_index >= 0:
            key = path_key(self.paths[self.current_index])
            self.select_button.configure(text="取消选择" if key in self.selected else "标记为已选")
            self._update_image_info()
        else:
            self.image_info_text.set("未载入图片")

    def close(self) -> None:
        self._cancel_interactive_render()
        self._cancel_scheduled_fit()
        if self._image_poll_job is not None:
            self.root.after_cancel(self._image_poll_job)
            self._image_poll_job = None
        self._cancel_all_image_loads()
        self._image_executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()

    def enter_review(self) -> None:
        indices = self._selected_indices()
        if not indices:
            messagebox.showinfo("没有已选图片", "请先标记需要导出的图片。", parent=self.root)
            return
        self.review_mode = True
        self.review_status.configure(text=f"正在复核 {len(indices)} 张已选图片")
        self.exit_review_button.pack(side="right")
        self.review_status.pack(side="right", padx=(0, 10))
        self._rebuild_tree()
        target = self.current_index if self.current_index in indices else indices[0]
        self.set_current(target, force=True)
        self.root.after_idle(self.canvas.focus_set)

    def exit_review(self) -> None:
        if not self.review_mode:
            return
        self.review_mode = False
        self.review_status.pack_forget()
        self.exit_review_button.pack_forget()
        self._rebuild_tree()
        self._sync_tree_selection()

    def start_export(self) -> None:
        if not self.review_mode:
            self.enter_review()
            return
        selected_paths = [path for path in self.paths if path_key(path) in self.selected]
        if not selected_paths:
            messagebox.showinfo("没有已选图片", "请先标记需要导出的图片。", parent=self.root)
            return

        initial_dir = str(self.export_directory) if self.export_directory else ""
        destination_name = filedialog.askdirectory(
            parent=self.root,
            title="选择导出文件夹",
            initialdir=initial_dir,
        )
        if not destination_name:
            return

        destination = Path(destination_name)
        if export_destination_matches_source_folder(destination, selected_paths):
            messagebox.showwarning(
                "请选择单独的导出文件夹",
                "导出目录不能与原图所在目录相同。请选择其他文件夹；原图不会被移动、覆盖或修改。",
                parent=self.root,
            )
            return
        self.export_directory = destination
        output_format = self.export_format.get()
        naming_mode = self.export_naming.get()
        quality = round(self.export_quality.get())
        self._export_queue = queue.Queue()
        self._export_cancel = threading.Event()
        self._export_dialog = ExportProgressDialog(self.root, len(selected_paths), self._export_cancel)
        self.export_button.configure(state="disabled")

        worker = threading.Thread(
            target=self._export_worker,
            args=(selected_paths, destination, output_format, naming_mode, quality),
            daemon=True,
        )
        worker.start()
        self.root.after(80, self._poll_export_queue)

    def _export_worker(
        self,
        paths: list[Path],
        destination: Path,
        output_format: str,
        naming_mode: str,
        quality: int,
    ) -> None:
        assert self._export_queue is not None
        assert self._export_cancel is not None
        errors: list[tuple[str, str]] = []
        exported = 0
        for index, source in enumerate(paths, start=1):
            if self._export_cancel.is_set():
                self._export_queue.put(("done", exported, errors, True, destination))
                return
            suffix = source.suffix if output_format == "保持原格式" else EXPORT_FORMATS[output_format][0]
            assert suffix is not None
            target = unique_output_path(destination, export_stem(source, index, naming_mode), suffix)
            try:
                export_image(source, target, output_format, quality)
                exported += 1
            except Exception as exc:
                errors.append((source.name, str(exc)))
            self._export_queue.put(("progress", index, len(paths), source.name))

        self._export_queue.put(("done", exported, errors, False, destination))

    def _poll_export_queue(self) -> None:
        if self._export_queue is None:
            return
        completed = False
        while True:
            try:
                message = self._export_queue.get_nowait()
            except queue.Empty:
                break
            if message[0] == "progress" and self._export_dialog is not None:
                _, done, total, filename = message
                self._export_dialog.set_progress(done, total, filename)
            elif message[0] == "done":
                _, exported, errors, cancelled, destination = message
                self._finish_export(exported, errors, cancelled, destination)
                completed = True
                break
        if not completed:
            self.root.after(80, self._poll_export_queue)

    def _finish_export(
        self,
        exported: int,
        errors: list[tuple[str, str]],
        cancelled: bool,
        destination: Path,
    ) -> None:
        if self._export_dialog is not None:
            self._export_dialog.grab_release()
            self._export_dialog.destroy()
        self._export_dialog = None
        self._export_queue = None
        self._export_cancel = None
        if cancelled:
            self._update_actions()
        else:
            self.exit_review()

        if cancelled:
            messagebox.showinfo("导出已取消", f"已导出 {exported} 张图片。", parent=self.root)
            return
        if errors:
            summary = "\n".join(f"{name}：{detail}" for name, detail in errors[:5])
            if len(errors) > 5:
                summary += f"\n另有 {len(errors) - 5} 个错误"
            messagebox.showwarning(
                "导出完成，但有错误",
                f"成功导出 {exported} 张，失败 {len(errors)} 张。\n\n{summary}",
                parent=self.root,
            )
        else:
            messagebox.showinfo(
                "导出完成",
                f"已将 {exported} 张图片导出到：\n{destination}",
                parent=self.root,
            )


def enable_windows_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def main() -> None:
    enable_windows_dpi_awareness()
    root = tk.Tk()
    PhotoSelectorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
