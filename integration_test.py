import contextlib
import io
import logging
import os
import tempfile

import machine
import pytest
import translator


@pytest.mark.golden_test("golden/*.yml")
def test_translator_and_machine(golden, caplog):
    # Установим уровень отладочного вывода на DEBUG
    caplog.set_level(logging.DEBUG)

    # Создаём временную папку для тестирования приложения.
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Готовим имена файлов для входных и выходных данных.
        source = os.path.join(tmpdirname, "source.src")
        input_stream = os.path.join(tmpdirname, "input.txt")
        instr_target = os.path.join(tmpdirname, "instr_target.o")
        data_target = os.path.join(tmpdirname, "data_target.o")
        print(source, input_stream, instr_target, data_target)

        # Записываем входные данные в файлы. Данные берутся из теста.
        with open(source, "w", encoding="utf-8") as file:
            file.write(golden["in_source"])
        with open(input_stream, "w", encoding="utf-8") as file:
            file.write(golden["in_stdin"])

        # Запускаем транслятор и собираем весь стандартный вывод в переменную
        # stdout
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            translator.main(source, instr_target, data_target)
            machine.main(instr_target, data_target, input_stream)

        # Выходные данные также считываем в переменные.
        with open(instr_target, encoding="utf-8") as file:
            code = file.read()

        with open(data_target, encoding="utf-8") as file:
            mem = file.read()

        # Проверяем, что ожидания соответствуют реальности.
        assert code == golden.out["out_code"]
        assert mem == golden.out["out_mem"]
        assert stdout.getvalue() == golden.out["out_stdout"]
        assert caplog.text == golden.out["out_log"]
