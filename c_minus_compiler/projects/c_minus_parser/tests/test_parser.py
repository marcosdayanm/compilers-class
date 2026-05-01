import os
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO


CURRENT_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, PROJECT_DIR)

from globalTypes import SyntaxNodeType, TokenType
from Parser import getParserErrors, globales, parser


def load_program(source):
    program = source + "$"
    globales(program, 0, len(source))


class ParserTests(unittest.TestCase):
    def test_parses_function_with_local_declarations_and_return(self):
        load_program(
            """
            int main(void)
            {
                int x;
                x = 1 + 2 * 3;
                return x;
            }
            """
        )

        ast = parser(False)

        self.assertEqual(ast.node_type, SyntaxNodeType.PROGRAM)
        fun_declaration = ast.children[0].children[0].children[0]
        self.assertEqual(fun_declaration.node_type, SyntaxNodeType.FUN_DECLARATION)
        self.assertEqual(fun_declaration.value, "main")
        self.assertEqual(getParserErrors(), [])

    def test_parses_arrays_calls_and_if_else(self):
        load_program(
            """
            int values[10];

            void main(void)
            {
                int x;
                values[0] = input();
                if (x < values[0])
                    output(values[0]);
                else
                    return;
            }
            """
        )

        ast = parser(False)

        self.assertEqual(ast.node_type, SyntaxNodeType.PROGRAM)
        self.assertEqual(len(ast.children[0].children), 2)
        self.assertEqual(getParserErrors(), [])

    def test_recovers_after_missing_semicolon(self):
        load_program(
            """
            void main(void)
            {
                int x
                x = 1;
                return;
            }
            """
        )

        with redirect_stdout(StringIO()):
            ast = parser(False)

        self.assertEqual(ast.node_type, SyntaxNodeType.PROGRAM)
        self.assertGreaterEqual(len(getParserErrors()), 1)

    def test_prints_terminal_tree_by_default(self):
        load_program(
            """
            int main(void)
            {
                int x;
                x = 1;
                return x;
            }
            """
        )

        output = StringIO()
        with redirect_stdout(output):
            ast = parser(imprime=True)

        lines = output.getvalue().strip().splitlines()
        stripped_lines = [line.strip() for line in lines]
        self.assertEqual(
            stripped_lines,
            [
                "INT:int",
                "ID:main",
                "VOID:void",
                "INT:int",
                "ID:x",
                "ID:x",
                "ASSIGN:=",
                "NUM:1",
                "RETURN:return",
                "ID:x",
            ],
        )
        self.assertNotIn("factor: 1", lines)
        self.assertTrue(any(line.startswith("                              NUM:1") for line in lines))

        terminal_nodes = ast.terminals()
        self.assertTrue(all(node.is_terminal for node in terminal_nodes))
        self.assertEqual(terminal_nodes[0].node_type, TokenType.INT)
        self.assertNotIn(TokenType.SEMI, [node.node_type for node in ast.abstract_terminals()])


if __name__ == "__main__":
    unittest.main()
