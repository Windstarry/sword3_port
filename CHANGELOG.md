# Changelog — 轩辕剑3天之痕 (Sword3) ARM64 so-loader

> 本文件汇总相对仓库基线（summertimesaga so-loader 范式）的修复与新功能。
> 详细的移植进度与架构见 `docs/PROGRESS.md` 与 `docs/HANDOFF.md`。

## 修复 (Fixes)

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
- **#2 手柄→鼠标模拟**：`sw_input_thread` 将手柄映射为鼠标事件（右/左摇杆移动、方向键步进、
  A/B 左/右键、L1/R1 滚轮），轩辕剑3天之痕为鼠标 RPG，解决掌机无法操作。
  > ⚠️ **已知问题（2026-10-13 核查）**：该实现已不在当前 `src/main.c` 中 —— 现存映射仅
  > L1/R1、A/B、Y 与 SELECT+START 退出热键，无任何光标移动（无 `SDL_MOUSEMOTION` 注入、
  > 无 `SDL_BUTTON_LEFT`）。实机表现为进游戏后方向键无效、无法选择"开始游戏/读取进度"。
  > 原始实现可在 `086ca0b` 的历史 `src/main.c` 中找到，在 `83508e3` 重构时被丢弃，待恢复。
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
- **`uinput_y_press.c`**：aarch64 静态虚拟 Xbox360 手柄（VID/PID `0x045e/0x028e`，命中 SDL
  内置映射），用于无人按键的端到端回归（`uinput_y_press [delay_s] [repeat]`）。
  编译产物不入库（见 `.gitignore`）。

## 仓库清理 (Repo hygiene)

- `.gitignore` 补 `logs/`（从设备拉回的崩溃日志 / 二进制取证副本）与
  `tools/uinput_y_press`（交叉编译产物）。
- `.gitignore` 补 `src/_unused_katanazero/`（误用脚手架反例，原称已忽略但实际被跟踪）与
  `libs/*.bak-*`（游戏 `.so` 备份，BYO-data 不入库）。
- 早期 ELF 符号侦察产物（`nm_apkx.txt` / `file_check.txt` / `check_refs.py`）归档至 `docs/diagnostics/`。
- `CHECK_REPORT.md`：本次静态审查报告（代码/文档/脚本一致性核查依据）。
