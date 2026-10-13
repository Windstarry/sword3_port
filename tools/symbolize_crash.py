# -*- coding: utf-8 -*-
"""Symbolize crash offsets in a shared object (nearest preceding dynamic symbol).

用法:
  python symbolize_crash.py <so_path> <offset_hex> [<offset_hex> ...]

示例:
  python symbolize_crash.py libs/libSWD3E.so 0x12D3C0 0x21348

说明:
  偏移量按 so 的 vaddr（即设备日志里的 PC - 加载基址）计算，就近匹配 .dynsym 中
  值不超过该偏移的符号（st_value<=off 的最大者），并标注是否落在符号 size 内。
"""
import sys

from elftools.elf.elffile import ELFFile


def load_syms(so_path):
    syms = []
    with open(so_path, "rb") as f:
        elf = ELFFile(f)
        dynsym = elf.get_section_by_name(".dynsym")
        if dynsym is None:
            raise SystemExit(f"{so_path}: 无 .dynsym 节")
        for s in dynsym.iter_symbols():
            val = s["st_value"]
            if val and s.name:
                syms.append((val, s["st_size"], s.name))
    syms.sort()
    return syms


def nearest(syms, off):
    lo, hi, idx = 0, len(syms), -1
    while lo < hi:
        mid = (lo + hi) // 2
        if syms[mid][0] <= off:
            idx = mid
            lo = mid + 1
        else:
            hi = mid
    if idx < 0:
        return None
    val, size, name = syms[idx]
    inside = " (inside)" if size and off < val + size else ""
    return f"{name}+0x{off - val:x}{inside}  [{name} @ 0x{val:x} size={size}]"


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    so_path, offsets = argv[1], [int(x, 0) for x in argv[2:]]
    syms = load_syms(so_path)
    print(f"# {so_path}: {len(syms)} 个具名动态符号")
    for off in offsets:
        n = nearest(syms, off)
        print(f"+0x{off:X}: {n if n else 'NO PRECEDING SYMBOL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
