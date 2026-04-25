from enum import Enum, IntEnum


class TokenType(Enum):
    ENDFILE = 0
    ERROR = 1

    IF = "if"
    ELSE = "else"
    INT = "int"
    RETURN = "return"
    VOID = "void"
    WHILE = "while"

    ID = 100
    NUM = 101

    PLUS = "+"
    MINUS = "-"
    TIMES = "*"
    OVER = "/"

    LT = "<"
    LTE = "<="
    GT = ">"
    GTE = ">="
    EQ = "=="
    NEQ = "!="
    ASSIGN = "="

    SEMI = ";"
    COMMA = ","
    LPAREN = "("
    RPAREN = ")"
    LBRACKET = "["
    RBRACKET = "]"
    LBRACE = "{"
    RBRACE = "}"


class InputSymbol(Enum):
    LETTER = "LETTER"
    DIGIT = "DIGIT"
    WHITESPACE = "WHITESPACE"
    EXCLAMATION = "!"
    EQUAL = "="
    LESS = "<"
    GREATER = ">"
    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    SEMI = ";"
    COMMA = ","
    LPAREN = "("
    RPAREN = ")"
    LBRACKET = "["
    RBRACKET = "]"
    LBRACE = "{"
    RBRACE = "}"
    EOF = "$"
    OTHER = "OTHER"


class LexerState(IntEnum):
    START = 0
    IN_ID = 1
    IN_INT = 2
    IN_BAD_NUM = 3
    SEEN_EXCLAMATION = 4
    IN_EXCL_ERROR = 5
    SEEN_ASSIGN = 6
    SEEN_LESS = 7
    SEEN_GREATER = 8
    SEEN_SLASH = 9
    IN_COMMENT = 10
    IN_COMMENT_STAR = 11
    COMMENT_EOF_FROM_BODY = 12
    COMMENT_EOF_FROM_STAR = 13
    IN_GENERIC_ERROR = 14

    # final states (1000's so if I introduce new states in the middle, I won't mess with the final state numbering)
    FINAL_ID = 1000
    FINAL_NUM_ERROR = 1001
    FINAL_INT = 1002
    FINAL_NEQ = 1003
    FINAL_EXCL_ERROR = 1004
    FINAL_EQ = 1005
    FINAL_ASSIGN = 1006
    FINAL_LTE = 1007
    FINAL_LT = 1008
    FINAL_GT = 1009
    FINAL_GTE = 1010
    FINAL_SIMPLE_SIGN = 1011
    FINAL_OVER = 1012
    FINAL_COMMENT = 1013
    FINAL_COMMENT_ERROR = 1014
    FINAL_EOF = 1015
    FINAL_GENERIC_ERROR = 1016


class ReservedWords(Enum):
    IF = "if"
    ELSE = "else"
    INT = "int"
    RETURN = "return"
    VOID = "void"
    WHILE = "while"


LETTER_CHARS: frozenset[str] = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
DIGIT_CHARS: frozenset[str] = frozenset("0123456789")
WHITESPACE_CHARS: frozenset[str] = frozenset({" ", "\t", "\n", "\r"})
RESERVED_LOOKUP: dict[str, TokenType] = {word.value: TokenType(word.value) for word in ReservedWords}


START_STATE: LexerState = LexerState.START
FINAL_STATES: frozenset[LexerState] = frozenset(
    {
        LexerState.FINAL_ID,
        LexerState.FINAL_NUM_ERROR,
        LexerState.FINAL_INT,
        LexerState.FINAL_NEQ,
        LexerState.FINAL_EXCL_ERROR,
        LexerState.FINAL_EQ,
        LexerState.FINAL_ASSIGN,
        LexerState.FINAL_LTE,
        LexerState.FINAL_LT,
        LexerState.FINAL_GT,
        LexerState.FINAL_GTE,
        LexerState.FINAL_SIMPLE_SIGN,
        LexerState.FINAL_OVER,
        LexerState.FINAL_COMMENT,
        LexerState.FINAL_COMMENT_ERROR,
        LexerState.FINAL_EOF,
        LexerState.FINAL_GENERIC_ERROR,
    }
)

# In these finals, the current character is not consumed and will be processed again by the initial state.
NONCONSUMING_FINAL_STATES: frozenset[LexerState] = frozenset(
    {
        LexerState.FINAL_ID,
        LexerState.FINAL_NUM_ERROR,
        LexerState.FINAL_INT,
        LexerState.FINAL_EXCL_ERROR,
        LexerState.FINAL_ASSIGN,
        LexerState.FINAL_LT,
        LexerState.FINAL_GT,
        LexerState.FINAL_OVER,
        LexerState.FINAL_COMMENT_ERROR,
        LexerState.FINAL_EOF,
        LexerState.FINAL_GENERIC_ERROR,
    }
)

# Quick classification for one-character symbols before consulting the DFA table.
CHAR_TO_INPUT_SYMBOL: dict[str, InputSymbol] = {
    "!": InputSymbol.EXCLAMATION,
    "=": InputSymbol.EQUAL,
    "<": InputSymbol.LESS,
    ">": InputSymbol.GREATER,
    "+": InputSymbol.PLUS,
    "-": InputSymbol.MINUS,
    "*": InputSymbol.STAR,
    "/": InputSymbol.SLASH,
    ";": InputSymbol.SEMI,
    ",": InputSymbol.COMMA,
    "(": InputSymbol.LPAREN,
    ")": InputSymbol.RPAREN,
    "[": InputSymbol.LBRACKET,
    "]": InputSymbol.RBRACKET,
    "{": InputSymbol.LBRACE,
    "}": InputSymbol.RBRACE,
    "$": InputSymbol.EOF,
}


