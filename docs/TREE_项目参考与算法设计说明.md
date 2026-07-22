# TREE 项目：参考依据与预期算法设计说明

**主题：** L-System 树干生成、器官实例与季节系统、纯顶点天气动画  
**版本：** v1.1（可运行原型实现版）  
**日期：** 2026-07-20  
**适用范围：** Maya/Python 原型与后续实时渲染实现

## 0. 文档结论

本项目采用“结构生成、几何解释、器官实例、季节状态、顶点动画”五层解耦架构：

1. 用参数化、随机 L-System 生成树干与枝条拓扑；
2. 用 3D turtle 将 L-string 解释为枝段网格，同时输出叶片/花朵可附着点的完整局部坐标框架；
3. 从项目内器官模型库中按权重选择叶片或花朵模型，并在附着点上生成逻辑实例；
4. 用受季节、温度、湿度和随机种子约束的离散状态机决定实例数量、模型状态和材质；
5. 用固定拓扑上的解析顶点位移或烘焙顶点缓存完成风、落叶、落花、雨、雪和积雪，不依赖骨骼、刚体或粒子求解器。

LPy 与 PlantGL 作为架构和算法思想来源，不要求直接安装进 Maya，也不复制其源代码。项目在 Maya/Python 内实现自己的数据结构和解释器，以降低部署、版本和许可证耦合风险。

## 1. 参考来源与本项目采用内容

### 1.1 LPy / OpenAlea

LPy 将 L-System 与 Python 动态语言结合，支持带参数模块、并行产生式、分解规则、解释规则、外部过程控制及 L-string/MTG 映射。[1][2] 本项目具体参考：

- **带参数模块：** 用 `Apex(order, age, radius, length)`、`Internode(length, radius)`、`LeafSite(...)`、`FlowerSite(...)` 表达结构和器官候选点，而不是只使用单字符。
- **产生与解释分离：** 产生式只决定拓扑和发育状态；解释阶段才创建网格和附着点。修改材质或模型库不需要重新设计树的文法。
- **模块化运行：** 树干、器官、季节和天气作为独立阶段，以明确的数据契约连接。
- **后处理：** 参考 LPy 可在推导步骤后访问 L-string/场景的思想，在本项目中加入拓扑验证、附着点筛选、额度分配和性能上限。
- **多尺度标识：** 不完整实现 MTG，但在 `branch_graph` 中保留树、轴、枝段、器官点的父子关系、阶次和深度，为天气权重与后续分析服务。

LPy 文档还允许用 `@g(geometry)` 或预定义 surface 在当前 turtle 位置和方向放置任意 PlantGL 几何。[3] 本项目把这一思想改写为“输出附着坐标框架 + 从器官库选择模型 + 实例变换”，从而不把叶片或花朵硬编码进 L-System。

### 1.2 PlantGL

PlantGL 提供面向植物的场景图、几何图元、变换、器官表示和树冠包络，其论文强调几何数据、算法和界面的分离，以及从器官到树冠的多尺度表示。[4][5] 本项目具体参考：

- **场景图分离：** 一个器官模型只保存一次，位置、旋转、缩放由实例变换给出。
- **植物几何图元：** 枝段使用变半径广义圆柱/截锥；叶片和花朵由独立三角网格资产提供。
- **局部坐标框架：** 每个几何对象由位置与正交基 `(H, L, U)` 确定方向。
- **树冠包络：** 不同相似树种使用球冠、锥冠、垂幕、窄柱等不同包络约束器官散布，而不是统一球形随机偏移。
- **可复用几何：** 叶片、花瓣和花心资产与树干拓扑解耦，便于季节替换和 LOD。

### 1.3 L-System 基础文献

《The Algorithmic Beauty of Plants》系统描述了括号 L-System、参数化/随机产生式、三维 turtle、树木建模、器官模型和发育动画。[6] Prusinkiewicz 的早期工作进一步明确了“两步法”：先生成符号串，再将其解释为三维 turtle 命令；随机 L-System 用于同一类植物的个体差异，预定义曲面可作为器官插入。[7]

本项目采用上述两步法、括号栈、三维 turtle、参数化和带权随机规则；不追求植物生理学全模拟，而把文法用作可控的形态生成器。

### 1.4 器官发育与季节变化

