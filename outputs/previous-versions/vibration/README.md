# 振动结果

分析对象：45 × 14 mm 机臂，末端 8.5 g（1106 电机 + 3020-3 桨 + 螺丝）。
分析类型：**无阻尼线性模态 + 单自由度受迫响应筛选**，不是整机模态，也不是飞行实测。

## 文件

| 文件 | 内容 |
|---|---|
| `f1_materials.png` | PLA / PETG / ABS / ASA / PC / PA，不同厚度的一阶垂直弯曲频率 |
| `response_vs_rpm.png` | 1P 竖向分量 / 3P 桨叶通过随转速的放大倍数 |
| `campbell.png` | 一阶模态与 1P/2P/3P 激励的交点 |
| `mode_shape_compare.gif` | PLA 3.5 mm vs 4.0 mm 一阶振型慢放 |
| `design_matrix.csv` | 13 个材料/厚度组合的完整数表 |
| `summary.json` | 模型假设、关键结论、局限 |

## 关键数

| 方案 | 一阶 f1 |
|---|---:|
| PLA 3.5 mm（旧） | 125 Hz |
| **PLA 4.0 mm（推荐）** | **151 Hz** |
| PLA 4.5 mm | 179 Hz |
| PETG 4.5 mm | 144 Hz |
| ABS 4.5 mm | 148 Hz |
| PA 3.5 mm | 90 Hz |

悬停带 **12–15k RPM** 在 1P 交点（PLA 4.0 约 9.1k）之上；危险区是 **2.5–10k RPM 的低油门段**，要快速穿过。详细解释见 [docs/07](../../../docs/previous-versions/07-振动与打印材料方案.md)。
