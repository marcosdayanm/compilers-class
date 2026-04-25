from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from globalTypes import (
    ADDOPS,
    DECLARATION_STARTS,
    EXPRESSION_STARTS,
    MULOPS,
    RELOPS,
    STATEMENT_STARTS,
    TYPE_SPECIFIERS,
    SyntaxNodeType,
    TokenType,
)
from lexer import Lexer


programa: str = ""
posicion: int = 0
progLong: int = 0
_lexer: Lexer | None = None
_parser: RecursiveDescentParser | None = None
_last_errors: list[str] = []


class BacktrackFailure(Exception):
    pass


@dataclass
class ASTNode:
    node_type: SyntaxNodeType
    value: str | None = None
    children: list[ASTNode] = field(default_factory=list)
    line: int | None = None
    column: int | None = None

    def pretty(self, indent: int = 0) -> str:
        label = self.node_type.value if self.value is None else f"{self.node_type.value}: {self.value}"
        lines = [" " * indent + label]
        for child in self.children:
            lines.append(child.pretty(indent + 2))
        return "\n".join(lines)


@dataclass
class ParserToken:
    token_type: TokenType
    lexeme: str
    line: int
    column: int


class RecursiveDescentParser:
    def __init__(self, lexer: Lexer) -> None:
        self.lexer = lexer
        self.tokens: list[ParserToken] = []
        self.current_index = -1
        self.current_token = ParserToken(TokenType.ENDFILE, "$", 1, 1)
        self.errors: list[str] = []
        self.trial_depth = 0

    def parse(self, imprime: bool = True) -> ASTNode:
        self.advance()
        ast = self.program()
        if self.current_token.token_type != TokenType.ENDFILE:
            self.syntax_error("Expected end of file.")
            self.synchronize(frozenset({TokenType.ENDFILE}))
        if imprime:
            print(ast.pretty())
        return ast

    def advance(self) -> None:
        next_index = self.current_index + 1
        if next_index < len(self.tokens):
            self.current_index = next_index
            self.current_token = self.tokens[self.current_index]
            return

        while True:
            token_type, lexeme = self.lexer.get_token(False)
            line, column = self.lexer.get_token_position()
            token = ParserToken(token_type, lexeme, line, column)
            if token_type != TokenType.ERROR:
                self.tokens.append(token)
                self.current_index = len(self.tokens) - 1
                self.current_token = token
                return

    def mark(self) -> int:
        return self.current_index

    def reset(self, mark: int) -> None:
        self.current_index = mark
        self.current_token = self.tokens[self.current_index]

    def match(
        self,
        expected: TokenType,
        context: str = "",
        recovery: frozenset[TokenType] = frozenset(),
    ) -> ParserToken:
        if self.current_token.token_type == expected:
            token = self.current_token
            self.advance()
            return token

        if self.trial_depth > 0:
            raise BacktrackFailure(f"Expected {expected.name}.")

        message = f"Expected {expected.name}"
        if context:
            message += f" in {context}"
        self.syntax_error(message + ".")

        sync_set = frozenset(set(recovery) | {expected, TokenType.ENDFILE})
        if self.current_token.token_type not in sync_set:
            self.synchronize(sync_set)
        if self.current_token.token_type == expected:
            token = self.current_token
            self.advance()
            return token
        return ParserToken(expected, "", self.current_token.line, self.current_token.column)

    def synchronize(self, sync_set: frozenset[TokenType]) -> None:
        while self.current_token.token_type not in sync_set and self.current_token.token_type != TokenType.ENDFILE:
            self.advance()

    def syntax_error(self, message: str) -> None:
        if self.trial_depth > 0:
            raise BacktrackFailure(message)
        line = self.current_token.line
        column = self.current_token.column
        source_line = self.lexer.source_line(line)
        pointer = " " * max(column - 1, 0) + "^"
        formatted = f"Line {line}: Syntax error: {message}\n{source_line}\n{pointer}"
        self.errors.append(formatted)
        print(formatted)

    def choice(
        self,
        context: str,
        alternatives: list[Callable[[], ASTNode]],
        recovery: frozenset[TokenType],
    ) -> ASTNode:
        start = self.mark()
        for alternative in alternatives:
            self.reset(start)
            self.trial_depth += 1
            try:
                node = alternative()
            except BacktrackFailure:
                continue
            finally:
                self.trial_depth -= 1
            return node

        self.reset(start)
        self.syntax_error(f"Expected {context}.")
        if self.current_token.token_type != TokenType.ENDFILE:
            self.advance()
        self.synchronize(frozenset(set(recovery) | {TokenType.ENDFILE}))
        return ASTNode(SyntaxNodeType.ERROR, value=context, line=self.current_token.line, column=self.current_token.column)

    def empty(self) -> ASTNode:
        return ASTNode(SyntaxNodeType.EMPTY)

    def program(self) -> ASTNode:
        return ASTNode(SyntaxNodeType.PROGRAM, children=[self.declaration_list()])

    def declaration_list(self) -> ASTNode:
        children: list[ASTNode] = []
        if self.current_token.token_type not in DECLARATION_STARTS:
            self.syntax_error("Program must start with a declaration.")
            self.synchronize(frozenset(set(DECLARATION_STARTS) | {TokenType.ENDFILE}))
        if self.current_token.token_type in DECLARATION_STARTS:
            children.append(self.declaration())
        children.append(self.declaration_list_prime())
        return ASTNode(SyntaxNodeType.DECLARATION_LIST, children=children)

    def declaration_list_prime(self) -> ASTNode:
        if self.current_token.token_type in DECLARATION_STARTS:
            return ASTNode(
                SyntaxNodeType.DECLARATION_LIST_PRIME,
                children=[self.declaration(), self.declaration_list_prime()],
            )
        return ASTNode(SyntaxNodeType.DECLARATION_LIST_PRIME, children=[self.empty()])

    def declaration(self, fn_name="declaration") -> ASTNode:
        child = self.choice(
            fn_name,
            [
                lambda: self.var_declaration(),
                lambda: self.fun_declaration(),
            ],
            frozenset(set(DECLARATION_STARTS) | {TokenType.ENDFILE}),
        )
        return ASTNode(SyntaxNodeType.DECLARATION, children=[child])

    def var_declaration(self, fn_name="var_declaration") -> ASTNode:
        type_node = self.type_specifier()
        identifier = self.match(
            TokenType.ID,
            fn_name,
            frozenset({TokenType.SEMI, TokenType.LBRACKET}) | DECLARATION_STARTS | STATEMENT_STARTS,
        )
        children = [type_node]
        value = identifier.lexeme

        if self.current_token.token_type == TokenType.LBRACKET:
            self.match(TokenType.LBRACKET, fn_name, frozenset({TokenType.NUM, TokenType.RBRACKET}))
            size = self.match(TokenType.NUM, fn_name, frozenset({TokenType.RBRACKET, TokenType.SEMI}))
            value = f"{identifier.lexeme}[{size.lexeme}]"
            self.match(TokenType.RBRACKET, fn_name, frozenset({TokenType.SEMI}) | DECLARATION_STARTS)

        self.match(TokenType.SEMI, fn_name, frozenset(set(DECLARATION_STARTS) | set(STATEMENT_STARTS) | {TokenType.RBRACE}))
        return ASTNode(SyntaxNodeType.VAR_DECLARATION, value=value, children=children, line=identifier.line, column=identifier.column)

    def type_specifier(self) -> ASTNode:
        if self.current_token.token_type in TYPE_SPECIFIERS:
            token = self.current_token
            self.advance()
            return ASTNode(SyntaxNodeType.TYPE_SPECIFIER, value=token.lexeme, line=token.line, column=token.column)

        self.syntax_error("Expected type_specifier.")
        self.synchronize(frozenset(set(TYPE_SPECIFIERS) | {TokenType.ID, TokenType.ENDFILE}))
        if self.current_token.token_type in TYPE_SPECIFIERS:
            return self.type_specifier()
        return ASTNode(SyntaxNodeType.TYPE_SPECIFIER, value="error", line=self.current_token.line, column=self.current_token.column)

    def fun_declaration(self, fn_name="fun_declaration") -> ASTNode:
        type_node = self.type_specifier()
        identifier = self.match(TokenType.ID, fn_name, frozenset({TokenType.LPAREN}))
        self.match(TokenType.LPAREN, fn_name, frozenset(set(TYPE_SPECIFIERS) | {TokenType.RPAREN}))
        params_node = self.params()
        self.match(TokenType.RPAREN, fn_name, frozenset({TokenType.LBRACE}))
        compound_node = self.compound_stmt()
        return ASTNode(
            SyntaxNodeType.FUN_DECLARATION,
            value=identifier.lexeme,
            children=[type_node, params_node, compound_node],
            line=identifier.line,
            column=identifier.column,
        )

    def params(self, fn_name="params") -> ASTNode:
        def void_params() -> ASTNode:
            void_token = self.match(TokenType.VOID, fn_name, frozenset({TokenType.RPAREN}))
            if self.current_token.token_type != TokenType.RPAREN:
                raise BacktrackFailure("Expected RPAREN after VOID params.")
            return ASTNode(SyntaxNodeType.PARAMS, value=void_token.lexeme, line=void_token.line, column=void_token.column)

        return self.choice(
            fn_name,
            [
                lambda: ASTNode(SyntaxNodeType.PARAMS, children=[self.param_list()]),
                void_params,
            ],
            frozenset({TokenType.RPAREN, TokenType.ENDFILE}),
        )

    def param_list(self) -> ASTNode:
        return ASTNode(SyntaxNodeType.PARAM_LIST, children=[self.param(), self.param_list_prime()])

    def param_list_prime(self, fn_name="param_list_prime") -> ASTNode:
        if self.current_token.token_type == TokenType.COMMA:
            self.match(TokenType.COMMA, fn_name, TYPE_SPECIFIERS)
            return ASTNode(
                SyntaxNodeType.PARAM_LIST_PRIME,
                children=[self.param(), self.param_list_prime()],
            )
        return ASTNode(SyntaxNodeType.PARAM_LIST_PRIME, children=[self.empty()])

    def param(self, fn_name="param") -> ASTNode:
        type_node = self.type_specifier()
        identifier = self.match(TokenType.ID, fn_name, frozenset({TokenType.COMMA, TokenType.RPAREN, TokenType.LBRACKET}))
        value = identifier.lexeme
        if self.current_token.token_type == TokenType.LBRACKET:
            self.match(TokenType.LBRACKET, fn_name, frozenset({TokenType.RBRACKET}))
            self.match(TokenType.RBRACKET, fn_name, frozenset({TokenType.COMMA, TokenType.RPAREN}))
            value = f"{identifier.lexeme}[]"
        return ASTNode(SyntaxNodeType.PARAM, value=value, children=[type_node], line=identifier.line, column=identifier.column)

    def compound_stmt(self, fn_name="compound_stmt") -> ASTNode:
        left = self.match(TokenType.LBRACE, fn_name, frozenset(set(DECLARATION_STARTS) | set(STATEMENT_STARTS) | {TokenType.RBRACE}))
        local_node = self.local_declarations()
        statement_node = self.statement_list()
        self.match(TokenType.RBRACE, fn_name, frozenset(set(DECLARATION_STARTS) | set(STATEMENT_STARTS) | {TokenType.ENDFILE}))
        return ASTNode(SyntaxNodeType.COMPOUND_STMT, children=[local_node, statement_node], line=left.line, column=left.column)

    def local_declarations(self) -> ASTNode:
        return ASTNode(SyntaxNodeType.LOCAL_DECLARATIONS, children=[self.local_declarations_prime()])

    def local_declarations_prime(self) -> ASTNode:
        if self.current_token.token_type in DECLARATION_STARTS:
            return ASTNode(
                SyntaxNodeType.LOCAL_DECLARATIONS_PRIME,
                children=[self.var_declaration(), self.local_declarations_prime()],
            )
        return ASTNode(SyntaxNodeType.LOCAL_DECLARATIONS_PRIME, children=[self.empty()])

    def statement_list(self) -> ASTNode:
        return ASTNode(SyntaxNodeType.STATEMENT_LIST, children=[self.statement_list_prime()])

    def statement_list_prime(self) -> ASTNode:
        if self.current_token.token_type in STATEMENT_STARTS:
            return ASTNode(
                SyntaxNodeType.STATEMENT_LIST_PRIME,
                children=[self.statement(), self.statement_list_prime()],
            )
        if self.current_token.token_type not in {TokenType.RBRACE, TokenType.ENDFILE}:
            self.syntax_error("Expected statement.")
            self.synchronize(frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE, TokenType.ENDFILE}))
            if self.current_token.token_type in STATEMENT_STARTS:
                return self.statement_list_prime()
        return ASTNode(SyntaxNodeType.STATEMENT_LIST_PRIME, children=[self.empty()])

    def statement(self) -> ASTNode:
        child = self.choice(
            "statement",
            [
                lambda: self.expression_stmt(),
                lambda: self.compound_stmt(),
                lambda: self.selection_stmt(),
                lambda: self.iteration_stmt(),
                lambda: self.return_stmt(),
            ],
            frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE, TokenType.ENDFILE}),
        )
        return ASTNode(SyntaxNodeType.STATEMENT, children=[child])

    def expression_stmt(self, fn_name="expression_stmt") -> ASTNode:
        if self.current_token.token_type == TokenType.SEMI:
            semi = self.match(TokenType.SEMI, fn_name, STATEMENT_STARTS | {TokenType.RBRACE})
            return ASTNode(SyntaxNodeType.EXPRESSION_STMT, value=semi.lexeme, line=semi.line, column=semi.column)

        expression_node = self.expression()
        self.match(TokenType.SEMI, fn_name, frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE}))
        return ASTNode(SyntaxNodeType.EXPRESSION_STMT, children=[expression_node])

    def selection_stmt(self, fn_name="selection_stmt") -> ASTNode:
        if_token = self.match(TokenType.IF, fn_name, frozenset({TokenType.LPAREN}))
        self.match(TokenType.LPAREN, fn_name, EXPRESSION_STARTS)
        condition = self.expression()
        self.match(TokenType.RPAREN, fn_name, STATEMENT_STARTS)
        then_statement = self.statement()
        children = [condition, then_statement]
        if self.current_token.token_type == TokenType.ELSE:
            self.match(TokenType.ELSE, fn_name, STATEMENT_STARTS)
            children.append(self.statement())
        return ASTNode(SyntaxNodeType.SELECTION_STMT, children=children, line=if_token.line, column=if_token.column)

    def iteration_stmt(self, fn_name="iteration_stmt") -> ASTNode:
        while_token = self.match(TokenType.WHILE, fn_name, frozenset({TokenType.LPAREN}))
        self.match(TokenType.LPAREN, fn_name, EXPRESSION_STARTS)
        condition = self.expression()
        self.match(TokenType.RPAREN, fn_name, STATEMENT_STARTS)
        body = self.statement()
        return ASTNode(SyntaxNodeType.ITERATION_STMT, children=[condition, body], line=while_token.line, column=while_token.column)

    def return_stmt(self, fn_name="return_stmt") -> ASTNode:
        return_token = self.match(TokenType.RETURN, fn_name, frozenset(set(EXPRESSION_STARTS) | {TokenType.SEMI}))
        if self.current_token.token_type == TokenType.SEMI:
            self.match(TokenType.SEMI, fn_name, STATEMENT_STARTS | {TokenType.RBRACE})
            return ASTNode(SyntaxNodeType.RETURN_STMT, line=return_token.line, column=return_token.column)

        expression_node = self.expression()
        self.match(TokenType.SEMI, fn_name, frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE}))
        return ASTNode(SyntaxNodeType.RETURN_STMT, children=[expression_node], line=return_token.line, column=return_token.column)

    def expression(self, fn_name="expression") -> ASTNode:
        def assignment_expression() -> ASTNode:
            var_node = self.var()
            assign_token = self.match(TokenType.ASSIGN, fn_name, EXPRESSION_STARTS)
            expression_node = self.expression()
            return ASTNode(
                SyntaxNodeType.EXPRESSION,
                value=assign_token.lexeme,
                children=[var_node, expression_node],
                line=assign_token.line,
                column=assign_token.column,
            )

        return self.choice(
            fn_name,
            [
                assignment_expression,
                lambda: ASTNode(SyntaxNodeType.EXPRESSION, children=[self.simple_expression()]),
            ],
            frozenset(set(STATEMENT_STARTS) | {TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
        )

    def var(self, fn_name="var") -> ASTNode:
        identifier = self.match(
            TokenType.ID,
            fn_name,
            frozenset({TokenType.LBRACKET, TokenType.ASSIGN, TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
        )
        children: list[ASTNode] = []
        value = identifier.lexeme
        if self.current_token.token_type == TokenType.LBRACKET:
            self.match(TokenType.LBRACKET, fn_name, EXPRESSION_STARTS)
            index = self.expression()
            self.match(TokenType.RBRACKET, fn_name, frozenset(set(ADDOPS) | set(MULOPS) | set(RELOPS) | {TokenType.ASSIGN, TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}))
            children.append(index)
            value = f"{identifier.lexeme}[]"
        return ASTNode(SyntaxNodeType.VAR, value=value, children=children, line=identifier.line, column=identifier.column)

    def simple_expression(self) -> ASTNode:
        additive_node = self.additive_expression()
        return ASTNode(SyntaxNodeType.SIMPLE_EXPRESSION, children=[additive_node, self.simple_expression_prime()])

    def simple_expression_prime(self) -> ASTNode:
        if self.current_token.token_type in RELOPS:
            return ASTNode(SyntaxNodeType.SIMPLE_EXPRESSION_PRIME, children=[self.relop(), self.additive_expression()])
        return ASTNode(SyntaxNodeType.SIMPLE_EXPRESSION_PRIME, children=[self.empty()])

    def relop(self) -> ASTNode:
        if self.current_token.token_type in RELOPS:
            operator = self.current_token
            self.advance()
            return ASTNode(SyntaxNodeType.RELOP, value=operator.lexeme, line=operator.line, column=operator.column)
        self.syntax_error("Expected relop.")
        return ASTNode(SyntaxNodeType.RELOP, value="error", line=self.current_token.line, column=self.current_token.column)

    def additive_expression(self) -> ASTNode:
        return ASTNode(SyntaxNodeType.ADDITIVE_EXPRESSION, children=[self.term(), self.additive_expression_prime()])

    def additive_expression_prime(self) -> ASTNode:
        if self.current_token.token_type in ADDOPS:
            return ASTNode(
                SyntaxNodeType.ADDITIVE_EXPRESSION_PRIME,
                children=[self.addop(), self.term(), self.additive_expression_prime()],
            )
        return ASTNode(SyntaxNodeType.ADDITIVE_EXPRESSION_PRIME, children=[self.empty()])

    def addop(self) -> ASTNode:
        if self.current_token.token_type in ADDOPS:
            operator = self.current_token
            self.advance()
            return ASTNode(SyntaxNodeType.ADDOP, value=operator.lexeme, line=operator.line, column=operator.column)
        self.syntax_error("Expected addop.")
        return ASTNode(SyntaxNodeType.ADDOP, value="error", line=self.current_token.line, column=self.current_token.column)

    def term(self) -> ASTNode:
        return ASTNode(SyntaxNodeType.TERM, children=[self.factor(), self.term_prime()])

    def term_prime(self) -> ASTNode:
        if self.current_token.token_type in MULOPS:
            return ASTNode(
                SyntaxNodeType.TERM_PRIME,
                children=[self.mulop(), self.factor(), self.term_prime()],
            )
        return ASTNode(SyntaxNodeType.TERM_PRIME, children=[self.empty()])

    def mulop(self) -> ASTNode:
        if self.current_token.token_type in MULOPS:
            operator = self.current_token
            self.advance()
            return ASTNode(SyntaxNodeType.MULOP, value=operator.lexeme, line=operator.line, column=operator.column)
        self.syntax_error("Expected mulop.")
        return ASTNode(SyntaxNodeType.MULOP, value="error", line=self.current_token.line, column=self.current_token.column)

    def factor(self, fn_name="factor") -> ASTNode:
        token_type = self.current_token.token_type
        if token_type == TokenType.LPAREN:
            left = self.match(TokenType.LPAREN, fn_name, EXPRESSION_STARTS)
            expression_node = self.expression()
            self.match(TokenType.RPAREN, fn_name, frozenset(set(ADDOPS) | set(MULOPS) | set(RELOPS) | {TokenType.SEMI, TokenType.COMMA, TokenType.RBRACKET, TokenType.RPAREN}))
            return ASTNode(SyntaxNodeType.FACTOR, value="()", children=[expression_node], line=left.line, column=left.column)

        if token_type == TokenType.ID:
            child = self.choice(
                "factor",
                [
                    lambda: self.call(),
                    lambda: self.var(),
                ],
                frozenset(set(ADDOPS) | set(MULOPS) | set(RELOPS) | {TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
            )
            return ASTNode(SyntaxNodeType.FACTOR, children=[child])

        if token_type == TokenType.NUM:
            number = self.match(TokenType.NUM, fn_name)
            return ASTNode(SyntaxNodeType.FACTOR, value=number.lexeme, line=number.line, column=number.column)

        self.syntax_error("Expected factor.")
        error_token = self.current_token
        factor_follow = frozenset(
            set(ADDOPS)
            | set(MULOPS)
            | set(RELOPS)
            | {TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET, TokenType.RBRACE}
        )
        if self.current_token.token_type not in factor_follow and self.current_token.token_type != TokenType.ENDFILE:
            self.advance()
        return ASTNode(SyntaxNodeType.FACTOR, children=[ASTNode(SyntaxNodeType.ERROR, value=error_token.lexeme, line=error_token.line, column=error_token.column)])

    def call(self, fn_name="call") -> ASTNode:
        identifier = self.match(TokenType.ID, fn_name, frozenset({TokenType.LPAREN}))
        self.match(TokenType.LPAREN, fn_name, frozenset(set(EXPRESSION_STARTS) | {TokenType.RPAREN}))
        args_node = self.args()
        self.match(TokenType.RPAREN, fn_name, frozenset(set(ADDOPS) | set(MULOPS) | set(RELOPS) | {TokenType.SEMI, TokenType.COMMA, TokenType.RBRACKET, TokenType.RPAREN}))
        return ASTNode(SyntaxNodeType.CALL, value=identifier.lexeme, children=[args_node], line=identifier.line, column=identifier.column)

    def args(self) -> ASTNode:
        if self.current_token.token_type in EXPRESSION_STARTS:
            return ASTNode(SyntaxNodeType.ARGS, children=[self.arg_list()])
        return ASTNode(SyntaxNodeType.ARGS, children=[self.empty()])

    def arg_list(self) -> ASTNode:
        return ASTNode(SyntaxNodeType.ARG_LIST, children=[self.expression(), self.arg_list_prime()])

    def arg_list_prime(self, fn_name="arg_list_prime") -> ASTNode:
        if self.current_token.token_type == TokenType.COMMA:
            self.match(TokenType.COMMA, fn_name, EXPRESSION_STARTS)
            return ASTNode(
                SyntaxNodeType.ARG_LIST_PRIME,
                children=[self.expression(), self.arg_list_prime()],
            )
        return ASTNode(SyntaxNodeType.ARG_LIST_PRIME, children=[self.empty()])


def globales(prog: str, pos: int, long: int) -> None:
    global programa
    global posicion
    global progLong
    global _lexer
    global _parser
    global _last_errors

    programa = prog
    posicion = pos
    progLong = long
    _last_errors = []
    _lexer = Lexer(prog, pos, long)
    _parser = RecursiveDescentParser(_lexer)


def parser(imprime: bool = True) -> ASTNode:
    global _lexer
    global _parser
    global _last_errors

    if _lexer is None:
        _lexer = Lexer(programa, posicion, progLong)
    if _parser is None:
        _parser = RecursiveDescentParser(_lexer)

    ast = _parser.parse(imprime)
    _last_errors = list(_parser.errors)
    return ast


def getParserErrors() -> list[str]:
    return list(_last_errors)
