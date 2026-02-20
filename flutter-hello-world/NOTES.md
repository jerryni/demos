# Flutter Hello World - 启动记录

## 环境

- macOS 26.2 / iPhone 15 Pro (iOS 26.1)
- Flutter debug 模式
- 通过 USB 连接真机调试

---

## 首次初始化（只需做一次）

### 1. Xcode 登录 Apple ID

Xcode → Settings → Accounts → 添加 Apple ID

### 2. 配置签名

打开 `ios/Runner.xcworkspace`：

```bash
open ios/Runner.xcworkspace
```

在 Xcode 里：

- 左侧选中 `Runner` → `Signing & Capabilities`
- `Team` 选你的 Apple ID
- `Bundle Identifier` 改成唯一值，例如 `com.yourname.flutterhelloworld`

### 3. iPhone 开启开发者模式

iPhone 上：`设置 → 隐私与安全性 → 开发者模式` → 打开开关 → 重启手机 → 重启后确认开启

> 开发者模式需要 iOS 16 及以上系统才有此选项。

### 4. iPhone 信任 Mac

iPhone 连接 Mac 后，iPhone 弹出"是否信任此电脑" → 点**信任**，输入密码确认。

### 5. 信任开发者证书（首次安装时）

iPhone 上：`设置 → 通用 → VPN与设备管理` → 找到你的 Apple ID 证书 → 点**信任**

---

## 启动步骤

### 1. 确认设备连接

```bash
flutter devices
```

iPhone 出现在列表里后，拿到设备 ID。

### 2. 运行到 iPhone

```bash
flutter run -d <设备ID>
```

例如：

```bash
flutter run -d 00008130-000A3D660160001C
```

### 3. 热重载

app 运行中，修改代码后在终端按：

- `r` 热重载（保留状态）
- `R` 热重启（重置状态）
- `q` 退出调试

---

## 遇到的问题

### 白屏后 app 直接退出

**原因：** Flutter debug 模式需要通过局域网连接 iPhone 上的 Dart VM，iPhone 没有授予本地网络权限导致连接失败，app 退出。

**报错信息：**

```
Flutter could not access the local network.
SocketException: Send failed (OS Error: No route to host, errno = 65)
```

**解决：** iPhone 上 `设置 → 隐私与安全性 → 本地网络` → 找到对应 app → 打开开关。

---

## Xcode 使用场景

日常开发不需要打开 Xcode，以下情况才需要：

- 配置签名 / Bundle ID
- 添加 iOS 原生权限（相机、定位等）
- 提交 App Store
- 排查原生层 crash

---

## 日志打印

```dart
debugPrint('your log here');
```

`debugPrint` 在 release 模式下自动禁用，优于 `print`。
