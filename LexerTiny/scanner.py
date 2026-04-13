from globalTypes import *

lineno = 1

def recibeScanner(prog, pos, long):
    global program
    global position
    global programLength
    program = prog
    position = pos
    programLength = long

def reservedLookup(tokenString):
    for w in ReservedWords:
        if tokenString == w.value:
            return TokenType(tokenString)
    return TokenType.ID

def getToken(imprime = True):
    global position, lineno
    tokenString = "" # string for storing token
    currentToken = None # is a TokenType value
    state = StateType.START # current state - always begins at START
    save = True # flag to indicate save to tokenString
    while (state != StateType.DONE):
        c = program[position]
        save = True
        if state == StateType.START:
            if c.isdigit():
                state = StateType.INNUM
            elif c.isalpha():
                state = StateType.INID
            elif c == ':':
                state = StateType.INASSIGN
            elif ((c == ' ') or (c == '\t') or (c == '\n')):
                save = False
                if (c == '\n'):
                    #print("línea: ", lineno)
                    lineno += 1 # incrementa el número de línea
            elif c == '{':
                save = False
                state = StateType.INCOMMENT
            else:
                state = StateType.DONE
                if position == programLength: #EOF
                    save = False
                    currentToken = TokenType.ENDFILE
                elif c == '=':
                    currentToken = TokenType.EQ
                elif c == '<':
                    currentToken = TokenType.LT
                elif c == '+':
                    currentToken = TokenType.PLUS
                elif c == '-':
                    currentToken = TokenType.MINUS
                elif c == '*':
                    currentToken = TokenType.TIMES
                elif c == '/':
                    currentToken = TokenType.OVER
                elif c == '(':
                    currentToken = TokenType.LPAREN
                elif c == ')':
                    currentToken = TokenType.RPAREN
                elif c == ';':
                    currentToken = TokenType.SEMI
                else:
                    currentToken = TokenType.ERROR
        elif state == StateType.INCOMMENT:
            save = False
            if position == programLength: #EOF
                state = StateType.DONE
                currentToken = TokenType.ENDFILE
            elif c == '}':
                state = StateType.START
            elif c == '\n':
                #print("línea: ", lineno)
                lineno += 1
        elif state == StateType.INASSIGN:
            state = StateType.DONE
            if c == '=':
                currentToken = TokenType.ASSIGN
            else:
                # backup in the input
                if position <= programLength:
                    position -= 1 # ungetNextChar()
                save = False
                currentToken = TokenType.ERROR
        elif state == StateType.INNUM:
            if not c.isdigit():
                # backup in the input
                if position <= programLength:
                    position -= 1 # ungetNextChar()
                save = False
                state = StateType.DONE
                currentToken = TokenType.NUM
        elif state == StateType.INID:
            if not c.isalpha():
                # backup in the input
                if position <= programLength:
                    position -= 1 # ungetNextChar()
                save = False
                state = StateType.DONE
                currentToken = TokenType.ID
        elif state == StateType.DONE:
            None
        else: # should never happen
            print('Scanner Bug: state= '+str(state))
            state = StateType.DONE
            currentToken = TokenType.ERROR
        if save:
            tokenString = tokenString + c
        if state == StateType.DONE:
            if currentToken == TokenType.ID:
                currentToken = reservedLookup(tokenString)
        position += 1
    if imprime:
        print(lineno, currentToken," = ", tokenString) # prints a token and its lexeme
    #print("CURRENT:", currentToken, lineno)
    return currentToken, tokenString, lineno

#f = open('prueba.tny', 'r')
##f = open('sample.tny', 'r')
#program = f.read() # lee todo el archivo a compilar
#programLength = len(program) # original program length
#program = program + '$' # add a character to represente EOF
#position = 0 # the position of the current char in file

