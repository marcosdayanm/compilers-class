from globalTypes import *
from scanner import *

token = None # holds current token
tokenString = None # holds the token string value 
Error = False
#lineno = 1
SintaxTree = None
imprimeScanner = False

def syntaxError(message):
    global Error
    print(">>> Syntax error at line " + str(lineno) + ": " + message, end='')
    Error = True

def match(expected):
    global token, tokenString, lineno
    if (token == expected):
        token, tokenString, lineno = getToken(imprimeScanner)
        #print("TOKEN:", token, lineno)
    else:
        syntaxError("unexpected token -> ")
        printToken(token,tokenString)
        print("      ")

def stmt_sequence():
    t = statement()
    p = t
    while ((token!=TokenType.ENDFILE) and (token!=TokenType.END)
           and (token!=TokenType.ELSE) and (token!=TokenType.UNTIL)):
        match(TokenType.SEMI)
        q = statement()
        if (q!=None):
            if (t==None):
                t = p = q
            else: # now p cannot be NULL either
                p.sibling = q
                p = q
    return t

def statement():
    global token, tokenString, lineno
    #print("STATEMENT: ", token, lineno)
    t = None;
    if token == TokenType.IF:
        t = if_stmt()
    elif token == TokenType.REPEAT:
        t = repeat_stmt()
    elif token == TokenType.ID:
        t = assign_stmt()
    elif token == TokenType.READ:
        t = read_stmt()
    elif token == TokenType.WRITE:
        t = write_stmt()
    else:
        syntaxError("unexpected token -> ")
        printToken(token,tokenString)
        token, tokenString, lineno = getToken()
    return t

def if_stmt():
    t = newStmtNode(StmtKind.IfK)
    match(TokenType.IF)
    if (t!=None):
        t.child[0] = exp()
    match(TokenType.THEN)
    if (t!=None):
        t.child[1] = stmt_sequence()
    if (token==TokenType.ELSE):
        match(TokenType.ELSE)
        if (t!=None):
            t.child[2] = stmt_sequence()
    match(TokenType.END)
    return t

def repeat_stmt():
    t = newStmtNode(StmtKind.RepeatK)
    match(TokenType.REPEAT)
    if (t!=None):
        t.child[0] = stmt_sequence()
    match(TokenType.UNTIL);
    if (t!=None):
        t.child[1] = exp()
    return t

def assign_stmt():
    t = newStmtNode(StmtKind.AssignK)
    if ((t!=None) and (token==TokenType.ID)):
        t.name = tokenString
    match(TokenType.ID)
    match(TokenType.ASSIGN)
    if (t!=None):
        t.child[0] = exp()
    return t

def read_stmt():
    t = newStmtNode(StmtKind.ReadK)
    match(TokenType.READ)
    if ((t!=None) and (token==TokenType.ID)):
        t.name = tokenString
    match(TokenType.ID)
    return t

def write_stmt():
    t = newStmtNode(StmtKind.WriteK)
    match(TokenType.WRITE)
    if (t!=None):
        t.child[0] = exp()
    return t

def exp():
    global token, tokenString
    t = simple_exp()
    if ((token==TokenType.LT) or (token==TokenType.EQ)):
        p = newExpNode(ExpKind.OpK)
        if (p!=None):
          p.child[0] = t
          p.op = token
          t = p
        match(token)
        if (t!=None):
            t.child[1] = simple_exp()
    return t

def simple_exp():
    t = term()
    while ((token==TokenType.PLUS) or (token==TokenType.MINUS)):
        p = newExpNode(ExpKind.OpK)
        if (p!=None):
          p.child[0] = t
          p.op = token
          t = p
          match(token)
          t.child[1] = term()
    return t

def term():
    t = factor();
    while ((token==TokenType.TIMES) or (token==TokenType.OVER)):
        p = newExpNode(ExpKind.OpK)
        if (p!=None):
            p.child[0] = t
            p.op = token
            t = p
            match(token)
            t.child[1] = factor()
    return t

def factor():
    global token, tokenString
    t = None
    if token == TokenType.NUM:
        t = newExpNode(ExpKind.ConstK)
        if ((t!=None) and (token==TokenType.NUM)):
            t.val = int(tokenString)
        match(TokenType.NUM)
    elif token == TokenType.ID:
        t = newExpNode(ExpKind.IdK)
        if ((t!=None) and (token==TokenType.ID)):
            t.name = tokenString
        match(TokenType.ID)
    elif token == TokenType.LPAREN:
        match(TokenType.LPAREN)
        t = exp()
        match(TokenType.RPAREN)
    else:
        syntaxError("unexpected token -> ")
        printToken(token,tokenString)
        token, tokenString, lineno = getToken()
    return t