# Main DFA table: current state + input class -> next state.
TRANSITION_TABLE: dict[LexerState, dict[InputSymbol, LexerState]] = {
    LexerState.START: {
        InputSymbol.WHITESPACE: LexerState.START,
        InputSymbol.LETTER: LexerState.IN_ID,
        InputSymbol.DIGIT: LexerState.IN_INT,
        InputSymbol.EXCLAMATION: LexerState.SEEN_EXCLAMATION,
        InputSymbol.EQUAL: LexerState.SEEN_ASSIGN,
        InputSymbol.LESS: LexerState.SEEN_LESS,
        InputSymbol.GREATER: LexerState.SEEN_GREATER,
        InputSymbol.SLASH: LexerState.SEEN_SLASH,
        InputSymbol.PLUS: LexerState.FINAL_SIMPLE_SIGN,
        InputSymbol.MINUS: LexerState.FINAL_SIMPLE_SIGN,
        InputSymbol.STAR: LexerState.FINAL_SIMPLE_SIGN,
        InputSymbol.SEMI: LexerState.FINAL_SIMPLE_SIGN,
        InputSymbol.COMMA: LexerState.FINAL_SIMPLE_SIGN,
        InputSymbol.LPAREN: LexerState.FINAL_SIMPLE_SIGN,
        InputSymbol.RPAREN: LexerState.FINAL_SIMPLE_SIGN,
        InputSymbol.LBRACKET: LexerState.FINAL_SIMPLE_SIGN,
        InputSymbol.RBRACKET: LexerState.FINAL_SIMPLE_SIGN,
        InputSymbol.LBRACE: LexerState.FINAL_SIMPLE_SIGN,
        InputSymbol.RBRACE: LexerState.FINAL_SIMPLE_SIGN,
        InputSymbol.EOF: LexerState.FINAL_EOF,
        InputSymbol.OTHER: LexerState.IN_GENERIC_ERROR,
    },
    LexerState.IN_ID: {
        InputSymbol.LETTER: LexerState.IN_ID,
        InputSymbol.DIGIT: LexerState.IN_ID,
        InputSymbol.OTHER: LexerState.FINAL_ID,
    },
    LexerState.IN_INT: {
        InputSymbol.DIGIT: LexerState.IN_INT,
        InputSymbol.LETTER: LexerState.IN_BAD_NUM,
        InputSymbol.OTHER: LexerState.FINAL_INT,
    },
    LexerState.IN_BAD_NUM: {
        InputSymbol.LETTER: LexerState.IN_BAD_NUM,
        InputSymbol.DIGIT: LexerState.IN_BAD_NUM,
        InputSymbol.OTHER: LexerState.FINAL_NUM_ERROR,
    },
    LexerState.SEEN_EXCLAMATION: {
        InputSymbol.EQUAL: LexerState.FINAL_NEQ,
        InputSymbol.OTHER: LexerState.IN_EXCL_ERROR,
    },
    LexerState.IN_EXCL_ERROR: {
        InputSymbol.WHITESPACE: LexerState.FINAL_EXCL_ERROR,
        InputSymbol.EOF: LexerState.FINAL_EXCL_ERROR,
        InputSymbol.OTHER: LexerState.IN_EXCL_ERROR,
    },
    LexerState.SEEN_ASSIGN: {
        InputSymbol.EQUAL: LexerState.FINAL_EQ,
        InputSymbol.OTHER: LexerState.FINAL_ASSIGN,
    },
    LexerState.SEEN_LESS: {
        InputSymbol.EQUAL: LexerState.FINAL_LTE,
        InputSymbol.OTHER: LexerState.FINAL_LT,
    },
    LexerState.SEEN_GREATER: {
        InputSymbol.EQUAL: LexerState.FINAL_GTE,
        InputSymbol.OTHER: LexerState.FINAL_GT,
    },
    LexerState.SEEN_SLASH: {
        InputSymbol.STAR: LexerState.IN_COMMENT,
        InputSymbol.OTHER: LexerState.FINAL_OVER,
    },
    LexerState.IN_COMMENT: {
        InputSymbol.STAR: LexerState.IN_COMMENT_STAR,
        InputSymbol.EOF: LexerState.COMMENT_EOF_FROM_BODY,
        InputSymbol.OTHER: LexerState.IN_COMMENT,
    },
    LexerState.IN_COMMENT_STAR: {
        InputSymbol.SLASH: LexerState.FINAL_COMMENT,
        InputSymbol.STAR: LexerState.IN_COMMENT_STAR,
        InputSymbol.EOF: LexerState.COMMENT_EOF_FROM_STAR,
        InputSymbol.OTHER: LexerState.IN_COMMENT,
    },
    LexerState.COMMENT_EOF_FROM_BODY: {
        InputSymbol.EOF: LexerState.FINAL_COMMENT_ERROR,
    },
    LexerState.COMMENT_EOF_FROM_STAR: {
        InputSymbol.EOF: LexerState.FINAL_COMMENT_ERROR,
    },
    LexerState.IN_GENERIC_ERROR: {
        InputSymbol.WHITESPACE: LexerState.FINAL_GENERIC_ERROR,
        InputSymbol.EOF: LexerState.FINAL_GENERIC_ERROR,
        InputSymbol.OTHER: LexerState.IN_GENERIC_ERROR,
    },
}
