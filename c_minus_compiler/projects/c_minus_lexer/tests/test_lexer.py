import os
import sys
import unittest


CURRENT_DIR = os.path.dirname(__file__)
PROJECT_DIR = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, PROJECT_DIR)

from globalTypes import TokenType
from lexer import globales, getToken


def load_program(source):
    program = source + "$"
    globales(program, 0, len(source))


class LexerTests(unittest.TestCase):
    def test_reserved_words_and_symbols(self):
        load_program("int main(void) { return 0; }")
        tokens = []
        token, lexeme = getToken(False)
        while token != TokenType.ENDFILE:
            tokens.append((token, lexeme))
            token, lexeme = getToken(False)

        self.assertEqual(
            tokens,
            [
                (TokenType.INT, "int"),
                (TokenType.ID, "main"),
                (TokenType.LPAREN, "("),
                (TokenType.VOID, "void"),
                (TokenType.RPAREN, ")"),
                (TokenType.LBRACE, "{"),
                (TokenType.RETURN, "return"),
                (TokenType.NUM, "0"),
                (TokenType.SEMI, ";"),
                (TokenType.RBRACE, "}"),
            ],
        )

    def test_comment_is_skipped(self):
        load_program("x = 1; /* hola */ y = 2;")
        tokens = []
        token, lexeme = getToken(False)
        while token != TokenType.ENDFILE:
            tokens.append((token, lexeme))
            token, lexeme = getToken(False)

        self.assertEqual(
            tokens,
            [
                (TokenType.ID, "x"),
                (TokenType.ASSIGN, "="),
                (TokenType.NUM, "1"),
                (TokenType.SEMI, ";"),
                (TokenType.ID, "y"),
                (TokenType.ASSIGN, "="),
                (TokenType.NUM, "2"),
                (TokenType.SEMI, ";"),
            ],
        )

    def test_invalid_integer_reports_error_token(self):
        load_program("contador = contador + 3indice;")
        expected_prefix = [
            (TokenType.ID, "contador"),
            (TokenType.ASSIGN, "="),
            (TokenType.ID, "contador"),
            (TokenType.PLUS, "+"),
            (TokenType.ERROR, "3indice"),
        ]

        result = []
        for _ in range(len(expected_prefix)):
            result.append(getToken(False))

        self.assertEqual(result, expected_prefix)

    def test_relational_and_division_tokens(self):
        load_program("a > b >= c / d;")
        tokens = []
        token, lexeme = getToken(False)
        while token != TokenType.ENDFILE:
            tokens.append((token, lexeme))
            token, lexeme = getToken(False)

        self.assertEqual(
            tokens,
            [
                (TokenType.ID, "a"),
                (TokenType.GT, ">"),
                (TokenType.ID, "b"),
                (TokenType.GTE, ">="),
                (TokenType.ID, "c"),
                (TokenType.OVER, "/"),
                (TokenType.ID, "d"),
                (TokenType.SEMI, ";"),
            ],
        )

    def test_unclosed_comment_reports_error(self):
        load_program("x = 1; /* comentario")
        tokens = []
        for _ in range(4):
            tokens.append(getToken(False))

        self.assertEqual(
            tokens,
            [
                (TokenType.ID, "x"),
                (TokenType.ASSIGN, "="),
                (TokenType.NUM, "1"),
                (TokenType.SEMI, ";"),
            ],
        )
        self.assertEqual(getToken(False), (TokenType.ERROR, "/* comentario"))


if __name__ == "__main__":
    unittest.main()
