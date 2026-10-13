# Changelog — 轩辕剑3天之痕 (Sword3) ARM64 so-loader

> 本文件汇总相对仓库基线（summertimesaga so-loader 范式）的修复与新功能。
> 详细的移植进度与架构见 `docs/PROGRESS.md` 与 `docs/HANDOFF.md`。

## 修复 (Fixes)

- **EE47 启动即闪退：`LD_LIBRARY_PATH` 丢失厂商 GL 目录** (`swd3de.sh`，2026-10-14)：
  整理脚本时误删了 `LD_LIBRARY_PATH` 首位的 **`/usr/lib/libmali`**（EmuELEC 特有）。
  EmuELEC 把 Mali 的 `libEGL.so` / `libGLESv2.so` / `libgbm.so` 单独放在该目录，
  `/usr/lib/libEGL.so` 只是 mesa/GLVND 转发库；不带该目录时设备 SDL2
  `dlopen` 到 mesa 那份 → `SDL_CreateWindow` 报
  `Can't load EGL/GL library on window creation.` → `SDL_main` 返回 2 →
  进程退出（表现为"进游戏就闪退"），随后还在 `fflush` 处二次 SIGSEGV。
  修复：按 `/usr/lib/libmali` → `/usr/lib/mali` → `.../aarch64-linux-gnu/mali`
  顺序探测，存在则置于 `LD_LIBRARY_PATH` 最前，并打印 `gl: vendor dir ...`。
  ROCKNIX 无该目录（EGL 直接在 `/usr/lib`），故探测式写法一份脚本通吃两系统。
  验证（EE47 192.168.31.216）：日志由 `SDL_CreateWindow FAILED` 变为
  `egl_shim: Window created logical 640x480 SDL 1024x768 drawable 1024x768`，
  `SDL_main` 正常推进到标题画面，无 CRASH。
  > 连带澄清：此前 EE 上"手柄方向无效"实为窗口创建失败、主循环未真正跑起来的
  > 次生现象；本条修复后，EE 日志同样出现
  > `[pad] inject via UpdateKeyStatus(SDL_Scancode)`，注入通道在 EE 上正常。
- **手柄方向键/确认键无效** (`src/main.c`，2026-10-13)：
  游戏零手柄 API（只轮询键盘），loader 原 `sw_input_thread` 仅处理 SELECT+START 退出，
  没有任何方向/确认注入。修复：`sw_input_thread` 枚举并打开**所有**手柄（原先只开
  idx=0，虚拟手柄常落在 idx=1），轮询 DPAD + 左摇杆 + A/B/L1/R1，把"键 + 按下/松开"
  封装为自定义 `SDL_UserEvent` 推入队列，由主线程 `sw_SDL_PollEvent` 拦截后直调
  `SDLINPUT::UpdateKeyStatus(DINPUT, scancode, down)`（先试
  `...E12SDL_Scancodeb`，失败再试 `...Eib`，最后才回退 `SDL_PushEvent`）。
  > 关键坑：**不能用 `SDL_PushEvent` 注入键盘** —— 它只进事件队列，不更新
  > `SDL_GetKeyboardState()` 的内部状态数组，而游戏是轮询式的，故日志有 44 条
  > `[pad]` 注入却毫无反应。必须直调 `UpdateKeyStatus`。
  验证：ROCKNIX 192.168.31.221 实机方向键 + A 可用；EE47 在本条 GL 修复后同样生效。
- **标题画面按 Y 闪退（SIGSEGV @ iRoleVar）** (`src/main.c`，2026-10-13)：
  实机在标题画面按 Y 打开作弊面板即闪退，`sig=11 si_code=1 si_addr=(nil)`。
  取证：PC 落在 `libSWD3E.so` 的 `iRoleVar`（`_Z8iRoleVarjjPjj`，`st_value=0x12D3B4`）
  入口 `+0xC`，该处 `ldr w9,[x8]` 解引用空指针 —— 即角色数据库两级全局指针的二级为 NULL。
  链路：按 Y → `sw_handle_cheat_pad` 开面板 → `sw_aff_load()` 读好感度 → `sw_role_var()`
  → 游戏 `iRoleVar()`；此时尚未进游戏，`RoleDataBase` 未初始化。
  修复：新增 `sw_role_db_ready()`，按反汇编推出的全局槽地址（数据段 vaddr `0x17A478`
  → 运行时 `data_base + 0x3638`）先判两级指针，未就绪直接返回 0，下游按
  "找不到好感数据"兜底。改动仅 `sw_role_var()` 一处前置守卫。
  回归验证：① 带临时自检钩子的等价构建模拟按 Y，日志两次「RoleDataBase 未就绪，跳过
  iRoleVar」，好感度 (-1,-1)，无 SIGSEGV；② 发布版（自检已回收）+ `tools/uinput_y_press`
  注入真实 Y 键，同一守卫命中，崩溃计数 0，进程存活。
