import sys

class ALU:
    def __init__(self):

class DataPath:

    data_memory_size = None

    data_memory = None

    data_address = None

    ac = None

    alu = None

    input_buffer = None

    output_buffer = None

    def __init__(self, data_memory_size: int, data_memory: int, input_buffer: list):
        self.data_memory_size = data_memory_size
        self.data_memory = [0] * data_memory_size
        self.data_address = 0
        self.acc = 0
        self.alu = ALU()
        self.input_buffer = input_buffer
        self.output_buffer = []


class ControlUnit:
    data_path = None

    _tick = None

    def __init__(self, data_path: DataPath):
        self.data_path = data_path
        self._tick = 0

    def tick(self):
        self._tick += 1

    def cur_tick(self) -> int:
        return self._tick
    
    def decode_and_execute_instr(self):
        return


def simulation(code: list, input_tokens: list, data_memory_size: int, limit: int):
    data_path = DataPath(data_memory_size, input_tokens)
    control_unit = ControlUnit(code, data_path)
    instr_counter = 0

    try:
        while instr_counter < limit:
            control_unit.decode_and_execute_instr()
            instr_counter += 1
    except HaltError:
        pass

    if instr_counter >= limit:
        return


def main():
    code = read_code(code_file)

if __name__ == "__main__":
    assert len(sys.argv) == 3, "Wrong arguments: machine.py <code_file> <input_file>"
    _, code_file, input_file = sys.argv
    main(code_file, input_file)