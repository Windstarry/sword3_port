/*
 * uinput_y_press.c — 回归验证工具：创建 uinput 虚拟 Xbox360 手柄，延时后注入一次 Y 键。
 *
 * 用途：在无人操作掌机时，验证 swd3de loader 在标题画面按 Y（打开作弊面板）不再崩溃。
 * 原理：设备 SDL2 通过 evdev 枚举手柄；uinput 设备用 Xbox360 的 VID/PID(0x045e/0x028e)
 *       命中 SDL 内置手柄映射 → BTN_NORTH 即 SDL_CONTROLLER_BUTTON_Y。
 *
 * 用法： ./uinput_y_press [按键前等待秒数=30] [按下后保持秒数=60]
 * 退出： SIGINT/SIGTERM 关闭设备；自身也会在保持时间后自行退出。
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

int main(int argc, char **argv) {
  int wait_s = argc > 1 ? atoi(argv[1]) : 30;
  int hold_s = argc > 2 ? atoi(argv[2]) : 60;

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
  fprintf(stderr, "[y-inject] virtual pad created (%s)\n", us.name);
  fflush(stderr);
  sleep(2);

  fprintf(stderr, "[y-inject] waiting %ds for game to reach title...\n", wait_s);
  fflush(stderr);
  sleep(wait_s > 0 ? wait_s : 1);

  fprintf(stderr, "[y-inject] sending Y (BTN_NORTH) press\n");
  fflush(stderr);
  emit(g_fd, EV_KEY, BTN_Y, 1);
  emit(g_fd, EV_SYN, SYN_REPORT, 0);
  usleep(150000);
  emit(g_fd, EV_KEY, BTN_Y, 0);
  emit(g_fd, EV_SYN, SYN_REPORT, 0);
  fprintf(stderr, "[y-inject] Y sent; holding pad %ds\n", hold_s);
  fflush(stderr);

  sleep(hold_s > 0 ? hold_s : 1);
  cleanup();
  fprintf(stderr, "[y-inject] done\n");
  return 0;
}
