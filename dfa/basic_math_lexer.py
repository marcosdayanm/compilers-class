def basic_math_lexer(
            s: str,
            tabla = [
                [1,6,7,8,0,8],
                [1,4,4,2,4,8],
                [3,8,8,8,8,8],
                [3,8,8,8,5,8],
            ],
            blanco: set = {' ', '\t', '\n', '$'},
            digitos: set = set('0123456789'),
            estado_inicial: int = 0,
            
    ):
    estado = estado_inicial
    p = 0
    lexema = ''
    token = ''
    col = 0

    while (s[p] != '$' or (s[p] == '$' and estado != 0)) and estado != 8:
        c = s[p]

        # equivalente al diccionario
        if c in digitos:
            col = 0
        elif c == '+':
            col = 1
        elif c == '-':
            col = 2
        elif c == '.':
            col = 3
        elif c in blanco:
            col = 4
        else:
            col = 5

        # cambia estado
        estado = tabla[estado][col]

        # procesar estados finales (4,5,6,7,8)
        if estado == 4:
            print(lexema, "ENTERO")
            lexema = ''
            estado = 0
            p -= 1

        elif estado == 5:
            print(lexema, "REAL")
            lexema = ''
            estado = 0
            p -= 1

        elif estado == 6:
            print('+', "SUMA")
            lexema = ''
            estado = 0

        elif estado == 7:
            print('-', "RESTA")
            lexema = ''
            estado = 0

        elif estado == 8:
            print(lexema, "ERROR")
            return
        
        p += 1
        if estado != 0:
            lexema += c


if __name__ == "__main__":
    basic_math_lexer("123+ 45.67 - 89 $")
