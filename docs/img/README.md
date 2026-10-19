# 文档配图

这些图由本地脚本 `work/make_doc_assets.py` 生成，尺寸取自 `docs/03-机架设计.md` 和 `work/make_frame_v3.py`。
**不要手改这里的 PNG/GIF**；改尺寸请改脚本重跑。

| 文件 | 内容 |
|---|---|
| `z-stack.gif` | Z 层叠剖视：底板厚度、22 mm 净空、飞控垫高、相机、电池 |
| `z-stack.png` | 上面动画的静态预览 |
| `fc-mount.png` | 飞控固定放大图：下面 M2×6、上面 M2×4、5 mm 尼龙柱 |
| `screw-map.png` | 底板孔位 → 五金分配 |
| `prop-compare.gif` | 3020-3 vs 3016-3 桨径/螺距/推力对比 |
| `prop-compare.png` | 上面动画的静态预览 |

仿真类图/动画不在这里，统一放在 [`outputs/vibration`](../../outputs/vibration/) 和 [`outputs/impact`](../../outputs/impact/)。
