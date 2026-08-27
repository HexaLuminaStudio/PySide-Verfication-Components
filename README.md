<p align="center">
  <img width="15%" src="https://img.cdn1.vip/i/6999d326d78b4_1771688742.webp" alt="PySide Verification Components">
</p>

# PySide Verification Components

面向 PySide6 桌面应用的可移植验证码组件集。提供三种滑块验证与两种点选验证，默认离线可用，也支持由项目传入远程图片地址。

> 这些组件适合阻止误触、增加自动操作成本，但客户端逻辑可以被绕过，不能替代服务端鉴权、限流和风控。

## 组件

- `BasicSliderCard` / `BasicSliderFlyout`：普通拼图滑块
- `FigureSliderCard` / `FigureSliderFlyout`：异形拼图滑块
- `CircleSliderCard` / `CircleSliderFlyout`：圆周旋转滑块
- `TextClickCard` / `TextClickFlyout`：文字顺序点选
- `IconClickCard` / `IconClickFlyout`：颜色与图形顺序点选

所有卡片都提供 `verificationSuccess` 与 `verificationFailed(str)` 信号；所有弹窗都提供 `success` 与 `failed(str)` 信号。

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

## 兼容说明

原有 `src.basicSliderVerification` 等导入路径仍然保留；新项目建议统一从 `pyside_verification` 导入。远程图片不再默认请求第三方随机图接口，避免离线、超时或接口变更导致组件不可用。

## 运行示例

```bash
python main.py
```

## 许可证

GPL-3.0，详见 `LICENSE`。
