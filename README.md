<p align="center">
  <img width="15%" src="https://img.cdn1.vip/i/6999d326d78b4_1771688742.webp" alt="PySide Verification Components">
</p>

# PySide Verification Components

面向 PySide6 桌面应用的可移植验证码组件集。提供四种滑块、两种点选与一种图块排序验证，默认离线可用，也支持由项目传入远程图片地址。

> 这些组件适合阻止误触、增加自动操作成本，但客户端逻辑可以被绕过，不能替代服务端鉴权、限流和风控。

## 组件

- `BasicSliderCard` / `BasicSliderFlyout`：普通拼图滑块
- `FigureSliderCard` / `FigureSliderFlyout`：异形拼图滑块
- `CircleSliderCard` / `CircleSliderFlyout`：圆周旋转滑块
- `RotateSliderCard` / `RotateSliderFlyout`：图片旋正滑块
- `TileOrderCard` / `TileOrderFlyout`：拖拽图块恢复图片顺序
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
