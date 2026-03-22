# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, Timer, ClockCycles


# ------------------------------------------------------------
# Function codes from MyTypes.encode(fc)
# ------------------------------------------------------------
FC_SLL_0 = 0b000100
FC_SRL_0 = 0b000110
FC_SRA_0 = 0b000111
FC_ADD   = 0b100000
FC_ADDU  = 0b100001
FC_SUB   = 0b100010
FC_SUBU  = 0b100011
FC_AND   = 0b100100
FC_OR    = 0b100101
FC_XOR   = 0b100110
FC_SEQ   = 0b100111
FC_SNE   = 0b101000
FC_SLT   = 0b101001
FC_SGT   = 0b101010
FC_SLE   = 0b101011
FC_SGE   = 0b101100
FC_SLTU  = 0b111010
FC_SGTU  = 0b111011
FC_SLEU  = 0b111100
FC_SGEU  = 0b111101
FC_MUL   = 0b111110


ALL_FC = [
    FC_SLL_0, FC_SRL_0, FC_SRA_0,
    FC_ADD, FC_ADDU, FC_SUB, FC_SUBU,
    FC_AND, FC_OR, FC_XOR,
    FC_SEQ, FC_SNE, FC_SLT, FC_SGT, FC_SLE, FC_SGE,
    FC_SLTU, FC_SGTU, FC_SLEU, FC_SGEU,
    FC_MUL
]


def fc_name(fc: int) -> str:
    names = {
        FC_SLL_0: "SLL_0",
        FC_SRL_0: "SRL_0",
        FC_SRA_0: "SRA_0",
        FC_ADD:   "ADD",
        FC_ADDU:  "ADDU",
        FC_SUB:   "SUB",
        FC_SUBU:  "SUBU",
        FC_AND:   "AND",
        FC_OR:    "OR",
        FC_XOR:   "XOR",
        FC_SEQ:   "SEQ",
        FC_SNE:   "SNE",
        FC_SLT:   "SLT",
        FC_SGT:   "SGT",
        FC_SLE:   "SLE",
        FC_SGE:   "SGE",
        FC_SLTU:  "SLTU",
        FC_SGTU:  "SGTU",
        FC_SLEU:  "SLEU",
        FC_SGEU:  "SGEU",
        FC_MUL:   "MUL",
    }
    return names.get(fc, f"UNKNOWN({fc:06b})")


def u32(x: int) -> int:
    return x & 0xFFFF_FFFF


def s32(x: int) -> int:
    x &= 0xFFFF_FFFF
    return x if x < 0x8000_0000 else x - 0x1_0000_0000


def golden_model(a: int, b: int, fc: int) -> int:
    a_u = u32(a)
    b_u = u32(b)
    a_s = s32(a)
    b_s = s32(b)
    shamt = b_u & 0x1F

    if fc == FC_ADD:
        return u32(a_u + b_u)
    if fc == FC_ADDU:
        return u32(a_u + b_u)
    if fc == FC_SUB:
        return u32(a_u - b_u)
    if fc == FC_SUBU:
        return u32(a_u - b_u)

    if fc == FC_AND:
        return a_u & b_u
    if fc == FC_OR:
        return a_u | b_u
    if fc == FC_XOR:
        return a_u ^ b_u

    if fc == FC_SLL_0:
        return u32(a_u << shamt)
    if fc == FC_SRL_0:
        return u32(a_u >> shamt)
    if fc == FC_SRA_0:
        return u32(a_s >> shamt)

    if fc == FC_SEQ:
        return 1 if a_u == b_u else 0
    if fc == FC_SNE:
        return 1 if a_u != b_u else 0
    if fc == FC_SLT:
        return 1 if a_s < b_s else 0
    if fc == FC_SGT:
        return 1 if a_s > b_s else 0
    if fc == FC_SLE:
        return 1 if a_s <= b_s else 0
    if fc == FC_SGE:
        return 1 if a_s >= b_s else 0

    if fc == FC_SLTU:
        return 1 if a_u < b_u else 0
    if fc == FC_SGTU:
        return 1 if a_u > b_u else 0
    if fc == FC_SLEU:
        return 1 if a_u <= b_u else 0
    if fc == FC_SGEU:
        return 1 if a_u >= b_u else 0

    if fc == FC_MUL:
        return ((a_u & 0xFF) * (b_u & 0xFF)) & 0xFFFF

    return 0


def make_ui(ext: int, nibble: int) -> int:
    return ((nibble & 0xF) << 4) | (ext & 0x1)


def get_out_nibble(dut) -> int:
    return (int(dut.uo_out.value) >> 4) & 0xF


def get_result_valid(dut) -> int:
    return int(dut.uo_out.value) & 0x1


def get_frame_error(dut) -> int:
    return (int(dut.uo_out.value) >> 1) & 0x1


def get_busy(dut) -> int:
    return (int(dut.uo_out.value) >> 2) & 0x1


async def drive_cycle(dut, ext: int, nibble: int) -> int:
    await FallingEdge(dut.clk)
    dut.ui_in.value = make_ui(ext, nibble)
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    return get_out_nibble(dut)


async def send_word32_msn_first(dut, value: int):
    for i in range(7, -1, -1):
        nib = (value >> (i * 4)) & 0xF
        await drive_cycle(dut, 1, nib)


async def send_func6_as_2nibbles(dut, fc: int):
    await drive_cycle(dut, 1, (fc >> 4) & 0x3)  # {2'b00, fc[5:4]}
    await drive_cycle(dut, 1, fc & 0xF)


