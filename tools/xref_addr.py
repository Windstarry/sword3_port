#!/usr/bin/env python3
"""定位 ELF 中对指定 vaddr 的引用点（aarch64 adrp+add / adr / literal pool）。

用途：找出"谁在读/写某个全局变量"，从而判断驱动源（键盘 or 鼠标）。
用法：
  python tools/xref_addr.py <elf> <vaddr> [--page 0x182000] [--max 40]
示例：
  python tools/xref_addr.py libs/libSWD3E.so 0x1822B0
"""
import sys
import argparse
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN


def load(so):
    data = open(so, 'rb').read()
    elf = ELFFile(open(so, 'rb'))
    # 只取"可执行节"（.text 等）：PT_LOAD 可执行段的开头含 ELF 头/.dynsym 等非代码
    # 数据，capstone 遇到无法解码的字节会直接终止迭代（表现为"0 处引用"）。
    segs = []
    for s in elf.iter_sections():
        if (s['sh_flags'] & 0x4) and s['sh_addr'] and s['sh_type'] != 'SHT_NOBITS':
            segs.append((s['sh_addr'], s['sh_size'], s['sh_offset']))
    if not segs:  # 回退：可执行 PT_LOAD 段
        for s in elf.iter_segments():
            if s['p_type'] == 'PT_LOAD' and (s['p_flags'] & 0x1):
                segs.append((s['p_vaddr'], s['p_filesz'], s['p_offset']))
    return data, elf, segs


def v2o(segs, a):
    for va, fsz, off in segs:
        if va <= a < va + fsz:
            return off + (a - va)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('elf')
    ap.add_argument('addr')
    ap.add_argument('--range', type=int, default=16,
                    help='目标变量字节范围（默认 16）')
    ap.add_argument('--max', type=int, default=40)
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args()

    target = int(a.addr, 0)
    data, elf, segs = load(a.elf)
    md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
    md.detail = False
    md.skipdata = True  # 跳过无法解码的字节，避免整段迭代提前终止

    hits = []
    # 反汇编每个可执行节，跟踪 adrp 写入的寄存器页基址
    for va, fsz, off in segs:
        base = off
        page_reg = {}
        code = data[base:base + fsz]
        for ins in md.disasm(code, va):
            mn = ins.mnemonic
            if mn == 'adrp':
                try:
                    imm = int(ins.op_str.split('#')[1], 0)
                    reg = ins.op_str.split()[0].rstrip(',')
                    page_reg[reg] = imm & ~0xFFF
                except (IndexError, ValueError):
                    pass
                continue
            if mn == 'adr':
                try:
                    imm = int(ins.op_str.split('#')[1], 0)
                    reg = ins.op_str.split()[0].rstrip(',')
                    if target <= imm < target + a.range:
                        hits.append((ins.address, mn, ins.op_str, imm))
                except (IndexError, ValueError):
                    pass
                continue
            if mn in ('add', 'sub'):
                parts = ins.op_str.split(',')
                if len(parts) >= 3 and parts[0].rstrip() in page_reg:
                    dst = parts[0].rstrip()
                    src = parts[1].strip()
                    if src in page_reg and dst == src:
                        try:
                            imm = int(parts[2].strip().lstrip('#'), 0)
                            addr = page_reg[src] + imm
                            if target <= addr < target + a.range:
                                hits.append((ins.address, mn, ins.op_str, addr))
                        except ValueError:
                            pass
                        continue
            if mn.startswith('str') or mn.startswith('ldr'):
                # [xN, #imm] 形式，配合已解析的页基址
                ops = ins.op_str
                if '[' in ops:
                    try:
                        inner = ops[ops.index('[') + 1:ops.index(']')]
                        if ',' in inner:
                            reg, offs = inner.split(',', 1)
                            reg = reg.strip()
                            if reg in page_reg:
                                imm = int(offs.strip().lstrip('#').rstrip(']'), 0)
                                addr = page_reg[reg] + imm
                                if target <= addr < target + a.range:
                                    hits.append((ins.address, mn, ops, addr))
                    except (ValueError, IndexError):
                        pass

    # 符号化
    syms = []
    for sec in (elf.get_section_by_name('.symtab'), elf.get_section_by_name('.dynsym')):
        if sec:
            for s in sec.iter_symbols():
                if s['st_value'] and s.name:
                    syms.append((s['st_value'], s['st_size'], s.name))
    syms.sort()

    def sym_at(addr):
        import bisect
        keys = [v for v, _, _ in syms]
        i = bisect.bisect_right(keys, addr) - 1
        if i < 0:
            return '?'
        v, sz, n = syms[i]
        if sz and addr < v + sz:
            return '%s+0x%X' % (n, addr - v)
        return '%s+0x%X?' % (n, addr - v)

    print('目标 vaddr 0x%X (+%d) 在 %s' % (target, a.range, a.elf))
    print('引用点 %d 处：' % len(hits))
    for addr, mn, ops, calc in hits[:a.max]:
        print('  0x%X  %-8s %-28s -> 0x%X   [%s]' % (addr, mn, ops, calc, sym_at(addr)))
    if len(hits) > a.max:
        print('  ... 另有 %d 处' % (len(hits) - a.max))


if __name__ == '__main__':
    main()
