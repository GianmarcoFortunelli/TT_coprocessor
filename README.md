![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg) ![](../../workflows/fpga/badge.svg)

# Tiny Tapeout 32-bit ALU with Integrated Multiplier

This repository contains a Tiny Tapeout user module implementing a **32-bit Arithmetic Logic Unit (ALU)** with an integrated multiplication operation.

The design was adapted for the Tiny Tapeout flow starting from previously developed hardware blocks: the ALU structure comes from a larger 32-bit processor datapath, while the multiplication unit was integrated from a dedicated arithmetic design and then simplified to fit the Tiny Tapeout area and interface constraints.

- [Project documentation](docs/info.md)

## Project overview

The module supports a compact but useful set of 32-bit ALU operations:

- **Arithmetic:** `ADD`, `ADDU`, `SUB`, `SUBU`
- **Logic:** `AND`, `OR`, `XOR`
- **Shifts:** `SLL`, `SRL`, `SRA`
- **Comparisons:** `SEQ`, `SNE`, `SLT`, `SGT`, `SLE`, `SGE`, `SLTU`, `SGTU`, `SLEU`, `SGEU`
- **Multiplication:** `MUL`

The ALU is wrapped in a Tiny Tapeout-friendly interface using a simple nibble-based protocol, so 32-bit operands and results can be exchanged over the limited available I/O pins.

### Multiplication behavior

To keep the design compatible with Tiny Tapeout constraints, the `MUL` operation uses only the **lower 8 bits** of each operand internally.  
The multiplier produces a **16-bit product**, which is then **zero-extended to 32 bits** on the ALU output.

## Tiny Tapeout interface

The project uses a custom serial protocol based on **4-bit transfers**.

### Inputs

- `ui_in[0]` → `ext_progr`: starts and keeps a transaction active
- `ui_in[7:4]` → input nibble
- `ui_in[3:1]` → unused

### Outputs

- `uo_out[7:4]` → output nibble
- `uo_out[2]` → `busy`
- `uo_out[1]` → `frame_error`
- `uo_out[0]` → `result_valid`
- `uo_out[3]` → unused

### Bidirectional IO

- `uio_in[7:0]` unused
- `uio_out[7:0]` unused
- `uio_oe[7:0]` disabled

## Transaction protocol

Each transaction is divided into two phases:

### 1. Read previous result
At the beginning of a transaction, the module outputs the result computed during the **previous** transaction.

- result is sent on `uo_out[7:4]`
- transmitted as **8 nibbles**
- order is **most significant nibble first**

### 2. Load new operation
The user then provides:

- operand A: 8 nibbles
- operand B: 8 nibbles
- function code: 2 nibbles

After internal processing, the computed result is stored and will be returned at the beginning of the **next** transaction.

This means the interface is intentionally pipelined at transaction level: a command does not immediately return its own result.

## Supported function codes

| Operation | FUNC_BITS |
|-----------|-----------|
| SLL       | `000100` |
| SRL       | `000110` |
| SRA       | `000111` |
| ADD       | `100000` |
| ADDU      | `100001` |
| SUB       | `100010` |
| SUBU      | `100011` |
| AND       | `100100` |
| OR        | `100101` |
| XOR       | `100110` |
| SEQ       | `100111` |
| SNE       | `101000` |
| SLT       | `101001` |
| SGT       | `101010` |
| SLE       | `101011` |
| SGE       | `101100` |
| SLTU      | `111010` |
| SGTU      | `111011` |
| SLEU      | `111100` |
| SGEU      | `111101` |
| MUL       | `111110` |

## How to use the design

To execute one operation:

1. Assert `ext_progr`
2. Read 8 output nibbles corresponding to the previous result
3. Send operand A over 8 cycles
4. Send operand B over 8 cycles
5. Send the function code over 2 cycles
6. Keep `ext_progr` high for 2 additional cycles
7. Deassert `ext_progr`

### Status bits

- `busy = 1`: transaction in progress
- `frame_error = 1`: protocol error detected
- `result_valid = 1`: at least one valid result has already been produced

## Verification

The design is intended to be driven synchronously with the main clock.  
Simulation and testbench support are included in the repository and can be adapted to reconstruct 32-bit values nibble by nibble and verify the returned results against the selected ALU function.

## About Tiny Tapeout

Tiny Tapeout is an educational initiative that makes it easier and cheaper to manufacture small digital designs on real silicon.

To learn more, visit https://tinytapeout.com.