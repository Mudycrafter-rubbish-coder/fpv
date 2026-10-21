#!/usr/bin/env python3
"""Generate hand-drawable 11x17 dot-matrix sheets for Chinese OSD glyphs.

The target is an AT7456E / MAX7456-compatible OSD font.  The chip stores
12x18 pixels per character; this tool uses the 11x17 area the user draws in.
Each Chinese glyph is rendered from a 12 px CJK pixel font, cropped to its
11x11 ink box, and placed on rows 4-14 of the 17-row cell.  The result is a
human-readable reference sheet, not an .mcm font file.

Examples
--------
python tools/osd_cn_dotmatrix.py
python tools/osd_cn_dotmatrix.py --text "电压电流高度速度" --out-dir outputs/osd_font_test
python tools/osd_cn_dotmatrix.py --text-file my_chars.txt --page-cols 5
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont


def _resource_root() -> Path:
    """Project root in source mode; PyInstaller extraction root when frozen."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[1]


PROJECT_ROOT = _resource_root()
DEFAULT_FONT = (
    PROJECT_ROOT
    / "assets"
    / "fonts"
    / "fusion-pixel-12px-monospaced-zh_hans.ms.bitmap.ttf"
)
DEFAULT_BASE_MCM = PROJECT_ROOT / "assets" / "fonts" / "betaflight_base.mcm"
DEFAULT_TEXT = (
    "电压电流高度速度距离卫星飞行时间姿态解锁失控返航"
    "电池温度信号油门模式警告低电量上升下降方向家里程"
    "转剩余分秒米公千最大小平均总连接断"
)

CELL_W = 11
CELL_H = 17
GLYPH_W = 11
GLYPH_H = 11
GLYPH_TOP = 3  # 0-based; rows 4-14 in a 1-based drawing grid

LABEL_FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/Deng.ttf"),
    Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
]


@dataclass
class Glyph:
    char: str
    index: int
    code: int
    rows: list[str]  # 17 strings, 11 chars each, '#' or '.'
    source: str = "pixel"  # "pixel" or "fallback"

    @property
    def bits(self) -> list[list[int]]:
        return [[1 if c == "#" else 0 for c in row] for row in self.rows]


@dataclass
class McmInfo:
    path: Path | None = None
    header_path: Path | None = None
    map_path: Path | None = None
    base_path: Path | None = None
    mode: str = "compact"
    slots: list[int] = field(default_factory=list)
    overwritten: list[int] = field(default_factory=list)
    error: str | None = None


def unique_chars(text: str, include_ascii: bool = False) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for ch in text:
        if ch.isspace() or ch in seen:
            continue
        if not include_ascii and ord(ch) < 128:
            continue
        seen.add(ch)
        out.append(ch)
    return out


def find_label_font() -> Path:
    for path in LABEL_FONT_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError(
        "找不到用于标注中文的字体；请安装微软雅黑/Noto Sans CJK，"
        "或用 --label-font 指定一个中文字体。"
    )


def load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    if not path.exists():
        raise FileNotFoundError(f"字体不存在: {path}")
    return ImageFont.truetype(str(path), size=size)


class MissingGlyphError(ValueError):
    """Raised when neither the pixel font nor a system fallback has a glyph."""


_NOTDEF_CHAR = "\U0010FFFF"
_notdef_cache: dict[tuple[str, int], tuple[tuple[int, int], bytes]] = {}


def _notdef_bitmap(font: ImageFont.FreeTypeFont) -> tuple[tuple[int, int], bytes]:
    key = (str(getattr(font, "path", "")), int(getattr(font, "size", 0)))
    cached = _notdef_cache.get(key)
    if cached is None:
        mask = font.getmask(_NOTDEF_CHAR, mode="L")
        cached = (mask.size, bytes(mask))
        _notdef_cache[key] = cached
    return cached


def font_has_glyph(font: ImageFont.FreeTypeFont, char: str) -> bool:
    """Detect the font's .notdef box without requiring fontTools.

    A missing character is rendered as glyph 0 (.notdef), which is usually a
    hollow rectangle.  Comparing its mask to a known unmapped codepoint avoids
    silently writing that rectangle into the OSD font.
    """
    if not char or char.isspace():
        return False
    try:
        mask = font.getmask(char, mode="L")
    except Exception:
        return False
    notdef_size, notdef_bytes = _notdef_bitmap(font)
    return mask.size != notdef_size or bytes(mask) != notdef_bytes


def _render_pixel_font_glyph(
    char: str,
    font: ImageFont.FreeTypeFont,
    threshold: int = 128,
) -> list[str]:
    """Render a character from the bundled 12 px bitmap font."""
    canvas = Image.new("L", (48, 48), 0)
    draw = ImageDraw.Draw(canvas)
    draw.text((0, 0), char, font=font, fill=255)
    binary = canvas.point(lambda p: 255 if p >= threshold else 0)
    bbox = binary.getbbox()
    if bbox is None:
        raise ValueError(f"字体没有渲染出「{char}」的像素；可能缺字。")

    ink = binary.crop(bbox)
    if ink.width > GLYPH_W or ink.height > GLYPH_H:
        # Outline-font fallback: fit the ink box without changing aspect ratio.
        ratio = min(GLYPH_W / ink.width, GLYPH_H / ink.height)
        size = (
            max(1, round(ink.width * ratio)),
            max(1, round(ink.height * ratio)),
        )
        ink = ink.resize(size, Image.Resampling.LANCZOS)
        ink = ink.point(lambda p: 255 if p >= threshold else 0)

    # Verify that the font actually contains a visible glyph, not just a box.
    if not ink.getbbox():
        raise ValueError(f"字体没有渲染出「{char}」的可见像素；可能缺字。")

    grid = [["." for _ in range(CELL_W)] for _ in range(CELL_H)]
    x0 = (GLYPH_W - ink.width) // 2
    y0 = GLYPH_TOP + (GLYPH_H - ink.height)
    for y in range(ink.height):
        for x in range(ink.width):
            if ink.getpixel((x, y)) >= threshold:
                gx, gy = x0 + x, y0 + y
                if 0 <= gx < CELL_W and 0 <= gy < CELL_H:
                    grid[gy][gx] = "#"
    return ["".join(row) for row in grid]