MAppleT 将树木发育拆为拓扑、随机过程和几何/力学过程，并按时间输出三维树形。[8] 本项目参考其“结构状态随时间推进、随机拓扑与几何表现分开”的方法，但不实现隐马尔可夫生长单元模型或完整生物力学。

Tang、Wu 与 Fan 用离散状态、几何变形和纹理组合表示叶片季节变化，并用温度、湿度、时间约束 Markov 转移；其实验树干也由 L-System 生成。[10] 本项目参考其“每个器官独立处于某一状态、整树外观由状态分布组成”，但将复杂质量弹簧形变替换为预制器官模型/形态键，以适合小组项目范围。

Jiao、Yang 与 Yang 将花朵变化分为开放和凋落阶段，并以 Bézier 曲面控制点及叶片纹理变化表现形态。[11] 本项目参考两阶段花朵生命周期和“形状 + 材质”联合变化；实时版本可用顶点形态插值，首版则在模型库中准备 `bud/bloom/wilt` 三类资产。

Stojanović 的 Maya/Python 工作证明随机 L-System、Python/PyMEL 和 Maya 网格生成可以构成完整的程序化树管线。[9] 本项目只把它作为 Maya 工程可行性参考，不采用其 Perlin 纹理作为核心算法。

### 1.5 纯顶点天气动画

GPU Gems 3 第 6 章用浅层枝条层级、风场、周期函数/噪声、分支相位和刚度参数合成树木风动，并指出该过程可完全放入 GPU，且无需保存上一帧状态。[12] 第 16 章把运动拆成整体弯曲与叶片细节弯曲，并用顶点色保存叶缘刚度、相位和整体刚度。[13]

Habel、Kusternig 与 Wimmer 用分层顶点位移和频域响应纹理实现受物理引导的实时树木动画。[14] 本项目参考“离线预计算枝段参数、运行时只做顶点位移”的结构，但首版使用较轻量的多频正弦和噪声。

Li 等用少量原始运动轨迹和低维特征合成大量落叶运动，并在 GPU 上求值。[15] 本项目参考“轨迹库 + 每实例系数”，避免为每片叶求解刚体运动。

Fearing 的积雪模型关注表面接收量与局部稳定性；Reynolds 等使用遮挡投影、累积缓冲、重着色和沿表面偏移表现动态积雪。[16][17] 本项目采用简化的朝上法线、遮挡、坡度和邻域平滑权重，并通过复制雪帽网格的顶点位移表现厚度。

### 1.6 参考映射摘要

| 本项目层次 | 主要参考 | 具体采用内容 |
|---|---|---|
| L-System 结构 | LPy、ABOP、Prusinkiewicz 1986 | 参数模块、并行/随机产生式、括号分支、推导与几何解释分离 |
| 枝干与器官几何 | PlantGL、LPy turtle | 场景图思想、局部 HLU 框架、广义圆柱、预定义器官几何与树冠包络 |
| 时间与季节 | MAppleT、Tang et al.、Jiao et al. | 结构/表现解耦、离散器官状态、受季节和环境约束的状态分布、开放/凋谢阶段 |
| 风动 | GPU Gems 3 Ch.6/16、Habel et al. | 多尺度顶点位移、分支相位/刚度、多频波、顶点色控制叶片细节 |
| 落叶/落花 | Li et al. | 预制轨迹库与低维系数，在固定顶点池中重放 |
| 雨雪 | Creus & Patow、Fearing、Reynolds et al. | 固定天气顶点池、朝上/遮挡接收权重、累积量与雪帽顶点偏移 |

## 2. 总体数据流

```text
参数/预设/随机种子
        ↓
参数化随机 L-System 并行推导
        ↓
Typed L-string + branch graph
        ↓
3D Turtle 几何解释
   ├─ 枝干静态网格
   ├─ AttachmentPoint[]
   └─ VertexMotionAttribute[]
        ↓
季节状态与约束筛选
        ↓
器官资产加权选择/逻辑实例
        ↓
固定拓扑整树网格与天气顶点池
        ↓
解析顶点动画或 Maya 顶点缓存
```

核心原则是：**L-System 输出“结构与可附着语义”，器官库决定“长什么样”，季节系统决定“出现多少和处于什么状态”，天气系统只改变固定拓扑的顶点位置。**

## 3. 树干生成算法

### 3.1 参数化随机 L-System

定义系统：

`G = (M, ω, P, Θ, seed)`

