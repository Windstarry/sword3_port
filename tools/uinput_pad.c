/*
 * uinput_pad.c — 回归验证工具：创建 uinput 虚拟 Xbox360 手柄，延时后注入按键序列。
 *
 * 用途：无人操作掌机时，验证 loader 的手柄处理路径。
 *   - 序列 "y"                    → 标题画面按 Y 开作弊面板（iRoleVar 空指针回归）
 *   - 序列 "dpad_down,dpad_down,a" → 主菜单导航（手柄→键盘注入回归）
 *
 * 原理：设备 SDL2 通过 evdev 枚举手柄；uinput 设备用 Xbox360 的
 *       VID/PID(0x045e/0x028e) 命中 SDL 内置手柄映射，于是
 *       BTN_NORTH→SDL_CONTROLLER_BUTTON_Y、ABS_HAT0Y→DPAD 上下、以此类推。
 *
 * 用法： ./uinput_pad [等待秒数=30] [按键序列="y"] [序列后保持秒数=20]
 * 序列： 逗号分隔，支持 y/a/b/x/l1/r1/start/select/dpad_up/dpad_down/dpad_left/dpad_right
 *        每个键按下 150ms，松开后间隔 350ms 再按下一个。
 * 退出： SIGINT/SIGTERM 销毁设备；序列结束后保持 hold 秒自行退出。
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <signal.h>
#include <linux/uinput.h>
#include <sys/ioctl.h>

static int g_fd = -1;

static void cleanup(void) {
  if (g_fd >= 0) {
    ioctl(g_fd, UI_DEV_DESTROY);
    close(g_fd);
    g_fd = -1;
  }
}

static void on_sig(int s) { (void)s; cleanup(); _exit(0); }

static void emit(int fd, int type, int code, int val) {
  struct input_event ie;
  memset(&ie, 0, sizeof ie);
  ie.type = (unsigned short)type;
  ie.code = (unsigned short)code;
  ie.value = val;
  if (write(fd, &ie, sizeof ie) != sizeof ie)
    perror("write input_event");
}

/* 按键名 → (类型, code)。DPAD 走 ABS_HAT0X/Y（Xbox360 手柄的 hat），
 * SDL 内置映射会把它翻成 SDL_CONTROLLER_BUTTON_DPAD_*。 */
struct keymap { const char *name; int type; int code; int val; };

static const struct keymap KMAP[] = {
    {"y",       EV_KEY, BTN_NORTH,  1},
    {"a",       EV_KEY, BTN_SOUTH,  1},
    {"b",       EV_KEY, BTN_EAST,   1},
    {"x",       EV_KEY, BTN_WEST,   1},
    {"l1",      EV_KEY, BTN_TL,     1},
    {"r1",      EV_KEY, BTN_TR,     1},
    {"start",   EV_KEY, BTN_START,  1},
    {"select",  EV_KEY, BTN_SELECT, 1},
    {"dpad_up",    EV_ABS, ABS_HAT0Y, -1},
    {"dpad_down",  EV_ABS, ABS_HAT0Y,  1},
    {"dpad_left",  EV_ABS, ABS_HAT0X, -1},
    {"dpad_right", EV_ABS, ABS_HAT0X,  1},
    {NULL, 0, 0, 0},
};

static int find_key(const char *name, int *type, int *code, int *val) {
  for (const struct keymap *k = KMAP; k->name; k++) {
    if (!strcmp(k->name, name)) {
      *type = k->type; *code = k->code; *val = k->val;
      return 1;
    }
  }
  return 0;
}

