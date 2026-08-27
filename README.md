<p align="center">
  <img width="15%" src="https://img.cdn1.vip/i/6999d326d78b4_1771688742.webp" alt="PySide Verification Components">
</p>

# PySide Verification Components

面向 PySide6 桌面应用的可移植验证码组件集。提供四种滑块、两种点选、图块排序、图形拖拽归位与路径描摹验证，默认离线可用；依赖图片的类型也支持由项目传入远程图片地址。

> 这些组件适合阻止误触、增加自动操作成本，但客户端逻辑可以被绕过，不能替代服务端鉴权、限流和风控。

## 组件

- `BasicSliderCard` / `BasicSliderFlyout`：普通拼图滑块
- `FigureSliderCard` / `FigureSliderFlyout`：异形拼图滑块
- `CircleSliderCard` / `CircleSliderFlyout`：圆周旋转滑块
- `RotateSliderCard` / `RotateSliderFlyout`：图片旋正滑块
- `TileOrderCard` / `TileOrderFlyout`：拖拽图块恢复图片顺序
- `DragMatchCard` / `DragMatchFlyout`：将彩色图形拖入匹配轮廓
- `PathTraceCard` / `PathTraceFlyout`：从起点连续描摹并依次经过路径节点
- `ConditionRegionCard` / `ConditionRegionFlyout`：选择所有符合颜色与形状条件的区域
- `DynamicTargetCard` / `DynamicTargetFlyout`：按住并持续跟随平滑移动的目标
- `ShortMemoryCard` / `ShortMemoryFlyout`：记住短暂亮起的区域顺序并复现
- `TextClickCard` / `TextClickFlyout`：文字顺序点选
- `IconClickCard` / `IconClickFlyout`：颜色与图形顺序点选

所有卡片都提供 `verificationSuccess` 与 `verificationFailed(str)` 信号；所有弹窗都提供 `success` 与 `failed(str)` 信号。全部卡片及弹窗都提供服务端验证接口。

## 安装

```bash
pip install .
```

开发环境可使用：

```bash
pip install -e ".[test]"
pytest
```

要求 Python 3.10+、PySide6 6.5+。

## 直接嵌入页面

```python
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget
from pyside_verification import BasicSliderCard

app = QApplication([])
window = QWidget()
layout = QVBoxLayout(window)

captcha = BasicSliderCard()
captcha.verificationSuccess.connect(lambda: print("验证成功"))
captcha.verificationFailed.connect(lambda reason: print("验证失败：", reason))
layout.addWidget(captcha)

window.show()
app.exec()
```

默认不访问网络，会生成离线背景。如需使用业务自己的图片服务：

```python
captcha = BasicSliderCard(image_url="https://example.com/captcha-background")
```

网络失败或图片无法解析时，组件会自动回退到离线背景，并通过图片控件的 `errorOccurred(str)` 信号报告原因。

## 弹出式使用

```python
from pyside_verification import TextClickFlyout

flyout = TextClickFlyout.create(target=button, parent=window)
flyout.success.connect(on_verified)
flyout.failed.connect(lambda reason: print(reason))
```

`target` 可以是一个 `QWidget`，也可以是全局坐标 `QPoint`。传入 `None` 时只创建实例，不立即显示。

## 自定义滑动策略

```python
from pyside_verification import BasicSliderCard, TrackPolicy

policy = TrackPolicy(
    min_samples=5,
    min_duration=0.15,
    max_duration=12.0,
    min_distance=24.0,
    reject_perfect_linear_tracks=True,
)
captcha = BasicSliderCard(track_policy=policy, tolerance=8)
```

滑块支持鼠标与键盘：方向键移动，`Shift + 方向键` 微调，回车或空格提交。

图片旋正验证码还可以指定服务端生成挑战时使用的初始角度。滑块答案范围为 `0`～`300`，对应顺时针旋转 `0°`～`360°`：

```python
from pyside_verification import RotateSliderCard

captcha = RotateSliderCard(
    initial_angle_degrees=137,
    angle_tolerance_degrees=6,
    image_scale=0.9,
)
```

