
# Лабораторная работа №3 (Упрощенный вариант)

## Студент

Аллаяров Игорь Олегович, P33121

## Вариант

asm | risc | harv | hw | instr | struct | stream | mem | cstr | prob2 | 8bit

asm -- синтаксис ассемблера. Необходима поддержка label-ов.

risc -- система команд должна быть упрощенной, в духе RISC архитектур:

* стандартизированная длина команд;
* операции над данными осуществляются только в рамках регистров;
* доступ к памяти и ввод-вывод -- отдельные операции (с учётом специфики вашего варианта mem/port);

harv -- Гарвардская архитектура.

hw -- hardwired CU. Реализуется как часть модели.

instr -- процессор необходимо моделировать с точностью до каждой инструкции (наблюдается состояние после каждой
инструкции).

struct -- в виде высокоуровневой структуры данных. Считается, что одна инструкция укладывается в одно машинное слово, за
исключением CISC архитектур.

stream -- ввод-вывод осуществляется как поток токенов. Есть в примере. Логика работы:

* при старте модели у вас есть буфер, в котором представлены все данные ввода (['h', 'e', 'l', 'l', 'o']);
* при обращении к вводу (выполнение инструкции) модель процессора получает "токен" (символ) информации;
* если данные в буфере кончились -- останавливайте моделирование;
* вывод данных реализуется аналогично, по выполнении команд в буфер вывода добавляется ещё один символ;
* по окончании моделирования показать все выведенные данные;
* логика работы с буфером реализуется в рамках модели на Python.

mem -- memory-mapped (порты ввода-вывода отображаются в память и доступ к ним осуществляется штатными командами),

* отображение портов ввода-вывода в память должно конфигурироваться (можно hardcode-ом).

cstr -- Null-terminated (C string)

8bit -- машинное слово -- 8 бит (как для памяти команд, так и для памяти данных, если они разделены).

## Язык программирования

### Форма Бэкуса-Наура

```ebnf
<program> ::= <code_line>
<code_line> ::= <data_definition> | <label_definition> | <directive>
<data_definition> ::= <label> ":\n" <data>
<label_definition> ::= <label> ":"
<directive> ::= <onear_instruction> <address_link> | <branch_instruction> <address_link> | <nullar_instruction>
<label> ::= <word>
<string> ::= "'" <text> "'"
<text> ::= {<letter>} "/"
<letter> ::= "a" | "b" | "c" | ... | "A" | "B" | ... | "Z" | "0" | ... | "1"
<address_link> = <label> | "(" <label> ")"
```

### Описание синтаксиса

Строка может представлять из себя:

* Метку (данных или подпрограммы)
    * Метки подпрограммы - имеет знак нижнего подчеркивания в начале названия
    * Метка подпрограммы - после определения метка имеет определение данных
        * Данные требуют ключевого слова `.word`
* Команда состоит из инструкции и метки
    * Инструкции имеют несколько форматов (rrr, rri, ri, i)
    * Все инструкции имеют одинаковый размер

### Описание семантики

* Глобальная видимость данных
* Поддержка строковых литералов в виде Null-terminated
    * В качестве нуль-символа используется символ косой черты `/`
* Последовательное выполнение кода
* Поддержка 2 видов меток - метка данных и метка подпрограммы
    * Пример объявления метки данных - `pointer:`
    * Пример объявления метки подпрограммы - `_start:`
    * Названия меток не могут повторяться, совпадать с названием команды, совпадать с ключевым словом `.word`
* Статистическое выделение памяти при запуске модели

## Организация памяти

Память команд

```text
+-----------------------------+
| 00       jmp N              | <-- PC
| 01       interrupt handle   |
|      ...                    |
| N - 1    interrupt handle   |
+-----------------------------+
| N        program            |
| N + 1    program            |
|      ...                    |
| 99       program            |
+-----------------------------+
```

Память данных

```text
+-----------------------------+
| 00       string literals    | <-- AR
|          and variables      |
|      ...                    |
|                             |
| 98       input file         |
| 99       output file        |
+-----------------------------+
```

* Виды адресации:
    * абсолютная
    * косвенная
* Адрес 98 зарезервирован для ввода
* Адрес 99 зарезервирован для вывода

## Система команд

### Особенности процессора

* Длина машинного слова не определена (слова знаковые)
* В качестве аргументов команды принимают адреса (ошибка выполнения при выход за границы) или регистры

## Цикл исполнения команды

1) Выборка инструкции
2) Исполнение команды
3) Проверка на прерывание

### Набор инструкций