- `M`：带类型和参数的模块集合；
- `ω`：初始公理，例如 `Apex(0, 0, r0, l0)`；
- `P`：并行产生式及其权重；
- `Θ`：全局参数，包括分支层级、角度、长度衰减、半径衰减、向性等；
- `seed`：确定性随机种子。

建议模块：

```text
Apex(order, age, radius, length)       生长点
Internode(length, r0, r1, branchId)    节间
BranchSite(slot, probability)          分叉候选
LeafSite(siteId, scale, stateMask)     叶片附着候选
FlowerSite(siteId, scale, stateMask)   花朵附着候选
Yaw(a), Pitch(a), Roll(a)              turtle 旋转
Push, Pop                               分支栈
```

产生式示意：

```text
Apex(o,a,r,l) : o < maxOrder
  → Internode(l,r,r·qr,id)
    [Yaw(+α+ε1) Pitch(β+ε2) Apex(o+1,a+1,r·qr,l·ql)]
    [Yaw(-α+ε3) Pitch(β+ε4) Apex(o+1,a+1,r·qr,l·ql)]
    LeafSite(...)
    Apex(o,a+1,r·qt,l)
```

其中 `ql` 为长度衰减，`qr` 为分支半径衰减，`qt` 为同轴节间渐细率，`ε` 为受随机种子控制的角度扰动。每个前驱可以有多条带权后继，用累计概率采样，实现同一预设下的个体变化。

### 3.2 确定性随机

为避免修改某一参数后整棵树的随机序列完全改变，随机值不只依赖调用顺序，而使用：

`u = hash01(globalSeed, modulePath, eventType, sampleIndex)`

`modulePath` 由父模块路径和局部分叉编号组成。这样同一分支的模型、器官选择和天气相位在相同种子下稳定复现，便于对比实验与调参。

### 3.3 3D turtle 状态

状态定义为：

`T = (p, H, L, U, r, branchId, parentId, depth)`

- `p`：当前位置；
- `(H,L,U)`：Head/Left/Up 正交基；
- `r`：当前半径；
- `branchId/parentId/depth`：拓扑语义。

`Internode(l,r0,r1)` 沿 `H` 前进并生成截锥；Yaw/Pitch/Roll 分别绕局部轴旋转；Push/Pop 保存或恢复完整 turtle 状态。每次旋转后重新正交化基向量，避免深层递归产生数值漂移。

### 3.4 枝段网格

每个枝段在起点和终点建立截面环：

`v(k,s) = p(s) + r(s)[cos(2πk/n)L(s) + sin(2πk/n)U(s)]`

其中 `s∈{0,1}`，`n` 是径向边数。相邻环连接为四边形或两个三角形。连续同轴枝段共享环；分叉首版允许截锥轻微相交，最终版可增加局部融合或重网格。

输出应保留每个顶点所属枝段、沿枝归一化位置和到根路径，以供顶点动画计算刚度与枢轴。

### 3.5 相似树种预设与树冠包络

每个预设至少包含：

- 主干半径、节间长度、层级、每节点分叉数；
- 水平/俯仰角均值与扰动；
- 长度和半径衰减；
- 向上、向下或光照方向的 tropism；
- 器官允许层级、树冠起始高度、局部扩散包络；
- 风动刚度系数。

圆冠阔叶使用椭球包络，针叶使用高度相关的锥形包络，垂柳允许低垂枝且使用纵向幕状包络，窄冠杨树使用中部稍宽的柱状包络。树种预设表示“相似形态”，不声明为严格植物学物种模型。

## 4. 附着点输出与器官资产系统

### 4.1 附着点不是单一位置

每条 `LeafSite` 或 `FlowerSite` 在解释阶段输出：

```text
AttachmentPoint {
  id, typeMask, branchId, parentBranchId,
  position, tangent, normal, binormal,
  branchDepth, branchOrder, branchRadius,
  distanceAlongBranch, crownHeight,
  exposure, age, seed, enabled
}
```

`position + tangent/normal/binormal` 构成完整刚体变换。器官的根部 pivot 对齐 `position`，器官主轴对齐 `tangent` 或 `normal`，随后加入叶序角、向上性和小随机扰动。

### 4.2 候选点生成

候选点来源分为：

1. L-System 显式 `LeafSite/FlowerSite` 模块；
2. 满足深度和半径阈值的细枝均匀采样点；
3. 唯一枝梢点。

