# OSD 中文点阵图

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

共 **60** 个：

`电压流高度速距离卫星飞行时间姿态解锁失控返航池温信号油门模式警告低量上升下降方向家里程转剩余分秒米公千最大小平均总连接断`



### .mcm 字库

- 文件：`osd_cn.mcm`（标准 MAX7456 格式，147,463 字节）
- 模式：`compact`，槽位 **0xC0–0xFB**
- 固件头文件：`osd_cn.h`
- 字符映射表：`osd_cn_map.csv`

MAX7456 只有 256 个字符码，汉字每个占 1 槽。`.mcm` 里的 ASCII/数字/图标来自
Betaflight 默认字库，汉字只写入上面的槽位。
**覆盖了原有非空槽位 55 个：** `0xC1 0xC2 0xC4 0xC5 0xC6 0xC7 0xC8 0xC9 0xCA 0xCB 0xCC 0xCD 0xCE 0xCF 0xD1 0xD2 0xD3 0xD4 0xD5 0xD6 …（共 55 个）`。如果你还要用这些槽对应的 OSD 图标，请改用 safe 模式或换起始槽位。



## 重新生成

```powershell
.venv\Scripts\python.exe tools\osd_cn_dotmatrix.py --text "你要显示的中文" --out-dir outputs\osd_font
```

默认字形来自 `assets/fonts/fusion-pixel-12px-monospaced-zh_hans.ms.bitmap.ttf`，是 12px 中文像素字体；
11×11 字身在 17 行格子里上下居中，底边对齐第 14 行。

## 重要限制

MAX7456 只有 256 个字符槽，汉字每个占 1 槽。图里的 `#01–#NN` 只是顺序编号；
`glyphs.csv/json` 里的 `suggested_code` 是实际写入 `.mcm` 的字符码。
另外，Betaflight 固件里的 OSD 标签本身是写死的英文，换字库不会自动把 `VOLT` 变成“电压”；
要显示中文，需要有自定义字符码的输出方式（或改固件/使用支持自定义文本的 OSD 方案）。
