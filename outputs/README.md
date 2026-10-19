# outputs · 结果与图纸

这里放**可以直接看的结果**：CAD 图纸、仿真图、动画、表格和模型记录。
真正生成这些结果的脚本在本地 `work/`（不进仓库），避免把几万行中间件和几百张逐帧 PNG 塞进 Git。

## 目录

| 目录 | 内容 | 先看什么 |
|---|---|---|
| [`cad/`](cad/) | v3 底板 / 上层板 / 相机托架 DXF、STL、预览 | `v3-preview.png` |
| [`vibration/`](vibration/) | 机臂模态、材料对比、Campbell 图、响应曲线、振型动画 | `f1_materials.png`、`campbell.png` |
| [`assembly/`](assembly/) | 整机装配模态、3D 振型动画、网格收敛 | `assembly_mode1_3d.gif` |
| [`impact/`](impact/) | stack 孔拉脱、底板臂根、长槽半孔、3D/热力图动画 | `stack_hole/top_plate_pull_3d.gif` |
| [`archive/`](archive/) | 旧版 CAD、旧版仿真；只作历史对照 | `sim-v1-manual/README.md` |

## 文件命名

- `*.gif`：动画；GitHub 页面会直接播放。
- `*_preview.png`：动画的静态预览（README/文档里用来兜底）。
- `*_manifest.json`：动画的参数、帧数、FPS、数值文件说明。
- `*_numeric.npz`：动画背后的数值数组（可复读，不依赖看图片）。
- `*.csv` / `*.json`：表格和结论；优先看这些，不要从图片反推数字。

## 说明

- 所有长度单位默认 **mm**；有限元应力单位 **MPa**。
- 仿真是**线性模态/静力筛选**，不是落摔实测；结论必须用挂重/落摔/黑匣子确认。
- 动画里的变形通常做了放大，标题会写放大倍数；真实变形以 `*_manifest.json` 和 `summary.json` 为准。
