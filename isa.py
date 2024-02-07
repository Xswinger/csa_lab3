import json
from enum import Enum

class Opcode(str, Enum):
    ADD = "add"
    SUB = "sub"
    INC = "inc"
    DEC = "dec"
    HALT = "halt"
    EI = "ei"
    DI = "di"
    CMP = "cmp"

    IRET = "iret"
    
    JMP = "jmp"


    def __str__(self):
        return str(self.value)
    
branch_instr = [Opcode.JMP]
proc_instr = [Opcode.IRET]
arithm_instr = [Opcode.ADD, Opcode.SUB, Opcode.INC, Opcode.DEC, Opcode.HALT, Opcode.EI, Opcode.DI, Opcode.CMP]

def write_code(filename, code):
    with open(filename, "w", encoding="utf-8") as file:
        buf = []
        for instr in code:
            buf.append(json.dumps(instr))
        file.write("[" + ",\n ".join(buf) + "]")


def read_code(filename):
    with open(filename, encoding="utf-8") as file:
        return json.loads(file.read())