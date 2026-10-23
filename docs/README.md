# Kepler V 文档

当前版本已经完成首飞。当前打印件、接线和装配以本页列出的文档为准。旧版设计和仿真单独保存在 [`previous-versions`](previous-versions/)。

## 先看这些

| 文档 | 内容 |
|---|---|
| [01 零件规格](01-零件规格.md) | 飞控、电机、图传、摄像头和五金规格 |
| [03 机架设计](03-机架设计.md) | 坐标、孔位、板厚和打印要求 |
| [04 接线与配置](04-接线与配置.md) | 飞控端口、供电和 Betaflight 配置 |
| [11 Fusion 整机模型](11-Fusion整机装配模型.md) | 当前模型结构、尺寸和装配关系 |
| [14 KEPLER V 辅助控制模块](14-KEPLER%20V辅助控制模块.md) | 辅助板接口和固件约束 |
| [15 FC 与图传接线速查](15-FC与图传接线速查.md) | 飞控焊盘、TS5823 Pro 线序和摄像头接法 |

## 当前状态

- 当前打印件：`PRINT_BASE`、`PRINT_TOP`、`TOP_LAYER_SPACER`、四片 `MOTOR_SPACER_3MM`、`VTX_TRAY_SEPARATE`、两片 XT30 线夹。
- 飞控安装孔距为 25.5 mm，M2，45° 摆放。
- 电机使用 6.364 mm 正方形孔心，对角 9 mm。
- 现在飞的是 3016-3 桨叶，悬停约 20% 油门。
- 图传、摄像头和 XT30 线夹都已经进入当前模型。

## 历史资料

仿真、V1 到 V4 的机架记录和旧截图在 [Previous versions](previous-versions/README.md)。这些结果基于旧模型，不能直接当成当前机架的验证结论。

## 工具

OSD 中文点阵和开机 Logo 的工具说明见 [12](12-OSD中文点阵.md) 和 [13](13-OSD启动Logo转换.md)。生成结果在 [`outputs`](../outputs/)。