每条候选点记录来源枝段，之后统一计算全树额度并公平分配，避免遍历顺序导致器官只集中在一侧。筛选约束包括枝段层级、树冠包络、最小间距、地面高度、朝向、光照暴露近似值和每枝最小覆盖量。

### 4.3 资产目录与元数据

建议目录：

```text
assets/organs/
  leaves/<family>/
    spring_bud/  spring_young/  summer_mature/
    autumn_color/  autumn_wilt/  winter_dry/
  flowers/<family>/
    bud/  bloom_small/  bloom_full/  wilt/  fallen/
  metadata/*.json
```

推荐支持 `.ma`、`.mb` 或 `.obj`；归一化规则为根部 pivot 位于原点，主生长方向为 `+Y`，正面法线为 `+Z`，真实尺寸写入元数据。每个资产元数据至少包含：`assetId`、`organType`、`compatiblePresets`、`seasonStates`、`weight`、`baseScale`、`scaleRange`、`materialSet`、`lod`、`vertexLayoutVersion`。

### 4.4 随机实例选择

对合格附着点 `i`：

1. 过滤不兼容的器官类型、树种、季节和 LOD；
2. 使用 `hash(seed, attachmentId, seasonState)` 得到稳定随机数；
3. 按资产权重累计采样；
4. 应用尺寸、绕轴角度和颜色变体；
5. 保存 `attachmentId → assetId → transform → state` 映射。

在最终纯顶点动画阶段，“实例”是逻辑实例。为允许每个器官拥有不同顶点轨迹，需要把实例实现为合并网格中的独立顶点片段，或在导出前执行 instance realization；不依赖 Maya 粒子实例器。

## 5. 季节系统

### 5.1 器官离散状态

叶片：

`Dormant → Bud → Young → Mature → Senescent → Wilted → Detached`

花朵：

`Dormant → Bud → Blooming → FullBloom → Wilted → Detached`

季节是宏观控制量，不直接等价于单一模型。每个器官点依据状态概率独立取样，因此同一棵树上可以同时出现新叶、成熟叶和花蕾，避免整树瞬间切换。

### 5.2 受约束状态转移

对状态 `s` 到 `s'`：

`P(s→s') = clamp(Bseason(s,s') + wT·fT(T) + wH·fH(H) + wA·age + noise, 0, 1)`

其中 `Bseason` 为季节基础转移矩阵，`T/H` 为可选温度和湿度，`age` 为器官年龄。首版只使用季节和稳定随机数；后续可加入环境变量。状态只允许沿生命周期前进，除非用户重新生成场景。

### 5.3 季节初始艺术参数

| 季节 | 叶片激活比例 | 主要叶状态 | 花朵激活比例 | 主要花状态 | 额外约束 |
|---|---:|---|---:|---|---|
| 春 | 0.50–0.70 | Bud/Young | 0.45–0.75 | Bud/FullBloom | 上层、受光枝优先开花 |
| 夏 | 0.85–1.00 | Mature | 0.05–0.15 | FullBloom/Wilted | 最大树冠覆盖，控制过密碰撞 |
| 秋 | 0.45–0.75 | Senescent/Wilted | 0.02–0.08 | Wilted | 按冠层暴露与随机阈值产生落叶 |
| 冬 | 0.00–0.08 | Wilted/Dry | 0 | Dormant | 仅保留少量枯叶或芽体 |

这些范围是美术初值而非植物学定量结论，必须在不同树种预设和镜头距离下校准。

### 5.4 模型与材质联动

状态决定三件事：

- **数量：** 通过稳定哈希阈值激活/停用附着点；
- **模型：** 从该状态允许的器官资产子集中选择；
- **材质/顶点形态：** 切换颜色、粗糙度和透明度，或在兼容拓扑资产间进行顶点插值。

为避免季节变化时器官随机跳到其他位置，`attachmentId` 和 `assetFamily` 固定，只有 `stateVariant`、激活标记和材质参数改变。

## 6. 纯顶点天气动画

### 6.1 定义与实现边界

本文所称“纯顶点动画”是：网格拓扑和索引固定，动画阶段只计算顶点位置（可附带顶点色/法线更新），不建立骨骼、不运行刚体、不使用 Maya 粒子求解器。Maya 原型可逐帧用 `MFnMesh.setPoints` 更新并烘焙 Alembic/顶点缓存；实时实现可把同一公式迁移到 vertex shader。

