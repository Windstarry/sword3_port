# 对比报告：参考构建（sword3.sh）vs 当前项目（swd3de.sh）

> 对比日期：2026-10-13
> 参考项目：`D:\360Downloads\BaiduNetdiskDownload\轩辕剑3天之痕_修复主菜单开启修改器闪退`
> 当前项目：`D:\ProgramData\sword3_port`（main 分支，提交 `de416f6`）
> 目的：定位「进入游戏后手柄方向无效、无法选择开始游戏/读取进度」的差异来源

---

## 一、参考项目概况

| 项 | 值 |
|---|---|
| 目录 | `轩辕剑3天之痕_修复主菜单开启修改器闪退/` |
| 布局 | `sword3.sh`（启动器）+ `sword3/`（游戏目录，含二进制与资源） |
| 二进制 | `sword3` 230016 B，2026-08-21 03:45 |
| 编译器 | Linaro GCC 6.3.1 20170404 |
| 已部署 | ROCKNIX `192.168.31.221` → `/storage/roms/ports/sword3.sh` + `/storage/roms/ports/sword3/` |
| 与本项目关系 | `sword3.sh` ≡ `swd3de.sh`，同为轩辕剑叁外传·天之痕端口启动器 |

当前项目二进制：256192 B，2026-10-13 构建，Ubuntu GCC 9.4.0。

---

## 二、启动脚本差异（关键）

| 维度 | 参考 `sword3.sh` | 当前 `swd3de.sh` | 影响 |
|---|---|---|---|
| 启动框架 | **独立启动器，不依赖 PortMaster**；自动探测 GAMEDIR（同级 `sword3/` 或自身） | 依赖 PortMaster：`controlfolder/control.txt`、`get_controls`、`$ESUDO`、`pm_platform_helper`、`pm_finish` | 参考版可在无 PortMaster 环境直接跑 |
| **手柄映射库** | 显式设 `SDL_GAMECONTROLLERCONFIG_FILE`（`/opt/inttools` → `/usr/config/SDL-GameControllerDB` → `/usr/share/SDL2` → PortMaster 四处候选），并 `echo "pad: controller db ..."` | **无此设置** | 手柄能否被 SDL 识别为标准 GameController（含 dpad）的关键 |
| **调试光标** | `export SUMMERTIME_CURSOR=1` | `export SUMMERTIME_CURSOR=0` | 参考版显示 loader 光标角标 |
| `LD_LIBRARY_PATH` | `$STAGING:$GAMEDIR`（注释明确：**把 `/usr/lib` 塞最前会拿到旧 Mali blob**，导致 mali user 10.6 vs kernel 11.7、窗口建不起来） | 追加 `/usr/lib:/usr/lib/aarch64-linux-gnu` | 潜在的 Mali 版本错配风险 |
| staging 软链 | 仅 `libc.so / libm.so / libdl.so` | 另加 `libSDL2*/libpng16/libz/libOpenSLES/libandroid` | 当前版覆盖更全 |
| 其他 | 无 | governor performance、`SHIM_DUMP_OPEN` 开关、单实例 `pkill`、中文 locale | 当前版运维能力更强 |

---

## 三、二进制差异

导出符号数：参考 719 / 当前 710。

### 3.1 参考版独有（8 个 API + 2 条日志串）

```
SDL_GameControllerGetJoystick   SDL_GameControllerMapping
SDL_GameControllerMappingForGUID SDL_JoystickGetButton
SDL_JoystickGetDeviceGUID        SDL_JoystickGetGUIDString
SDL_JoystickNameForIndex         SDL_JoystickNumButtons
"[input] js%d name='%s' guid=%s gc=%d"
"[input] mapping %s"
```

→ 参考版具备 **joystick 层轮询 + 手柄枚举/映射诊断**；当前版完全没有（源码中 `SDL_Joystick*` 仅 `SDL_JoystickEventState`/`SDL_NumJoysticks`）。

### 3.2 当前版独有

```
[cheat] RoleDataBase              ← 本轮新增的 iRoleVar 空指针守卫
[shim:PNG_RW] decoder png=%s typed=%s libpng=yes
mmap %d MB failed
```

### 3.3 双方一致（排除项）

- 均 hook `commButtonClass::draw / drawButtonText / IsClick`（选中框 PSV 风格）
- 均把 `UIGamePad::{init,Update,SetMode,CheckStateRelease,Motion,C2,Close}` → `ret0`（禁用 Android 虚拟摇杆 UI）
- 均使用 `_ZN8SDLINPUT15UpdateKeyStatusEib`（游戏键盘状态注入）
- 均有 `SDL_PushEvent`；**均无 `SDL_WarpMouse` / `SDL_GetMouseState`**
  → **两边都不是「摇杆→鼠标移动」方案**，而是「手柄→游戏键盘/内部按键」方案

---

## 四、实机日志差异

