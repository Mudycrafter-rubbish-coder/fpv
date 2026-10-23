# KEPLER V 辅助控制模块 V1

> 设计源在相邻目录 `../eda`，EasyEDA 工程与原理图归那里管理；本文记录它与 Kepler V 主机的接口、装配和配置约束。

## 定位

辅助板使用 CH32V003F4P6，通过飞控 UART5 的 MSP 连接读取 RC/状态数据，并独立输出：

- 2 路舵机 PWM
- 3 路 3.3 V GPIO
- 2 路录像模块低有效触发

辅助板不参与飞控的姿态稳定控制。辅助板失效、复位或通信超时时，飞控本体仍正常工作；舵机和 GPIO 按固件定义进入安全状态。

## 飞控接口

UART5 不再配置为 PINIO，而是完整分配给辅助板 MSP：

| 飞控 | 辅助板 J1 | 说明 |
|---|---|---|
| UART5 TX | 3 `FC_UART5_TX` | 飞控 -> MCU |
| UART5 RX | 4 `FC_UART5_RX` | MCU -> 飞控 |
| 5V | 1 `FC_5V` | 只给辅助板逻辑供电 |
| GND | 2 `GND` | 必须共地 |

Betaflight 端口页把 UART5 设为 MSP，建议 115200。固件启动后先校验 MSP API 版本，再轮询通道和状态；不能假定一次响应包含所有字段。

## 输出接口

- J2/J3：两路舵机 PWM，各为 `PWM + GND`。
- J4：`GPIO1 + GPIO2 + GPIO3 + GND`。
- J5：`DVR_AVI_N + DVR_JPG_N + GND`。
- J6：`+3V3 + GND + SWIO + NRST`，接 WCH-LinkE 烧录和恢复。

原理图中的连接器符号只用于表达接口。最终 PCB 已把这些点做成可直接焊线的 2.54 mm 通孔焊盘，不装排针。

舵机电源必须使用独立 BEC，直接供到舵机，不经过辅助板 3.3 V 稳压器。舵机地与飞控/辅助板共地。

## USB 配置口与在线宏

板载 USB-C 接 CH340N，再通过 74HC4053 自动切换 UART：

- 正常飞行：UART5 连到 CH32V003，走 Betaflight MSP。
- 插入电脑：`USB_SEL` 拉高，UART 自动切到 CH340N，电脑可直接配置辅助板。
- 拔出 USB：`USB_SEL` 被拉低，自动回飞控 MSP。

USB 只负责在线配置、自定义宏和日志输出，不替代 SWIO 烧录。需要换固件或从异常状态恢复时仍使用 J6。

自定义宏和配置先存 CH32V003 内部 Flash。固件应先写入 RAM 临时配置，确认命令完整后再分页落盘，并做简单磨损均衡，避免每次串口通信都擦写 Flash。

## 录像触发

录像模块的 `AVI`、`JPG` 仍然是对地短接有效，接到 J5：

| 录像模块 | 辅助板 J5 | 说明 |
|---|---|---|
| `AVI` | J5-1 `DVR_AVI_N` | MCU 输出低脉冲触发录像 |
| `JPG` | J5-2 `DVR_JPG_N` | MCU 输出低脉冲触发拍照 |
| `GND` | J5-3 `GND` | 信号地 |

录像模块仍由飞控 5 V 供电。CH32V003 的 PC1/PC5 是 5 V 容忍脚，配置为开漏输出；板端各有 10 kΩ 上拉到 5 V。MCU 复位、断线或输出释放时，AVI/JPG 自动回到高电平，避免误触发。

## 供电与安全

- 飞控 5 V `FC_5V` 和 USB 5 V `USB_5V` 经 BAT54C 做 OR，再进入 XC6206P332MR-G 产生 3.3 V。
- 5 V 双输入不会互相反灌；USB 单独插入时可给 MCU、CH340 和逻辑电路供电。
- NRST：10 kΩ 上拉、100 nF 到地，并引到 J6。
- 舵机 PWM 与 GPIO 都有 10 kΩ 下拉，启动和复位时不悬空。
- USB D+/D- 经过 USBLC6-2SC6 ESD 保护。

## 尺寸与封装约束

- 最终 V1 PCB：`25.000 mm × 26.016 mm`，4 层。
- 原首选目标是 `20 mm × 20 mm`，但现有可手焊 USB-C、SWIO 与全部线束焊盘放不下；增加 1.016 mm 高度后仍低于 30 mm 上限。
- 最大允许：`30 mm × 30 mm`，不再扩大。
- 不使用 LQFP、QFN、BGA；现有 IC 均为 TSSOP-20、SOP-8、SOIC-16、SOT-23。
- 外部接口使用 2.54 mm 通孔焊盘，直接焊线，不安装排针；J1～J6 已从 BOM 排除。
- V1 保留 USB-C，便于反复插拔配置；如果第二版必须严格压到 20 mm 方形，可改成 `USB 5V / D- / D+ / GND` 四个大焊盘并接 USB 线尾。
- 2 g 重量目标会与 USB-C、焊盘尺寸和 PCB 板厚冲突；最终重量需要首板装配后实测。

## 设计状态

- 原理图 V1 已在 EasyEDA Pro 4.1.78 完成。
- 原理图：`KEPLER V Auxiliary Control Module / Control`。
- Board：`KEPLER_V_AUX`。
- PCB V1 已完成全板布线、双内层电源铜和保存重载回读。
- PCB 尺寸：`25.000 × 26.016 mm`，4 层。
- PCB 统计：36 个器件、501 段走线、47 个过孔、2 个覆铜网络。
- 原生 PCB DRC：0 violation。
- 扩展 DFM：0 error、64 warning；没有开路、短路、焊盘内过孔或单层过孔。
- 原生原理图 DRC：0 fatal / 0 error / 0 warning。
- 网络检查：0 悬空功能脚、0 短路、0 桥接、0 零长度导线。
- 详细引脚、BOM 和网络说明见 `../../eda/doc/01-原理图设计说明.md`。
- 预览图：`../../eda/outputs/schematic/kep_aux_schematic_v1.png`。
- PCB 设计、DRC/DFM 与制造限制见 `../../eda/doc/02-PCB布线与制造检查.md`。
- PCB 顶层预览：`../../eda/outputs/pcb/kep_aux_final_top.png`。
- PCB 底层预览：`../../eda/outputs/pcb/kep_aux_final_bottom.png`。

## 尚未完成

- 原理图功能分区框尚未绘制，不影响电气连接。
- PCB 仍有 23 个位号压焊盘 warning；这些文字在制造时会被阻焊开窗裁切，需要在下单前检查最终 Gerber 丝印。
- `C1`、`C6`、`C7` 的去耦距离超过工具建议值，若要进一步优化电源瞬态响应，下一版应优先调整这三个电容。
- USB 为 Full-Speed，未做 High-Speed 级别的阻抗和等长控制；现有走线适用于 CH340N。
- USB-C 定位槽到走线采用 8 mil（0.2032 mm）规则，下单前必须在 JLC DFM 预览中复核槽边。
- 需要用实物确认录像模块输入阈值、上拉到 5 V 的实际需求和舵机线束固定方式。