由于固定拓扑不能真正创建或删除几何，雨滴、雪片、落叶和落花必须在动画开始前预分配。未激活单元缩到极小、移到不可见池位置或使用透明度屏蔽。

### 6.2 顶点运动属性

每个枝干顶点保存：

- `branchId`、`parentBranchId`、`branchDepth`；
- 枝基枢轴 `pivot` 与枝方向；
- 沿枝归一化坐标 `u`；
- 刚度 `stiffness`；
- 相位 `phase` 和噪声种子；
- 主干、枝条、叶片细节权重。

可在 Maya 中存入 color set/UV set 或独立数组。叶片/花朵顶点额外保存 `organInstanceId`、局部根部坐标、叶缘权重、脱落时间和轨迹编号。

### 6.3 风场与树木弯曲

二维风场：

`W(x,t) = D·[V0 + G(t)] + T(x,t)`

`D` 为风向，`V0` 为基础强度，`G(t)` 为低频阵风，`T(x,t)` 为平移噪声形成的局部湍流。

枝段弯曲角：

`θb(t) = Ab·u^γ·[a1 sin(ω1t+φb) + a2 sin(ω2t+1.7φb) + n(x,t)]`

`Ab` 随枝长增加、随半径/刚度减小。可用悬臂梁比例近似：

`Ab ∝ L³ / (E·r⁴ + ε)`

为避免分支同步，每枝由稳定哈希生成 `φb`。每个顶点最多累计主干、一级枝和当前细枝三层旋转，符合浅层层级即可产生可信运动的参考结论。[12]

### 6.4 叶片与花朵细节弯曲

器官根部权重为 0、边缘权重接近 1。顶点位移由两个频段组成：

`Δvdetail = normal·wedge·Aedge·wave(t+phase) + tangent·worgan·Aflutter·wave2(t)`

参考 Crysis 方法，可将顶点色 R/G/B 分别编码叶缘权重、每器官相位和整体刚度。[13] 花瓣使用更低刚度、更高细节幅度；冬季枯叶刚度和高频抖动增加。

### 6.5 落叶与落花

为每个可脱落器官预先记录 `detachTime`。在脱落前，顶点继续使用附着点随树运动的变换；脱落后切换到解析轨迹：

`x(τ) = p0 + v0τ + 0.5gτ² + Wavgτ + Fflutter(τ)`

其中 `τ=t-detachTime`。旋转用低维轨迹库表示：

`R(τ) = Σ ck·Bk(τ)`

`Bk` 是若干预制翻滚、摆落、螺旋轨迹，`ck` 由器官形状和随机种子决定。该设计参考大量落叶运动的“原始轨迹 + 低维特征”方法。[15] 花瓣下降速度更低、风阻更高；落叶允许更大的翻滚角速度。

### 6.6 雨

预分配若干线段或四边形雨滴，每个雨滴用 `dropId` 生成初始位置：

`y(t) = ytop - mod(speed·t + hash(dropId)·H, H)`

`x/z` 使用哈希位置并加入风向漂移。雨滴四边形沿速度方向拉长，全部顶点通过解析函数循环，不产生或销毁粒子。拍打效果首版不做真实碰撞，只在树冠包络中预分配短寿命 splash 小片，并按接近表面的时间窗展开/收拢。

### 6.7 雪与积雪

飘雪同样使用固定四边形池，下降速度低，并加入横向正弦漂移和不同相位。积雪在枝干和器官表面生成一份固定拓扑的雪帽副本。每个雪帽顶点预计算：

`eligibility = saturate((n·Up - slopeMin)/(1-slopeMin)) · exposure · occlusion`

累积量：

`a(t+Δt) = clamp(a(t) + snowIntensity·eligibility·Δt - meltRate·Δt, 0, 1)`

雪帽位置：

`vsnow(t) = vbase(t) + n·maxDepth·smooth(a(t))`

邻域拉普拉斯平滑限制尖刺；坡度超过稳定阈值时减少累积量，作为 Fearing 稳定性模型的轻量近似。[16] 遮挡与沿法线偏移参考实时遮挡积雪方法。[17]

## 7. 模块接口建议

