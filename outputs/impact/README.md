# 冲击与拉脱结果

分析类型：**线性静力冲击等效 + 单螺丝/半孔拉脱**；不是瞬态落摔/接触仿真。
材料：PLA，E = 3.3 GPa，ν = 0.35，ρ = 1240 kg/m³（各向同性筛选值，不是打印件实测）。

## 子目录

| 目录 | 内容 | 关键结论 |
|---|---|---|
| [`stack_hole/`](stack_hole/) | 上层板前侧 stack 孔拉脱、垫片对比、整体弯曲 | 100 N 时 Ø5 约 19 MPa；1000 g 等效约 35 MPa；必须加 Ø5–6 垫片 |
| [`frame_arm/`](frame_arm/) | 底板 FL 臂 50 N 电机载荷 3D | 臂根名义约 43 MPa；菱形尖角是危险点，要 R2–3 倒圆 + 三角筋 |
| [`slot_half_hole/`](slot_half_hole/) | 4 个长槽半孔，250 g / 500 g，面内/面外 | 500 g 面外 75 g 上板约 70 MPa；183 g 整机约 171 MPa；不能作唯一承力点 |

根目录：

- `summary.json` — 上层板/底板的总结论
- `key_results.csv` — 关键数值表

## 先看

- `stack_hole/top_plate_pull_3d.gif` — 孔边 3D 应力环
- `stack_hole/top_plate_load_heatmap.gif` — 0→100 N 热力图
- `frame_arm/frame_arm_50N_3d.gif` — 底板臂根弯曲
- `slot_half_hole/slot_pull_bars.png` — 8 个半孔工况柱状图
- `slot_half_hole/slot_half_hole_3d.gif` — 500 g 面外 3D 特写

详细解释见 [docs/08](../../docs/08-冲击与螺丝拉脱.md) 和 [docs/09](../../docs/09-长槽半孔拉脱.md)。