def render_pixel_glyph(
    char: str,
    font: ImageFont.FreeTypeFont,
    threshold: int = 128,
) -> list[str]:
    """Render one character from a font known to contain it."""
    if not font_has_glyph(font, char):
        raise MissingGlyphError(f"字体里没有「{char}」（U+{ord(char):04X}）")
    return _render_pixel_font_glyph(char, font, threshold=threshold)


def _render_outline_font_glyph(
    char: str,
    font: ImageFont.FreeTypeFont,
    threshold: int = 110,
) -> list[str]:
    """Downsample a system CJK outline font for rare characters.

    11x11 is very small, so this is intentionally a fallback: it keeps the
    character usable instead of emitting a .notdef rectangle, but complex
    glyphs will look dense.
    """
    canvas = Image.new("L", (256, 256), 0)
    draw = ImageDraw.Draw(canvas)
    draw.text((0, 0), char, font=font, fill=255)
    bbox = canvas.getbbox()
    if bbox is None:
        raise MissingGlyphError(f"兜底字体没有渲染出「{char}」")

    ink = canvas.crop(bbox)
    ratio = min(GLYPH_W / ink.width, GLYPH_H / ink.height)
    size = (
        max(1, round(ink.width * ratio)),
        max(1, round(ink.height * ratio)),
    )
    ink = ink.resize(size, Image.Resampling.LANCZOS)
    ink = ink.point(lambda p: 255 if p >= threshold else 0)

    grid = [["." for _ in range(CELL_W)] for _ in range(CELL_H)]
    x0 = (GLYPH_W - ink.width) // 2
    y0 = GLYPH_TOP + (GLYPH_H - ink.height)
    for y in range(ink.height):
        for x in range(ink.width):
            if ink.getpixel((x, y)) >= threshold:
                gx, gy = x0 + x, y0 + y
                if 0 <= gx < CELL_W and 0 <= gy < CELL_H:
                    grid[gy][gx] = "#"
    return ["".join(row) for row in grid]


def render_glyph_with_fallback(
    char: str,
    font: ImageFont.FreeTypeFont,
    *,
    fallback_fonts: Iterable[Path] | None = None,
) -> tuple[list[str], str]:
    """Return (rows, source).  source is 'pixel' or 'fallback'."""
    if font_has_glyph(font, char):
        return _render_pixel_font_glyph(char, font), "pixel"

    candidates = list(fallback_fonts or LABEL_FONT_CANDIDATES)
    for path in candidates:
        if not path.exists():
            continue
        try:
            candidate = load_font(path, 128)
        except Exception:
            continue
        if not font_has_glyph(candidate, char):
            continue
        return _render_outline_font_glyph(char, candidate), "fallback"

    raise MissingGlyphError(
        f"「{char}」（U+{ord(char):04X}）在内置像素字库和系统兜底字体里都没有，"
        "请换字或手动补一个字形。"
    )


def build_glyphs(
    text: str,
    font: ImageFont.FreeTypeFont,
    code_start: int,
    *,
    include_ascii: bool = False,
) -> list[Glyph]:
    chars = unique_chars(text, include_ascii=include_ascii)
    if not chars:
        raise ValueError("输入里没有可用的非空白字符。")
    if code_start < 0 or code_start + len(chars) > 256:
        raise ValueError("code-start 加上字符数超过 0xFF，256 个格放不下。")
    glyphs: list[Glyph] = []
    for i, ch in enumerate(chars):
        rows, source = render_glyph_with_fallback(ch, font)
        glyphs.append(Glyph(ch, i + 1, code_start + i, rows, source))
    return glyphs


class McmCapacityError(ValueError):
    """Raised when the requested glyphs do not fit in the available slots."""


def load_mcm(path: Path) -> list[list[int]]:
    """Read a MAX7456 .mcm file into 256 x 216 pixel values (0/1/2)."""
    path = Path(path)
    text = path.read_text(encoding="ascii")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "MAX7456":
        raise ValueError(f"{path.name} 不是 MAX7456 .mcm（缺少 MAX7456 头）")
    data = lines[1:]
    expected = 256 * 64
    if len(data) != expected:
        raise ValueError(f"{path.name} 行数不对：{len(data)}，应为 {expected}")

    chars: list[list[int]] = []
    for char_index in range(256):
        pixels: list[int] = []
        for line in data[char_index * 64 : (char_index + 1) * 64]:
            if len(line) != 8 or any(ch not in "01" for ch in line):
                raise ValueError(
                    f"{path.name} 第 {char_index + 1} 个字符里有非法行：{line!r}"
                )
            for i in range(0, 8, 2):
                pixels.append(int(line[i : i + 2], 2))
        chars.append(pixels[:216])
    return chars


