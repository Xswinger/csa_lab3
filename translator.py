from __future__ import annotations

import sys

from isa import Opcode, write_code, write_memory

data = [0] * 100


def symbols(symbol) -> Opcode:
    return {"add", "addi", "sub", "inc", "dec", "halt", "ei", "di", "cmp", "iret", "jmp"}


def symbol_to_opcode(symbol):
    return {
        "nop": Opcode.NOP,
        "halt": Opcode.HALT,
        "ei": Opcode.EI,
        "di": Opcode.DI,
        "iret": Opcode.IRET,
        "inc": Opcode.INC,
        "dec": Opcode.DEC,
        "load": Opcode.LOAD,
        "store": Opcode.STORE,
        "add": Opcode.ADD,
        "addi": Opcode.ADDI,
        "cmp": Opcode.CMP,
        "test": Opcode.TEST,
        "jne": Opcode.JNE,
        "je": Opcode.JE,
        "jg": Opcode.JG,
        "jmp": Opcode.JMP,
    }.get(symbol, Opcode.NOP)


# чтение файла
def read_lines(source_filename: str) -> tuple[list[str], int]:
    source_loc = 0
    lines = []
    with open(source_filename) as file:
        for line in file:
            source_loc += 1
            line = line.strip()
            if line != "":
                lines.append(line)
    return lines, source_loc


# строки кода в операторы
def lines_to_words_and_labels(code_lines) -> tuple[dict, dict]:
    labels = {}
    words = {}
    position = 0
    memory_position = 4
    for line in code_lines:
        if line[-1] == ":":
            if line[0] != "_":
                labels[line[0:-1]] = [memory_position, -1]
            else:
                labels[line[0:-1]] = [-1, position]
        elif line.startswith(".word"):
            position, memory_position, words = parse_word(position, memory_position, line[6:], words, labels)
        else:
            args = line.split(" ")
            kv = [args[0]]
            for i in range(1, len(args)):
                kv.append(args[i])
            words[position] = kv
            position += 1
    return words, labels


# Индексация слова данных (в т.ч. разбиение строк по буквам)
def parse_word(position, memory_position, word_line, words, labels) -> tuple[int, dict]:
    char_num = 0
    while char_num < len(word_line):
        if word_line[char_num] == "'":
            char_num += 1
            while word_line[char_num] != "'":
                data[memory_position] = [ord(word_line[char_num])]
                memory_position += 1
                char_num += 1
            char_num += 1
        elif word_line[char_num].isnumeric() or word_line[char_num] == "-":
            cur_num = word_line[char_num]
            char_num += 1
            while char_num < len(word_line) and word_line[char_num].isnumeric():
                cur_num += word_line[char_num]
                char_num += 1
            data[memory_position] = [int(cur_num)]
            memory_position += 1
        elif word_line[char_num] == "," or word_line[char_num] == " ":
            char_num += 1
        else:
            label = ""
            while char_num < len(word_line) and word_line[char_num] != "," and word_line[char_num] != " ":
                label += word_line[char_num]
                char_num += 1
            if label[0] != "_":
                data[memory_position] = [int(labels[label][0])]
                memory_position += 1
    return position, memory_position, words


# Подмена меток на индексы + установка вида адресации (True - косвенный)
def link_labels(words, labels) -> dict:
    replaced = {}
    for w_index, word in words.items():
        indirect = False
        for part in range(0, len(word)):
            if isinstance(word[part], str) and word[part].startswith("("):
                indirect = True
                word[part] = word[part][1:-1]
            if labels.get(word[part]) is not None:
                if labels[word[part]][0] != -1:
                    word[part] = int(labels[word[part]][0])
                else:
                    word[part] = int(labels[word[part]][1])
        word.append(indirect)
        replaced[w_index] = word
    return replaced


def find_program_start(labels) -> int:
    counter = 0
    position = None
    for index, label in labels.items():
        if index == "_start":
            counter += 1
            position = label[1]
    assert counter == 1, f"Error: got _start label {counter} times"
    return position + 1


# трансляция в машинный код
def to_machine_code(raw_code, _start_position) -> list:
    code = [{"index": 0, "opcode": Opcode.JMP, "arg1": _start_position, "arg2": 0, "arg3": 0, "is_indirect": False}]
    for index, word in raw_code.items():
        if len(word) == 2:
            instr = {
                "index": index + 1,
                "opcode": symbol_to_opcode(word[0]),
                "arg1": 0,
                "arg2": 0,
                "arg3": 0,
                "is_indirect": word[-1],
            }
        elif len(word) == 3:
            arg = word[1]
            if word[0] in ("jne", "je", "jg", "jmp"):
                arg += 1
            instr = {
                "index": index + 1,
                "opcode": symbol_to_opcode(word[0]),
                "arg1": arg,
                "arg2": 0,
                "arg3": 0,
                "is_indirect": word[-1],
            }
        elif len(word) == 4:
            instr = {
                "index": index + 1,
                "opcode": symbol_to_opcode(word[0]),
                "arg1": word[1],
                "arg2": word[2],
                "arg3": 0,
                "is_indirect": word[-1],
            }
        elif len(word) == 5:
            instr = {
                "index": index + 1,
                "opcode": symbol_to_opcode(word[0]),
                "arg1": word[1],
                "arg2": word[2],
                "arg3": word[3],
                "is_indirect": word[-1],
            }
        else:
            raise f"Incorrect operands count = {len(word)}"
        code.append(instr)
    return code


# Трансляция программы в машинный код
def translate(source_filename) -> tuple[list, int]:
    lines, source_loc = read_lines(source_filename)

    instrs, labels = lines_to_words_and_labels(lines)

    raw_code = link_labels(instrs, labels)

    _start_position = find_program_start(labels)

    code = to_machine_code(raw_code, _start_position)

    return code, data, source_loc


def main(source_filename, prog_filename, data_filename):
    global data

    code, data, source_loc = translate(source_filename)

    write_code(prog_filename, code)
    write_memory(data_filename, data)

    print("source LoC:", source_loc, "code instr:", len(code))


if __name__ == "__main__":
    assert len(sys.argv) == 4, "Wrong arguments: translator.py <input_file> <prog_file> <data_file>"
    _, source_filename, prog_filename, data_filename = sys.argv

    main(source_filename, prog_filename, data_filename)
