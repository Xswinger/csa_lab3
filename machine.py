import sys
import logging
import json

from typing import Optional
from isa import Opcode, Selectors, rrr_format_instr, rri_format_instr, ri_format_instr, ProgramMode
from alu import ALU, ALUOpcode

class HaltError(Exception):
    def __init__(self, opcode):
        self.message = f"Met {opcode}"
        super().__init__(self.message)

class DataPath:

    data_memory_size = None

    data_memory = None
    # память данных

    instr_memory_size = None
    # размер памяти инструкций

    instr_memory = None
    # память инструкций

    ar = None
    # регистр адреса в памяти

    pc = None
    # регистр адреса следующей программы

    dr = None
    # регистр данных (хранение промеж. данных)

    ir = None

    out_add = None
    in_add = None

    sr1 = None
    sr2 = None
    sr3 = None
    # saved регистры

    ps = None
    # регистр статуса программы

    alu = None

    input_buffer = None

    output_buffer = None

    def __init__(self, data_memory_size: int, instr_memory_size: int, input_buffer: list):
        self.alu = ALU()
        self.data_memory_size = data_memory_size
        self.data_memory = [0] * data_memory_size
        self.instr_memory_size = instr_memory_size
        self.instr_memory = [0] * instr_memory_size

        self.in_add = 98
        self.out_add = 99

        self.ar = 0
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

    # установить регистр адреса памяти данных
    def signal_latch_ar(self):
        self.ar = self.alu.result

    # установить данные для записи в память данных
    def signal_latch_dr_direct(self):
        self.dr = self.alu.result

    # установить текущую инструкцию по регистру адреса в памяти
    def signal_latch_ir(self):
        assert self.pc >= 0, "Address below memory limit"
        assert self.pc <= self.instr_memory_size, "Address above memory limit"
        self.ir = self.instr_memory[self.pc]

    # установить промежуточные данные по регистру адреса в памяти
    def signal_latch_dr(self):
        assert self.ar >= 0, "Address below memory limit"
        assert self.ar <= self.data_memory_size, "Address above memory limit"
        self.dr = self.data_memory[self.ar]

    # установить следующую команду
    def signal_latch_pc(self):
        self.pc = self.alu.result % self.instr_memory_size

    # установить флаги состояния по флагам алу
    def signal_latch_ps_flags(self):
        self.ps["N"] = self.alu.n_flag
        self.ps["Z"] = self.alu.z_flag

    # установить флаги состояния алу по результату 
    def signal_latch_ps(self):
        self.alu.n_flag = True if int(self.alu.result / 100) == 1 else False
        self.alu.z_flag = True if int((self.alu.result / 10) % 10) == 1 else False
        self.ps["INT_EN"] = True if self.alu.result % 10 == 1 else False

    def signal_enable_interrupts(self):
        self.ps["INT_EN"] = True

    def signal_disable_interrupts(self):
        self.ps["INT_EN"] = False

    def signal_latch_sr(self, sel: Selectors, reg_name: str):
        assert sel in {Selectors.FROM_INPUT, Selectors.FROM_ALU}, f"Unknown selector '{sel}'"
        if sel == Selectors.FROM_ALU:
            if reg_name == 'sr1':
                self.sr1 = self.alu.result
            elif reg_name == 'sr2':
                self.sr2 = self.alu.result
            else:
                self.sr3 = self.alu.result
        else:
            symbol = self.input_buffer.pop(0)
            symbol_code = ord(symbol)
            if reg_name == 'sr1':
                self.sr1 = symbol_code
            elif reg_name == 'sr2':
                self.sr2 = symbol_code
            else:
                self.sr3 = symbol_code
            logging.debug("input: %s", repr(symbol))
    
    def signal_output(self):
        symbol = chr(self.data_memory[self.out_add])
        logging.debug("output_buffer: %s << %s", repr("".join(self.output_buffer)), repr(symbol))
        self.output_buffer.append(symbol)

    def signal_wr(self):
        self.data_memory[self.ar] = self.alu.result
        if self.ar == self.out_add:
            self.signal_output()

    def signal_execute_alu_op(self, operation, left_sel: Selectors = None, right_sel: Selectors = None):
        src_a = None
        src_b = None

        if left_sel is not None:
            assert left_sel in {Selectors.FROM_SR_1, Selectors.FROM_SR_2, Selectors.FROM_SR_3, Selectors.FROM_PS}, f"Unknown left selector '{right_sel}'"
            if left_sel == Selectors.FROM_SR_1:
                src_a = self.sr1
            elif left_sel == Selectors.FROM_SR_2:
                src_a = self.sr2
            elif left_sel == Selectors.FROM_SR_3:
                src_a = self.sr3
            else:
                n = 1 if self.ps["N"] else 0
                z = 1 if self.ps["Z"] else 0
                int_en = 1 if self.ps["INT_EN"] else 0
                src_a = n * 100 + z * 10 + int_en

        if right_sel is not None:
            assert right_sel in {
                Selectors.FROM_DR,
                Selectors.FROM_PC
            }, f"Unknown right selector '{right_sel}'"
            if right_sel == Selectors.FROM_DR:
                src_b = self.dr
            else:
                src_b = self.pc

        self.alu.set_details(src_a, src_b, operation)
        self.alu.calc()



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

    # выполнить команду
    def execute(self):
        ir, ps = self.data_path.ir, self.data_path.ps
        opcode = ir["opcode"]

        if ir["is_indirect"]:
            if ir["arg2"] == "sr1":
                    self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_SR_1)
            elif ir["arg2"] == "sr2":
                    self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_SR_2)
            elif ir["arg2"] == "sr3":
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_SR_3)
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
        if code['opcode'] == Opcode.ADD:
            self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
            self.data_path.signal_latch_ar()
            self.inc_tick()
            
            self.data_path.signal_latch_dr()
            if code['arg1'] == 'sr1':
                self.data_path.signal_execute_alu_op(ALUOpcode.ADD, left_sel=Selectors.FROM_SR_1, right_sel=Selectors.FROM_DR)
            elif code['arg2'] == 'sr2':
                self.data_path.signal_execute_alu_op(ALUOpcode.ADD, left_sel=Selectors.FROM_SR_2, right_sel=Selectors.FROM_DR)
            else:
                self.data_path.signal_execute_alu_op(ALUOpcode.ADD, left_sel=Selectors.FROM_SR_3, right_sel=Selectors.FROM_DR)
            self.data_path.signal_latch_sr(Selectors.FROM_ALU)
            self.inc_tick()

    def execute_rri(self, code: object, ps: dict):
        if code['opcode'] == Opcode.STORE:
            if code['arg1'] == 'sr1':
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_SR_1)
            elif code['arg1'] == 'sr2':
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_SR_2)
            else:
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_SR_3)
            self.data_path.signal_latch_dr_direct()
            self.data_path.signal_wr()
            self.inc_tick()

        elif code['opcode'] == Opcode.LOAD:
            self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
            self.data_path.signal_latch_dr()
            self.inc_tick()

            self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
            if self.data_path.ar == 98:
                self.data_path.signal_latch_sr(Selectors.FROM_INPUT, code['arg1'])
            else:
                self.data_path.signal_latch_sr(Selectors.FROM_ALU, code['arg1'])
            self.inc_tick()

        elif code['opcode'] == Opcode.ADDI:
            self.data_path.signal_execute_alu_op(ALUOpcode.INC_A, left_sel=Selectors.FROM_SR_1)
            self.data_path.signal_latch_sr(Selectors.FROM_ALU, code['arg1'])
            self.inc_tick()

            self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
            self.data_path.signal_latch_ar()
            self.inc_tick()

            self.data_path.signal_latch_dr()
            if code['arg1'] == 'sr1':
                self.data_path.signal_execute_alu_op(ALUOpcode.ADD, left_sel=Selectors.FROM_SR_1, right_sel=Selectors.FROM_DR)
            elif code['arg2'] == 'sr2':
                self.data_path.signal_execute_alu_op(ALUOpcode.ADD, left_sel=Selectors.FROM_SR_2, right_sel=Selectors.FROM_DR)
            else:
                self.data_path.signal_execute_alu_op(ALUOpcode.ADD, left_sel=Selectors.FROM_SR_3, right_sel=Selectors.FROM_DR)
            self.data_path.signal_latch_sr(Selectors.FROM_ALU)
            self.inc_tick()

        elif code['opcode'] == Opcode.CMP:
            if code['arg1'] == 'sr1':
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_SR_1)
            elif code['arg1'] == 'sr2':
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_SR_2)
            else:
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_A, left_sel=Selectors.FROM_SR_3)

            self.data_path.dr = self.data_path.alu.result
            self.inc_tick()

            if code['arg2'] == 'sr1':
                self.data_path.signal_execute_alu_op(ALUOpcode.CMP, left_sel=Selectors.FROM_SR_1, right_sel=Selectors.FROM_DR)
            elif code['arg2'] == 'sr2':
                self.data_path.signal_execute_alu_op(ALUOpcode.CMP, left_sel=Selectors.FROM_SR_2, right_sel=Selectors.FROM_DR)
            else:
                self.data_path.signal_execute_alu_op(ALUOpcode.CMP, left_sel=Selectors.FROM_SR_3, right_sel=Selectors.FROM_DR)
            self.inc_tick()
        
    def execute_ri(self, code: object, ps: dict):
        if code['opcode'] == Opcode.INC:
            if code['arg1'] == 'sr1':
                self.data_path.signal_execute_alu_op(ALUOpcode.INC_A, left_sel=Selectors.FROM_SR_1)
            elif code['arg2'] == 'sr2':
                self.data_path.signal_execute_alu_op(ALUOpcode.INC_A, left_sel=Selectors.FROM_SR_2)
            else:
                self.data_path.signal_execute_alu_op(ALUOpcode.INC_A, left_sel=Selectors.FROM_SR_3)

            self.data_path.signal_latch_sr(Selectors.FROM_ALU, code['arg1'])
            self.inc_tick()
        # elif code['opcode'] == Opcode.LOADI:
        #     self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
        #     self.data_path.signal_latch_dr()
        #     self.inc_tick()

        #     self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
        #     self.data_path.signal_latch_sr(Selectors.FROM_ALU, code['arg1'])
        #     self.inc_tick()
        elif code['opcode'] == Opcode.DEC:
            if code['arg1'] == 'sr1':
                self.data_path.signal_execute_alu_op(ALUOpcode.DEC_A, left_sel=Selectors.FROM_SR_1)
            elif code['arg2'] == 'sr2':
                self.data_path.signal_execute_alu_op(ALUOpcode.DEC_A, left_sel=Selectors.FROM_SR_2)
            else:
                self.data_path.signal_execute_alu_op(ALUOpcode.DEC_A, left_sel=Selectors.FROM_SR_3)

            self.data_path.signal_latch_sr(Selectors.FROM_ALU, code['arg1'])
            self.inc_tick()

    def execute_i(self, code: object, ps: dict):
        if code['opcode'] == Opcode.NOP:
            self.inc_tick()

        elif code['opcode'] == Opcode.HALT:
            raise HaltError(Opcode.HALT)
        
        elif code['opcode'] == Opcode.EI:
            self.data_path.signal_enable_interrupts()
            self.inc_tick()

        elif code['opcode'] == Opcode.DI:
            self.data_path.signal_disable_interrupts()
            self.inc_tick()
        
        elif code['opcode'] == Opcode.IRET:
            self.data_path.dr = 97
            self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
            self.data_path.signal_latch_ar()
            self.inc_tick()
            # self.data_path.signal_execute_alu_op(ALUOpcode.INC_B, right_sel=Selectors.FROM_SP)
            # self.data_path.signal_latch_sp()
            self.data_path.signal_latch_dr()
            self.inc_tick()
            self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
            self.data_path.signal_latch_pc()
            self.inc_tick()
            #  Восстанавливаем PS
            # self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_SP)
            # self.data_path.signal_latch_ar()
            # self.inc_tick()
            # self.data_path.signal_execute_alu_op(ALUOpcode.INC_B, right_sel=Selectors.FROM_SP)
            # self.data_path.signal_latch_sp()
            # self.data_path.signal_latch_dr()
            # self.inc_tick()
            # self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
            # self.data_path.signal_latch_ps()
            # self.inc_tick()
            self.mode = ProgramMode.NORMAL
            self.inc_tick()
        elif code['opcode'] == Opcode.JNE:
            if not ps["Z"]:
                self.data_path.dr = code['arg1']
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
                self.data_path.signal_latch_pc()
                self.inc_tick()
        elif code['opcode'] == Opcode.JE:
            if ps["Z"]:
                self.data_path.dr = code['arg1']
                self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
                self.data_path.signal_latch_pc()
                self.inc_tick()
        elif code['opcode'] == Opcode.JMP:
            self.data_path.dr = code['arg1']
            self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
            self.data_path.signal_latch_pc()
            self.inc_tick()

    def go_to_interrupt(self):
        self.data_path.dr = 97
        #  Сохраняем на стеке PS и PC
        self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
        self.data_path.signal_latch_ar()
        self.inc_tick()
        self.data_path.signal_execute_alu_op(ALUOpcode.DEC_B, right_sel=Selectors.FROM_PC)
        self.data_path.signal_latch_dr_direct()
        self.data_path.signal_wr()
        self.inc_tick()
        # self.data_path.signal_execute_alu_op(ALUOpcode.DEC_B, right_sel=Selectors.FROM_SP)
        # self.data_path.signal_latch_ar()
        # self.inc_tick()
        # self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_PC)
        # self.data_path.signal_wr()
        # self.inc_tick()
        #  Перемещаем в PC адрес подпрограммы обработки прерывания
        self.data_path.dr = 1
        # self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
        # self.data_path.signal_latch_ar()
        # self.inc_tick()
        # self.data_path.signal_latch_dr()
        self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_DR)
        self.data_path.signal_latch_pc()
        self.inc_tick()

    def check_for_interruptions(self, enabled: bool = False) -> bool:
        position = 0
        self.data_path.input_buffer = self.data_path.input_buffer[0 if position == 0 else position - 1 :]
        if not enabled or not self.data_path.input_buffer:
            return False
        else:
            return True
    
    def instr_fetch(self):
        self.data_path.signal_execute_alu_op(ALUOpcode.SKIP_B, right_sel=Selectors.FROM_PC)
        self.data_path.signal_latch_ar()
        self.data_path.signal_latch_ir()
        if self.data_path.ir['opcode'] == Opcode.STORE or self.data_path.ir['opcode'] == Opcode.LOAD:
            if self.data_path.ir['arg2'] not in ['sr1', 'sr2', 'sr3']:
                self.data_path.ar = self.data_path.ir['arg2']
        self.inc_tick()

        self.data_path.signal_execute_alu_op(ALUOpcode.INC_B, right_sel=Selectors.FROM_PC)
        self.data_path.signal_latch_pc()
        self.data_path.signal_latch_dr()
        self.inc_tick()

    def decode_and_execute_instr(self):
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
        return "TICK: {:4} | PC: {:3} | IR: {:5} | DR: {:3} | SR1: {:3} | SR2: {:3} | SR3: {:3} | AR: {:3} | N: {:1} | Z: {:1} | INT_EN: {:1} | data[AR]: {:3} | mode: {}".format(
            self.cur_tick(),
            self.data_path.pc,
            self.data_path.ir["opcode"],
            self.data_path.dr,
            (self.data_path.sr1 if self.data_path.sr1 else 'None'),
            (self.data_path.sr2 if self.data_path.sr2 else 'None'),
            (self.data_path.sr3 if self.data_path.sr3 else 'None'),
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
        logging.warning("Instruction limit exceeded!") 

    logging.info("output_buffer: %s", repr("".join(data_path.output_buffer)))
    return data_path.output_buffer, instr_counter, control_unit.cur_tick()

def read_code(filename):
    with open(filename, encoding="utf-8") as file:
        return json.loads(file.read())

def main(code_file: str, memory_file: str, input_file: Optional[str]):
    code = read_code(code_file)
    memory = read_code(memory_file)

    tokens = []

    if input_file is not None:
        with open(input_file, encoding="utf-8") as file:
            input_text = file.read()
            for char in input_text:
                tokens.append(char)

    output, instr_counter, ticks = simulation(code, memory, tokens=tokens, data_memory_size=100, instr_memory_size=100, limit=100)

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