| Инструкция | Число тактов |
|----|----|
|  inc  |  1  |
|  dec  |  1  |
|  add  |  2  |
|  addi  |  3  |
|  load  |  2  |
|  store  |  1  |
|  cmp  |  2  |
|  nop  |  1  |
|  ei  |  1  |
|  di  |  1  |
|  iret  |  4  |
|  jne  |  0 - 1  |
|  je  |  0 - 1  |
|  jmp  |  1  |
|  halt  |  0  |

### Способ кодирования инструкций

Кодирование происходит в формат JSON, инструкция имеет вид:

```json
{
    "index": 0,
    "opcode": "add",
    "arg1": 1,
    "argr2": 0,
    "arg3": 0,
    "is_indirect"
}
```

где:

* `index` - индекс
* `opcode` - код операции
* `arg1` - аргумент 1
* `arg2` - аргумент 2
* `arg3` - аргумент 3
* `is_indirect` - способ адресации (косвенная или прямая)

## Транслятор

Интерфейс командной строки:

`translator.py <input_file> <prog_file> <data_file>`

Реализация: [translator.py](/translator.py)

### Принцип работы транслятора

Основные понятия в процессе трансляции:

* строка (line) - строка кода исходного файла
* метка (label) - символьное имя для обозначения данных или кода
* инструкция (instruction) -- команда с аргументами исходного кода

Этапы:

1) Получение строк из исходного кода
2) Получение меток и адресов в памяти, на которые они ссылаются, инструкций
3) Подмена меток на адреса в памяти, указания типа адресации
4) Кодирование инструкций в машинный код

## Модель процессора

Интерфейс командной строки:

`machine.py <code_file> <memory_file> [<input_file>]`

Реализация: [machine.py](/machine.py)

### Схема Datapath

![DataPath](/img/CSA3LabDP.png)

### Схема ControlUnit

![ControlUnit](/img/CSA3LabCU.png)

## Тестирование

### Разработанные тесты

* `hello` - напечатать "Hello world"
* `cat` - вывод введенной строки

Интеграционные тесты реализованы в [integration_test](/integration_test.py):

Стратегия: golden tests, конфигурация в папке [golden/](/golden/)

### Описание работы CI

CI при помощи Github Action:
```text
name: Python CI

on:
  push:
    branches:
      - master
    paths:
      - ".github/workflows/*"
      - "**/*.py"
  pull_request:
    branches:
      - master
    paths:
      - ".github/workflows/*"
      - "**/*.py"

defaults:
  run:
    working-directory: ./

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: 3.11

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install poetry
          poetry install

      - name: Run tests and collect coverage
        run: |
          poetry run coverage run -m pytest .
          poetry run coverage report -m
        env:
          CI: true

  lint:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: 3.11

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install poetry
          poetry install

      - name: Check code formatting with Ruff
        run: poetry run ruff format --check .

      - name: Run Ruff linters
        run: poetry run ruff check .
```

где:

* poetry -- инструмент управления зависимостями для языка программирования Python
* coverage -- формирование отчёта об уровне покрытия исходного кода
* pytest -- фреймворк для тестирования (в нашем случае - запуска тестов)
* ruff -- утилита для форматирования и проверки стиля кода

Прохождение тестов:

```text
============================= test session starts ==============================
platform linux -- Python 3.11.8, pytest-7.4.4, pluggy-1.4.0
rootdir: /home/runner/work/csa_lab3/csa_lab3
configfile: pyproject.toml
plugins: golden-0.2.2
collected 2 items

integration_test.py ..                                                   [100%]

============================== 2 passed in 0.20s ===============================
Name                  Stmts   Miss  Cover   Missing
---------------------------------------------------
alu.py                   60      5    92%   17, 52, 56, 62, 70
integration_test.py      32      0   100%
isa.py                   54      1    98%   51
machine.py              348     59    83%   124, 126, 199, 201, 213, 222-241, 246, 268-290, 296, 304, 322, 328-337, 341, 368-371, 374-377, 499-506
translator.py           117      7    94%   87, 161-171, 203-206
---------------------------------------------------
TOTAL                   611     72    88%
```

```text
| ФИО                      | алг             | LoC | code байт | code инстр. | инстр. | такт. | вариант                                                                   |
| Аллаяров Игорь Олегович | hello           | 22  | -         | 11          | 100    | 413   | asm | risc | harv | hw | instr | struct | stream | mem | cstr | prob2 | 8bit |
| Аллаяров Игорь Олегович | cat             | 32  | -         | 15          | 55     | 228   | asm | risc | harv | hw | instr | struct | stream | mem | cstr | prob2 | 8bit |
```