def gap_slots(base: Sequence[Sequence[int]]) -> list[int]:
    """Return usable blank slots, preferring 0x80+ over ASCII gaps.

    The blank space character (0x20) and end-of-font marker (0xFF) are never
    used.  Control codes 0x00-0x1F are skipped because some firmwares treat
    them as OSD control/symbol codes even when their glyph is blank.
    """
    def blank(code: int) -> bool:
        return all(pixel == 1 for pixel in base[code])

    high = [code for code in range(0x80, 0xFF) if blank(code)]
    ascii_gaps = [code for code in range(0x20, 0x7F) if code != 0x20 and blank(code)]
    return high + ascii_gaps


def write_mcm(chars: Sequence[Sequence[int]], path: Path) -> None:
    """Write the canonical 147,463-byte MAX7456 .mcm file (LF line endings)."""
    if len(chars) != 256:
        raise ValueError("MAX7456 字库必须有 256 个字符")
    with Path(path).open("w", encoding="ascii", newline="\n") as f:
        f.write("MAX7456")
        for pixels in chars:
            values = list(pixels[:216])
            if len(values) < 216:
                values.extend([1] * (216 - len(values)))
            # 216 pixels = 54 bytes; the remaining 10 bytes are 0x55 padding.
            values.extend([1] * (256 - len(values)))
            for row in range(64):
                chunk = values[row * 4 : row * 4 + 4]
                f.write("\n" + "".join(f"{value:02b}" for value in chunk))


def write_mcm_header(chars: Sequence[Sequence[int]], path: Path) -> None:
    """Write the 16 KB packed C header used by several OSD firmwares."""
    if len(chars) != 256:
        raise ValueError("MAX7456 字库必须有 256 个字符")
    packed: list[int] = []
    for pixels in chars:
        values = list(pixels[:216])
        values.extend([1] * (256 - len(values)))
        for i in range(64):
            if i >= 54:
                packed.append(0x55)
                continue
            chunk = values[i * 4 : i * 4 + 4]
            packed.append(
                (chunk[0] << 6)
                | (chunk[1] << 4)
                | (chunk[2] << 2)
                | chunk[3]
            )
    with Path(path).open("w", encoding="ascii", newline="\n") as f:
        f.write("PROGMEM const byte fontdata[16384] = {")
        for i, value in enumerate(packed):
            if i:
                f.write(",")
            if i % 32 == 0:
                f.write("\n  ")
            f.write(f"0x{value:02x}")
        f.write("\n};\n")


def glyph_to_cell(glyph: Glyph) -> list[int]:
    """Place a 17x11 hand-drawing grid into the 18x12 MAX7456 cell."""
    cell = [1] * 216
    for y in range(CELL_H):
        for x in range(CELL_W):
            if glyph.rows[y][x] == "#":
                cell[y * 12 + x] = 2
    return cell


def write_mcm_outputs(
    glyphs: Sequence[Glyph],
    out_dir: Path,
    *,
    base_mcm: Path | None = None,
    mode: str = "compact",
    start: int = 0xC0,
    slot_map: dict[str, int] | None = None,
) -> McmInfo:
    """Merge Chinese glyphs into the Betaflight base font and write .mcm/.h/map."""
    base_path = Path(base_mcm or DEFAULT_BASE_MCM)
    base = load_mcm(base_path)
    count = len(glyphs)

    if slot_map is not None:
        mode = "manual"
        missing = [glyph.char for glyph in glyphs if glyph.char not in slot_map]
        if missing:
            raise ValueError(f"手动映射缺少这些字：{''.join(missing)}")
        slots = [int(slot_map[glyph.char]) for glyph in glyphs]
        if any(slot < 0 or slot > 0xFF for slot in slots):
            raise ValueError("手动映射里有超出 0x00–0xFF 的槽位")
        if len(set(slots)) != len(slots):
            raise ValueError("手动映射里有重复槽位")
    else:
        mode = "gaps" if mode == "safe" else mode
        if mode not in {"compact", "gaps"}:
            raise ValueError("mcm_mode 只能是 gaps（safe）或 compact")
        if mode == "gaps":
            available = gap_slots(base)
            slots = available[:count]
            if len(slots) < count:
                raise McmCapacityError(
                    f"底字库 {base_path.name} 只有 {len(available)} 个空槽，但需要 {count} 个；"
                    "请换一个空槽更多的底字库、缩短文本，或关闭“只填空隙”改用 compact。"
                )
        else:
            if start < 0 or start + count > 0x100:
                raise McmCapacityError(
                    f"compact 模式从 0x{start:02X} 起放不下 {count} 个字；"
                    "请缩短文本，或把 --mcm-start 设小一点（会更早覆盖图标）。"
                )
            slots = list(range(start, start + count))

    overwritten = [
        code
        for code in slots
        if any(pixel != 1 for pixel in base[code])
    ]
    for glyph, slot in zip(glyphs, slots):
        glyph.code = slot

    merged = [pixels[:] for pixels in base]
    for glyph, slot in zip(glyphs, slots):
        merged[slot] = glyph_to_cell(glyph)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mcm_path = out_dir / "osd_cn.mcm"
    header_path = out_dir / "osd_cn.h"
    map_path = out_dir / "osd_cn_map.csv"
    write_mcm(merged, mcm_path)
    write_mcm_header(merged, header_path)

    with map_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["index", "char", "unicode", "code", "slot_decimal", "source", "base_slot_blank"]
        )
        for glyph, slot in zip(glyphs, slots):
            writer.writerow(
                [
                    glyph.index,
                    glyph.char,
                    f"U+{ord(glyph.char):04X}",
                    f"0x{slot:02X}",
                    slot,
                    glyph.source,
                    "yes" if all(pixel == 1 for pixel in base[slot]) else "no",
                ]
            )

    return McmInfo(
        path=mcm_path,
        header_path=header_path,
        map_path=map_path,
        base_path=base_path,
        mode=mode,
        slots=slots,
        overwritten=overwritten,
    )


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = find_label_font()
    if bold and path.name.lower().startswith("msyh"):
        bold_path = path.with_name("msyhbd.ttc")
        if bold_path.exists():
            path = bold_path
    return load_font(path, size)