图块排序验证码默认切成 4 条纵向图块，可在 3～6 块之间配置。鼠标拖动图块即可交换位置；键盘用户可以按空格拿起图块，再使用左右方向键移动：

```python
from pyside_verification import TileOrderCard

captcha = TileOrderCard(
    tile_count=4,
    animation_duration_ms=180,
)
```

将 `animation_duration_ms` 设为 `0` 可以关闭图块换位动画。

图形拖拽归位默认提供 3 个不同图形，支持配置 2～4 个。错误归位会平滑返回，全部匹配后自动验证：

```python
from pyside_verification import DragMatchCard

captcha = DragMatchCard(
    shape_count=3,
    animation_duration_ms=180,
)
```

路径描摹验证码默认生成 5 个节点。鼠标必须从起点按下并保持拖动，依次经过所有节点后松开；键盘用户可以按空格开始、使用方向键推进或回退，并在终点按空格提交：

```python
from pyside_verification import PathTraceCard

captcha = PathTraceCard(
    node_count=5,
    hit_radius=18,
    path_tolerance=14,
    backtrack_tolerance=12,
)
```

判定不仅检查节点顺序，还会验证整段轨迹是否始终位于虚线路径的容差走廊内，并拒绝跨段、大幅回退以及到达终点后继续乱画。`path_tolerance` 控制允许偏离路径的像素距离，`backtrack_tolerance` 控制允许自然手抖产生的小幅回退。

条件区域点选默认生成 9 个颜色与形状不同的区域。用户可以反复选择或取消，确认后才会提交；键盘用户使用方向键移动、空格切换选择、回车确认、Esc 清空：

```python
from pyside_verification import ConditionRegionCard

captcha = ConditionRegionCard(region_count=9)
```

服务端挑战可以指定区域、不透明 ID 和筛选条件：

```python
from pyside_verification import ConditionRegionCard, RegionSpec

captcha = ConditionRegionCard(
    region_count=6,
    regions=[
        RegionSpec("area-a", "blue", "circle"),
        RegionSpec("area-b", "blue", "circle"),
        RegionSpec("area-c", "blue", "triangle"),
        RegionSpec("area-d", "green", "circle"),
        RegionSpec("area-e", "orange", "square"),
        RegionSpec("area-f", "purple", "diamond"),
    ],
    condition_color="blue",
    condition_shape="circle",
    require_server_verification=True,
    challenge_token="opaque-server-token",
)
```

动态目标追踪验证码会在用户按住目标后开始运动，并检查整个过程的有效跟随率、连续偏离时间和最大偏离距离。键盘用户按空格开始，再用方向键控制追踪光标：

```python
from pyside_verification import DynamicTargetCard

captcha = DynamicTargetCard(
    target_speed=60,
    tracking_radius=30,
    min_follow_ratio=0.78,
)
```

短时记忆验证码会在卡片显示后依次高亮 3～7 个区域，播放完成后隐藏提示，用户需要按原顺序复现。键盘用户使用方向键移动、空格或回车选择：

```python
from pyside_verification import ShortMemoryCard

captcha = ShortMemoryCard(
    sequence_length=4,
    flash_duration_ms=520,
    gap_duration_ms=170,
)
```

`reduced_motion=True` 会延长每次展示和间隔，降低快速闪烁。服务端挑战可以指定固定顺序、不透明区域 ID 和序列 ID：

```python
captcha = ShortMemoryCard(
    sequence_length=4,
    sequence_indices=[0, 5, 2, 7],
    cell_ids=[f"cell-{index}" for index in range(9)],
    sequence_id="memory-sequence-v2",
    require_server_verification=True,
    challenge_token="opaque-server-token",
)
```

默认时长会根据平滑后轨迹的真实长度自动计算，目标约以每秒 60 像素匀速移动，通常需要 4.5～8 秒完成，不再因某一段距离较长而突然加速。需要固定业务时长时仍可显式传入 `tracking_duration`。

可以通过 `reduced_motion=True` 缩小本地随机轨迹范围并降低刷新频率。服务端挑战可指定轨迹点、不透明目标 ID 与轨迹 ID；提交载荷包含有上限的用户轨迹及行为指标：

