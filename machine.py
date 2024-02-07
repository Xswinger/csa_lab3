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
    def __init__(self):

def simulation():

def main():