async def transaction(dut, a: int, b: int, fc: int) -> int:
    dumped_prev = 0

    # 1 ciclo per uscire da IDLE ed entrare nel dump
    await drive_cycle(dut, 1, 0)

    # 8 nibble del risultato precedente, MS nibble first
    for _ in range(8):
        nib = await drive_cycle(dut, 1, 0)
        dumped_prev = ((dumped_prev << 4) | nib) & 0xFFFF_FFFF

    # 8 nibble di A
    await send_word32_msn_first(dut, a)

    # 8 nibble di B
    await send_word32_msn_first(dut, b)

    # 2 nibble di FUNC
    await send_func6_as_2nibbles(dut, fc)

    # 2 cicli interni APPLY + CAPTURE
    await drive_cycle(dut, 1, 0)
    await drive_cycle(dut, 1, 0)

    # chiusura sessione
    await drive_cycle(dut, 0, 0)

    assert get_frame_error(dut) == 0, "frame_error alzato"
    return dumped_prev


async def run_case(dut, a: int, b: int, fc: int, expected_prev: int) -> int:
    expected_new = golden_model(a, b, fc)
    dumped_prev = await transaction(dut, a, b, fc)

    assert dumped_prev == expected_prev, (
        f"\n[ERROR] {fc_name(fc)}"
        f"\n  A             = 0x{a:08X}"
        f"\n  B             = 0x{b:08X}"
        f"\n  dumped_prev   = 0x{dumped_prev:08X}"
        f"\n  expected_prev = 0x{expected_prev:08X}"
    )

    return expected_new


async def flush_last_result(dut, expected_prev: int):
    dumped_prev = await transaction(dut, 0, 0, FC_ADD)

    assert dumped_prev == expected_prev, (
        f"\n[ERROR] FLUSH"
        f"\n  dumped_prev   = 0x{dumped_prev:08X}"
        f"\n  expected_prev = 0x{expected_prev:08X}"
    )


@cocotb.test()
async def test_project(dut):
    dut._log.info("Start")

    clock = Clock(dut.clk, 10, unit="us")
    cocotb.start_soon(clock.start())

    # Reset
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0

    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 2)

    expected_prev = 0
    tests_run = 0

    # Directed tests
    expected_prev = await run_case(dut, 0x0000_0001, 0x0000_0002, FC_ADD,   expected_prev); tests_run += 1
    expected_prev = await run_case(dut, 0x0000_0007, 0x0000_0003, FC_SUB,   expected_prev); tests_run += 1
    expected_prev = await run_case(dut, 0xF0F0_0F0F, 0x0FF0_F00F, FC_AND,   expected_prev); tests_run += 1
    expected_prev = await run_case(dut, 0xF0F0_0F0F, 0x0FF0_F00F, FC_OR,    expected_prev); tests_run += 1
    expected_prev = await run_case(dut, 0xAAAA_5555, 0x1234_5678, FC_XOR,   expected_prev); tests_run += 1

    expected_prev = await run_case(dut, 0x0000_0001, 0x0000_0004, FC_SLL_0, expected_prev); tests_run += 1
    expected_prev = await run_case(dut, 0x8000_0000, 0x0000_0004, FC_SRL_0, expected_prev); tests_run += 1
    expected_prev = await run_case(dut, 0x8000_0000, 0x0000_0004, FC_SRA_0, expected_prev); tests_run += 1

    expected_prev = await run_case(dut, 0x0000_0011, 0x0000_0011, FC_SEQ,   expected_prev); tests_run += 1
    expected_prev = await run_case(dut, 0x0000_0011, 0x0000_0022, FC_SNE,   expected_prev); tests_run += 1

    expected_prev = await run_case(dut, 0xFFFF_FFFF, 0x0000_0001, FC_SLT,   expected_prev); tests_run += 1
    expected_prev = await run_case(dut, 0x7FFF_FFFF, 0x8000_0000, FC_SGT,   expected_prev); tests_run += 1
    expected_prev = await run_case(dut, 0x8000_0000, 0x8000_0000, FC_SLE,   expected_prev); tests_run += 1
    expected_prev = await run_case(dut, 0x8000_0000, 0x8000_0000, FC_SGE,   expected_prev); tests_run += 1

    expected_prev = await run_case(dut, 0x0000_0001, 0xFFFF_FFFF, FC_SLTU,  expected_prev); tests_run += 1
    expected_prev = await run_case(dut, 0xFFFF_FFFF, 0x0000_0001, FC_SGTU,  expected_prev); tests_run += 1
    expected_prev = await run_case(dut, 0x0000_0001, 0x0000_0001, FC_SLEU,  expected_prev); tests_run += 1
    expected_prev = await run_case(dut, 0xFFFF_FFFF, 0xFFFF_FFFF, FC_SGEU,  expected_prev); tests_run += 1

    expected_prev = await run_case(dut, 0x0000_0013, 0x0000_0007, FC_MUL,   expected_prev); tests_run += 1
    expected_prev = await run_case(dut, 0x1234_ABCD, 0x0000_00EF, FC_MUL,   expected_prev); tests_run += 1

    expected_prev = await run_case(dut, 0xFFFF_FFFF, 0x0000_0001, FC_ADD,   expected_prev); tests_run += 1
    expected_prev = await run_case(dut, 0x0000_0000, 0x0000_0001, FC_SUB,   expected_prev); tests_run += 1

    # Random tests
    for _ in range(200):
        a = random.getrandbits(32)
        b = random.getrandbits(32)
        fc = random.choice(ALL_FC)
        expected_prev = await run_case(dut, a, b, fc, expected_prev)
        tests_run += 1

    # Flush finale per leggere l'ultimo risultato calcolato
    await flush_last_result(dut, expected_prev)
    tests_run += 1

    dut._log.info(f"PASS. Tests run = {tests_run}")