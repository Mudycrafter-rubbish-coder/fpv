#!/usr/bin/env python3
"""Double-click GUI for the 11x17 Chinese OSD dot-matrix generator."""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageTk

# Make the module import work both in source mode and inside PyInstaller.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from osd_cn_dotmatrix import (  # noqa: E402
    CELL_H,
    CELL_W,
    DEFAULT_BASE_MCM,
    DEFAULT_FONT,
    DEFAULT_TEXT,
    PROJECT_ROOT,
    build_glyphs,
    find_label_font,
    gap_slots,
    generate_all,
    load_font,
    load_mcm,
    render_live_preview,
    unique_chars,
)


APP_TITLE = "OSD 中文点阵生成器"
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


def desktop_dir() -> Path:
    """Return the real Windows desktop, including OneDrive-redirected desktops."""
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
            )
            value, _ = winreg.QueryValueEx(key, "Desktop")
            path = Path(os.path.expandvars(value))
            if path.exists():
                return path
        except Exception:
            pass
    for candidate in (Path.home() / "Desktop", Path.home()):
        if candidate.exists():
            return candidate
    return Path.cwd()


def unique_output_dir(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = base / f"中文点阵_{stamp}"
    counter = 2
    while candidate.exists():
        candidate = base / f"中文点阵_{stamp}_{counter}"
        counter += 1
    return candidate


class SlotMapper(tk.Toplevel):
    """Pick which 0x00-0xFF slot receives each generated Chinese glyph."""

    BASE_W = 12
    BASE_H = 18

    def __init__(
        self,
        master: "App",
        base_path: Path,
        glyphs: list,
        initial_map: dict[str, int] | None = None,
    ) -> None:
        super().__init__(master)
        self.title("手动分配 .mcm 槽位")
        self.geometry("1120x880")
        self.minsize(1020, 780)
        self.configure(bg=BG)
        self.transient(master)
        self.grab_set()

        self.base_path = Path(base_path)
        self.base = load_mcm(self.base_path)
        self.glyphs = glyphs
        self.glyph_by_char = {glyph.char: glyph for glyph in glyphs}
        self.char_order = [glyph.char for glyph in glyphs]
        self.mapping = {
            char: int(slot)
            for char, slot in (initial_map or {}).items()
            if char in self.glyph_by_char and 0 <= int(slot) <= 0xFF
        }
        self.selected_char: str | None = self.char_order[0] if self.char_order else None
        self.cell = 40
        self.result: dict[str, int] | None = None
        self._grid_photo: ImageTk.PhotoImage | None = None
        self._base_thumbs: dict[int, Image.Image] = {}
        self._char_thumbs: dict[str, Image.Image] = {}

        self._build_thumbs()
        self._build_ui()
        self._refresh_all()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _build_thumbs(self) -> None:
        for code, pixels in enumerate(self.base):
            thumb = Image.new("RGBA", (self.BASE_W * 2, self.BASE_H * 2), (0, 0, 0, 0))
            draw = ImageDraw.Draw(thumb)
            for y in range(self.BASE_H):
                for x in range(self.BASE_W):
                    value = pixels[y * 12 + x]
                    if value == 2:
                        draw.rectangle(
                            [x * 2, y * 2, x * 2 + 1, y * 2 + 1],
                            fill=(238, 238, 225, 255),
                        )
                    elif value == 0:
                        draw.rectangle(
                            [x * 2, y * 2, x * 2 + 1, y * 2 + 1],
                            fill=(0, 0, 0, 255),
                        )
            self._base_thumbs[code] = thumb

        for glyph in self.glyphs:
            thumb = Image.new("RGBA", (CELL_W * 2, CELL_H * 2), (0, 0, 0, 0))
            draw = ImageDraw.Draw(thumb)
            for y, row in enumerate(glyph.rows):
                for x, value in enumerate(row):
                    if value == "#":
                        draw.rectangle(
                            [x * 2, y * 2, x * 2 + 1, y * 2 + 1],
                            fill=(238, 238, 225, 255),
                        )
            self._char_thumbs[glyph.char] = thumb

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=18, pady=(14, 8))
        tk.Label(
            header,
            text="手动分配槽位",
            bg=BG,
            fg=INK,
            font=("Microsoft YaHei UI", 18, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text=(
                "左边选一个汉字，再点右边格子。绿色=底字库空槽，橙色点=会替换原有字符，"
                "蓝框=已分配。右键清除。"
            ),
            bg=BG,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", pady=(3, 0))

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        body.grid_columnconfigure(0, weight=0, minsize=340)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=0)

        left = tk.Frame(body, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right = tk.Frame(body, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        right.grid(row=0, column=1, sticky="nsew")

        tk.Label(
            left,
            text=f"底字库：{self.base_path.name}",
            bg=CARD,
            fg=INK,
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(12, 4))
        self.summary_var = tk.StringVar(value="")
        tk.Label(
            left,
            textvariable=self.summary_var,
            bg=CARD,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
            anchor="w",
            justify="left",
            wraplength=310,
        ).pack(fill="x", padx=14, pady=(0, 8))

        self.listbox = tk.Listbox(
            left,
            height=24,
            exportselection=False,
            font=("Microsoft YaHei UI", 10),
            bg="#fbfbf9",
            fg=INK,
            selectbackground=ACCENT,
            selectforeground="white",
            relief="flat",
            highlightbackground=BORDER,
            highlightthickness=1,
            activestyle="none",
        )
        self.listbox.pack(fill="both", expand=True, padx=14, pady=(0, 8))
        self.listbox.bind("<<ListboxSelect>>", self._on_list_select)

        btns = tk.Frame(left, bg=CARD)
        btns.pack(fill="x", padx=14, pady=(0, 6))
        ttk.Button(btns, text="自动填空隙", command=self._auto_fill).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(btns, text="清空分配", command=self._clear).pack(
            side="left", fill="x", expand=True, padx=(6, 0)
        )

        self.selected_var = tk.StringVar(value="")
        tk.Label(
            left,
            textvariable=self.selected_var,
            bg=CARD,
            fg="#0f6b3d",
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
        ).pack(fill="x", padx=14, pady=(0, 10))

        self.canvas = tk.Canvas(
            right,
            width=640,
            height=640,
            bg="#101418",
            highlightthickness=0,
        )
        self.canvas.pack(padx=10, pady=(10, 4))
        self.canvas.bind("<Button-1>", self._on_grid_click)
        self.canvas.bind("<Button-3>", self._on_grid_right_click)
        self.canvas.bind("<Motion>", self._on_grid_motion)

        self.hover_var = tk.StringVar(value="把鼠标移到格子上看槽位信息。")
        tk.Label(
            right,
            textvariable=self.hover_var,
            bg=CARD,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 8))

        bottom = tk.Frame(body, bg=BG)
        bottom.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        tk.Button(
            bottom,
            text="保存映射并返回",
            command=self._save,
            bg=ACCENT,
            fg="white",
            activebackground=ACCENT_DARK,
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            font=("Microsoft YaHei UI", 11, "bold"),
            padx=18,
            pady=8,
        ).pack(side="right")
        ttk.Button(bottom, text="取消", command=self._cancel).pack(
            side="right", padx=(0, 8)
        )
        tk.Label(
            bottom,
            text="保存后回到主界面，再点“生成点阵图 + .mcm”即可使用这份映射。",
            bg=BG,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left")

    def _slot_owner(self, code: int) -> str | None:
        for char, slot in self.mapping.items():
            if slot == code:
                return char
        return None

    def _refresh_all(self) -> None:
        self._refresh_list()
        self._render_grid()
        assigned = len(self.mapping)
        gaps = len(gap_slots(self.base))
        overwritten = sum(
            1
            for slot in self.mapping.values()
            if any(pixel != 1 for pixel in self.base[slot])
        )
        self.summary_var.set(
            f"{len(self.glyphs)} 个字 · 已分配 {assigned} · 空槽 {gaps} · 覆盖 {overwritten}"
        )
        if self.selected_char:
            self.selected_var.set(f"当前汉字：{self.selected_char}")
        else:
            self.selected_var.set("没有可分配的汉字")

    def _refresh_list(self) -> None:
        self.listbox.delete(0, "end")
        for glyph in self.glyphs:
            slot = self.mapping.get(glyph.char)
            slot_text = f"0x{slot:02X}" if slot is not None else "未分配"
            self.listbox.insert("end", f"{glyph.char}    →    {slot_text}")
        if self.selected_char in self.char_order:
            index = self.char_order.index(self.selected_char)
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(index)
            self.listbox.activate(index)
            self.listbox.see(index)

    def _render_grid(self) -> None:
        cell = self.cell
        cols = rows = 16
        image = Image.new("RGB", (cols * cell, rows * cell), (16, 20, 24))
        draw = ImageDraw.Draw(image)
        try:
            label_font = ImageFont.truetype(str(find_label_font()), 8)
        except Exception:
            label_font = ImageFont.load_default()

        for code in range(256):
            col = code % cols
            row = code // cols
            x = col * cell
            y = row * cell
            blank = all(pixel == 1 for pixel in self.base[code])
            owner = self._slot_owner(code)
            if owner:
                bg = (17, 34, 50)
            elif blank:
                bg = (13, 31, 23)
            else:
                bg = (23, 24, 27)
            draw.rectangle([x, y, x + cell - 1, y + cell - 1], fill=bg)

            if owner:
                thumb = self._char_thumbs[owner]
                image.paste(
                    thumb,
                    (x + (cell - thumb.width) // 2, y + (cell - thumb.height) // 2),
                    thumb,
                )
                draw.rectangle(
                    [x + 1, y + 1, x + cell - 2, y + cell - 2],
                    outline=(70, 150, 220),
                    width=2,
                )
            else:
                thumb = self._base_thumbs[code]
                image.paste(
                    thumb,
                    (x + (cell - thumb.width) // 2, y + 2),
                    thumb,
                )
                draw.rectangle(
                    [x + 1, y + 1, x + cell - 2, y + cell - 2],
                    outline=(38, 92, 63) if blank else (48, 48, 52),
                    width=1,
                )

            draw.text(
                (x + 2, y + 1),
                f"{code:02X}",
                font=label_font,
                fill=(150, 205, 170) if blank else (160, 160, 165),
            )
            if owner and not blank:
                draw.ellipse(
                    [x + cell - 9, y + 3, x + cell - 4, y + 8],
                    fill=(240, 150, 40),
                )

        self._grid_photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._grid_photo)

    def _event_slot(self, event: tk.Event) -> int | None:
        x = int(self.canvas.canvasx(event.x))
        y = int(self.canvas.canvasy(event.y))
        if x < 0 or y < 0 or x >= 16 * self.cell or y >= 16 * self.cell:
            return None
        return (y // self.cell) * 16 + (x // self.cell)

    def _on_list_select(self, _event: tk.Event | None = None) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        self.selected_char = self.char_order[selection[0]]
        self.selected_var.set(f"当前汉字：{self.selected_char}")

    def _on_grid_motion(self, event: tk.Event) -> None:
        code = self._event_slot(event)
        if code is None:
            self.hover_var.set("把鼠标移到格子上看槽位信息。")
            return
        blank = all(pixel == 1 for pixel in self.base[code])
        owner = self._slot_owner(code)
        status = "空槽" if blank else "底字库已有字符"
        if owner:
            status += f" · 当前分配给「{owner}」"
        self.hover_var.set(f"0x{code:02X} · {status}")

    def _on_grid_click(self, event: tk.Event) -> None:
        code = self._event_slot(event)
        if code is None:
            return
        if not self.selected_char:
            messagebox.showinfo("先选字", "先在左边选择一个汉字。", parent=self)
            return

        owner = self._slot_owner(code)
        if owner and owner != self.selected_char:
            if not messagebox.askyesno(
                "槽位已占用",
                f"0x{code:02X} 已经分配给「{owner}」。\n改给「{self.selected_char}」吗？",
                parent=self,
            ):
                return
            del self.mapping[owner]

        blank = all(pixel == 1 for pixel in self.base[code])
        if not blank and owner != self.selected_char:
            if not messagebox.askyesno(
                "替换底字库字符",
                f"0x{code:02X} 在底字库里已经有字符。\n"
                f"确定用「{self.selected_char}」替换它吗？",
                parent=self,
            ):
                return

        # One glyph per slot; remove the old slot of this character first.
        self.mapping.pop(self.selected_char, None)
        self.mapping[self.selected_char] = code
        self._refresh_all()

    def _on_grid_right_click(self, event: tk.Event) -> None:
        code = self._event_slot(event)
        if code is None:
            return
        owner = self._slot_owner(code)
        if owner:
            del self.mapping[owner]
            self._refresh_all()

    def _auto_fill(self) -> None:
        available = [
            code for code in gap_slots(self.base) if code not in self.mapping.values()
        ]
        unassigned = [char for char in self.char_order if char not in self.mapping]
        for char, code in zip(unassigned, available):
            self.mapping[char] = code
        if len(unassigned) > len(available):
            messagebox.showwarning(
                "空槽不够",
                f"还有 {len(unassigned) - len(available)} 个字没有空槽可放。\n"
                "可以手动点击底字库里想替换的格子。",
                parent=self,
            )
        self._refresh_all()

    def _clear(self) -> None:
        self.mapping.clear()
        self._refresh_all()

    def _save(self) -> None:
        missing = [char for char in self.char_order if char not in self.mapping]
        if missing:
            messagebox.showwarning(
                "还没分配完",
                f"还有 {len(missing)} 个字没有槽位：{''.join(missing)}\n"
                "先点“自动填空隙”，或手动给它们选格子。",
                parent=self,
            )
            return
        self.result = dict(self.mapping)
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1180x980")
        self.minsize(1000, 820)
        self.configure(bg=BG)

        self.last_output: Path | None = None
        self.manual_slots: dict[str, int] = {}
        self._base_summary = "正在检查底字库…"
        self.preview_photo: ImageTk.PhotoImage | None = None
        self.preview_source: Image.Image | None = None
        self._preview_job: str | None = None
        self._live_job: str | None = None
        self._last_live_text = ""

        self._build_style()
        self._build_ui()
        self._set_icon()
        self.after(700, self._update_live_preview)
        self.after(200, self._inspect_base_font)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BG, foreground=INK)
        style.configure("Muted.TLabel", background=BG, foreground=MUTED)
        style.configure("Card.TLabel", background=CARD, foreground=INK)
        style.configure("CardMuted.TLabel", background=CARD, foreground=MUTED)
        style.configure(
            "TButton",
            font=("Microsoft YaHei UI", 10),
            padding=(12, 7),
        )
        style.configure(
            "TCheckbutton",
            background=CARD,
            foreground=INK,
            font=("Microsoft YaHei UI", 10),
        )

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg=BG)
        header.pack(fill="x", padx=20, pady=(16, 10))
        tk.Label(
            header,
            text=APP_TITLE,
            bg=BG,
            fg=INK,
            font=("Microsoft YaHei UI", 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="输入中文 → 生成 11×17 点阵图、空白模板和 CSV/TXT/JSON。每个汉字占 1 个 OSD 字符格。",
            bg=BG,
            fg=MUTED,
            font=("Microsoft YaHei UI", 10),
        ).pack(anchor="w", pady=(4, 0))

        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        main.grid_columnconfigure(0, weight=0, minsize=500)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        self._build_left_card(main)
        self._build_preview_card(main)

    def _build_left_card(self, parent: tk.Widget) -> None:
        card = tk.Frame(
            parent,
            bg=CARD,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 14))

        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="both", expand=True, padx=18, pady=16)

        tk.Label(
            inner,
            text="要显示的中文",
            bg=CARD,
            fg=INK,
            font=("Microsoft YaHei UI", 12, "bold"),
        ).pack(anchor="w")
        tk.Label(
            inner,
            text="空格和换行会忽略，重复字自动合并；默认跳过数字和英文字母。",
            bg=CARD,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", pady=(2, 8))

        text_wrap = tk.Frame(
            inner,
            bg="#fbfbf9",
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        text_wrap.pack(fill="both", expand=True)
        self.text = tk.Text(
            text_wrap,
            width=42,
            height=6,
            wrap="word",
            font=("Microsoft YaHei UI", 11),
            bg="#fbfbf9",
            fg=INK,
            insertbackground=INK,
            relief="flat",
            padx=10,
            pady=8,
            undo=True,
        )
        self.text.pack(fill="both", expand=True)
        self.text.insert("1.0", DEFAULT_TEXT)
        self.text.bind("<KeyRelease>", self._schedule_live_preview, add="+")
        self.text.bind("<<Paste>>", self._schedule_live_preview_soon, add="+")
        self.text.bind("<<Cut>>", self._schedule_live_preview_soon, add="+")
        self.text.bind("<<Undo>>", self._schedule_live_preview_soon, add="+")

        output_label = tk.Label(
            inner,
            text="输出文件夹",
            bg=CARD,
            fg=INK,
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        output_label.pack(anchor="w", pady=(14, 4))

        output_row = tk.Frame(inner, bg=CARD)
        output_row.pack(fill="x")
        self.out_var = tk.StringVar(value=str(desktop_dir() / "OSD中文点阵输出"))
        entry = tk.Entry(
            output_row,
            textvariable=self.out_var,
            font=("Microsoft YaHei UI", 9),
            bg="#fbfbf9",
            fg=INK,
            relief="flat",
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        entry.pack(side="left", fill="x", expand=True, ipady=6)
        ttk.Button(
            output_row,
            text="浏览…",
            command=self.choose_output,
        ).pack(side="left", padx=(8, 0))

        tk.Label(
            inner,
            text="底字库（.mcm）",
            bg=CARD,
            fg=INK,
            font=("Microsoft YaHei UI", 10, "bold"),
        ).pack(anchor="w", pady=(12, 4))

        base_row = tk.Frame(inner, bg=CARD)
        base_row.pack(fill="x")
        self.base_mcm_var = tk.StringVar(value=str(DEFAULT_BASE_MCM))
        base_entry = tk.Entry(
            base_row,
            textvariable=self.base_mcm_var,
            font=("Microsoft YaHei UI", 8),
            bg="#fbfbf9",
            fg=INK,
            relief="flat",
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        base_entry.pack(side="left", fill="x", expand=True, ipady=5)
        ttk.Button(
            base_row,
            text="选择…",
            command=self.choose_base_font,
        ).pack(side="left", padx=(8, 0))

        self.base_info_var = tk.StringVar(value="正在检查底字库…")
        self.base_info_label = tk.Label(
            inner,
            textvariable=self.base_info_var,
            bg=CARD,
            fg=MUTED,
            font=("Microsoft YaHei UI", 8),
            anchor="w",
        )
        self.base_info_label.pack(fill="x", pady=(3, 0))

        self.gaps_only = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            inner,
            text="只填空隙（保留底字库所有字符）",
            variable=self.gaps_only,
        ).pack(anchor="w", pady=(6, 0))

        self.auto_open = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            inner,
            text="生成后自动打开文件夹",
            variable=self.auto_open,
        ).pack(anchor="w", pady=(2, 0))

        self.mcm_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            inner,
            text="同时生成 MAX7456 .mcm 字库",
            variable=self.mcm_var,
        ).pack(anchor="w", pady=(4, 0))

        self.generate_button = tk.Button(
            inner,
            text="生成点阵图 + .mcm",
            command=self.generate,
            bg=ACCENT,
            fg="white",
            activebackground=ACCENT_DARK,
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            font=("Microsoft YaHei UI", 12, "bold"),
            pady=11,
        )
        self.generate_button.pack(fill="x", pady=(16, 0))

        secondary = tk.Frame(inner, bg=CARD)
        secondary.pack(fill="x", pady=(9, 0))
        ttk.Button(
            secondary,
            text="恢复默认字表",
            command=self.restore_default,
        ).pack(side="left")
        ttk.Button(
            secondary,
            text="打开输出文件夹",
            command=self.open_output,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            secondary,
            text="手动分配…",
            command=self.open_slot_mapper,
        ).pack(side="left", padx=(8, 0))

        self.status_var = tk.StringVar(value="等待生成。")
        self.status = tk.Label(
            inner,
            textvariable=self.status_var,
            bg=CARD,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
            justify="left",
            anchor="w",
            wraplength=380,
        )
        self.status.pack(fill="x", pady=(12, 0))

        tk.Label(
            inner,
            text="默认只在底字库空槽里放汉字；空槽不够时可取消勾选，从 0xC0 起覆盖。",
            bg=CARD,
            fg="#8a5a00",
            font=("Microsoft YaHei UI", 9),
            justify="left",
            wraplength=380,
            anchor="w",
        ).pack(fill="x", pady=(8, 0))

    def _build_preview_card(self, parent: tk.Widget) -> None:
        card = tk.Frame(
            parent,
            bg=CARD,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        card.grid(row=0, column=1, sticky="nsew")

        top = tk.Frame(card, bg=CARD)
        top.pack(fill="x", padx=16, pady=(14, 8))
        self.preview_title_var = tk.StringVar(value="实时预览")
        tk.Label(
            top,
            textvariable=self.preview_title_var,
            bg=CARD,
            fg=INK,
            font=("Microsoft YaHei UI", 12, "bold"),
        ).pack(side="left")
        tk.Label(
            top,
            text="黑格 = 亮像素 · 空格 = 透明",
            bg=CARD,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
        ).pack(side="right")

        self.preview_info_var = tk.StringVar(value="输入中文后自动更新")
        tk.Label(
            card,
            textvariable=self.preview_info_var,
            bg=CARD,
            fg=MUTED,
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(0, 8))

        self.preview_label = tk.Label(
            card,
            text="生成后这里显示第 1 页点阵图\n\n每个汉字 = 1 个 11×17 点阵",
            bg="#f1f1ee",
            fg="#77777b",
            font=("Microsoft YaHei UI", 12),
            anchor="center",
        )
        self.preview_label.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.preview_label.bind("<Configure>", self._on_preview_resize)

    def _set_icon(self) -> None:
        icon = PROJECT_ROOT / "assets" / "osd_icon.ico"
        if icon.exists():
            try:
                self.iconbitmap(default=str(icon))
            except Exception:
                pass

    def _on_preview_resize(self, _event: tk.Event) -> None:
        if self.preview_source is None:
            return
        if self._preview_job:
            self.after_cancel(self._preview_job)
        self._preview_job = self.after(150, self._refresh_preview)

    def _refresh_preview(self) -> None:
        self._preview_job = None
        if self.preview_source is None:
            return
        width = max(320, self.preview_label.winfo_width() - 8)
        height = max(320, self.preview_label.winfo_height() - 8)
        image = self.preview_source.copy()
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        self.preview_photo = ImageTk.PhotoImage(image)
        self.preview_label.configure(image=self.preview_photo, text="")

    def _schedule_live_preview(self, _event: tk.Event | None = None) -> None:
        if self._live_job:
            self.after_cancel(self._live_job)
        self._live_job = self.after(350, self._update_live_preview)

    def _schedule_live_preview_soon(self, _event: tk.Event | None = None) -> None:
        if self._live_job:
            self.after_cancel(self._live_job)
        self._live_job = self.after(40, self._update_live_preview)

    def _update_live_preview(self) -> None:
        self._live_job = None
        text = self.text.get("1.0", "end").strip()
        if text == self._last_live_text:
            return
        self._last_live_text = text

        try:
            image, shown, total, fallback_chars = render_live_preview(text, max_chars=30)
        except Exception as exc:
            self.preview_source = None
            self.preview_photo = None
            self.preview_label.configure(
                image="",
                text=f"预览失败：{exc}",
                fg="#a33",
            )
            self.preview_title_var.set("实时预览")
            self.preview_info_var.set("字体缺字或输入有误")
            return

        if image is None:
            self.preview_source = None
            self.preview_photo = None
            self.preview_label.configure(
                image="",
                text="输入中文后这里实时显示\n\n每个汉字 = 1 个 11×17 点阵",
                fg="#77777b",
            )
            self.preview_title_var.set("实时预览")
            self.preview_info_var.set("等待输入")
            return

        self.preview_source = image
        self.preview_title_var.set("实时预览")
        if total > shown:
            self.preview_info_var.set(
                f"显示前 {shown} 个不同汉字，共 {total} 个；生成后看完整分页"
            )
        else:
            self.preview_info_var.set(f"{total} 个不同汉字 · 实时更新")
        if fallback_chars:
            self.preview_info_var.set(
                self.preview_info_var.get()
                + f" · {len(fallback_chars)} 个字用了系统字体兜底"
            )
        self._refresh_preview()

    def show_preview(self, path: Path) -> None:
        self.preview_source = Image.open(path).convert("RGB")
        self._refresh_preview()

    def choose_output(self) -> None:
        chosen = filedialog.askdirectory(
            title="选择输出文件夹",
            initialdir=self.out_var.get() or str(desktop_dir()),
        )
        if chosen:
            self.out_var.set(chosen)

    def choose_base_font(self) -> None:
        current = Path(self.base_mcm_var.get().strip() or DEFAULT_BASE_MCM)
        chosen = filedialog.askopenfilename(
            title="选择底字库 .mcm",
            initialdir=str(current.parent if current.parent.exists() else PROJECT_ROOT),
            filetypes=[("MAX7456 字库", "*.mcm"), ("所有文件", "*.*")],
        )
        if chosen:
            self.base_mcm_var.set(chosen)
            self.manual_slots.clear()
            self._inspect_base_font()

    def _refresh_base_info(self) -> None:
        manual = f" · 手动映射 {len(self.manual_slots)} 个" if self.manual_slots else ""
        self.base_info_var.set(self._base_summary + manual)
        self.base_info_label.configure(fg=MUTED)

    def _inspect_base_font(self) -> None:
        raw = self.base_mcm_var.get().strip()
        if not raw:
            self._base_summary = "还没有选择底字库"
            self.base_info_var.set(self._base_summary)
            self.base_info_label.configure(fg="#a33")
            return
        path = Path(raw).expanduser()
        if not path.exists():
            self._base_summary = f"找不到：{path.name}"
            self.base_info_var.set(self._base_summary)
            self.base_info_label.configure(fg="#a33")
            return
        try:
            base = load_mcm(path)
            gaps = gap_slots(base)
        except Exception as exc:
            self._base_summary = f"读不了：{exc}"
            self.base_info_var.set(self._base_summary)
            self.base_info_label.configure(fg="#a33")
            return
        self._base_summary = f"{path.name} · 可用空槽 {len(gaps)} 个"
        self._refresh_base_info()

    def open_slot_mapper(self) -> None:
        text = self.text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("没有输入", "先输入要显示的中文。")
            return
        base_path = Path(
            self.base_mcm_var.get().strip() or str(DEFAULT_BASE_MCM)
        ).expanduser()
        if not base_path.exists():
            messagebox.showerror("底字库不存在", f"{base_path}\n\n请重新选择 .mcm。")
            return
        try:
            font = load_font(DEFAULT_FONT, 12)
            glyphs = build_glyphs(text, font, 0)
        except Exception as exc:
            messagebox.showerror("生成汉字失败", f"{type(exc).__name__}: {exc}")
            return
        if not glyphs:
            messagebox.showwarning("没有汉字", "输入里没有可写入字库的汉字。")
            return
        try:
            dialog = SlotMapper(self, base_path, glyphs, self.manual_slots)
        except Exception as exc:
            messagebox.showerror("打开槽位表失败", f"{type(exc).__name__}: {exc}")
            return
        self.wait_window(dialog)
        if dialog.result is not None:
            self.manual_slots = dict(dialog.result)
            self._refresh_base_info()
            self.status_var.set(
                f"手动映射已保存：{len(self.manual_slots)} 个汉字。\n"
                "现在点“生成点阵图 + .mcm”即可使用。"
            )

    def restore_default(self) -> None:
        self.text.delete("1.0", "end")
        self.text.insert("1.0", DEFAULT_TEXT)
        self.status_var.set("已恢复默认字表。")
        self._schedule_live_preview_soon()

    def open_output(self) -> None:
        target = self.last_output
        if target is None:
            target = Path(self.out_var.get().strip() or desktop_dir())
        if not target.exists():
            try:
                target.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                messagebox.showerror("打不开", f"{target}\n\n{exc}")
                return
        try:
            os.startfile(str(target))
        except Exception:
            import subprocess

            subprocess.Popen(["explorer", str(target)])

    def generate(self) -> None:
        text = self.text.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning("没有输入", "先输入要显示的中文。")
            return

        base_text = self.out_var.get().strip()
        if not base_text:
            messagebox.showwarning("没有输出目录", "请选择输出文件夹。")
            return
        base = Path(base_text).expanduser()
        try:
            out_dir = unique_output_dir(base)
        except Exception as exc:
            messagebox.showerror("输出目录不可用", f"{base}\n\n{exc}")
            return

        mcm_requested = self.mcm_var.get()
        mcm_mode = "gaps" if self.gaps_only.get() else "compact"
        chars = unique_chars(text)
        slot_map: dict[str, int] | None = None
        if mcm_requested and self.manual_slots:
            missing = [char for char in chars if char not in self.manual_slots]
            if not missing:
                slot_map = {char: self.manual_slots[char] for char in chars}
                mcm_mode = "manual"
            else:
                open_mapper = messagebox.askyesno(
                    "手动映射不完整",
                    f"还有 {len(missing)} 个汉字没有手动槽位：{''.join(missing)}\n\n"
                    "要现在手动分配吗？选“否”会改用自动空槽。",
                )
                if open_mapper:
                    self.open_slot_mapper()
                    return
        base_path = Path(
            self.base_mcm_var.get().strip() or str(DEFAULT_BASE_MCM)
        ).expanduser()
        if mcm_requested:
            if not base_path.exists():
                messagebox.showerror("底字库不存在", f"{base_path}\n\n请重新选择 .mcm。")
                return
            if self.gaps_only.get() and slot_map is None:
                try:
                    base_chars = load_mcm(base_path)
                    gaps = gap_slots(base_chars)
                except Exception as exc:
                    messagebox.showerror("底字库不可用", f"{base_path}\n\n{exc}")
                    return
                needed = len(unique_chars(text))
                if needed > len(gaps):
                    proceed = messagebox.askyesno(
                        "空槽不够",
                        f"需要 {needed} 个不同汉字，底字库只有 {len(gaps)} 个空槽。\n\n"
                        "仍要生成点阵图吗？这次不会生成 .mcm。",
                    )
                    if not proceed:
                        return
                    mcm_requested = False

        self.status_var.set("正在生成，请稍等…")
        self.generate_button.configure(state="disabled", bg="#8a8a8a")
        self.update_idletasks()
        try:
            glyphs, pages, _font, mcm_info = generate_all(
                text,
                out_dir,
                title="OSD 中文点阵 · 自定义",
                mcm=mcm_requested,
                mcm_mode=mcm_mode,
                mcm_start=0xC0,
                base_mcm=base_path,
                slot_map=slot_map,
            )
        except Exception as exc:
            messagebox.showerror("生成失败", f"{type(exc).__name__}: {exc}")
            self.status_var.set("生成失败，详见弹窗。")
            return
        finally:
            self.generate_button.configure(state="normal", bg=ACCENT)

        self.last_output = out_dir
        if self._live_job:
            self.after_cancel(self._live_job)
            self._live_job = None
        self._last_live_text = text
        status = f"完成：{len(glyphs)} 个字，{len(pages)} 页。\n{out_dir}"
        if mcm_info.path:
            status += (
                f"\n.mcm：0x{min(mcm_info.slots):02X}–0x{max(mcm_info.slots):02X}"
                f"，覆盖 {len(mcm_info.overwritten)} 个非空槽"
                + ("（手动映射）" if mcm_info.mode == "manual" else "")
            )
        elif mcm_info.error:
            status += f"\n.mcm 未生成：{mcm_info.error}"
        elif not mcm_requested:
            status += "\n本次只生成点阵图，没有写 .mcm。"
        self.status_var.set(status)
        self.preview_title_var.set("生成结果（第 1 页）")
        self.preview_info_var.set(f"完整输出：{len(glyphs)} 个字，{len(pages)} 页")
        self.show_preview(out_dir / "dotmatrix_page_01.png")
        if self.auto_open.get():
            self.open_output()


def run_headless(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--selftest", nargs="?", const="__default__")
    parser.add_argument("--livecheck", type=Path)
    parser.add_argument("--text")
    parser.add_argument("--out-dir", type=Path)
    args, _unknown = parser.parse_known_args(argv)

    if args.selftest is not None:
        out = (
            Path(args.selftest)
            if args.selftest != "__default__"
            else Path.cwd() / "selftest_out"
        )
        glyphs, pages, _font, _mcm_info = generate_all(
            "电压电流高度速度距离卫星",
            out,
            title="OSD 自检",
        )
        (out / "selftest_ok.txt").write_text(
            f"glyphs={len(glyphs)} pages={len(pages)}\n",
            encoding="utf-8",
        )
        return 0

    if args.livecheck:
        image, shown, total, _fallback_chars = render_live_preview(DEFAULT_TEXT)
        if image is None:
            raise RuntimeError("实时预览没有生成图像")
        image.save(args.livecheck)
        print(f"livecheck: {shown}/{total} chars -> {args.livecheck}")
        return 0

    if args.text:
        out = args.out_dir or (Path.cwd() / "OSD中文点阵输出")
        generate_all(args.text, out, title="OSD 中文点阵 · 自定义")
        return 0
    return -1


def main() -> int:
    headless = run_headless(sys.argv[1:])
    if headless >= 0:
        return headless

    enable_high_dpi()
    app = App()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
