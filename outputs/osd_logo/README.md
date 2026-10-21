# Kepler V · OSD 启动 Logo 示例

三个 BMP 都是飞控要求的固定格式：

- 288 × 72
- 24-bit BMP
- 62,262 字节
- 只有纯绿 `(0,255,0)`、纯黑、纯白

| 文件 | 说明 |
|---|---|
| **`kepler_v_boot_logo.bmp`** | **当前正式文件：保持比例，绿色留边** |
| `kepler_v2_boot_logo.bmp` | 改名前生成的同一张 Kepler V 图 |
| `kepler_boot_logo.bmp` | 早期示例，保持比例 |
| `kepler_boot_logo_fill.bmp` | 早期示例，拉伸填满 288×72 |
| `kepler_boot_logo_cover.bmp` | 早期示例，填满并裁切上下 |

`*_preview.png` 是 4 倍放大预览，只用于看效果，不要上传给飞控。