```text
TreeConfig
  → LSystemDeriver.derive()
  → LStringModel
  → TurtleInterpreter.interpret()
  → TreeGeometry + BranchGraph + AttachmentPoint[]

AttachmentPoint[] + OrganLibrary + SeasonConfig
  → SeasonResolver.resolve()
  → OrganInstance[]
  → MeshAssembler.realize_instances()
  → StaticCombinedMesh + VertexMotionAttribute[]

StaticCombinedMesh + VertexMotionAttribute[] + WeatherConfig
  → VertexAnimator.evaluate(frame)
  → vertex positions
  → Maya point cache / Alembic / real-time vertex shader
```

建议文件划分：

```text
src/lsystem/grammar.py
src/lsystem/derive.py
src/geometry/turtle.py
src/geometry/branch_mesh.py
src/organs/library.py
src/organs/attachments.py
src/season/state_machine.py
src/animation/vertex_wind.py
src/animation/vertex_fall.py
src/animation/vertex_weather.py
assets/organs/...
tests/...
```

## 8. 实现顺序

1. **数据契约：** 完成 typed L-string、branch graph、attachment point 和 vertex motion attribute。
2. **L-System 重构：** 产生式与几何解释分离，加入稳定路径随机和符号数量上限。
3. **器官库：** 制作/收集拓扑规范一致的叶片与花朵资产，编写元数据校验器。
4. **季节静态快照：** 先实现四季数量、资产和材质切换，再扩展连续状态转移。
5. **风动顶点动画：** 实现主干/枝条/器官三个频段并烘焙顶点缓存。
6. **脱落与天气池：** 实现固定池落叶、落花、雨、雪；最后加入雪帽累积。
7. **验证与调参：** 不同预设、种子、季节和强度组合进行自动化与视觉检查。

## 9. 验收标准

- 同一配置和种子产生完全一致的拓扑、附着点和资产选择。
- 分支层级、分叉数、角度、长度和半径参数有独立可测的几何影响。
- 每个附着点包含位置与正交方向框架，器官根部无明显漂浮或翻转。
- 达到器官数量上限时，额度仍覆盖所有合格枝区，而非集中在遍历前部。
- 四季共享相同 `attachmentId`，状态变化不导致位置随机跳变。
- 最终天气场景不包含骨骼、刚体和粒子求解器；拓扑在动画开始后不变化。
- 风强度为 0 时顶点严格回到静止位置；增加强度时位移连续且无枝段断裂。
- 落叶/落花在脱落帧与树上原器官位置、形状和朝向连续。
- 积雪优先出现在朝上且未遮挡表面，强度增加时厚度单调增加。

## 10. 采用边界、风险与说明

- 本项目参考 LPy/PlantGL 的公开论文、文档和架构，不声明复现其完整功能。
- 目前建议采用 clean-room 方式自行实现；如未来直接复制或链接其代码，必须单独核验当时版本的许可证与发布义务。
- L-System 擅长可控拓扑，但不能自动保证真实树种识别；预设应称为“相似形态”。
- 纯顶点动画性能高且便于缓存，但固定拓扑意味着所有可能出现的器官和天气单元需预分配。
- Maya 顶点缓存适合作业演示；若转向实时引擎，需把同一属性和公式迁移到 vertex shader，并重新评估顶点数量、draw call 和透明排序。
- 论文中的完整质量弹簧、流体、积雪稳定或生物发育模型超出当前项目范围；本文明确使用视觉可信的简化模型。

## 11. v1.1 实际落地情况（2026-07-20）

本轮已将前述“预期方案”落实到 `maya_lsystem_tree_generator`，并保留纯 Python 数据层与 Maya 表现层的分离。

| 设计项 | 当前实现 | 代码位置 |
|---|---|---|
| Typed L-string | `LModule(name, parameters, path_id)`；每个模块保留推导路径 | `src/core.py` |
| 稳定随机 | `SHA-256(seed, path/id, channel)` 映射到 `[0,1]`，规则、角度、长度、资产和动画相位互不消耗共享随机序列 | `src/core.py`、`src/assets.py` |
| Branch graph | `BranchGraph.children/roots/terminal_indices()` 保存显式父子拓扑 | `src/core.py` |
| 管道模型半径 | 按末端负载和指数 `n=2.3` 回算半径，再施加层级缩放与渐细约束 | `src/core.py` |
| 附着点输出 | 输出稳定 `AttachmentPoint[]`，包括 id、类型、枝段、沿枝参数、位置、局部标架、深度、暴露度和 seed | `src/core.py`、`src/maya_mesh.py` |
| 器官资产库 | JSON 目录、OBJ 解析、基部 pivot 与单位高度归一化、按状态加权选择 | `src/assets.py`、`assets/organs/catalog.json` |
| 季节固定候选池 | 同一 `attachment_id` 使用独立随机流；季节改变数量/状态/模型时，共享候选器官的位置保持不变 | `src/foliage.py` |
| 真实器官网格 | Maya 合并网格直接由目录中的 OBJ 变换得到；原程序化叶/花保留为无资产时的回退 | `src/maya_foliage.py` |
| 纯顶点风雨雪 | 风、雨、雪、落叶、落花和积雪均预分配固定拓扑；时间变化时仅以 `MFnMesh.setPoints` 更新顶点 | `src/vertex_animation.py`、`src/maya_weather.py` |