- **两套 `libSWD3E.so` 的符号名差异导致功能静默失效** (`src/main.c`，2026-10-13)：
  全量核对 `main.c` 引用的 45 个 `sw_sym()` 符号后发现：参考构建 so（`4375fb6a`，1488384B）
  全部命中，而本仓库 `libs/` 的 so（`037a9e92`，1519528B）缺 2 个 —— 缺的符号 `sw_sym`
  返回 0，调用方静默跳过，不报错：
  - `MainMenu_selectitem` → 本仓库 so 里该变量名为 **`selectitem`**（`0x1822B0`；
    参考版为 `0x16C824`，两者都是 `selectitem/M/R/G/I/k/Aselectitem` 数组的首元素，
    布局完全一致）。缺失会让 `sw_btn_is_selected()` 恒为 0（选中框不显示）。
    修复：`sw_menu_select()` 两个名字都试，找不到仍返回 NULL 由调用方判空。
  - `_ZN8SDLINPUT15UpdateKeyStatusEib` → 本仓库 so 只有
    `...E12SDL_Scancodeb` 重载（参考版两者都有）。修复见上：键盘注入改走 SDL 事件
    队列，不再依赖该符号。**遗留**：L1/R1 菜单换人仍走 `sw_menu_man_key(25/26)`，
    在本仓库 so 上因符号缺失而不生效（25/26 作 scancode 查 `gkeyMapping` 无对应项），
    待后续按 `gkeyMapping` 的 `id7=PAGEUP/id8=PAGEDOWN` 另做适配。
  > 提示：换用另一份 so 时，所有硬编码偏移需重算（例如 `sw_role_db_ready()` 的
  > `data_base + 0x3638` 是按本仓库 so 推的）。
- **构建脚本对象通配隐患** (`build_docker.sh`)：`build/` 目录跨次构建复用，而 `libbionic_shim`
  阶段会产出 `build/libc_compat_shim.o`（定义 LIBC 版本节点，脚本注释明确禁止进主程序）。
  原 `build/*.o` 通配会把上一轮遗留的该对象链入主程序，导致产物随构建次数漂移
  （实测第二次构建导出符号 710→914）。改为显式排除该对象。
- **启动脚本调试光标笔误** (`swd3de.sh`)：原 `SUMMERTIME_CURSOR=1` 会每帧绘制调试光标角标，
  与 README / `egl_shim` 注释"关闭调试光标"意图相反，改为 `SUMMERTIME_CURSOR=0`。
- **启动方式文档澄清** (`README.md`)：明确脚本须经 **PortMaster** 启动（由 `control.txt` 注入
  `$directory`），`GAMEDIR="$directory/ports/sword3"`；ROCKNIX 下即
  `/storage/roms/ports/sword3/swd3de.sh`。脱离 PortMaster 手动 `bash` 会因 `$directory`
  未定义得到错误路径。
- **部署脚本 IP 可参数化** (`deploy_to_device.sh`)：`IP` 支持 `$1` 覆盖（默认 `192.168.31.16`），
  适配测试设备 IP 不固定的场景。

## 新功能 (Features，已在 `main.c` / `libbionic_shim.c` 实现)

- **#1 中文编码检测**：`libbionic_shim` 拦截 `TTF_RenderUTF8_*`，按游戏实际打开的字体名
  （`CT.ttf`→BIG5 繁体 / `CS.ttf`→GBK 简体）推断编码并转 UTF-8，修复对话/剧情缺字乱码。
