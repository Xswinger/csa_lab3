from enum import Enum
from typing import ClassVar


class ALUOpcode(str, Enum):
    ADD = "add"
    CMP = "cmp"
    TEST = "test"
    INC_A = "inc_a"
    INC_B = "inc_b"
    DEC_A = "dec_a"
    DEC_B = "dec_b"
    SKIP_A = "skip_a"
    SKIP_B = "skip_b"

    def __str__(self) -> str:
        return str(self.value)


class ALU:
    operations: ClassVar = [
        ALUOpcode.ADD,
        ALUOpcode.CMP,
        ALUOpcode.TEST,
        ALUOpcode.INC_A,
        ALUOpcode.INC_B,
        ALUOpcode.DEC_A,
        ALUOpcode.DEC_B,
        ALUOpcode.SKIP_A,
        ALUOpcode.SKIP_B,
    ]

    src_left = None
    src_right = None

    result = None
    operation = None

    n_flag: ClassVar[bool] = None
    z_flag: ClassVar[bool] = None

    def __init__(self):
        self.src_left = None
        self.src_right = None

        self.result = 0
        self.operation = None

    def calc(self):
        tmp_result = None
        if self.operation == ALUOpcode.ADD:
            self.result = self.src_a + self.src_b
        elif self.operation == ALUOpcode.CMP:
            tmp_result = self.src_a - self.src_b
        elif self.operation == ALUOpcode.TEST:
            tmp_result = self.src_a & self.src_b
        elif self.operation == ALUOpcode.INC_A:
            self.result = self.src_a + 1
        elif self.operation == ALUOpcode.INC_B:
            self.result = self.src_b + 1
        elif self.operation == ALUOpcode.DEC_A:
            self.result = self.src_a - 1
        elif self.operation == ALUOpcode.DEC_B:
            self.result = self.src_b - 1
        elif self.operation == ALUOpcode.SKIP_A:
            self.result = self.src_a
        elif self.operation == ALUOpcode.SKIP_B:
            self.result = self.src_b
        else:
            raise f"Unknown ALU operation: {self.operation}"
        self.set_flags(tmp_result)

    def set_flags(self, tmp_result=None):
        if tmp_result is None:
            self.n_flag = self.result < 0
            self.z_flag = self.result == 0
        else:
            self.n_flag = tmp_result < 0
            self.z_flag = tmp_result == 0

    def set_details(self, src_a, src_b, operation: ALUOpcode):
        assert operation in self.operations, f"Unknown ALU operation: {operation}"
        self.src_a = src_a
        self.src_b = src_b
        self.operation = operation