| 项 | 参考版（ROCKNIX 221，2026-10-13 23:09 实跑） | 当前版（EmuELEC 216，2026-10-13 22:01 实跑） |
|---|---|---|
| 手柄映射库 | `pad: controller db /storage/.config/SDL-GameControllerDB/gamecontrollerdb.txt` | 无 |
| 手柄枚举 | `[input] js0 name='retrogame_joypad' guid=0300… gc=1` | 无 |
| 手柄映射 | `[input] mapping …,dpleft:b15,dpdown:b14,dpright:b16,dpup:b13,…`（dpad 完整） | 无 |
| 手柄打开 | `[input] pad opened (idx=0) retrogame_joypad` | `[input] pad opened (idx=0) gamepad` |
| `[patch]` 数 | **18**（含 `_ZN9UIGamePadC2Ev -> ret0`） | **17**（缺 `UIGamePadC2Ev`） |
| canary patch | `SDL_SS2D::Init skip false stack_chk`（命中） | `SDL_SS2D::Init canary site mismatch 97ffffa7 54ffff0b`（**未命中**） |
| 菜单进入 | 曾出现 `[menu-init] A-item-bar / A-enter-item`、`[onehit]` | **无 `[menu-init]`**（与「选不进菜单」吻合） |
| 日志量 | 18754 行 | 721 行 |

---

## 五、手柄方向无效的根因（源码级，当前项目）

当前 `src/main.c` 的手柄按键处理**全部集中在事件回调** `sw_SDL_PollEvent()`（:1747）：

| 处理函数 | 行 | 覆盖范围 |
|---|---|---|
| `sw_handle_cheat_pad` | :1374 | Y → 开/关作弊面板（面板内 dpad 导航） |
| B 分支 | :1758 | 右键 / 战斗返回 |
| START 分支 | :1774 | 吞掉 |
| A 分支 | :1776 | 物品栏 / extra 菜单 |
| `sw_handle_menu_man` | :1101 | **只处理 L1/R1**（→ `UpdateKeyStatus(DINPUT, 25/26, down)`） |
| `sw_handle_extra_pad` | :880 | DPAD **仅当 `sw_cmd_extra_active()`（战斗撤退/自动菜单）为真**时处理 |
| `sw_input_thread` | :1790 | **仅有 SELECT+START 退出**，无其它按键 |

**结论**：标题画面 / 主菜单下 `sw_cmd_extra_active()` 为假，DPAD 被原样放行给游戏；而 `libSWD3E.so` 是纯鼠标键盘 RPG（**无任何 Joystick/GameController 导入**），不识别 controller 事件 → 方向键无响应、无法选择「开始游戏 / 读取进度」。

佐证：选中框绘制 `sw_btn_is_selected()`（:311）依赖游戏内部 `MenuSelect` 索引，该索引由**键盘导航**驱动；键盘注入的既有通道是 `sw_menu_man_key()` → `SDLINPUT::UpdateKeyStatus(DINPUT, key, down)`（:1080），当前仅用于 L1/R1（key 25/26），**未接方向键与确认键**。

参考版多出的 joystick 层 API 表明：它在输入线程内**轮询 joystick 按钮**，走同一 `UpdateKeyStatus` 通道做键盘注入——这正是当前版缺失的一层。

---

## 六、建议下一步

1. **同机复现**：把当前构建部署到 ROCKNIX `192.168.31.221`（与参考版同设备、同手柄），排除设备/固件差异。
2. **补齐输入层**：在 `sw_input_thread` 内做 DPAD / A / B / L1 / R1 轮询，经 `UpdateKeyStatus(DINPUT, key, down)` 注入方向键与确认/取消键（沿用 L1/R1 已有的 key 25/26 通道）。
3. **对齐脚本**：`swd3de.sh` 补 `SDL_GAMECONTROLLERCONFIG_FILE` 与 `[input]` 枚举/映射打印，提升可观测性。
4. **修 canary 失配**：`SDL_SS2D::Init canary site mismatch`（参考版能命中）。
5. **复核守卫**：参考版用到 `RolePool` 符号，可作为我们 `sw_role_db_ready()` 守卫的交叉验证方向。

---

## 附：测试环境现状（2026-10-13 核对）

| IP | 实际系统 | 凭据 | 布局 | 已部署 |
|---|---|---|---|---|
| `192.168.31.216` | **EmuELEC 4.7-Nexus**（`20260930094611`，内核 6.1.118） | root/emuelec | **分裂式**：`roms/ports/swd3de/` + `roms/ports_scripts/swd3de.sh` | 当前项目构建 |
| `192.168.31.221` | **ROCKNIX**（`20260809`，内核 6.18.21） | root/rocknix | **同目录**：`roms/ports/sword3.sh` + `roms/ports/sword3/` | 参考构建 |

> 注：`192.168.31.216` 实测为 EmuELEC 而非 ROCKNIX；ROCKNIX 设备为 `192.168.31.221`。
