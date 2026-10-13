# -*- coding: utf-8 -*-
"""Disassemble around a crash vaddr in an ELF shared object (aarch64, capstone).

用法:
  python disasm_crash.py <so_path> <vaddr_hex> [--before N] [--after N]

示例:
  # 崩溃 PC = 基址 + 0x12D3C0
  python disasm_crash.py libs/libSWD3E.so 0x12D3C0 --before 4 --after 40

说明:
  vaddr 为 so 内 vaddr（设备日志 PC 减去加载基址）。脚本按 PT_LOAD 段换算
  vaddr→文件偏移，再从崩溃点前 --before 条指令起反汇编，并标记 CRASH PC。
"""
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile


def load_segments(so_path):
    segs = []
    with open(so_path, "rb") as f:
        elf = ELFFile(f)
        for seg in elf.iter_segments():
            if seg["p_type"] == "PT_LOAD":
                segs.append((seg["p_vaddr"], seg["p_filesz"], seg["p_offset"]))
    return segs


def v2o(segs, vaddr):
    for va, size, off in segs:
        if va <= vaddr < va + size:
            return off + (vaddr - va)
    return None


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    so_path = argv[1]
    vaddr = int(argv[2], 0)
    before, after = 4, 40
    args = argv[3:]
    for i, a in enumerate(args):
        if a == "--before" and i + 1 < len(args):
            before = int(args[i + 1])
        elif a == "--after" and i + 1 < len(args):
            after = int(args[i + 1])

    data = open(so_path, "rb").read()
    segs = load_segments(so_path)
    start = vaddr - before * 4
    fo = v2o(segs, start)
    if fo is None:
        print(f"vaddr 0x{vaddr:X} 不在任何 PT_LOAD 段内")
        return 1

    md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    code = data[fo : fo + (before + after) * 4]
    print(f"--- {so_path} +0x{start:X} .. +0x{vaddr + after * 4:X}（崩溃 PC=+0x{vaddr:X}）---")
    for ins in md.disasm(code, start):
        mark = "  <<< CRASH PC" if ins.address == vaddr else ""
        print(f"  +0x{ins.address:06X}: {ins.mnemonic:8s} {ins.op_str}{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
