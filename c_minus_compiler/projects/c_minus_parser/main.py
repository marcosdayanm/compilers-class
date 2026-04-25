import sys

from Parser import globales, parser


def run_parser(filename="sample.c-", imprime=True):
    with open(filename, "r", encoding="utf-8") as file:
        programa = file.read()

    progLong = len(programa)
    programa = programa + "$"
    posicion = 0

    globales(programa, posicion, progLong)
    return parser(imprime)


def main():
    filename = sys.argv[1] if len(sys.argv) > 1 else "sample.c-"
    run_parser(filename)


if __name__ == "__main__":
    main()
