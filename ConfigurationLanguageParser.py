import re
import sys


class ConfigParserError(Exception):
    """Класс для ошибок парсера."""
    pass


class YAMLToConfigParser:
    def __init__(self):
        self.constants = {}  # Для хранения определённых констант

    def validate_name(self, name):
        """Проверяет валидность имени константы."""
        if not re.fullmatch(r"[_A-Z][_a-zA-Z0-9]*", name):
            raise ConfigParserError(f"Недопустимое имя: {name}")

    def parse_value(self, value):
        """Обрабатывает строковые значения, распознавая числа, массивы и вложенные массивы."""
        value = value.strip()

        # Проверяем, является ли значение числом
        if value.isdigit() or (value.replace('.', '', 1).isdigit() and value.count('.') < 2):
            return value

        # Проверяем, является ли значение массивом
        if value.startswith("[") and value.endswith("]"):
            return self.parse_array(value)

        # Если формат значения не распознан
        raise ConfigParserError(f"Неподдерживаемое значение: {value}")

    def parse_array(self, array_str):
        """Обрабатывает массивы и вложенные массивы."""
        # Убираем внешние квадратные скобки
        array_str = array_str[1:-1].strip()
        if not array_str:
            return "#()"

        items = []
        current_item = []
        depth = 0

        for char in array_str:
            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1

            if char == "," and depth == 0:
                # Завершаем текущий элемент
                items.append("".join(current_item).strip())
                current_item = []
            else:
                current_item.append(char)

        # Добавляем последний элемент
        if current_item:
            items.append("".join(current_item).strip())

        # Рекурсивно обрабатываем элементы массива
        parsed_items = [self.parse_value(item) for item in items]
        return f"#({', '.join(parsed_items)})"

    def process_constant_line(self, line):
        """Обрабатывает одну строку из блока constants."""
        key, value = map(str.strip, line.split(":", 1))
        self.validate_name(key)  # Проверяем имя

        if key in self.constants:
            raise ConfigParserError(f"Дублирование определения константы: {key}")

        # Преобразуем значение и сохраняем его
        parsed_value = self.parse_value(value)
        self.constants[key] = parsed_value
        return f"def {key} = {parsed_value};"

    def process_configuration_line(self, line):
        """Обрабатывает одну строку из блока configuration."""
        key, value = map(str.strip, line.split(":", 1))
        self.validate_name(key)  # Проверяем имя

        value = value.strip('"')
        if value.startswith("@{") and value.endswith("}"):
            ref_name = value[2:-1]
            if ref_name not in self.constants:
                raise ConfigParserError(f"Ссылка на неопределённую константу: {ref_name}")
            resolved_value = self.constants[ref_name]
        else:
            raise ConfigParserError(f"Неправильный формат ссылки на константу: {value}")

        return f"{key} = {resolved_value};"

    def parse(self, yaml_data):
        """Основной метод для парсинга с разделением строк и комментариев."""
        parsed_lines = []  # Массив для хранения строк с их типами и дополнительной информацией

        # Разделяем строки на части: тип, содержимое, номер строки, комментарий
        for line_number, line in enumerate(yaml_data.splitlines(), start=1):
            stripped_line = line.strip()
            if not stripped_line:  # Пустые строки обрабатываются отдельно
                parsed_lines.append(["none", "", line_number, ""])
                continue

            # Отделяем комментарий
            comment = ""
            if "#" in stripped_line:
                code_part, comment = map(str.strip, stripped_line.split("#", 1))
            else:
                code_part = stripped_line

            # Определяем тип строки
            if re.fullmatch(r".+:\s*\"@{.+}\"", code_part):  # Маска для конфигураций
                line_type = "config"
            elif re.fullmatch(r".+:\s*.+", code_part):  # Маска для констант
                line_type = "const"
            else:  # Всё остальное — none
                line_type = "none"

            parsed_lines.append([line_type, code_part, line_number, comment])

        # Первый проход: обработка констант
        output_lines = []
        for entry in parsed_lines:
            line_type, code_part, line_number, comment = entry
            if line_type == "const":
                processed_line = self.process_constant_line(code_part)
                entry[1] = processed_line  # Обновляем строку в массиве

        # Второй проход: обработка конфигураций
        for entry in parsed_lines:
            line_type, code_part, line_number, comment = entry
            if line_type == "config":
                processed_line = self.process_configuration_line(code_part)
                entry[1] = processed_line  # Обновляем строку в массиве

        # Удаляем строки типа "none" без комментариев
        parsed_lines = [entry for entry in parsed_lines if entry[0] != "none" or entry[3]]

        # Перемещаем комментарии (строки типа "none") к следующим строкам
        final_lines = []
        pending_comments = []

        for entry in parsed_lines:
            line_type, processed_line, line_number, comment = entry

            if line_type == "none":
                # Сохраняем комментарии для следующей строки
                pending_comments.append((processed_line, comment))
            else:
                # Приклеиваем накопленные комментарии
                for _, pending_comment in pending_comments:
                    if pending_comment:
                        final_lines.append([line_type, "", line_number, pending_comment])
                pending_comments.clear()
                final_lines.append(entry)

        # Сортировка: сначала по типу (const перед config), затем по исходному номеру строки
        final_lines.sort(key=lambda x: (0 if x[0] == "const" else 1 if x[0] == "config" else 2, x[2]))

        # Склеиваем строки для вывода
        output_lines = []
        for _, processed_line, _, comment in final_lines:
            if comment:
                if processed_line:
                    output_lines.append(f"{processed_line} % {comment}")
                else:
                    output_lines.append(f"% {comment}")
            elif processed_line:
                output_lines.append(processed_line)

        return "\n".join(output_lines)


def main(input_file, output_file):
    with open(input_file, "r") as f:
        yaml_data = f.read()

    parser = YAMLToConfigParser()
    try:
        config_output = parser.parse(yaml_data)
        with open(output_file, "w") as f:
            f.write(config_output)
        print("Конфигурация успешно преобразована.")
    except ConfigParserError as e:
        print(f"Ошибка: {e}")
        raise


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python ConfigurationLanguageParser.py <input.yaml> <output.txt>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    main(input_file, output_file)
