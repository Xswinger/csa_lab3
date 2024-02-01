import json
from enum import Enum

class Opcode(str, Enum):
    EQUAL = "equal"
    SUM = "sum"
    DIF = "dif"

    JMP = "jmp"


    def __str__(self):
        return str(self.value)

def write_code(filename, code):
    with open(filename, "w", encoding="utf-8") as file:
        buf = []
        for instr in code:
            buf.append(json.dumps(instr))
        file.write("[" + ",\n ".join(buf) + "]")


def read_code(filename):
    with open(filename, encoding="utf-8") as file:
        return json.loads(file.read())  #  code