### 11.1 已收录的免费器官资产

资产来自 **Kenney Nature Kit 2.1**，共筛选 5 组叶片 OBJ 和 9 组花朵 OBJ。原资源使用 **CC0-1.0**，允许个人、教学和商业项目自由使用。项目保留原始许可证文本、来源页和获取日期；即使许可证不强制署名，汇报材料仍建议注明 “Organ assets: Kenney Nature Kit (CC0)”。

- 目录：`assets/organs/`
- 目录元数据：`assets/organs/catalog.json`
- 来源记录：`assets/organs/SOURCES.md`
- 许可证：`assets/organs/LICENSE_KENNEY_CC0.txt`
- 来源页：https://kenney.nl/assets/nature-kit

OBJ 加载后执行：

`v' = (vx / h, (vy - ymin) / h, vz / h)`

其中 `h = ymax - ymin`。因此器官根部落在局部 `Y=0`，主生长方向统一为 `+Y`，再由附着点的切向、法向和副法向组成实例变换。

### 11.2 当前纯顶点动画公式

风动使用两个频带的解析波，并以归一化高度平方作为柔顺权重：

`w = saturate((y-ymin)/H)^2`

`Δp = D · H · 0.055 · Iwind · w · [sin(ω1t+φ) + 0.32sin(ω2t+1.71φ)]`

雨雪使用固定四边形池。元素 `i` 的起始位置和相位由稳定哈希给出，纵向位置循环为：

`y_i(t) = ytop - mod(speed·t/H + phase_i, 1)·(H+margin)`

落叶/落花从其树上 `attachment_id` 对应实例的原位置出发，延迟、漂移和旋转相位同样由稳定哈希产生。池中使用的顶点直接来自该实例的 `asset_id`，因此不会再出现“树上器官与飘落器官形状不一致”。

积雪使用与枝干相同拓扑的雪帽副本，累积量为：

`a(t)=smoothstep(start, accumulationEnd, t)`

`vsnow = vrest + Up · snowDisplacement · a(t) · (0.35 + 0.65·heightWeight)`

这一实现优先保证课堂演示中积雪厚度变化清楚、拓扑固定和可缓存。基于真实法线、遮挡和坡度的雪接收权重仍属于下一阶段增强项。

### 11.3 验证结果与边界

- 当前自动化测试覆盖 L-System 参数影响、确定性、树形差异、管道半径约束、附着点稳定性、四季数量关系、器官资产解析、季节共享位置以及顶点动画零强度边界。
- Maya 天气模块不再调用 particle/nParticle、emitter、field、collision 或 nonlinear deformer。
- `timeChanged` 回调适合交互预览；交付镜头前应烘焙为 Maya Geometry Cache 或 Alembic，以避免重新打开场景后依赖脚本回调注册。
- 当前雨滴“拍打”以穿过树冠的视觉反馈为主，尚未实现逐滴精确碰撞；若需要明显水花，可增加预分配 splash 四边形池并用树冠包络的解析命中时间驱动。
- 当前枝段仍按独立圆台组合，近距离可能看到分叉接缝。最终高质量版本可增加共享环、分叉焊接或隐式曲面重建，但这会明显提高网格构建复杂度。

## 参考文献与项目

[1] OpenAlea. **LPy: An open source Python version of Lindenmayer Systems.** GitHub. https://github.com/openalea/lpy （访问日期：2026-07-20）

