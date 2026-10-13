# -*- coding: utf-8 -*-
"""Upload a local file to a handheld test device over SSH (no scp/sftp needed).

EmuELEC/ROCKNIX 的 dropbear 常未启用 sftp 子系统（paramiko open_sftp 后 open()
直接 ENOENT），故走 "cat > dst" 经 exec_command stdin 写入，最稳。

用法:
  python tools/ssh_put.py <local_file> <remote_abs_path> [--host IP] [--user U] [--pass P]

连接默认值: 192.168.31.216 / root / emuelec（可用 EE_HOST/EE_USER/EE_PASS 覆盖）。
远端路径为设备绝对路径（/storage/...）；写完后自动 chmod 755 并打印 md5。
"""
import os
import re
import sys

import paramiko


def fix_msys_path(p):
    """Git Bash 会把以 / 开头的 argv 按 POSIX→Windows 规则改写。

    例：/storage/roms/ports_scripts/swd3de.sh 被传成
    C:/.../PortableGit/storage/roms/ports_scripts/swd3de.sh，
    远端 sh 自然找不到。这里把明显的设备绝对路径还原回来。
    """
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
    src, dst = args[0], fix_msys_path(args[1])
    data = open(src, "rb").read()

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(
        opts["host"], port=22, username=opts["user"], password=opts["pass"],
        timeout=10, look_for_keys=False, allow_agent=False,
    )
    try:
        cmd = (
            f"cat > {dst}.tmp && chmod 755 {dst}.tmp && mv -f {dst}.tmp {dst} "
            f"&& ls -la {dst} && md5sum {dst}"
        )
        sin, out, err = c.exec_command(cmd, timeout=120)
        sin.write(data)
        sin.flush()
        sin.channel.shutdown_write()
        o = out.read().decode("utf-8", "replace")
        e = err.read().decode("utf-8", "replace")
        if o:
            print(o)
        if e.strip():
            print("[stderr]", e)
    finally:
        c.close()
    print(f"uploaded {src} -> {opts['host']}:{dst} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
