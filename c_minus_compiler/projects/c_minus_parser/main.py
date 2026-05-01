import sys

from Parser import globales, parser


def run_parser(filename="sample.c-", imprime=True, terminales=True):
    with open(filename, "r", encoding="utf-8") as file:
        programa = file.read()

    progLong = len(programa)
    programa = programa + "$"
    posicion = 0

    globales(programa, posicion, progLong)
    return parser(imprime, terminales)


def main():
    args = sys.argv[1:]
    # terminales = "--full" not in args
    terminales = False
    filenames = [arg for arg in args if arg != "--full"]
    filename = filenames[0] if filenames else "sample.c-"
    run_parser(filename, terminales=terminales)


if __name__ == "__main__":
    main()
