import unittest
import tempfile
import os
from ConfigurationLanguageParser import YAMLToConfigParser, ConfigParserError


class TestYAMLToConfigParser(unittest.TestCase):
    def setUp(self):
        self.parser = YAMLToConfigParser()

    def test_validate_name_valid(self):
        valid_names = ["DEVICE_ID", "THRESHOLD", "_CONFIG_123"]
        for name in valid_names:
            self.parser.validate_name(name)  # Не должно выбросить исключений

    def test_validate_name_invalid(self):
        invalid_names = ["device-id", "123CONFIG", "config!", ""]
        for name in invalid_names:
            with self.assertRaises(ConfigParserError):
                self.parser.validate_name(name)

    def test_parse_value_valid_numbers(self):
        self.assertEqual(self.parser.parse_value("123"), "123")
        self.assertEqual(self.parser.parse_value("45.67"), "45.67")

    def test_parse_value_invalid(self):
        with self.assertRaises(ConfigParserError):
            self.parser.parse_value("not_a_number")
        with self.assertRaises(ConfigParserError):
            self.parser.parse_value("[invalid]")

    def test_parse_value_array(self):
        self.assertEqual(
            self.parser.parse_value("[1, 2, 3]"),
            "#(1, 2, 3)"
        )
        self.assertEqual(
            self.parser.parse_value("[1, [2.5, 3.3], 4]"),
            "#(1, #(2.5, 3.3), 4)"
        )

    def test_process_constant_line_valid(self):
        result = self.parser.process_constant_line("DEVICE_ID: 12345")
        self.assertEqual(result, "def DEVICE_ID = 12345;")
        self.assertEqual(self.parser.constants["DEVICE_ID"], "12345")

    def test_process_constant_line_duplicate(self):
        self.parser.constants["DEVICE_ID"] = "12345"
        with self.assertRaises(ConfigParserError):
            self.parser.process_constant_line("DEVICE_ID: 67890")

    def test_process_configuration_line_valid(self):
        self.parser.constants["DEVICE_ID"] = "12345"
        result = self.parser.process_configuration_line('Id: "@{DEVICE_ID}"')
        self.assertEqual(result, "Id = 12345;")

    def test_process_configuration_line_invalid_reference(self):
        with self.assertRaises(ConfigParserError):
            self.parser.process_configuration_line('Id: "@{UNKNOWN}"')

    def test_parse_valid(self):
        yaml_input = """
    # Comment at the start
    constants: # Constants definition
      DEVICE_ID: 12345 # Device ID
      THRESHOLD: 75.5
      TAGS: [[1, 2], [3.5, 4]]

    configuration: # Configuration rules
      Id: "@{DEVICE_ID}"
      Threshold: "@{THRESHOLD}"
      Tags: "@{TAGS}"
    """
        expected_output = """% Comment at the start
% Constants definition
def DEVICE_ID = 12345; % Device ID
def THRESHOLD = 75.5;
def TAGS = #(#(1, 2), #(3.5, 4));
% Configuration rules
Id = 12345;
Threshold = 75.5;
Tags = #(#(1, 2), #(3.5, 4));"""
        self.assertEqual(self.parser.parse(yaml_input), expected_output)

    def test_parse_invalid(self):
        invalid_yaml = """
constants:
  DEVICE_ID: invalid_value
"""
        with self.assertRaises(ConfigParserError):
            self.parser.parse(invalid_yaml)


class TestMainFunction(unittest.TestCase):
    def setUp(self):
        # Создаём временные файлы для тестов
        self.input_file = tempfile.NamedTemporaryFile(delete=False)
        self.output_file = tempfile.NamedTemporaryFile(delete=False)

    def tearDown(self):
        try:
            self.input_file.close()
            self.output_file.close()
        except Exception:
            pass
        os.unlink(self.input_file.name)
        os.unlink(self.output_file.name)

    def test_main_valid(self):
        input_data = """
    # Gaming Server Configuration
    constants:
      PLAYER_CAPACITY: 100.0
      WEAPON_DAMAGE: [10.5, 20.2, [30.8, 40.9], 50.0]

    configuration:
      MaxPlayers: "@{PLAYER_CAPACITY}"
      WeaponDamage: "@{WEAPON_DAMAGE}"
    """
        expected_output = """% Gaming Server Configuration
def PLAYER_CAPACITY = 100.0;
def WEAPON_DAMAGE = #(10.5, 20.2, #(30.8, 40.9), 50.0);
MaxPlayers = 100.0;
WeaponDamage = #(10.5, 20.2, #(30.8, 40.9), 50.0);"""
        self.input_file.write(input_data.encode())
        self.input_file.close()

        # Запуск функции main
        from ConfigurationLanguageParser import main
        main(self.input_file.name, self.output_file.name)

        # Чтение и проверка результата
        with open(self.output_file.name, "r") as f:
            output_data = f.read()
        self.assertEqual(output_data.strip(), expected_output.strip())

    def test_main_invalid(self):
        input_data = """
    constants:
      INVALID_CONSTANT: invalid_value
    """
        self.input_file.write(input_data.encode())
        self.input_file.close()

        from ConfigurationLanguageParser import main
        with self.assertRaises(ConfigParserError):
            main(self.input_file.name, self.output_file.name)


if __name__ == "__main__":
    unittest.main()
