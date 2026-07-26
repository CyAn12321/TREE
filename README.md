# Maya L-System 参数化树生成器

这是一个基于 Maya/Python 的参数化树木生成与风动画工具。

## 功能

- 参数化控制主干粗细。
- 参数化控制分支层级数量（包含主干层）。
- 参数化控制每个生长节点的侧向分叉数量。
- 参数化控制基础分支角度。
- 固定随机种子，可复现同一棵树。
- 四种形态预设：圆冠阔叶、塔形针叶、垂柳形、窄冠杨树。
- 每种形态使用独立冠层包络：针叶保持下宽上窄，垂柳沿低垂枝挂叶，杨树形成填实的狭长柱冠。
- 四季变量：春、夏、秋、冬。
- 季节自动控制叶片密度、尺寸与颜色材质。
- 季节自动控制花朵数量、开放程度、颜色和凋谢下垂形态。
- 叶片密度、叶片尺寸、花朵密度和花朵尺寸可在季节基础上继续微调。
- 叶片按多叶簇分布，并依据树种覆盖不同数量的末端与中层细枝，默认形成连续且保留树种轮廓的高密度树冠。
- 全树先统一计算叶片和花朵额度，再公平分配到各合格枝条与枝梢；达到网格上限时也不会只集中在先生成的一侧。
- 生成单一多边形网格，减少 Maya 场景节点数量。
- L-System 直接输出带稳定 ID 和局部坐标框架的叶片/花朵附着点。
- 叶片和花朵全部使用程序化网格生成，不依赖外部器官模型资产。
- 当前第一阶段动画系统只实现风吹树枝摇摆：树干、树枝、细枝和附着的叶花网格共同使用 Maya bend deformer 与表达式驱动。
- 雨、雪、积雪、落叶和落花动画已从当前 Maya 动画创建路径中移除，后续作为独立阶段重新设计。

预设只表达相似树种的整体轮廓，不是严格的植物学物种模拟。

## 在 Maya 中打开工具

在 Maya Script Editor 的 Python 页签执行：

```python
import io
import maya.cmds as cmds

SCRIPT_PATH = cmds.fileDialog2(
    fileFilter="Python Files (*.py)",
    dialogStyle=2,
    fileMode=1,
)[0]
with io.open(SCRIPT_PATH, "r", encoding="utf-8") as script_file:
    SCRIPT_SOURCE = script_file.read()
exec(compile(SCRIPT_SOURCE, SCRIPT_PATH, "exec"), {
    "__file__": SCRIPT_PATH,
    "__name__": "__main__",
})
```

工具窗口中选择预设，调整参数后点击“生成树模型”。

## 参数说明

| 参数 | 说明 |
| --- | --- |
| 主干半径 | 根部枝段的初始半径 |
| 分支层级 | 递归层级总数，主干计为第 1 层 |
| 每个节点分叉数 | 每次递归生长产生的侧枝数，范围 `1–6`，主轴延续不计入 |
| 分支角度 | L-System turtle 的基础偏航/俯仰角 |
| 随机种子 | 控制产生式选择、角度和枝长扰动 |
| 枝干截面边数 | 每条锥台枝段的径向边数 |
| 生成枝端定位器 | 可视化枝端；完整 `AttachmentPoint[]` 始终由数据层输出 |
| 季节 | 切换春夏秋冬的叶片和花朵状态 |
| 叶片密度倍率 | 在季节默认密度上增减叶片数量 |
| 叶片尺寸倍率 | 在季节默认尺寸上调整叶片大小 |
| 树冠蓬松度 | 让叶簇和花簇离开枝条、填充周围三维冠层空间；`0` 为贴枝，`1` 为默认蓬松树冠 |
| 花朵密度倍率 | 在季节默认花期上增减花朵数量 |
| 花朵尺寸倍率 | 调整花朵整体尺寸，凋谢程度仍由季节控制 |
| 动画开始/结束帧 | 控制风动画的播放范围 |
| 风力强度 | `0–1`，控制树枝摇摆幅度与频率 |
| 风向角度 | 控制 bend deformer 的风向 |

## 代码结构

```text
TREE/
├─ launcher.py          # Maya 启动入口
├─ src/core.py          # 纯 Python L-System、3D turtle 和预设
├─ src/maya_mesh.py     # Maya 单网格构建器
├─ src/foliage.py       # 四季、叶片/花朵分布与凋谢数据
├─ src/maya_foliage.py  # 叶片、花瓣、花心合并网格及材质
├─ src/weather.py       # 纯 Python 风、落叶和落花参数规划
├─ src/vertex_animation.py # 纯 Python 风摆动参考公式
├─ src/maya_weather.py  # Maya 风摆动与落叶/落花粒子动画
├─ src/maya_ui.py       # Maya 参数面板
└─ tests/test_core.py   # 不启动 Maya 即可运行的测试
```

## 测试

```powershell
python -m unittest discover -s tests -v
```

## 风动画排查

- 当前动画组属性会显示 `wind_sway`、`falling_organs` 或两者组合，`implementationVersion` 为 `weather-keyed-fall-1.9`；树枝、树叶和花瓣共用单一低频风摆动，落叶/落花从实际叶片/花瓣位置生成，并沿慢速、带风向偏移的多段曲线下落。
- 播放范围会自动设置为界面中的开始帧和结束帧。
- 风由 bend deformer 表达式驱动，落叶和落花由独立同源网格实例的关键帧驱动，不依赖 Maya Dynamics Solver。生成树时不会自动添加动画；可在 UI 调整 `Falling Leaf Intensity` / `Falling Flower Intensity`，再点击 `Add / Refresh Weather Animation` 或 `Remove Weather Animation`。
