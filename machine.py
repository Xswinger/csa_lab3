from __future__ import annotations

import json
import logging
import sys

from alu import ALU, ALUOpcode
from isa import Opcode, ProgramMode, Selectors, ri_format_instr, rri_format_instr, rrr_format_instr


class HaltError(Exception):
    def __init__(self, opcode):
        self.message = f"Met {opcode}"
        super().__init__(self.message)


class DataPath:
    data_memory_size = None

    data_memory = None

    instr_memory_size = None

    instr_memory = None

    ar = None

    pc = None

    dr = None

    ir = None

    # порты
    int_out_add = None
    chr_out_add = None
    in_add = None

    # регистры временного хранения
    tr1 = None
    tr2 = None
    tr3 = None

    ps = None

    alu = None

    input_buffer = None

    output_buffer = None

    def __init__(self, data_memory_size: int, instr_memory_size: int, input_buffer: list):
        self.alu = ALU()
        self.data_memory_size = data_memory_size
        self.data_memory = [0] * data_memory_size
        self.instr_memory_size = instr_memory_size
        self.instr_memory = [0] * instr_memory_size

        self.in_add = 0
        self.chr_out_add = 1
        self.int_out_add = 2

        self.ar = 4
        self.pc = 0
        self.dr = 0
        self.ir = 0

        self.ps = {"N": self.alu.n_flag, "Z": self.alu.z_flag, "INT_EN": False}
        self.input_buffer = input_buffer
        self.output_buffer = []

    # заполнить память командами программы и данными
    def signal_fill_memory(self, program: list, mem: list):
        for com_cell in program:
            index = com_cell["index"]
            com_cell.pop("index")
            self.instr_memory[index] = com_cell
        self.data_memory = mem

    def signal_latch_ar(self):
        self.ar = self.alu.result

    def signal_latch_ir(self):
        assert self.pc >= 0, "Address below memory limit"
        assert self.pc <= self.instr_memory_size, "Address above memory limit"
        self.ir = self.instr_memory[self.pc]

    # установить промежуточные данные по выходу АЛУ
    def signal_latch_dr_direct(self):
        self.dr = self.alu.result

    # установить промежуточные данные по ячейке в памяти
    def signal_latch_dr(self):
        assert self.ar >= 0, "Address below memory limit"
        assert self.ar <= self.data_memory_size, "Address above memory limit"
        self.dr = self.data_memory[self.ar]

    def signal_latch_pc(self):
        self.pc = self.alu.result

    # установить флаги состояния по флагам АЛУ
    def signal_latch_ps_flags(self):
        self.ps["N"] = self.alu.n_flag
        self.ps["Z"] = self.alu.z_flag

    def signal_enable_interrupts(self):
        self.ps["INT_EN"] = True

    def signal_disable_interrupts(self):
        self.ps["INT_EN"] = False

    # установка временных регистров (по результату АЛУ или из буфера ввода)
    def signal_latch_tr(self, sel: Selectors, reg_name: str):
        assert sel in {Selectors.FROM_INPUT, Selectors.FROM_ALU}, f"Unknown selector '{sel}'"
        if sel == Selectors.FROM_ALU:
            if reg_name == "tr1":
                self.tr1 = self.alu.result
            elif reg_name == "tr2":
                self.tr2 = self.alu.result
            else:
                self.tr3 = self.alu.result
        else:
            symbol = self.input_buffer.pop(0)
            symbol_code = ord(symbol)
            self.data_memory[self.in_add] = symbol_code
            if reg_name == "tr1":
                self.tr1 = self.data_memory[self.in_add]
            elif reg_name == "tr2":
                self.tr2 = self.data_memory[self.in_add]
            else:
                self.tr3 = self.data_memory[self.in_add]
            logging.debug("input: %s", repr(symbol))

    def signal_output(self):
        value = self.data_memory[self.ar]
        if self.ar == self.int_out_add:
            symbol = value
        else:
            symbol = chr(value)
        logging.debug("output_buffer: %s << %s", repr("".join(self.output_buffer)), repr(symbol))
        self.output_buffer.append(str(symbol))

    def signal_wr(self):
        self.data_memory[self.ar] = self.alu.result
        if self.ar == self.chr_out_add or self.ar == self.int_out_add:
            self.signal_output()

    def signal_execute_alu_op(self, operation, left_sel: Selectors = None, right_sel: Selectors = None):
        src_a = None
        src_b = None

        if left_sel is not None:
            assert left_sel in {
                Selectors.FROM_TR_1,
                Selectors.FROM_TR_2,
                Selectors.FROM_TR_3,
            }, f"Unknown left selector '{right_sel}'"
            if left_sel == Selectors.FROM_TR_1:
                src_a = self.tr1
            elif left_sel == Selectors.FROM_TR_2:
                src_a = self.tr2
            else:
                src_a = self.tr3

        if right_sel is not None:
            assert right_sel in {Selectors.FROM_DR, Selectors.FROM_PC}, f"Unknown right selector '{right_sel}'"
            if right_sel == Selectors.FROM_DR:
                src_b = self.dr
            else:
                src_b = self.pc

        self.alu.prepare_exec(src_a, src_b, operation)
        self.alu.exec()