[2] Boudon, F., Pradal, C., Cokelaer, T., Prusinkiewicz, P., & Godin, C. (2012). **L-Py: An L-System Simulation Framework for Modeling Plant Architecture Development Based on a Dynamic Language.** Frontiers in Plant Science, 3, 76. https://doi.org/10.3389/fpls.2012.00076

[3] OpenAlea LPy Documentation. **L-Py Turtle advanced primitives / L-Systems.** https://lpy.readthedocs.io/en/latest/user/turtleAdvanced.html ; https://lpy.readthedocs.io/en/latest/user/lsystems.html （访问日期：2026-07-20）

[4] OpenAlea. **PlantGL: Open-source graphic toolkit for 3D virtual plants.** GitHub. https://github.com/openalea/plantgl （访问日期：2026-07-20）

[5] Pradal, C., Boudon, F., Nouguier, C., Chopard, J., & Godin, C. (2009). **PlantGL: A Python-based geometric library for 3D plant modelling at different scales.** Graphical Models, 71(1), 1–21. https://doi.org/10.1016/j.gmod.2008.10.001

[6] Prusinkiewicz, P., & Lindenmayer, A. (1990). **The Algorithmic Beauty of Plants.** Springer-Verlag. Electronic edition: https://algorithmicbotany.org/papers/ （访问日期：2026-07-20）

[7] Prusinkiewicz, P. (1986). **Applications of L-systems to computer imagery.** In Graph-Grammars and Their Application to Computer Science, LNCS 291. https://algorithmicbotany.org/papers/applications-of-l-systems-to-computer-imagery.html

[8] Costes, E., Smith, C., Renton, M., Guédon, Y., Prusinkiewicz, P., & Godin, C. (2008). **MAppleT: simulation of apple tree development using mixed stochastic and biomechanical models.** Functional Plant Biology, 35(10), 936–950. https://doi.org/10.1071/FP08081

[9] Stojanović, N. (2016). **A method for generating stochastic 3D tree models with Python in Autodesk Maya.** Journal of Graphic Engineering and Design, 7(2), 25–30. https://doi.org/10.24867/JGED-2016-2-025

[10] Tang, Y., Wu, D.-Y., & Fan, J. (2013). **Computational Approach to Seasonal Changes of Living Leaves.** Computational and Mathematical Methods in Medicine, 2013, 619385. https://doi.org/10.1155/2013/619385

[11] Jiao, D., Yang, M., & Yang, G. (2018). **Physically-based Dynamic Algorithms for Time-Varying of Flowers and Leaves.** Journal of System Simulation, 30(6), 2076–2085. https://doi.org/10.16182/j.issn1004731x.joss.201806010

[12] Zioma, R. (2007). **GPU-Generated Procedural Wind Animations for Trees.** GPU Gems 3, Chapter 6. https://developer.nvidia.com/gpugems/gpugems3/part-i-geometry/chapter-6-gpu-generated-procedural-wind-animations-trees

[13] Sousa, T. (2007). **Vegetation Procedural Animation and Shading in Crysis.** GPU Gems 3, Chapter 16. https://developer.nvidia.com/gpugems/gpugems3/part-iii-rendering/chapter-16-vegetation-procedural-animation-and-shading-crysis

[14] Habel, R., Kusternig, A., & Wimmer, M. (2009). **Physically Guided Animation of Trees.** Computer Graphics Forum, 28(2). https://doi.org/10.1111/j.1467-8659.2009.01391.x

[15] Li, C., Qian, J., Tong, R., Chang, J., & Zhang, J. (2015). **GPU based real-time simulation of massive falling leaves.** Computational Visual Media, 1(4), 351–358. https://doi.org/10.1007/s41095-015-0025-1

[16] Fearing, P. (2000). **Computer modelling of fallen snow.** Proceedings of SIGGRAPH 2000, 37–46. https://doi.org/10.1145/344779.344809

[17] Reynolds, D. T., Laycock, S. D., & Day, A. M. (2015). **Real-time accumulation of occlusion-based snow.** The Visual Computer, 31(5), 689–700. https://doi.org/10.1007/s00371-014-0995-5

[18] Creus, C., & Patow, G. A. (2013). **R4: Realistic rain rendering in realtime.** Computers & Graphics. https://doi.org/10.1016/j.cag.2012.12.002

[19] Kenney. **Nature Kit 2.1.** 330 nature-themed 3D assets, Creative Commons Zero 1.0. https://kenney.nl/assets/nature-kit （访问日期：2026-07-20）