def _page_layout(
    cols: int,
    rows: int,
    cell: int,
    margin: int = 34,
) -> dict[str, int]:
    grid_w = CELL_W * cell
    grid_h = CELL_H * cell
    block_w = grid_w + 48
    block_h = grid_h + 108
    header_h = 86
    footer_h = 32
    return {
        "grid_w": grid_w,
        "grid_h": grid_h,
        "block_w": block_w,
        "block_h": block_h,
        "header_h": header_h,
        "footer_h": footer_h,
        "page_w": cols * block_w + 2 * margin,
        "page_h": rows * block_h + header_h + footer_h + 2 * margin,
        "margin": margin,
    }


def draw_block(
    draw: ImageDraw.ImageDraw,
    glyph: Glyph,
    x: int,
    y: int,
    cell: int,
    *,
    label_font: ImageFont.FreeTypeFont,
    small_font: ImageFont.FreeTypeFont,
    tiny_font: ImageFont.FreeTypeFont,
) -> None:
    grid_x = x + 30
    grid_y = y + 72
    grid_w = CELL_W * cell
    grid_h = CELL_H * cell

    # Header: character and its metadata.
    draw.text((x + 4, y + 2), glyph.char, font=label_font, fill=(20, 20, 20))
    meta = (
        f"U+{ord(glyph.char):04X}   #{glyph.index:02d}   0x{glyph.code:02X}"
        if glyph.char
        else "空白模板"
    )
    draw.text((x + 62, y + 14), meta, font=small_font, fill=(95, 95, 95))

    # Column numbers.
    for c in range(CELL_W):
        cx = grid_x + c * cell + cell / 2
        draw.text((cx - 4, grid_y - 18), str(c + 1), font=tiny_font, fill=(120, 120, 120))

    # Row numbers.
    for r in range(CELL_H):
        cy = grid_y + r * cell + cell / 2
        draw.text((grid_x - 20, cy - 6), str(r + 1).zfill(2), font=tiny_font, fill=(120, 120, 120))

    # Cells.  White = transparent, black = lit pixel.
    for r, row in enumerate(glyph.rows):
        for c, value in enumerate(row):
            left = grid_x + c * cell
            top = grid_y + r * cell
            if value == "#":
                draw.rectangle(
                    [left, top, left + cell, top + cell],
                    fill=(15, 15, 15),
                )

    # Pixel grid.
    grid_color = (205, 205, 205)
    for c in range(CELL_W + 1):
        px = grid_x + c * cell
        draw.line([(px, grid_y), (px, grid_y + grid_h)], fill=grid_color, width=1)
    for r in range(CELL_H + 1):
        py = grid_y + r * cell
        draw.line([(grid_x, py), (grid_x + grid_w, py)], fill=grid_color, width=1)

    # Stronger outline and the 11x11 glyph box.
    draw.rectangle(
        [grid_x, grid_y, grid_x + grid_w, grid_y + grid_h],
        outline=(30, 30, 30),
        width=2,
    )
    box_top = grid_y + GLYPH_TOP * cell
    box_bottom = box_top + GLYPH_H * cell
    draw.rectangle(
        [grid_x, box_top, grid_x + grid_w, box_bottom],
        outline=(70, 130, 190),
        width=1,
    )


def make_png_page(
    glyphs: Sequence[Glyph],
    out_path: Path,
    *,
    page_cols: int,
    page_rows: int,
    cell: int,
    page_number: int,
    page_count: int,
    title: str,
) -> None:
    layout = _page_layout(page_cols, page_rows, cell)
    page = Image.new("RGB", (layout["page_w"], layout["page_h"]), (250, 250, 248))
    draw = ImageDraw.Draw(page)

    draw.text(
        (layout["margin"], 22),
        title,
        font=_font(28, bold=True),
        fill=(20, 20, 20),
    )
    subtitle = (
        f"11×17 点阵 · 蓝色框内为 11×11 字身（第 4–14 行）"
        f" · 第 {page_number}/{page_count} 页"
    )
    draw.text(
        (layout["margin"], 58),
        subtitle,
        font=_font(14),
        fill=(90, 90, 90),
    )

    label_font = _font(34, bold=True)
    small_font = _font(10)
    tiny_font = _font(8)
    for local_index, glyph in enumerate(glyphs):
        col = local_index % page_cols
        row = local_index // page_cols
        x = layout["margin"] + col * layout["block_w"]
        y = layout["header_h"] + layout["margin"] + row * layout["block_h"]
        draw_block(
            draw,
            glyph,
            x,
            y,
            cell,
            label_font=label_font,
            small_font=small_font,
            tiny_font=tiny_font,
        )

    footer = (
        "黑格 = 亮像素；空格 = 透明。只画白/透明，不要把背景涂黑。"
        " 字形参考 Fusion Pixel 12px（SIL OFL 1.1）。"
    )
    draw.text(
        (layout["margin"], layout["page_h"] - 25),
        footer,
        font=_font(10),
        fill=(110, 110, 110),
    )
    page.save(out_path)


