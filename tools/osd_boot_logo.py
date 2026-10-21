#!/usr/bin/env python3
"""Convert an image to a 288x72, 24-bit MAX7456 boot-logo BMP.

The OSD expects three exact colors:
  (0, 255, 0)   transparent key / green background
  (0, 0, 0)     black
  (255, 255, 255) white

The source image may have a non-uniform green background and anti-aliased
edges.  The converter estimates the background from the border, removes it
with a black/white matte, then resizes the masks to 288x72.  The result is
always a plain 24-bit BMP with exactly those three colors.
"""

from __future__ import annotations

import argparse
import ctypes
import sys
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np
from PIL import Image, ImageTk


TARGET_W = 288
TARGET_H = 72
GREEN = np.array([0, 255, 0], dtype=np.uint8)
BLACK = np.array([0, 0, 0], dtype=np.uint8)
WHITE = np.array([255, 255, 255], dtype=np.uint8)

BG = "#f3f3f1"
CARD = "#ffffff"
INK = "#1d1d1f"
MUTED = "#6b6b70"
ACCENT = "#146c94"
ACCENT_DARK = "#0f5373"
BORDER = "#d8d8d4"


def enable_high_dpi() -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def detect_background(image: Image.Image) -> np.ndarray:
    """Estimate the source background from the image border."""
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    h, w, _ = rgb.shape
    k = max(2, min(h, w) // 100)
    border = np.concatenate(
        [
            rgb[:k].reshape(-1, 3),
            rgb[-k:].reshape(-1, 3),
            rgb[:, :k].reshape(-1, 3),
            rgb[:, -k:].reshape(-1, 3),
        ],
        axis=0,
    )
    return np.median(border, axis=0)


def source_masks(
    image: Image.Image,
    background: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (foreground_alpha, white_mask, background_rgb)."""
    has_alpha = image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    )

    if has_alpha:
        rgba = np.asarray(image.convert("RGBA"), dtype=np.float32)
        rgb = rgba[..., :3]
        alpha = rgba[..., 3] / 255.0
        lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
        white = ((lum >= 140) & (alpha > 0.01)).astype(np.float32)
        bg = (
            np.asarray(background, dtype=np.float32)
            if background is not None
            else np.array([0.0, 255.0, 0.0], dtype=np.float32)
        )
        return alpha, white, bg

    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    bg = (
        np.asarray(background, dtype=np.float32)
        if background is not None
        else detect_background(image)
    )

    def solve(foreground: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        direction = foreground - bg
        denom = float(direction @ direction)
        if denom <= 1e-6:
            zero = np.zeros(rgb.shape[:2], dtype=np.float32)
            return zero, zero
        alpha = ((rgb - bg) @ direction) / denom
        alpha = np.clip(alpha, 0.0, 1.0)
        reconstructed = bg + alpha[..., None] * direction
        residual = np.linalg.norm(rgb - reconstructed, axis=2)
        return alpha, residual

    alpha_w, residual_w = solve(np.array([255.0, 255.0, 255.0], dtype=np.float32))
    alpha_k, residual_k = solve(np.array([0.0, 0.0, 0.0], dtype=np.float32))
    choose_white = residual_w <= residual_k
    alpha = np.where(choose_white, alpha_w, alpha_k)
    foreground = alpha > 0.5
    white = (foreground & choose_white).astype(np.float32)
    alpha = np.where(foreground, alpha, 0.0).astype(np.float32)
    return alpha, white, bg


def _resize_mask(mask: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    image = Image.fromarray((mask * 255).astype(np.uint8), mode="L")
    return np.asarray(
        image.resize(size, Image.Resampling.LANCZOS), dtype=np.float32
    )


def convert_to_boot_logo(
    image: Image.Image,
    *,
    mode: str = "fit",
    background: np.ndarray | None = None,
) -> tuple[Image.Image, np.ndarray]:
    """Return (288x72 RGB image, estimated source background)."""
    if mode not in {"fit", "fill", "cover"}:
        raise ValueError("mode 只能是 fit / fill / cover")

    alpha, white, bg = source_masks(image, background=background)
    ys, xs = np.where(alpha > 0.5)
    if len(xs) == 0:
        raise ValueError("没有检测到前景内容；请检查背景色或图片。")

    pad = max(1, min(image.size) // 200)
    x0 = max(0, int(xs.min()) - pad)
    y0 = max(0, int(ys.min()) - pad)
    x1 = min(image.width, int(xs.max()) + 1 + pad)
    y1 = min(image.height, int(ys.max()) + 1 + pad)
    alpha_c = alpha[y0:y1, x0:x1]
    white_c = white[y0:y1, x0:x1]
    ch, cw = alpha_c.shape
    if cw < 1 or ch < 1:
        raise ValueError("裁剪后的前景为空。")

    if mode == "fit":
        scale = min((TARGET_W - 4) / cw, (TARGET_H - 4) / ch)
        nw = max(1, round(cw * scale))
        nh = max(1, round(ch * scale))
        ox = (TARGET_W - nw) // 2
        oy = (TARGET_H - nh) // 2
    elif mode == "fill":
        nw, nh = TARGET_W, TARGET_H
        ox = oy = 0
    else:  # cover
        scale = max(TARGET_W / cw, TARGET_H / ch)
        nw = max(TARGET_W, round(cw * scale))
        nh = max(TARGET_H, round(ch * scale))
        ox = (TARGET_W - nw) // 2
        oy = (TARGET_H - nh) // 2

    alpha_r = _resize_mask(alpha_c, (nw, nh))
    white_r = _resize_mask(white_c, (nw, nh))

    if mode == "cover":
        cx = (nw - TARGET_W) // 2
        cy = (nh - TARGET_H) // 2
        alpha_r = alpha_r[cy : cy + TARGET_H, cx : cx + TARGET_W]
        white_r = white_r[cy : cy + TARGET_H, cx : cx + TARGET_W]
        nw, nh = TARGET_W, TARGET_H
        ox = oy = 0

    out = np.empty((TARGET_H, TARGET_W, 3), dtype=np.uint8)
    out[:, :] = GREEN
    h = min(nh, TARGET_H - oy)
    w = min(nw, TARGET_W - ox)
    a = alpha_r[:h, :w] >= 128
    wh = white_r[:h, :w] >= 128
    target = out[oy : oy + h, ox : ox + w]
    target[a & wh] = WHITE
    target[a & ~wh] = BLACK
    return Image.fromarray(out, "RGB"), bg


def _bmp_info(path: Path) -> tuple[int, int, int, int]:
    raw = Path(path).read_bytes()
    if raw[:2] != b"BM":
        raise ValueError("不是 BMP 文件")
    offset = int.from_bytes(raw[10:14], "little")
    width = int.from_bytes(raw[18:22], "little", signed=True)
    height = int.from_bytes(raw[22:26], "little", signed=True)
    bit_count = int.from_bytes(raw[28:30], "little")
    return width, height, bit_count, offset


def save_bmp(image: Image.Image, path: Path) -> None:
    """Save exactly 288x72 24-bit BMP with only the three OSD colors."""
    path = Path(path)
    if image.size != (TARGET_W, TARGET_H) or image.mode != "RGB":
        raise ValueError("输出必须是 288x72 RGB 图像")
    colors = set(image.getcolors(maxcolors=32) or [])
    if any(color not in {(0, 255, 0), (0, 0, 0), (255, 255, 255)} for _count, color in colors):
        raise ValueError(f"输出里出现了非 OSD 颜色：{colors}")
    image.save(path, format="BMP")

    width, height, bit_count, offset = _bmp_info(path)
    if (width, abs(height), bit_count, offset) != (TARGET_W, TARGET_H, 24, 54):
        raise ValueError(
            f"BMP 头不对：{width}x{abs(height)}, {bit_count}-bit, offset={offset}"
        )
    expected_size = 54 + TARGET_W * TARGET_H * 3
    if path.stat().st_size != expected_size:
        raise ValueError(
            f"BMP 文件大小不对：{path.stat().st_size}，应为 {expected_size}"
        )


def make_preview(image: Image.Image, scale: int = 4) -> Image.Image:
    return image.resize(
        (image.width * scale, image.height * scale),
        Image.Resampling.NEAREST,
    )


def cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="把图片转成 288x72、24-bit、三色的 MAX7456 启动 Logo BMP"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--mode", choices=["fit", "fill", "cover"], default="fit")
    parser.add_argument("--preview", type=Path)
    parser.add_argument(
        "--background",
        help="手动指定源背景色，格式 RRGGBB；默认从边框自动估计",
    )
    args = parser.parse_args(argv)

    background = None
    if args.background:
        text = args.background.lstrip("#")
        if len(text) != 6:
            raise ValueError("--background 需要 RRGGBB")
        background = np.array(
            [int(text[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float32
        )

    image = Image.open(args.input)
    result, bg = convert_to_boot_logo(image, mode=args.mode, background=background)
    out = args.output or args.input.with_name(args.input.stem + "_boot_logo.bmp")
    save_bmp(result, out)
    if args.preview:
        make_preview(result).save(args.preview)
    print(f"输出: {out}")
    print(f"尺寸: {result.size[0]}x{result.size[1]}, 24-bit BMP, 3 colors")
    print(f"源背景估计: RGB({bg[0]:.0f},{bg[1]:.0f},{bg[2]:.0f})")
    return 0


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OSD 启动 Logo 转换器")
        self.geometry("1050x760")
        self.minsize(900, 680)
        self.configure(bg=BG)
        self.source_path: Path | None = None
        self.source_image: Image.Image | None = None
        self.result_image: Image.Image | None = None
        self.original_photo: ImageTk.PhotoImage | None = None
        self.result_photo: ImageTk.PhotoImage | None = None
        self.background_text = "自动"

        self._style()
        self._build()
        self.after(200, self._load_first_arg)

    def _style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(10, 6))
        style.configure(
            "TRadiobutton",
            background=CARD,
            foreground=INK,
            font=("Microsoft YaHei UI", 10),
        )

    def _build(self) -> None:
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=20, pady=(16, 10))
        tk.Label(
            header,
            text="OSD 启动 Logo 转换器",
            bg=BG,
            fg=INK,
            font=("Microsoft YaHei UI", 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="输出固定为 288×72、24-bit BMP，只保留纯绿 #00FF00、纯黑、纯白。",
            bg=BG,
            fg=MUTED,
            font=("Microsoft YaHei UI", 10),
        ).pack(anchor="w", pady=(4, 0))

        top = tk.Frame(self, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        top.pack(fill="x", padx=20, pady=(0, 12))
        row = tk.Frame(top, bg=CARD)
        row.pack(fill="x", padx=14, pady=12)
        self.path_var = tk.StringVar()
        entry = tk.Entry(
            row,
            textvariable=self.path_var,
            font=("Microsoft YaHei UI", 9),
            bg="#fbfbf9",
            fg=INK,
            relief="flat",
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        entry.pack(side="left", fill="x", expand=True, ipady=6)
        tk.Button(
            row,
            text="选择图片…",
            command=self.choose_image,
            bg=ACCENT,
            fg="white",
            activebackground=ACCENT_DARK,
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            font=("Microsoft YaHei UI", 10, "bold"),
            padx=14,
            pady=6,
        ).pack(side="left", padx=(8, 0))

        modes = tk.Frame(top, bg=CARD)
        modes.pack(fill="x", padx=14, pady=(0, 10))
        self.mode_var = tk.StringVar(value="fit")
        for value, text in [
            ("fit", "保持比例 · 留绿边"),
            ("fill", "拉伸填满 288×72"),
            ("cover", "填满并裁切"),
        ]:
            tk.Radiobutton(
                modes,
                text=text,
                value=value,
                variable=self.mode_var,
                command=self.convert_preview,
                bg=CARD,
                fg=INK,
                activebackground=CARD,
                selectcolor="#dcecf5",
                font=("Microsoft YaHei UI", 9),
            ).pack(side="left", padx=(0, 16))

        self.info_var = tk.StringVar(value="还没有选择图片。")
        tk.Label(
            top,
            textvariable=self.info_var,
            bg=CARD,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 10))

        previews = tk.Frame(self, bg=BG)
        previews.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        previews.grid_columnconfigure(0, weight=1)
        previews.grid_columnconfigure(1, weight=1)
        previews.grid_rowconfigure(0, weight=1)

        for col, title in [(0, "原图"), (1, "转换后（放大 4×）")]:
            card = tk.Frame(
                previews, bg=CARD, highlightbackground=BORDER, highlightthickness=1
            )
            card.grid(row=0, column=col, sticky="nsew", padx=(0, 8) if col == 0 else (8, 0))
            tk.Label(
                card,
                text=title,
                bg=CARD,
                fg=INK,
                font=("Microsoft YaHei UI", 11, "bold"),
            ).pack(anchor="w", padx=12, pady=(10, 6))
            label = tk.Label(
                card,
                text="选择图片后显示",
                bg="#f1f1ee",
                fg="#77777b",
                font=("Microsoft YaHei UI", 10),
            )
            label.pack(fill="both", expand=True, padx=12, pady=(0, 12))
            if col == 0:
                self.original_label = label
            else:
                self.result_label = label

        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", padx=20, pady=(0, 16))
        self.save_button = tk.Button(
            bottom,
            text="保存 BMP…",
            command=self.save_bmp_file,
            bg=ACCENT,
            fg="white",
            activebackground=ACCENT_DARK,
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            font=("Microsoft YaHei UI", 12, "bold"),
            padx=20,
            pady=9,
            state="disabled",
        )
        self.save_button.pack(side="right")
        self.preview_button = tk.Button(
            bottom,
            text="保存预览 PNG…",
            command=self.save_preview_file,
            bg="#e7e7e3",
            fg=INK,
            activebackground="#d8d8d2",
            relief="flat",
            cursor="hand2",
            font=("Microsoft YaHei UI", 10),
            padx=14,
            pady=8,
            state="disabled",
        )
        self.preview_button.pack(side="right", padx=(0, 8))

    def _load_first_arg(self) -> None:
        if len(sys.argv) > 1:
            path = Path(sys.argv[1])
            if path.exists():
                self.load_image(path)

    def choose_image(self) -> None:
        path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[
                ("图片", "*.png;*.bmp;*.jpg;*.jpeg;*.gif;*.webp"),
                ("所有文件", "*.*"),
            ],
        )
        if path:
            self.load_image(Path(path))

    def load_image(self, path: Path) -> None:
        try:
            image = Image.open(path)
            image.load()
        except Exception as exc:
            messagebox.showerror("打不开图片", f"{path}\n\n{exc}")
            return
        self.source_path = path
        self.source_image = image
        self.path_var.set(str(path))
        self._show_original()
        self.convert_preview()

    def _show_original(self) -> None:
        if self.source_image is None:
            return
        image = self.source_image.copy()
        image.thumbnail((450, 420), Image.Resampling.LANCZOS)
        self.original_photo = ImageTk.PhotoImage(image)
        self.original_label.configure(image=self.original_photo, text="")

    def convert_preview(self) -> None:
        if self.source_image is None:
            return
        try:
            result, bg = convert_to_boot_logo(
                self.source_image, mode=self.mode_var.get()
            )
        except Exception as exc:
            self.info_var.set(f"转换失败：{exc}")
            self.result_image = None
            self.result_label.configure(text=f"转换失败：{exc}", image="")
            self.save_button.configure(state="disabled")
            self.preview_button.configure(state="disabled")
            return

        self.result_image = result
        self.info_var.set(
            f"输出：288×72 · 24-bit BMP · 纯绿/黑/白三色  |  "
            f"源背景约 RGB({bg[0]:.0f},{bg[1]:.0f},{bg[2]:.0f})"
        )
        preview = make_preview(result, scale=4)
        self.result_photo = ImageTk.PhotoImage(preview)
        self.result_label.configure(image=self.result_photo, text="")
        self.save_button.configure(state="normal")
        self.preview_button.configure(state="normal")

    def default_output(self) -> str:
        if self.source_path:
            return str(self.source_path.with_name(self.source_path.stem + "_boot_logo.bmp"))
        return "boot_logo.bmp"

    def save_bmp_file(self) -> None:
        if self.result_image is None:
            return
        path = filedialog.asksaveasfilename(
            title="保存 OSD 启动 Logo",
            defaultextension=".bmp",
            initialfile=Path(self.default_output()).name,
            filetypes=[("BMP", "*.bmp")],
        )
        if not path:
            return
        try:
            save_bmp(self.result_image, Path(path))
        except Exception as exc:
            messagebox.showerror("保存失败", f"{path}\n\n{exc}")
            return
        messagebox.showinfo(
            "完成",
            f"已保存：\n{path}\n\n"
            "288×72 · 24-bit BMP · 纯绿/黑/白三色",
        )

    def save_preview_file(self) -> None:
        if self.result_image is None:
            return
        path = filedialog.asksaveasfilename(
            title="保存预览 PNG",
            defaultextension=".png",
            initialfile=Path(self.default_output()).with_suffix("").name + "_preview.png",
            filetypes=[("PNG", "*.png")],
        )
        if not path:
            return
        try:
            make_preview(self.result_image, scale=4).save(path)
        except Exception as exc:
            messagebox.showerror("保存失败", f"{path}\n\n{exc}")
            return
        messagebox.showinfo("完成", f"已保存预览：\n{path}")


def main() -> int:
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        return cli(sys.argv[1:])
    enable_high_dpi()
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