- **#2 手柄→键盘注入**（2026-10-13 重做，取代早期的"手柄→鼠标模拟"）：
  > ⚠️ 早期实现（摇杆/方向键→`SDL_MOUSEMOTION`、`A/B`→左/右键、`L1/R1`→滚轮，见 `086ca0b`）
  > 在 `83508e3` 重构中被丢弃，之后 `sw_input_thread` 只剩 SELECT+START 退出热键，
  > 实机表现为进游戏后方向键无效、无法选择"开始游戏/读取进度"。本轮按**键盘**路线重做：
  >
  > **为什么是键盘而不是鼠标**：`libSWD3E.so` 的 `.dynsym` 中零个 `SDL_Joystick*` /
  > `SDL_GameController*` 导入（纯鼠标键盘 RPG），但它自带
  > `PlayConsole(SDL_Event*)`（本地 so `@0x839D4`）处理 `SDL_KEYDOWN/KEYUP`，再由
  > `SDLINPUT::UpdateKeyStatus` 写入 `DINPUT`；且 `gkeyMapping`（由 `KeyMappingSetup`
  > 初始化）实测为 `id3=LEFT id4=UP id5=RIGHT id6=DOWN id12=RETURN id0=ESCAPE id1=SPACE`。
  >
  > **实现（第二轮，已证伪第一轮）**：`sw_input_thread` 每 16ms 轮询**所有**手柄
  > （最多 4 个，热插拔补开）的 DPAD / 左摇杆 / A，用**自定义 `SDL_UserEvent`**
  > 把"注入哪个键、按下还是松开"递给主线程，由 `sw_SDL_PollEvent` 在**游戏主线程**
  > 调用 `SDLINPUT::UpdateKeyStatus(DINPUT, key, down)`。
  > 按键为脉冲式：按下沿立即发一个 70ms 按下脉冲，按住 400ms 后按 140ms 连发，松开收尾。
  > 战斗撤退/自动（extra）菜单下让位给 `sw_handle_extra_pad`，避免双重触发。
  >
  > ❌ 第一轮直接推 `SDL_KEYDOWN/SDL_KEYUP` 事件，实机无效：EE47 上 loader 确实注入了
  > 44 次（日志有 `[pad]` 记录）但游戏毫无反应。原因是 `SDL_PushEvent` 只入队，
  > **不会更新 `SDL_GetKeyboardState` 的内部状态数组**（该数组由 SDL 内部
  > `SDL_SendKeyboardKey` 维护），而本游戏正是用 `SDL_GetKeyboardState` +
  > `SDLINPUT::UpdateKeyStatus` 轮询按键。（游戏虽也有 `PlayConsole(SDL_Event*)`
  > 处理 `SDL_KEYUP`，但那只覆盖个别特殊键，不是主输入链路。）
- **#3 退出热键下沉**：SELECT+START 在 loader 内部每帧轮询物理手柄并 `_exit(0)`，不再依赖 gptokeyb。
- **内置修改器 (trainer)**：金钱 / 满血 / 不遇敌 / 一击必杀 / 抓怪 / 炼妖 / 符鬼 等开关。
- **菜单换人 / 物品栏**：解绑装备后 L1/R1 的残留绑定，避免 `DrawRoleIcon2` 崩溃。
- **标题署名**：标题画面加入 "ported by windstarry" 字样（避开大宇印章）。
- **`SDL_SS2D::Init` 栈 canary patch**：用 bind mount `/tmp/s3` 缩短绝对路径，规避
  `isAnySlotExist()` 定长栈缓冲溢出 abort（sig=6）。
- **`GetVideoPath` / `GetACTPath` hook**：扩展资源路径重定向，覆盖视频 / ACT 资源。

## 诊断工具 (`tools/`)

- **`symbolize_crash.py`**：读取设备 `debug.log` 中的 PC/LR/FP 与 so 加载基址，换算成
  `libSWD3E.so` 内偏移，再用 `.dynsym`/`.symtab` 就近符号化。
- **`disasm_crash.py`**：基于 capstone(aarch64) 反汇编崩溃点周边指令，按 `PT_LOAD` 段
  完成 vaddr→file offset 换算。
- **`ee_ssh.py`**：本机无 sshpass 时的 paramiko SSH 通道（用于 EE47/ROCKNIX 设备的
  拉取日志、部署二进制、远程执行）。
- **`uinput_pad.c`**：aarch64 静态虚拟 Xbox360 手柄（VID/PID `0x045e/0x028e`，命中 SDL
  内置映射），用于无人按键的端到端回归。支持按键序列：
  `uinput_pad [等待秒数] ["dpad_down,dpad_down,a"] [保持秒数]`，键名含
  `y/a/b/x/l1/r1/start/select/dpad_up|down|left|right`。取代早期的 `uinput_y_press.c`
  （后者只能注入 Y）。编译产物不入库（见 `.gitignore`）。
- **`xref_addr.py`**：aarch64 交叉引用定位——找出哪些函数读/写了某个全局 vaddr
  （跟踪 `adrp`+`add`/`ldr`/`str` 的页基址）。用于判断"某个状态由谁驱动"
  （本轮据此确认 `PlayConsole` 处理键盘事件）。注意必须只扫可执行 **section**
  并开 `skipdata`：扫整个 `PT_LOAD` 段会在 ELF 头处遇到无法解码的字节而提前终止，
  表现为"0 处引用"的假阴性。

## 仓库清理 (Repo hygiene)

- `.gitignore` 补 `logs/`（从设备拉回的崩溃日志 / 二进制取证副本）与
  `tools/uinput_y_press`（交叉编译产物）。
- `.gitignore` 补 `src/_unused_katanazero/`（误用脚手架反例，原称已忽略但实际被跟踪）与
  `libs/*.bak-*`（游戏 `.so` 备份，BYO-data 不入库）。
- 早期 ELF 符号侦察产物（`nm_apkx.txt` / `file_check.txt` / `check_refs.py`）归档至 `docs/diagnostics/`。
- `CHECK_REPORT.md`：本次静态审查报告（代码/文档/脚本一致性核查依据）。