def svg_block(glyph: Glyph, x: int, y: int, cell: int) -> str:
    grid_x = x + 30
    grid_y = y + 72
    grid_w = CELL_W * cell
    grid_h = CELL_H * cell
    parts: list[str] = []
    parts.append(
        f'<text x="{x + 4}" y="{y + 42}" font-size="34" font-weight="700" fill="#141414">'
        f"{escape(glyph.char)}</text>"
    )
    meta = (
        f"U+{ord(glyph.char):04X} · #{glyph.index:02d} · 0x{glyph.code:02X}"
        if glyph.char
        else "空白模板"
    )
    parts.append(
        f'<text x="{x + 62}" y="{y + 34}" font-size="11" fill="#5f5f5f">'
        f"{meta}</text>"
    )
    for c in range(CELL_W):
        cx = grid_x + c * cell + cell / 2
        parts.append(
            f'<text x="{cx:.2f}" y="{grid_y - 7}" text-anchor="middle" '
            f'font-size="8" fill="#787878">{c + 1}</text>'
        )
    for r in range(CELL_H):
        cy = grid_y + r * cell + cell / 2 + 3
        parts.append(
            f'<text x="{grid_x - 6}" y="{cy:.2f}" text-anchor="end" '
            f'font-size="8" fill="#787878">{r + 1:02d}</text>'
        )
    for r, row in enumerate(glyph.rows):
        for c, value in enumerate(row):
            if value == "#":
                left = grid_x + c * cell
                top = grid_y + r * cell
                parts.append(
                    f'<rect x="{left}" y="{top}" width="{cell}" height="{cell}" '
                    'fill="#0f0f0f"/>'
                )
    grid_lines: list[str] = []
    for c in range(CELL_W + 1):
        px = grid_x + c * cell
        grid_lines.append(f"M{px},{grid_y}V{grid_y + grid_h}")
    for r in range(CELL_H + 1):
        py = grid_y + r * cell
        grid_lines.append(f"M{grid_x},{py}H{grid_x + grid_w}")
    parts.append(
        f'<path d="{" ".join(grid_lines)}" fill="none" stroke="#cdcdcd" '
        'stroke-width="1" shape-rendering="crispEdges"/>'
    )
    parts.append(
        f'<rect x="{grid_x}" y="{grid_y}" width="{grid_w}" height="{grid_h}" '
        'fill="none" stroke="#1e1e1e" stroke-width="2"/>'
    )
    box_top = grid_y + GLYPH_TOP * cell
    parts.append(
        f'<rect x="{grid_x}" y="{box_top}" width="{grid_w}" height="{GLYPH_H * cell}" '
        'fill="none" stroke="#4682be" stroke-width="1"/>'
    )
    return "\n".join(parts)


def make_svg(
    glyphs: Sequence[Glyph],
    out_path: Path,
    *,
    page_cols: int,
    page_rows: int,
    cell: int,
    title: str,
) -> None:
    layout = _page_layout(page_cols, page_rows, cell)
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout["page_w"]}" '
        f'height="{layout["page_h"]}" viewBox="0 0 {layout["page_w"]} {layout["page_h"]}">',
        '<rect width="100%" height="100%" fill="#fafaf8"/>',
        '<style>text{font-family:"Microsoft YaHei","Noto Sans SC","PingFang SC",sans-serif}</style>',
        f'<text x="{layout["margin"]}" y="42" font-size="28" font-weight="700" fill="#141414">'
        f"{escape(title)}</text>",
        f'<text x="{layout["margin"]}" y="68" font-size="14" fill="#5a5a5a">'
        "11×17 点阵 · 蓝色框内为 11×11 字身（第 4–14 行）</text>",
    ]
    for local_index, glyph in enumerate(glyphs):
        col = local_index % page_cols
        row = local_index // page_cols
        x = layout["margin"] + col * layout["block_w"]
        y = layout["header_h"] + layout["margin"] + row * layout["block_h"]
        parts.append(svg_block(glyph, x, y, cell))
    parts.append(
        f'<text x="{layout["margin"]}" y="{layout["page_h"] - 18}" font-size="10" fill="#6e6e6e">'
        "黑格 = 亮像素；空格 = 透明。字形参考 Fusion Pixel 12px（SIL OFL 1.1）。</text>"
    )
    parts.append("</svg>")
    out_path.write_text("\n".join(parts), encoding="utf-8")


def make_blank(cell: int, out_png: Path, out_svg: Path) -> None:
    width = CELL_W * cell + 140
    height = CELL_H * cell + 160
    img = Image.new("RGB", (width, height), (250, 250, 248))
    draw = ImageDraw.Draw(img)
    draw.text((28, 24), "空白 11×17 点阵模板", font=_font(28, bold=True), fill=(20, 20, 20))
    draw.text(
        (28, 64),
        "每格 1 像素；黑格 = 亮像素（2），空格 = 透明（1）。",
        font=_font(14),
        fill=(90, 90, 90),
    )
    glyph = Glyph("", 0, 0, ["." * CELL_W for _ in range(CELL_H)])
    draw_block(
        draw,
        glyph,
        28,
        92,
        cell,
        label_font=_font(30),
        small_font=_font(10),
        tiny_font=_font(8),
    )
    img.save(out_png)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fafaf8"/>',
        '<style>text{font-family:"Microsoft YaHei","Noto Sans SC",sans-serif}</style>',
        '<text x="28" y="44" font-size="28" font-weight="700" fill="#141414">'
        "空白 11×17 点阵模板</text>",
        '<text x="28" y="76" font-size="14" fill="#5a5a5a">'
        "每格 1 像素；黑格 = 亮像素（2），空格 = 透明（1）。</text>",
        svg_block(glyph, 28, 92, cell),
        "</svg>",
    ]
    out_svg.write_text("\n".join(parts), encoding="utf-8")


