import json
from enum import Enum


class ProgramMode(str, Enum):
    NORMAL = "normal"
    INTERRUPT = "interrupt"

    def __str__(self) -> str:
        return str(self.value)


class Opcode(str, Enum):
    NOP = "nop"
    HALT = "halt"

    EI = "ei"
    DI = "di"
    IRET = "iret"

    LOAD = "load"
    STORE = "store"

    ADD = "add"
    ADDI = "addi"

    CMP = "cmp"
    TEST = "test"

    INC = "inc"
    DEC = "dec"

    JNE = "jne"
    JE = "je"
    JG = "jg"
    JMP = "jmp"

    def __str__(self):
        return str(self.value)


class Selectors(str, Enum):
    FROM_INPUT = "from_input"
    FROM_ALU = "from_alu"
    FROM_DR = "from_dr"
    FROM_PC = "from_pc"
    FROM_TR_1 = "from_tr_1"
    FROM_TR_2 = "from_tr_2"
    FROM_TR_3 = "from_tr_3"
    FROM_PS = "from_ps"

    def __str__(self) -> str:
        return str(self.value)


rrr_format_instr = [Opcode.ADD]
rri_format_instr = [Opcode.ADDI, Opcode.CMP, Opcode.TEST]
ri_format_instr = [Opcode.STORE, Opcode.LOAD, Opcode.INC, Opcode.DEC]
i_format_instr = [Opcode.NOP, Opcode.HALT, Opcode.IRET, Opcode.JNE, Opcode.JE, Opcode.JG, Opcode.JMP]


def write_code(filename: str, code: list):
    with open(filename, "w", encoding="utf-8") as file:
        buf = []
        for instr in code:
            buf.append(json.dumps(instr))
        file.write("[" + ",\n ".join(buf) + "]")


def write_memory(filename: str, memory: list):
    with open(filename, "w", encoding="utf-8") as file:
        buf = []
        for ceil in memory:
            if isinstance(ceil, list):
                buf.append(str(ceil[0]))
            else:
                buf.append(str(ceil))
        file.write("[" + ",\n ".join(buf) + "]")