# Function newStmtNode creates a new statement
# node for syntax tree construction
def newStmtNode(kind):
    t = TreeNode();
    if (t==None):
        print("Out of memory error at line " + lineno)
    else:
        #for i in range(MAXCHILDREN):
        #    t.child[i] = None
        #t.sibling = None
        t.nodekind = NodeKind.StmtK
        t.stmt = kind
        t.lineno = lineno
    return t

# Function newExpNode creates a new expression 
# node for syntax tree construction

def newExpNode(kind):
    t = TreeNode()
    if (t==None):
        print("Out of memory error at line " + lineno)
    else:
        #for i in range(MAXCHILDREN):
        #    t.child[i] = None
        #t.sibling = None
        t.nodekind = NodeKind.ExpK
        t.exp = kind
        t.lineno = lineno
        t.type = ExpType.Void
    return t

# Procedure printToken prints a token 
# and its lexeme to the listing file
def printToken(token, tokenString):
    if token in {TokenType.IF, TokenType.THEN, TokenType.ELSE, TokenType.END,
                 TokenType.REPEAT, TokenType.UNTIL, TokenType.READ,
                 TokenType.WRITE}:
      print(" reserved word: " + tokenString);
    elif token == TokenType.ASSIGN:
        print(":=")
    elif token == TokenType.LT:
        print("<")
    elif token == TokenType.EQ:
        print("=")
    elif token == TokenType.LPAREN:
        print(listing,"(")
    elif token == TokenType.RPAREN:
        print(")")
    elif token == TokenType.SEMI:
        print(";")
    elif token == TokenType.PLUS:
        print("+")
    elif token == TokenType.MINUS:
        print("-")
    elif token == TokenType.TIMES:
        print("*")
    elif token == TokenType.OVER:
        print("/")
    elif token == TokenType.ENDFILE:
        print("EOF")
    elif token == TokenType.NUM:
      print("NUM, val= " + tokenString)
    elif token == ID:
        print("ID, name= " + tokenString);
    elif token == TokenType.ERROR:
        print("ERROR: " + tokenString)
    else: # should never happen
        print("Unknown token: " + token)

# Variable indentno is used by printTree to
# store current number of spaces to indent
indentno = 0

# printSpaces indents by printing spaces */
def printSpaces():
    print(" "*indentno, end = "")

# procedure printTree prints a syntax tree to the 
# listing file using indentation to indicate subtrees
def printTree(tree):
    global indentno
    indentno+=2 # INDENT
    while tree != None:
        printSpaces();
        if (tree.nodekind==NodeKind.StmtK):
            if tree.stmt == StmtKind.IfK:
                print(tree.lineno, "If")
            elif tree.stmt == StmtKind.RepeatK:
                print(tree.lineno, "Repeat")
            elif tree.stmt == StmtKind.AssignK:
                print(tree.lineno, "Assign to: ",tree.name)
            elif tree.stmt == StmtKind.ReadK:
                print(tree.lineno, "Read: ",tree.name)
            elif tree.stmt == StmtKind.WriteK:
                print(tree.lineno, "Write")
            else:
                print(tree.lineno, "Unknown ExpNode kind")
        elif tree.nodekind==NodeKind.ExpK:
            if tree.exp == ExpKind.OpK:
                print(tree.lineno, "Op: ", end ="")
                printToken(tree.op," ")
            elif tree.exp == ExpKind.ConstK:
                print(tree.lineno, "Const: ",tree.val)
            elif tree.exp == ExpKind.IdK:
                print(tree.lineno, "Id: ",tree.name)
            else:
                print(tree.lineno, "Unknown ExpNode kind")
        else:
            print(tree.lineno, "Unknown node kind");
        for i in range(MAXCHILDREN):
            printTree(tree.child[i])
        tree = tree.sibling
    indentno-=2 #UNINDENT

# the primary function of the parser
# Function parse returns the newly 
# constructed syntax tree

def parse(imprime = True):
    global token, tokenString, lineno
    token, tokenString, lineno = getToken(imprimeScanner)
    t = stmt_sequence()
    if (token != TokenType.ENDFILE):
        syntaxError("Code ends before file\n")
    if imprime:
        printTree(t)
    return t, Error

def recibeParser(prog, pos, long): # Recibe los globales del main
    recibeScanner(prog, pos, long) # Para mandar los globales

#syntaxTree = parse()
