from globalTypes import *
from lexer import *


def run_lexer(filename="sample.c-"):
    with open(filename, "r", encoding="utf-8") as file:
        programa = file.read()

    progLong = len(programa)
    programa = programa + "$"
    posicion = 0

    globales(programa, posicion, progLong)

    token, tokenString = getToken(True)
    while token != TokenType.ENDFILE:
        token, tokenString = getToken(True)


if __name__ == "__main__":
    run_lexer()