def make_preview(glyphs: Sequence[Glyph], out_path: Path) -> None:
    """A small simulated OSD screen using the generated Chinese glyphs."""
    lines = [
        "电压 12.6V",
        "电流 28.4A",
        "高度 86m",
        "速度 42km",
        "卫星 12",
        "飞行 03:42",
        "姿态 解锁",
        "返航 距离 1.2km",
        "低电量 返航",
    ]
    by_char = {g.char: g for g in glyphs}
    preview_font = load_font(DEFAULT_FONT, 12)
    fallback_rows: dict[str, list[str]] = {}

    def rows_for(ch: str) -> list[str]:
        if ch in by_char:
            return by_char[ch].rows
        if ch not in fallback_rows:
            fallback_rows[ch] = render_pixel_glyph(ch, preview_font)
        return fallback_rows[ch]

    cols, rows = 30, 16
    cell_w, cell_h = 12, 18
    screen = Image.new("RGB", (cols * cell_w, rows * cell_h), (5, 10, 16))

    # Draw a subtle scanline / gradient so the preview reads as a video image.
    for y in range(screen.height):
        shade = 8 + int(12 * y / max(1, screen.height - 1))
        for x in range(screen.width):
            screen.putpixel((x, y), (shade // 2, shade, shade // 2 + 4))

    for line_index, line in enumerate(lines):
        x_cell = 1
        y_cell = 1 + line_index * 1.55
        for ch in line:
            if ch == " ":
                x_cell += 1
                continue
            for r, row in enumerate(rows_for(ch)):
                for c, value in enumerate(row):
                    if value == "#":
                        px = x_cell * cell_w + c
                        py = int(y_cell * cell_h) + r
                        if 0 <= px < screen.width and 0 <= py < screen.height:
                            screen.putpixel((px, py), (245, 245, 235))
            x_cell += 1

    scale = 4
    preview = screen.resize(
        (screen.width * scale, screen.height * scale),
        Image.Resampling.NEAREST,
    )
    canvas = Image.new("RGB", (preview.width + 48, preview.height + 98), (250, 250, 248))
    canvas.paste(preview, (24, 70))
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 18), "OSD 效果预览（实际 360×288，放大 4×）", font=_font(24, bold=True), fill=(20, 20, 20))
    draw.text(
        (24, 48),
        "中文按 1 个 OSD 字符格显示；这里只演示字形，不代表 Betaflight 已内置中文标签。",
        font=_font(11),
        fill=(95, 95, 95),
    )
    canvas.save(out_path)


