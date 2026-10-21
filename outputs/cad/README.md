# Kepler V · CAD 图纸

## 当前版本（v3）

| 文件 | 内容 |
|---|---|
| `v3-bottom-plate.dxf` | 底板 2D 轮廓（机臂、中心板、孔位） |
| `v3-top-plate.dxf` | 上层板 2D 轮廓（stack 孔、长槽、相机扎带孔） |
| `v3-camera-tray.dxf` | 旧版相机托架 2D 轮廓（仅作历史对照） |
| `v3-camera-tray.stl` | 旧版相机托架 3D 打印件（前唇会挡 S1039 镜头，**不要再用**） |
| `v3r-camera-tray.stl` | 装配版相机托架（去掉前唇、加侧颊/避让口，底面 z=0，水密） |
| `antenna-mount-tpu.stl` | 图传天线 TPU 夹子（底面 z=0，水密） |
| `v3-preview.png` | 俯视预览 |

单位：**mm**。DXF 的图层和孔位说明见 [docs/03-机架设计.md](../../docs/03-机架设计.md)。

整机装配和新增打印件的说明见
[docs/11-Fusion整机装配模型.md](../../docs/11-Fusion整机装配模型.md)。

> 实际做冲击/振动分析用的 STL 是 Fusion 导出的 **底板 4.0 mm / 上层板 3.0 mm** 版本；
> 早期设计文档写的是底板 3.5 mm。以实际打印的 STL 为准，见 [docs/08](../../docs/08-冲击与螺丝拉脱.md)。

## 历史版本

`archive/` 里是 v1/v2 和最早的 3 寸框架图，只作对照；不要拿旧图直接打印。

生成脚本在本地 `work/`：

- `work/make_frame_v3.py` — v3 DXF
- `work/make_tray.py` — 相机托架
- `work/check_frame.py` — 轮廓闭合/桨盘余量检查