```python
captcha = DynamicTargetCard(
    waypoints=[(70, 82), (122, 38), (190, 52), (236, 118), (154, 132)],
    target_id="target-a",
    path_id="path-v3",
    require_server_verification=True,
    challenge_token="opaque-server-token",
)
```

服务端生成挑战时，可以传入固定坐标和不透明节点 ID。提交载荷包含有上限的压缩轨迹、相对时间、路径长度、命中数与输入方式；服务端仍应独立核对节点顺序和轨迹合理性：

```python
captcha = PathTraceCard(
    node_count=5,
    nodes=[(28, 52), (89, 118), (150, 42), (211, 124), (272, 64)],
    node_ids=["n-a", "n-b", "n-c", "n-d", "n-e"],
    require_server_verification=True,
    challenge_token="opaque-server-token",
)
```

服务端挑战可以传入固定图形类型、不透明图形 ID、目标 ID 和目标排列：

```python
captcha = DragMatchCard(
    shape_types=["circle", "triangle", "star"],
    shape_ids=["shape-a", "shape-b", "shape-c"],
    target_ids=["slot-1", "slot-2", "slot-3"],
    target_order=[1, 2, 0],
    require_server_verification=True,
    challenge_token="opaque-server-token",
)
```

当挑战由服务端生成时，可以同时传入服务端绑定的初始排列和不透明图块 ID：

```python
captcha = TileOrderCard(
    tile_count=4,
    initial_order=[2, 0, 3, 1],
    tile_ids=["tile-a", "tile-b", "tile-c", "tile-d"],
    require_server_verification=True,
    challenge_token="opaque-server-token",
)
```

## 生产环境的人机验证

内置轨迹分析会检查采样数量、耗时、速度变化、重复步长、重复采样间隔、直线拟合、纵向偏移和异常回退，并给出 `riskScore`、`metrics` 与 `signals`。这些数据只能增加简单脚本的成本，不能证明操作者一定是真人。

生产环境请开启服务端强制验证。滑块和点选组件都支持该模式；开启后，服务端没有明确接受前，组件不会发出成功信号：

```python
from pyside_verification import AttemptPolicy, BasicSliderCard

captcha = BasicSliderCard(
    require_server_verification=True,
    challenge_token=challenge_from_api["token"],
    challenge_ttl_seconds=challenge_from_api["expiresIn"],
    attempt_policy=AttemptPolicy(max_failures=5, cooldown_seconds=30),
)

def submit_to_server(payload):
    # 交给项目自己的异步网络层；不要在桌面客户端保存服务端密钥。
    api.verify_captcha_async(payload, on_verified)

def on_verified(response):
    captcha.resolveServerVerification(
        response["attemptId"],
        response["accepted"],
        response.get("reason", ""),
    )

captcha.verificationRequested.connect(submit_to_server)
captcha.challengeRefreshRequested.connect(fetch_a_new_server_challenge)
```

服务端必须自己完成以下工作：

- 生成不可预测、短时有效、一次性使用的挑战令牌，并绑定具体操作、账号和会话；
- 根据令牌保存的挑战状态独立核对答案，原子地消费令牌，拒绝过期与重放；
- 按账号、会话、设备和网络来源做分层限流、递增延迟与风险记录；
- 把客户端上报的轨迹风险分仅作为辅助信号，绝不能直接信任；
- 对高风险操作叠加登录态、二次确认或 MFA，而不是只依赖验证码。

内置离线图片适用于演示和低风险场景。真正的生产挑战应由后端或专业人机验证服务生成并保留正确答案；仅把本地随机题目的结果传给服务端，不会形成可信安全边界。

## 兼容说明

原有 `src.basicSliderVerification` 等导入路径仍然保留；新项目建议统一从 `pyside_verification` 导入。远程图片不再默认请求第三方随机图接口，避免离线、超时或接口变更导致组件不可用。

## 运行示例

```bash
python main.py
```

## 许可证

GPL-3.0，详见 `LICENSE`。