int main(int argc, char **argv) {
  int wait_s = argc > 1 ? atoi(argv[1]) : 30;
  const char *seq = argc > 2 ? argv[2] : "y";
  int hold_s = argc > 3 ? atoi(argv[3]) : 20;

  signal(SIGINT, on_sig);
  signal(SIGTERM, on_sig);

  g_fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK);
  if (g_fd < 0) { perror("open /dev/uinput"); return 1; }

  ioctl(g_fd, UI_SET_EVBIT, EV_KEY);
  ioctl(g_fd, UI_SET_EVBIT, EV_ABS);
  ioctl(g_fd, UI_SET_EVBIT, EV_SYN);
  ioctl(g_fd, UI_SET_KEYBIT, BTN_A);
  ioctl(g_fd, UI_SET_KEYBIT, BTN_B);
  ioctl(g_fd, UI_SET_KEYBIT, BTN_X);
  ioctl(g_fd, UI_SET_KEYBIT, BTN_Y);
  ioctl(g_fd, UI_SET_KEYBIT, BTN_TL);
  ioctl(g_fd, UI_SET_KEYBIT, BTN_TR);
  ioctl(g_fd, UI_SET_KEYBIT, BTN_START);
  ioctl(g_fd, UI_SET_KEYBIT, BTN_SELECT);
  ioctl(g_fd, UI_SET_KEYBIT, BTN_MODE);
  ioctl(g_fd, UI_SET_ABSBIT, ABS_X);
  ioctl(g_fd, UI_SET_ABSBIT, ABS_Y);
  ioctl(g_fd, UI_SET_ABSBIT, ABS_Z);
  ioctl(g_fd, UI_SET_ABSBIT, ABS_RZ);
  ioctl(g_fd, UI_SET_ABSBIT, ABS_HAT0X);
  ioctl(g_fd, UI_SET_ABSBIT, ABS_HAT0Y);

  struct uinput_abs_setup abs;
  const int axes[] = {ABS_X, ABS_Y, ABS_Z, ABS_RZ, ABS_HAT0X, ABS_HAT0Y};
  for (unsigned i = 0; i < sizeof axes / sizeof axes[0]; i++) {
    memset(&abs, 0, sizeof abs);
    abs.code = (unsigned short)axes[i];
    abs.absinfo.minimum = -32768;
    abs.absinfo.maximum = 32767;
    abs.absinfo.fuzz = 16;
    abs.absinfo.flat = 128;
    ioctl(g_fd, UI_ABS_SETUP, &abs);
  }

  struct uinput_setup us;
  memset(&us, 0, sizeof us);
  us.id.bustype = BUS_USB;
  us.id.vendor = 0x045e;   /* Microsoft */
  us.id.product = 0x028e;  /* Xbox 360 pad → 命中 SDL 内置映射 */
  us.id.version = 0x0110;
  snprintf(us.name, UINPUT_MAX_NAME_SIZE, "Microsoft X-Box 360 pad");
  if (ioctl(g_fd, UI_DEV_SETUP, &us) < 0) { perror("UI_DEV_SETUP"); return 1; }
  if (ioctl(g_fd, UI_DEV_CREATE) < 0) { perror("UI_DEV_CREATE"); return 1; }
  fprintf(stderr, "[pad-inject] virtual pad created (%s)\n", us.name);
  fflush(stderr);
  sleep(2);

  fprintf(stderr, "[pad-inject] waiting %ds for game...\n", wait_s);
  fflush(stderr);
  sleep(wait_s > 0 ? wait_s : 1);

  char buf[256];
  snprintf(buf, sizeof buf, "%s", seq);
  char *save = NULL;
  for (char *tok = strtok_r(buf, ",", &save); tok;
       tok = strtok_r(NULL, ",", &save)) {
    int type, code, val;
    if (!find_key(tok, &type, &code, &val)) {
      fprintf(stderr, "[pad-inject] unknown key '%s', skipped\n", tok);
      continue;
    }
    fprintf(stderr, "[pad-inject] %s: press\n", tok);
    fflush(stderr);
    emit(g_fd, type, code, val);
    emit(g_fd, EV_SYN, SYN_REPORT, 0);
    usleep(150000);
    emit(g_fd, type, code, 0);   /* hat 归零 / 按键松开 */
    emit(g_fd, EV_SYN, SYN_REPORT, 0);
    fprintf(stderr, "[pad-inject] %s: release\n", tok);
    fflush(stderr);
    usleep(350000);
  }

  fprintf(stderr, "[pad-inject] sequence done; holding pad %ds\n", hold_s);
  fflush(stderr);
  sleep(hold_s > 0 ? hold_s : 1);
  cleanup();
  fprintf(stderr, "[pad-inject] exit\n");
  return 0;
}
