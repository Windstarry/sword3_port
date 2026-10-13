# -*- coding: utf-8 -*-
"""SSH helper for handheld test devices (EmuELEC / ROCKNIX) via paramiko.

本机若没有 sshpass（Windows 常见），用本脚本走 paramiko 通道执行远程命令。

用法:
  python ee_ssh.py "cmd1" ["cmd2" ...]

连接参数（按优先级）:
  命令行:  --host <ip>  --user <u>  --pass <p>  --port <n>
  环境变量: EE_HOST / EE_USER / EE_PASS / EE_PORT
  默认值:  192.168.31.216 / root / emuelec / 22

示例:
  python ee_ssh.py --host 192.168.31.216 "uname -a" "ls /storage/roms/ports"

注意: 请勿把真实密码硬编码进本文件后提交；用 --pass 或环境变量 EE_PASS 传入。
"""
import os
import sys

import paramiko

DEFAULT_HOST = os.environ.get("EE_HOST", "192.168.31.216")
DEFAULT_USER = os.environ.get("EE_USER", "root")
DEFAULT_PASS = os.environ.get("EE_PASS", "emuelec")
DEFAULT_PORT = int(os.environ.get("EE_PORT", "22"))


def parse_args(argv):
    opts = {
        "host": DEFAULT_HOST,
        "user": DEFAULT_USER,
        "pass": DEFAULT_PASS,
        "port": DEFAULT_PORT,
    }
    cmds = []
    i = 1
    keymap = {"--host": "host", "--user": "user", "--pass": "pass", "--port": "port"}
    while i < len(argv):
        a = argv[i]
        if a in keymap and i + 1 < len(argv):
            opts[keymap[a]] = int(argv[i + 1]) if a == "--port" else argv[i + 1]
            i += 2
            continue
        cmds.append(a)
        i += 1
    return opts, cmds


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    opts, cmds = parse_args(argv)
    if not cmds:
        print(__doc__)
        return 2

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        opts["host"],
        port=opts["port"],
        username=opts["user"],
        password=opts["pass"],
        timeout=10,
        look_for_keys=False,
        allow_agent=False,
    )
    try:
        for cmd in cmds:
            print(f"===== $ {cmd}")
            _, stdout, stderr = client.exec_command(cmd, timeout=120)
            out = stdout.read().decode("utf-8", "replace")
            err = stderr.read().decode("utf-8", "replace")
            if out:
                print(out)
            if err.strip():
                print("[stderr]", err)
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
