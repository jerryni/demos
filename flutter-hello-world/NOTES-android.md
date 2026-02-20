# Flutter Android 真机调试 - 启动记录

## 环境

- macOS 26.2 / Android 14 (API 34)
- Flutter debug 模式
- 通过 USB 连接真机调试

---

## 首次初始化（只需做一次）

### 1. 安装完整 Android SDK

通过 brew 安装 Android Studio（自带完整 SDK）：

```bash
brew install --cask android-studio
```

打开 Android Studio 完成初始化向导。向导中会下载模拟器系统镜像（约 1.8GB），如果下载失败或不需要模拟器，直接点 **Cancel** / **Finish** 跳过，不影响真机调试。

核心组件确认安装即可：
- `build-tools`
- `platform-tools`
- `platforms;android-xx`

### 2. 安装 cmdline-tools

Android Studio → Settings → Languages & Frameworks → Android SDK：

1. **Android SDK Location** 填写：`/Users/ni/Library/Android/sdk`
2. 切到 **SDK Tools** 标签页
3. 勾选 **Android SDK Command-line Tools (latest)** → Apply

### 3. 设置环境变量

```bash
echo 'export ANDROID_HOME=$HOME/Library/Android/sdk' >> ~/.zshrc
echo 'export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin' >> ~/.zshrc
echo 'export PATH=$PATH:$ANDROID_HOME/platform-tools' >> ~/.zshrc
source ~/.zshrc
```

### 4. 接受 Android 许可证

```bash
flutter doctor --android-licenses
```

一路输入 `y` 回车。

### 5. 手机开启 USB 调试

`设置 → 开发者选项 → USB 调试` 打开。

> 没有开发者选项？去 `设置 → 关于手机 → 版本号`，连续点 7 次解锁。

### 6. USB 连接设置

连接 USB 后，下拉通知栏，USB 模式选 **文件传输（MTP）**，不要选"仅充电"。

### 7. 信任 Mac

手机弹出"是否允许 USB 调试" → 点**允许**。

---

## 启动步骤

### 1. 确认设备连接

```bash
flutter devices
```

Android 设备出现在列表里，拿到设备 ID。

### 2. 运行到 Android

```bash
flutter run -d <设备ID>
```

---

## 遇到的问题

### flutter devices 看不到 Android 设备

**原因：** USB 模式选了"仅充电"，或未点击手机上的 USB 调试授权弹窗。

**解决：**
1. 下拉通知栏，USB 模式改为**文件传输（MTP）**
2. 拔插 USB，手机弹出授权弹窗点**允许**
3. 运行 `adb devices` 确认设备识别

---

### Build failed: `What went wrong: 25.0.1`

**原因：** `ANDROID_HOME` 指向的是 `android-platform-tools`（只有 adb），不是完整 Android SDK，缺少 `build-tools` 和 `cmdline-tools`。

**解决：** 安装完整 Android SDK（见上方初始化步骤）。

---

### `Android sdkmanager not found`

**原因：** `cmdline-tools` 未安装。

**解决：** 通过 Android Studio SDK Manager 安装 **Android SDK Command-line Tools (latest)**。

---

### `INSTALL_FAILED_USER_RESTRICTED: Install canceled by user`

**原因：** 编译安装 APK 时手机弹出安装确认，未点允许。

**解决：** 重新运行 `flutter run`，盯着手机屏幕，弹窗出现时点**安装**。

---

## 日志打印

```dart
debugPrint('your log here');
```

`debugPrint` 在 release 模式下自动禁用，优于 `print`。