class ControlUnit:
    data_path = None

    instruction_counter = None

    _tick = None

    mode = None

    def __init__(self, data_path: DataPath, program: list, mem: list):
        self.mode = ProgramMode.NORMAL
        self.data_path = data_path
        self.instruction_counter = 0
        self._tick = 0
        data_path.signal_fill_memory(program, mem)

    def inc_tick(self):
        self._tick += 1

    def cur_tick(self) -> int:
        return self._tick

    def execute(self):
        ir, ps = self.data_path.ir, self.data_path.ps
        opcode = ir["opcode"]

        if ir["is_indirect"]:
            if ir["arg2"] == "tr1":
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_TR_1)
            elif ir["arg2"] == "tr2":
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_TR_2)
            elif ir["arg2"] == "tr3":
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_TR_3)
            else:
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)

            self.data_path.signal_latch_ar()
            self.inc_tick()

            self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
            self.data_path.signal_latch_dr()
            self.inc_tick()

        if opcode in rrr_format_instr:
            self.execute_rrr(ir)
        elif opcode in rri_format_instr:
            self.execute_rri(ir, ps)
        elif opcode in ri_format_instr:
            self.execute_ri(ir, ps)
        else:
            self.execute_i(ir, ps)

    def execute_rrr(self, code: object):
        if code["opcode"] == Opcode.ADD:
            if code["arg1"] == "tr1":
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_TR_1)
            elif code["arg1"] == "tr2":
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_TR_2)
            else:
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_TR_3)
            self.data_path.signal_latch_dr_direct()
            self.inc_tick()

            if code["arg2"] == "tr1":
                self.data_path.signal_execute_alu_op(
                    ALUOpcode.ADD, left_sel=Selectors.FROM_TR_1, right_sel=Selectors.FROM_DR
                )
            elif code["arg2"] == "tr2":
                self.data_path.signal_execute_alu_op(
                    ALUOpcode.ADD, left_sel=Selectors.FROM_TR_2, right_sel=Selectors.FROM_DR
                )
            else:
                self.data_path.signal_execute_alu_op(
                    ALUOpcode.ADD, left_sel=Selectors.FROM_TR_3, right_sel=Selectors.FROM_DR
                )
            self.data_path.signal_latch_tr(Selectors.FROM_ALU, code["arg1"])
            self.inc_tick()

    def execute_rri(self, code: object, ps: dict):
        if code["opcode"] == Opcode.ADDI:
            self.data_path.signal_execute_alu_op(ALUOpcode.INC_A, left_sel=Selectors.FROM_TR_1)
            self.data_path.signal_latch_tr(Selectors.FROM_ALU, code["arg1"])
            self.inc_tick()

            self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
            self.data_path.signal_latch_ar()
            self.inc_tick()

            self.data_path.signal_latch_dr()
            if code["arg1"] == "tr1":
                self.data_path.signal_execute_alu_op(
                    ALUOpcode.ADD, left_sel=Selectors.FROM_TR_1, right_sel=Selectors.FROM_DR
                )
            elif code["arg2"] == "tr2":
                self.data_path.signal_execute_alu_op(
                    ALUOpcode.ADD, left_sel=Selectors.FROM_TR_2, right_sel=Selectors.FROM_DR
                )
            else:
                self.data_path.signal_execute_alu_op(
                    ALUOpcode.ADD, left_sel=Selectors.FROM_TR_3, right_sel=Selectors.FROM_DR
                )
            self.data_path.signal_latch_tr(Selectors.FROM_ALU)
            self.inc_tick()

        elif code["opcode"] == Opcode.CMP:
            if code["arg1"] == "tr1":
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_TR_1)
            elif code["arg1"] == "tr2":
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_TR_2)
            else:
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_TR_3)
            self.data_path.signal_latch_dr_direct()
            self.inc_tick()

            if code["arg2"] == "tr1":
                self.data_path.signal_execute_alu_op(
                    ALUOpcode.CMP, left_sel=Selectors.FROM_TR_1, right_sel=Selectors.FROM_DR
                )
            elif code["arg2"] == "tr2":
                self.data_path.signal_execute_alu_op(
                    ALUOpcode.CMP, left_sel=Selectors.FROM_TR_2, right_sel=Selectors.FROM_DR
                )
            else:
                self.data_path.signal_execute_alu_op(
                    ALUOpcode.CMP, left_sel=Selectors.FROM_TR_3, right_sel=Selectors.FROM_DR
                )
            self.inc_tick()

        elif code["opcode"] == Opcode.TEST:
            if code["arg1"] == "tr1":
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_TR_1)
            elif code["arg1"] == "tr2":
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_TR_2)
            else:
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_TR_3)
            self.data_path.signal_latch_dr_direct()
            self.inc_tick()

            if code["arg2"] == "tr1":
                self.data_path.signal_execute_alu_op(
                    ALUOpcode.TEST, left_sel=Selectors.FROM_TR_1, right_sel=Selectors.FROM_DR
                )
            elif code["arg2"] == "tr2":
                self.data_path.signal_execute_alu_op(
                    ALUOpcode.TEST, left_sel=Selectors.FROM_TR_2, right_sel=Selectors.FROM_DR
                )
            else:
                self.data_path.signal_execute_alu_op(
                    ALUOpcode.TEST, left_sel=Selectors.FROM_TR_3, right_sel=Selectors.FROM_DR
                )
            self.inc_tick()

    def execute_ri(self, code: object, ps: dict):
        if code["opcode"] == Opcode.STORE:
            if code["arg1"] == "tr1":
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_TR_1)
            elif code["arg1"] == "tr2":
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_TR_2)
            else:
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_TR_3)
            self.data_path.signal_latch_dr_direct()
            self.data_path.signal_wr()
            self.inc_tick()

        elif code["opcode"] == Opcode.LOAD:
            self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
            self.data_path.signal_latch_dr()
            self.inc_tick()

            self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
            if self.data_path.ar == 0:
                self.data_path.signal_latch_tr(Selectors.FROM_INPUT, code["arg1"])
            else:
                self.data_path.signal_latch_tr(Selectors.FROM_ALU, code["arg1"])
            self.inc_tick()

        elif code["opcode"] == Opcode.INC:
            if code["arg1"] == "tr1":
                self.data_path.signal_execute_alu_op(ALUOpcode.INC_A, left_sel=Selectors.FROM_TR_1)
            elif code["arg2"] == "tr2":
                self.data_path.signal_execute_alu_op(ALUOpcode.INC_A, left_sel=Selectors.FROM_TR_2)
            else:
                self.data_path.signal_execute_alu_op(ALUOpcode.INC_A, left_sel=Selectors.FROM_TR_3)

            self.data_path.signal_latch_tr(Selectors.FROM_ALU, code["arg1"])
            self.inc_tick()
        elif code["opcode"] == Opcode.DEC:
            if code["arg1"] == "tr1":
                self.data_path.signal_execute_alu_op(ALUOpcode.DEC_A, left_sel=Selectors.FROM_TR_1)
            elif code["arg2"] == "tr2":
                self.data_path.signal_execute_alu_op(ALUOpcode.DEC_A, left_sel=Selectors.FROM_TR_2)
            else:
                self.data_path.signal_execute_alu_op(ALUOpcode.DEC_A, left_sel=Selectors.FROM_TR_3)

            self.data_path.signal_latch_tr(Selectors.FROM_ALU, code["arg1"])
            self.inc_tick()

    def execute_i(self, code: object, ps: dict):
        if code["opcode"] == Opcode.NOP:
            self.inc_tick()

        elif code["opcode"] == Opcode.HALT:
            raise HaltError(Opcode.HALT)

        elif code["opcode"] == Opcode.EI:
            self.data_path.signal_enable_interrupts()
            self.inc_tick()

        elif code["opcode"] == Opcode.DI:
            self.data_path.signal_disable_interrupts()
            self.inc_tick()

        elif code["opcode"] == Opcode.IRET:
            self.data_path.dr = 3
            self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
            self.data_path.signal_latch_ar()
            self.inc_tick()
            self.data_path.signal_latch_dr()
            self.inc_tick()
            self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
            self.data_path.signal_latch_pc()
            self.inc_tick()
            self.mode = ProgramMode.NORMAL
            self.inc_tick()
        elif code["opcode"] == Opcode.JNE:
            if not ps["Z"]:
                self.data_path.dr = code["arg1"]
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
                self.data_path.signal_latch_pc()
                self.inc_tick()
        elif code["opcode"] == Opcode.JE:
            if ps["Z"]:
                self.data_path.dr = code["arg1"]
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
                self.data_path.signal_latch_pc()
                self.inc_tick()
        elif code["opcode"] == Opcode.JG:
            if not ps["N"]:
                self.data_path.dr = code["arg1"]
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
                self.data_path.signal_latch_pc()
                self.inc_tick()
        elif code["opcode"] == Opcode.JMP:
            self.data_path.dr = code["arg1"]
            self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
            self.data_path.signal_latch_pc()
            self.inc_tick()

    def go_to_interrupt(self):
        self.data_path.dr = 3
        #  сохранить PC
        self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
        self.data_path.signal_latch_ar()
        self.inc_tick()
        self.data_path.signal_execute_alu_op(ALUOpcode.DEC_B, right_sel=Selectors.FROM_PC)
        self.data_path.signal_latch_dr_direct()
        self.data_path.signal_wr()
        self.inc_tick()
        #  запись в pc адреса обработчика прерывания
        self.data_path.dr = 1
        self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
        self.data_path.signal_latch_pc()
        self.inc_tick()

    def check_for_interruptions(self, enabled: bool = False) -> bool:
        position = 0
        self.data_path.input_buffer = self.data_path.input_buffer[0 if position == 0 else position - 1 :]
        if not enabled or not self.data_path.input_buffer:
            return False
        return True

    def instr_fetch(self):
        self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_PC)
        self.data_path.signal_latch_ar()
        self.data_path.signal_latch_ir()
        if self.data_path.ir["opcode"] == Opcode.STORE or self.data_path.ir["opcode"] == Opcode.LOAD:
            if self.data_path.ir["arg2"] not in ["tr1", "tr2", "tr3"]:
                self.data_path.ar = self.data_path.ir["arg2"]
        self.inc_tick()

        self.data_path.signal_execute_alu_op(ALUOpcode.INC_B, right_sel=Selectors.FROM_PC)
        self.data_path.signal_latch_pc()
        self.data_path.signal_latch_dr()
        self.inc_tick()

    def decode_and_execute_instr(self) -> None:
        self.instr_fetch()
        self.execute()

        self.data_path.signal_latch_ps_flags()
        next_interrupt = self.check_for_interruptions(self.data_path.ps["INT_EN"])

        logging.debug("%s", self)

        if next_interrupt:
            logging.warning("Entering into interruption...")
            self.mode = ProgramMode.INTERRUPT
            self.go_to_interrupt()
        return

    def __repr__(self) -> str:
        return "TICK: {:4} | PC: {:3} | IR: {:5} | DR: {:3} | TR1: {:3} | TR2: {:3} | TR3: {:3} | AR: {:3} | N: {:1} | Z: {:1} | INT_EN: {:1} | data[AR]: {:3} | mode: {}".format(
            self.cur_tick(),
            self.data_path.pc,
            self.data_path.ir["opcode"],
            self.data_path.dr,
            (self.data_path.tr1 if self.data_path.tr1 or self.data_path.tr1 == 0 else "None"),
            (self.data_path.tr2 if self.data_path.tr2 or self.data_path.tr2 == 0 else "None"),
            (self.data_path.tr3 if self.data_path.tr3 or self.data_path.tr3 == 0 else "None"),
            self.data_path.ar,
            (1 if self.data_path.ps["N"] else 0),
            (1 if self.data_path.ps["Z"] else 0),
            (1 if self.data_path.ps["INT_EN"] else 0),
            self.data_path.data_memory[self.data_path.ar],
            self.mode,
        )


