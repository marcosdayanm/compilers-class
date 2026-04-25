def match(c):
    global token, pos
    if token == c:
        pos += 1
        if pos == len(lexed_list): # here the parse should call the lexer to get one token at a time
            token = "$"
        else:
            token = lexed_list[pos]
        return True
    return False


def expression():
    if term():
        while token in {'+', '-'}:
            match(token)
            if not term():
                return False
        return True
    else:
        return False


def term():
    if factor():
        while token == '*':
            match(token)
            if not factor():
                return False
        return True
    else:
        return False
    

def factor():
    if token in {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9'}:
        return match(token)
    elif token == '(':
        return match('(') and expression() and match(')')
    else:
        return False


if __name__ == "__main__":
    global token, pos, lexed_list
    pos = 0
    # lexed_list = ['(', '3', '+', '4', ')', '*', '5'] # True
    # lexed_list = ['5'] # True
    lexed_list = '3*4+5+' # False
    token = lexed_list[pos]
    print(expression() and not (pos < len(lexed_list)))