def write_data(glyphs: Sequence[Glyph], out_dir: Path) -> None:
    with (out_dir / "glyphs.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["index", "char", "unicode", "suggested_code", "source"]
            + [f"row_{i:02d}" for i in range(1, CELL_H + 1)]
        )
        for g in glyphs:
            writer.writerow(
                [g.index, g.char, f"U+{ord(g.char):04X}", f"0x{g.code:02X}", g.source]
                + [row.replace("#", "1").replace(".", "0") for row in g.rows]
            )

    data = {
        "cell_width": CELL_W,
        "cell_height": CELL_H,
        "glyph_width": GLYPH_W,
        "glyph_height": GLYPH_H,
        "glyph_top": GLYPH_TOP,
        "legend": {"#": "lit pixel (white)", ".": "transparent"},
        "glyphs": [
            {
                "index": g.index,
                "char": g.char,
                "unicode": f"U+{ord(g.char):04X}",
                "suggested_code": f"0x{g.code:02X}",
                "source": g.source,
                "rows": g.rows,
            }
            for g in glyphs
        ],
    }
    (out_dir / "glyphs.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = ["OSD 中文 11×17 点阵", "黑格# = 亮，点. = 透明；每行 11 格，共 17 行。", ""]
    for g in glyphs:
        lines.append(
            f"{g.char}  U+{ord(g.char):04X}  #{g.index:02d}  0x{g.code:02X}  source={g.source}"
        )
        lines.extend(g.rows)
        lines.append("")
    (out_dir / "glyphs.txt").write_text("\n".join(lines), encoding="utf-8")


def write_readme(
    out_dir: Path,
    glyphs: Sequence[Glyph],
    *,
    text: str,
    font_path: Path,
    mcm_info: McmInfo,
) -> None:
    chars = "".join(g.char for g in glyphs)
    fallback_chars = [g.char for g in glyphs if g.source == "fallback"]
    if fallback_chars:
        fallback_note = (
            f"\n> 注意：以下 {len(fallback_chars)} 个字不在内置像素字库里，"
            f"使用了系统字体兜底，11×11 下可能较挤：`{''.join(fallback_chars)}`。\n"
        )
    else:
        fallback_note = ""
    try:
        font_display = font_path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        font_display = font_path.name
    if mcm_info.path:
        slot_min = min(mcm_info.slots)
        slot_max = max(mcm_info.slots)
        base_name = (
            mcm_info.base_path.name if mcm_info.base_path is not None else "底字库"
        )
        overwritten = mcm_info.overwritten
        overwrite_note = ""
        if overwritten:
            shown = " ".join(f"0x{code:02X}" for code in overwritten[:20])
            if len(overwritten) > 20:
                shown += f" …（共 {len(overwritten)} 个）"
            overwrite_note = (
                f"\n**覆盖了原有非空槽位 {len(overwritten)} 个：** `{shown}`。"
                "如果你还要用这些槽对应的 OSD 图标，请改用 safe 模式或换起始槽位。\n"
            )
        mcm_note = f"""### .mcm 字库

- 文件：`osd_cn.mcm`（标准 MAX7456 格式，147,463 字节）
- 模式：`{mcm_info.mode}`，槽位 **0x{slot_min:02X}–0x{slot_max:02X}**
- 固件头文件：`osd_cn.h`
- 字符映射表：`osd_cn_map.csv`

MAX7456 只有 256 个字符码，汉字每个占 1 槽。`.mcm` 里的其他字符来自底字库
`{base_name}`，汉字只写入上面的槽位。{overwrite_note}
"""
    elif mcm_info.error:
        mcm_note = f"""### .mcm 未生成

`{mcm_info.error}`

点阵图仍然已生成；缩短文本或调整槽位策略后会重新尝试写 `.mcm`。
"""
    else:
        mcm_note = ""
    readme = f"""# OSD 中文点阵图

这是给 AT7456E / MAX7456 类 OSD 用的 **11×17 点阵图 + 可直接烧录的 `.mcm` 字库**。

- 每个字占 1 个 OSD 字符格。
- 图里的黑格 = 亮像素（值 2），空格 = 透明（值 1）。
- 11×11 的字身放在第 **4–14 行**；蓝框就是字身范围。
- 第 1–3 行、15–17 行留白，方便和原有数字/英文字母对齐。
- 列号 1–11，行号 1–17 都标在格子边上。

## 文件

| 文件 | 用途 |
|---|---|
| `dotmatrix_page_*.png` | 直接照着画的点阵总表 |
| `dotmatrix_all.svg` | 矢量版，可无损放大 |
| `blank_11x17.png` / `.svg` | 空白模板 |
| `preview_osd.png` | 模拟 OSD 显示效果 |
| `glyphs.csv` | 每行 17 个 0/1 串，方便批量处理 |
| `glyphs.txt` | 纯文本点阵，适合复制粘贴 |
| `glyphs.json` | 程序读取用 |
| `osd_cn.mcm` | MAX7456 字库，Betaflight 字体管理器可加载 |
| `osd_cn.h` | 16 KB 打包 C 头文件，给自定义固件用 |
| `osd_cn_map.csv` | 汉字 ↔ 字符槽映射 |

## 本次字符

共 **{len(glyphs)}** 个：

`{chars}`

{fallback_note}

{mcm_note}

## 重新生成

```powershell
.venv\\Scripts\\python.exe tools\\osd_cn_dotmatrix.py --text "你要显示的中文" --out-dir outputs\\osd_font
```

默认字形来自 `{font_display}`，是 12px 中文像素字体；
11×11 字身在 17 行格子里上下居中，底边对齐第 14 行。

## 重要限制

MAX7456 只有 256 个字符槽，汉字每个占 1 槽。图里的 `#01–#NN` 只是顺序编号；
`glyphs.csv/json` 里的 `suggested_code` 是实际写入 `.mcm` 的字符码。
另外，Betaflight 固件里的 OSD 标签本身是写死的英文，换字库不会自动把 `VOLT` 变成“电压”；
要显示中文，需要有自定义字符码的输出方式（或改固件/使用支持自定义文本的 OSD 方案）。
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="生成 11×17 中文 OSD 点阵图和 MAX7456 .mcm 字库"
    )
    parser.add_argument("--text", default=DEFAULT_TEXT, help="要生成的中文字符串")
    parser.add_argument("--text-file", type=Path, help="从 UTF-8 文本文件读取字符")
    parser.add_argument("--out-dir", type=Path, default=PROJECT_ROOT / "outputs" / "osd_font")
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT, help="中文像素字体")
    parser.add_argument("--font-size", type=int, default=12, help="字体渲染尺寸，像素字体用 12")
    parser.add_argument("--code-start", type=lambda s: int(s, 0), default=0xC0)
    parser.add_argument(
        "--mcm-mode",
        choices=["compact", "gaps", "safe"],
        default="compact",
        help="compact=从 mcm-start 连续写；gaps/safe=只写底字库空槽",
    )
    parser.add_argument(
        "--mcm-start",
        type=lambda s: int(s, 0),
        default=0xC0,
        help="compact 模式的起始槽位，默认 0xC0",
    )
    parser.add_argument(
        "--base-mcm",
        type=Path,
        default=DEFAULT_BASE_MCM,
        help="作为底字库的 Betaflight .mcm",
    )
    parser.add_argument("--no-mcm", action="store_true", help="只出点阵图，不写 .mcm")
    parser.add_argument(
        "--include-ascii",
        action="store_true",
        help="连 ASCII 字符也生成（默认跳过，因为 OSD 原有字库已有）",
    )
    parser.add_argument("--page-cols", type=int, default=6)
    parser.add_argument("--page-rows", type=int, default=5)
    parser.add_argument("--cell", type=int, default=22, help="PNG 每格像素")
    parser.add_argument("--title", default="OSD 中文点阵 · 常用飞控术语")
    parser.add_argument("--no-preview", action="store_true")
    return parser.parse_args(argv)


def generate_all(
    text: str,
    out_dir: Path,
    *,
    font_path: Path | None = None,
    font_size: int = 12,
    code_start: int = 0xC0,
    include_ascii: bool = False,
    page_cols: int = 6,
    page_rows: int = 5,
    cell: int = 22,
    title: str = "OSD 中文点阵 · 常用飞控术语",
    preview: bool = True,
    mcm: bool = True,
    mcm_mode: str = "compact",
    mcm_start: int = 0xC0,
    base_mcm: Path | None = None,
    slot_map: dict[str, int] | None = None,
) -> tuple[list[Glyph], list[list[Glyph]], Path, McmInfo]:
    """Generate the complete package and return (glyphs, pages, font, mcm_info)."""
    if page_cols < 1 or page_rows < 1:
        raise ValueError("page_cols / page_rows 必须大于 0")
    if cell < 4:
        raise ValueError("cell 太小，建议至少 8")

    resolved_font = (font_path or DEFAULT_FONT).resolve()
    font = load_font(resolved_font, font_size)
    glyphs = build_glyphs(
        text,
        font,
        0 if mcm else code_start,
        include_ascii=include_ascii,
    )
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    mcm_info = McmInfo(mode=mcm_mode)
    if mcm:
        try:
            mcm_info = write_mcm_outputs(
                glyphs,
                out_dir,
                base_mcm=base_mcm,
                mode=mcm_mode,
                start=mcm_start,
                slot_map=slot_map,
            )
        except Exception as exc:
            # Keep the charts usable even when the requested text does not fit
            # the chosen slot strategy.
            mcm_info = McmInfo(mode=mcm_mode, error=f"{type(exc).__name__}: {exc}")

    per_page = page_cols * page_rows
    pages = [glyphs[i : i + per_page] for i in range(0, len(glyphs), per_page)]
    for page_index, page_glyphs in enumerate(pages, start=1):
        rows_this_page = min(page_rows, math.ceil(len(page_glyphs) / page_cols))
        make_png_page(
            page_glyphs,
            out_dir / f"dotmatrix_page_{page_index:02d}.png",
            page_cols=page_cols,
            page_rows=rows_this_page,
            cell=cell,
            page_number=page_index,
            page_count=len(pages),
            title=title,
        )

    # One tall SVG containing every page; easier to zoom/print than a raster.
    make_svg(
        glyphs,
        out_dir / "dotmatrix_all.svg",
        page_cols=page_cols,
        page_rows=max(page_rows, math.ceil(len(glyphs) / page_cols)),
        cell=cell,
        title=title,
    )
    make_blank(32, out_dir / "blank_11x17.png", out_dir / "blank_11x17.svg")
    if preview:
        make_preview(glyphs, out_dir / "preview_osd.png")

    write_data(glyphs, out_dir)
    write_readme(
        out_dir,
        glyphs,
        text=text,
        font_path=resolved_font,
        mcm_info=mcm_info,
    )
    return glyphs, pages, resolved_font, mcm_info


def render_live_preview(
    text: str,
    *,
    max_chars: int = 30,
    cols: int = 6,
    cell: int = 5,
    margin: int = 12,
    gap: int = 2,
) -> tuple[Image.Image | None, int, int, list[str]]:
    """Render a fast white-on-dark preview of the current text.

    Returns (image, shown_char_count, total_char_count, fallback_chars).
    It intentionally limits itself to the first max_chars distinct characters
    so typing stays responsive even for very long input.
    """
    chars = unique_chars(text)
    if not chars:
        return None, 0, 0, []

    shown = chars[:max_chars]
    font = load_font(DEFAULT_FONT, 12)
    glyphs = build_glyphs("".join(shown), font, 0x80)
    rows = math.ceil(len(glyphs) / cols)
    cell_w = CELL_W * cell
    cell_h = CELL_H * cell
    width = margin * 2 + cols * cell_w + (cols - 1) * gap
    height = margin * 2 + rows * cell_h + (rows - 1) * gap

    image = Image.new("RGB", (width, height), (7, 12, 17))
    draw = ImageDraw.Draw(image)
    for index, glyph in enumerate(glyphs):
        col = index % cols
        row = index // cols
        x0 = margin + col * (cell_w + gap)
        y0 = margin + row * (cell_h + gap)
        draw.rectangle(
            [x0 - 1, y0 - 1, x0 + cell_w, y0 + cell_h],
            fill=(12, 20, 27),
            outline=(28, 42, 52),
        )
        for r, glyph_row in enumerate(glyph.rows):
            for c, value in enumerate(glyph_row):
                if value == "#":
                    draw.rectangle(
                        [
                            x0 + c * cell,
                            y0 + r * cell,
                            x0 + (c + 1) * cell - 1,
                            y0 + (r + 1) * cell - 1,
                        ],
                        fill=(245, 245, 232),
                    )
    fallback_chars = [g.char for g in glyphs if g.source == "fallback"]
    return image, len(glyphs), len(chars), fallback_chars


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    text = args.text
    if args.text_file:
        text = args.text_file.read_text(encoding="utf-8")

    glyphs, pages, _font_path, mcm_info = generate_all(
        text,
        args.out_dir,
        font_path=args.font,
        font_size=args.font_size,
        code_start=args.code_start,
        include_ascii=args.include_ascii,
        page_cols=args.page_cols,
        page_rows=args.page_rows,
        cell=args.cell,
        title=args.title,
        preview=not args.no_preview,
        mcm=not args.no_mcm,
        mcm_mode=args.mcm_mode,
        mcm_start=args.mcm_start,
        base_mcm=args.base_mcm,
    )
    out_dir = args.out_dir.resolve()
    print(f"生成 {len(glyphs)} 个字形，{len(pages)} 页：{out_dir}")
    print("字符：" + "".join(g.char for g in glyphs))
    print("先看：dotmatrix_page_01.png / dotmatrix_all.svg / blank_11x17.png")
    if mcm_info.path:
        print(
            f".mcm：{mcm_info.path}  槽 0x{min(mcm_info.slots):02X}-"
            f"0x{max(mcm_info.slots):02X}  覆盖 {len(mcm_info.overwritten)} 个非空槽"
        )
    elif mcm_info.error:
        print(f".mcm 未生成：{mcm_info.error}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
