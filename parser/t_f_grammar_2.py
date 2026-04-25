from enum import Enum

class ExpressionType(Enum):
    OP = "OP"
    CONST = "CONST"


class TreeNode:
    def __init__(self):
        self.node_type: ExpressionType | None = None # expression type on CFG

        # wether having op or val, but not both
        self.op: str | None = None
        self.val: str | None = None

        self.left: TreeNode | None = None
        self.right: TreeNode | None = None


def new_node(node_type: ExpressionType):
    """Creates a new tree node with the specified node type."""
    t = TreeNode()
    if t is None:
        raise MemoryError("Out of memory!")
    t.node_type = node_type
    return t


def syntax_error(error_msg):
    """Handles syntax errors by printing an error message and exiting the program."""
    print(f"Syntax error: {error_msg}")
    exit(1)


def print_spaces(indentation=4):
    print(" " * indentation, end='')


def print_tree(node: TreeNode | None):
    global indentation
    indentation += 2
    if node is not None:
        print_spaces(indentation)
        if node.node_type == ExpressionType.OP:
            print(f"OP: {node.op}")
        elif node.node_type == ExpressionType.CONST:
            print(f"CONST: {node.val}")
        else:
            print("Unknown ExpressionType")
        print_tree(node.left)
        print_tree(node.right)
    indentation -= 2


def match(c) -> None:
    global token, pos
    if token == c:
        pos += 1
        if pos == len(lexed_list): # here the parse should call the lexer to get one token at a time
            token = "$"
        else:
            token = lexed_list[pos]
    else:
        syntax_error(f"Unexpected token in match(): {token}")


def expression() -> TreeNode | None:
    t = term()
    while token in {'+', '-'}:
        op_node = new_node(ExpressionType.OP)
        op_node.left = t
        op_node.op = token
        match(token)
        op_node.right = term()
        t = op_node
    return t
    

def term() -> TreeNode | None:
    t = factor()
    while token == "*":
        op_node = new_node(ExpressionType.OP)
        op_node.left = t
        op_node.op = token
        match(token)
        op_node.right = factor()
        t = op_node
    return t

    

def factor() -> TreeNode | None:
    t = TreeNode()
    if token in {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9'}:
        t = new_node(ExpressionType.CONST)
        t.val = token
        match(token)
    elif token == '(':
        match('(')
        t = expression()
        match(')')
    else:
        syntax_error(f"Unexpected token in factor(): {token}")
        t = None
    return t


if __name__ == "__main__":
    global token, pos, lexed_list, indentation
    pos = 0
    indentation = 0
    # lexed_list = ['(', '3', '+', '4', ')', '*', '5'] # True
    # lexed_list = ['5'] # True
    # lexed_list = '3*4+5+' # False
    # lexed_list = "3+5-(5*4)-7"
    lexed_list = input("Enter an expression: ")
    token = lexed_list[pos]
    ast = expression()
    if token != "$":
        syntax_error("Unexpected token: " + token)
    else:
        print_tree(ast)