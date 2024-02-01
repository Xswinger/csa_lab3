from isa import Opcode, write_code
import sys

def symbols():
    """Полное множество символов языка brainfuck."""
    return {"<", ">", "+", "-", ",", ".", "[", "]", "="}

def symbol_to_opcode(symbol):
    return {
        
    }

def translate(source_filename) -> tuple[list, int]:
    """Многопроходная трансляция программы в машинный код"""
    # lines, source_loc = read_lines(source_filename)
    # lines_without_comments = remove_comments(lines)
    # words, labels = lines_to_words_and_labels(lines_without_comments)
    # raw_code = link_labels(words, labels)
    # _start_position = find_program_start(labels)
    # code = to_machine_code(raw_code, _start_position)
    # return code, source_loc

def main(source_filename, target_filename):
    code, source_loc = translate(source_filename)

    write_code(target_filename, code)

    print("source LoC:", source_loc, "code instr:", len(code))


if __name__ == "__main__":
    assert len(sys.argv) == 3, "Wrong arguments: translator.py <input_file> <target_file>"
    _, source_filename, target_filename = sys.argv
    main(source_filename, target_filename)