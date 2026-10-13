# -*- coding: utf-8 -*-
"""Download a file from a handheld test device over SSH (no scp/sftp needed).

EmuELEC/ROCKNIX 的 dropbear 常未启用 sftp 子系统（paramiko open_sftp 后 open()
直接 ENOENT），故走 "cat <remote>" 经 exec_command stdout 取回。

用法:
  python tools/ssh_get.py <remote_abs_path> <local_file> [--host IP] [--user U] [--pass P]

连接默认值: 192.168.31.216 / root / emuelec（可用 EE_HOST/EE_USER/EE_PASS 覆盖）。
"""
import os
import re
import sys

import paramiko


def fix_msys_path(p):
    """Git Bash 会把以 / 开头的 argv 改写成 Windows 路径，这里还原。"""
    if p.startswith("/"):
        return p
    q = p.replace("\\", "/")
    m = re.search(r"(/(?:storage|tmp|opt|usr|home|var|etc|root|roms|dev|mnt)\b.*)$", q)
    return m.group(1) if m else p


def main(argv):
    args = []
    opts = {
        "host": os.environ.get("EE_HOST", "192.168.31.216"),
        "user": os.environ.get("EE_USER", "root"),
        "pass": os.environ.get("EE_PASS", "emuelec"),
    }
    i = 1
    keymap = {"--host": "host", "--user": "user", "--pass": "pass"}
    while i < len(argv):
        a = argv[i]
        if a in keymap and i + 1 < len(argv):
            opts[keymap[a]] = argv[i + 1]
            i += 2
            continue
        args.append(a)
        i += 1
    if len(args) < 2:
        print(__doc__)
        return 2
    remote, local = fix_msys_path(args[0]), args[1]

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        opts["host"], port=22, username=opts["user"], password=opts["pass"],
        timeout=10, look_for_keys=False, allow_agent=False,
    )
    try:
        _, out, err = c.exec_command(f"cat {remote}", timeout=180)
        data = out.read()
        e = err.read().decode("utf-8", "replace")
        os.makedirs(os.path.dirname(os.path.abspath(local)) or ".", exist_ok=True)
        open(local, "wb").write(data)
        if e.strip():
            print("[stderr]", e)
    finally:
        c.close()
    print(f"downloaded {opts['host']}:{remote} -> {local} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