def simulation(code: list, memory: list, tokens: list, data_memory_size: int, instr_memory_size: int, limit: int):
    data_path = DataPath(data_memory_size, instr_memory_size, tokens)
    control_unit = ControlUnit(data_path, code, memory)
    instr_counter = 0

    try:
        while instr_counter < limit:
            control_unit.decode_and_execute_instr()
            instr_counter += 1
    except HaltError:
        pass

    if instr_counter >= limit:
        logging.warning("Instruction limit exceeded")

    logging.info("output_buffer: %s", repr("".join(data_path.output_buffer)))
    return data_path.output_buffer, instr_counter, control_unit.cur_tick()


def read_code(filename):
    with open(filename, encoding="utf-8") as file:
        return json.loads(file.read())


def main(code_file: str, memory_file: str, input_file: str | None = None):
    code = read_code(code_file)
    memory = read_code(memory_file)

    tokens = []

    if input_file is not None:
        with open(input_file, encoding="utf-8") as file:
            input_text = file.read()
            for char in input_text:
                tokens.append(char)

    output, instr_counter, ticks = simulation(
        code, memory, tokens=tokens, data_memory_size=100, instr_memory_size=100, limit=600
    )

    print("".join(output))
    print("instr_counter: ", instr_counter, "ticks:", ticks)


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.DEBUG)
    assert 3 <= len(sys.argv) <= 4, "Wrong arguments: machine.py <code_file> <memory_file> [<input_file>]"
    if len(sys.argv) == 3:
        _, code_file, memory_file = sys.argv
        input_file = None
    else:
        _, code_file, memory_file, input_file = sys.argv
    main(code_file, memory_file, input_file)
