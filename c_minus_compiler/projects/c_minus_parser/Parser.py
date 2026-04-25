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
    """Internal signal used by choice() when a grammar alternative does not match."""


@dataclass
class ASTNode:
    """Node for the syntax tree; terminals are stored as value/position on grammar nodes."""

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
    """Token plus source position captured from the injected lexer."""

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
        """Entry point: primes the lookahead token, parses program, and prints the AST if requested."""
        self.advance()
        ast = self.program()
        if self.current_token.token_type != TokenType.ENDFILE:
            self.syntax_error("Expected end of file.")
            self.synchronize(frozenset({TokenType.ENDFILE}))
        if imprime:
            print(ast.pretty())
        return ast

    def advance(self) -> None:
        """Move to the next token, reusing buffered tokens when backtracking has already scanned them."""
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
        """Return the current token-buffer index so choice() can restore it after a failed alternative."""
        return self.current_index

    def reset(self, mark: int) -> None:
        """Restore parser lookahead to a previously saved token-buffer index."""
        self.current_index = mark
        self.current_token = self.tokens[self.current_index]

    def match(
        self,
        expected: TokenType,
        context: str,
        recovery: frozenset[TokenType] = frozenset(),
    ) -> ParserToken:
        """Consume one required terminal; during choice() trials, failure backtracks instead of printing."""
        if self.current_token.token_type == expected:
            token = self.current_token
            self.advance()
            return token

        if self.trial_depth > 0:
            raise BacktrackFailure(f"Expected {expected.name}.")

        self.syntax_error(f"Expected {expected.name} in {context}.")
        sync_set = frozenset(set(recovery) | {expected, TokenType.ENDFILE})
        if self.current_token.token_type not in sync_set:
            self.synchronize(sync_set)
        if self.current_token.token_type == expected:
            token = self.current_token
            self.advance()
            return token
        return ParserToken(expected, "", self.current_token.line, self.current_token.column)

    def choice(
        self,
        context: str,
        alternatives: list[Callable[[], ASTNode]],
        recovery: frozenset[TokenType],
    ) -> ASTNode:
        """Try grammar alternatives from left to right, backtracking silently until one succeeds."""
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

    def synchronize(self, sync_set: frozenset[TokenType]) -> None:
        """Panic-mode recovery: discard tokens until a token in sync_set can resume parsing."""
        while self.current_token.token_type not in sync_set and self.current_token.token_type != TokenType.ENDFILE:
            self.advance()

    def syntax_error(self, message: str) -> None:
        """Record and print a parser error with the source line and caret position."""
        if self.trial_depth > 0:
            raise BacktrackFailure(message)
        line = self.current_token.line
        column = self.current_token.column
        source_line = self.lexer.source_line(line)
        pointer = " " * max(column - 1, 0) + "^"
        formatted = f"Line {line}: Syntax error: {message}\n{source_line}\n{pointer}"
        self.errors.append(formatted)
        print(formatted)

    def empty(self) -> ASTNode:
        """Build the explicit epsilon node used by productions with an empty alternative."""
        return ASTNode(SyntaxNodeType.EMPTY)

    def program(self) -> ASTNode:
        """program -> declaration_list"""
        return ASTNode(SyntaxNodeType.PROGRAM, children=[self.declaration_list()])

    def declaration_list(self) -> ASTNode:
        """declaration_list -> declaration declaration_list_prime"""
        return ASTNode(
            SyntaxNodeType.DECLARATION_LIST,
            children=[self.declaration(), self.declaration_list_prime()],
        )

    def declaration_list_prime(self, fn_name="declaration_list_prime") -> ASTNode:
        """declaration_list_prime -> declaration declaration_list_prime | empty"""
        return self.choice(
            fn_name,
            [
                lambda: ASTNode(SyntaxNodeType.DECLARATION_LIST_PRIME, children=[self.declaration(), self.declaration_list_prime()]),
                lambda: ASTNode(SyntaxNodeType.DECLARATION_LIST_PRIME, children=[self.empty()]),
            ],
            frozenset({TokenType.ENDFILE}),
        )

    def declaration(self, fn_name="declaration") -> ASTNode:
        """declaration -> var_declaration | fun_declaration"""
        return ASTNode(
            SyntaxNodeType.DECLARATION,
            children=[
                self.choice(
                    fn_name,
                    [self.var_declaration, self.fun_declaration],
                    frozenset(set(DECLARATION_STARTS) | {TokenType.ENDFILE}),
                )
            ],
        )

    def var_declaration(self, fn_name="var_declaration") -> ASTNode:
        """var_declaration -> type_specifier ID SEMI | type_specifier ID LBRACKET NUM RBRACKET SEMI"""
        def scalar_var_declaration() -> ASTNode:
            type_node = self.type_specifier()
            identifier = self.match(TokenType.ID, fn_name, frozenset({TokenType.SEMI}))
            self.match(
                TokenType.SEMI,
                fn_name,
                frozenset(set(DECLARATION_STARTS) | set(STATEMENT_STARTS) | {TokenType.RBRACE}),
            )
            return ASTNode(
                SyntaxNodeType.VAR_DECLARATION,
                value=identifier.lexeme,
                children=[type_node],
                line=identifier.line,
                column=identifier.column,
            )

        def array_var_declaration() -> ASTNode:
            type_node = self.type_specifier()
            identifier = self.match(TokenType.ID, fn_name, frozenset({TokenType.LBRACKET}))
            self.match(TokenType.LBRACKET, fn_name, frozenset({TokenType.NUM}))
            size = self.match(TokenType.NUM, fn_name, frozenset({TokenType.RBRACKET}))
            self.match(TokenType.RBRACKET, fn_name, frozenset({TokenType.SEMI}))
            self.match(
                TokenType.SEMI,
                fn_name,
                frozenset(set(DECLARATION_STARTS) | set(STATEMENT_STARTS) | {TokenType.RBRACE}),
            )
            return ASTNode(
                SyntaxNodeType.VAR_DECLARATION,
                value=f"{identifier.lexeme}[{size.lexeme}]",
                children=[type_node],
                line=identifier.line,
                column=identifier.column,
            )

        return self.choice(
            "var_declaration",
            [array_var_declaration, scalar_var_declaration],
            frozenset(set(DECLARATION_STARTS) | set(STATEMENT_STARTS) | {TokenType.RBRACE}),
        )

    def type_specifier(self) -> ASTNode:
        """type_specifier -> INT | VOID"""
        def token_node(token_type: TokenType) -> ASTNode:
            token = self.match(token_type, "type_specifier", frozenset({TokenType.ID}))
            return ASTNode(SyntaxNodeType.TYPE_SPECIFIER, value=token.lexeme, line=token.line, column=token.column)

        return self.choice(
            "type_specifier",
            [
                lambda: token_node(TokenType.INT),
                lambda: token_node(TokenType.VOID),
            ],
            frozenset({TokenType.ID, TokenType.ENDFILE}),
        )

    def fun_declaration(self) -> ASTNode:
        """fun_declaration -> type_specifier ID LPAREN params RPAREN compound_stmt"""
        type_node = self.type_specifier()
        identifier = self.match(TokenType.ID, "fun_declaration", frozenset({TokenType.LPAREN}))
        self.match(TokenType.LPAREN, "fun_declaration", frozenset(set(TYPE_SPECIFIERS) | {TokenType.RPAREN}))
        params_node = self.params()
        self.match(TokenType.RPAREN, "fun_declaration", frozenset({TokenType.LBRACE}))
        compound_node = self.compound_stmt()
        return ASTNode(
            SyntaxNodeType.FUN_DECLARATION,
            value=identifier.lexeme,
            children=[type_node, params_node, compound_node],
            line=identifier.line,
            column=identifier.column,
        )

    def params(self) -> ASTNode:
        """params -> param_list | VOID"""
        def void_params() -> ASTNode:
            void_token = self.match(TokenType.VOID, "params", frozenset({TokenType.RPAREN}))
            return ASTNode(SyntaxNodeType.PARAMS, value=void_token.lexeme, line=void_token.line, column=void_token.column)

        return self.choice(
            "params",
            [
                lambda: ASTNode(SyntaxNodeType.PARAMS, children=[self.param_list()]),
                void_params,
            ],
            frozenset({TokenType.RPAREN, TokenType.ENDFILE}),
        )

    def param_list(self) -> ASTNode:
        """param_list -> param param_list_prime"""
        return ASTNode(SyntaxNodeType.PARAM_LIST, children=[self.param(), self.param_list_prime()])

    def param_list_prime(self) -> ASTNode:
        """param_list_prime -> COMMA param param_list_prime | empty"""
        return self.choice(
            "param_list_prime",
            [
                lambda: (
                    self.match(TokenType.COMMA, "param_list_prime", TYPE_SPECIFIERS), 
                    ASTNode(SyntaxNodeType.PARAM_LIST_PRIME, children=[self.param(), self.param_list_prime()],
                ))[-1],
                lambda: ASTNode(SyntaxNodeType.PARAM_LIST_PRIME, children=[self.empty()]),
            ],
            frozenset({TokenType.RPAREN}),
        )

    def param(self) -> ASTNode:
        """param -> type_specifier ID | type_specifier ID LBRACKET RBRACKET"""
        def scalar_param() -> ASTNode:
            type_node = self.type_specifier()
            identifier = self.match(TokenType.ID, "param", frozenset({TokenType.COMMA, TokenType.RPAREN}))
            return ASTNode(
                SyntaxNodeType.PARAM,
                value=identifier.lexeme,
                children=[type_node],
                line=identifier.line,
                column=identifier.column,
            )

        def array_param() -> ASTNode:
            type_node = self.type_specifier()
            identifier = self.match(TokenType.ID, "param", frozenset({TokenType.LBRACKET}))
            self.match(TokenType.LBRACKET, "param", frozenset({TokenType.RBRACKET}))
            self.match(TokenType.RBRACKET, "param", frozenset({TokenType.COMMA, TokenType.RPAREN}))
            return ASTNode(
                SyntaxNodeType.PARAM,
                value=f"{identifier.lexeme}[]",
                children=[type_node],
                line=identifier.line,
                column=identifier.column,
            )

        return self.choice(
            "param",
            [array_param, scalar_param],
            frozenset({TokenType.COMMA, TokenType.RPAREN}),
        )

    def compound_stmt(self) -> ASTNode:
        """compound_stmt -> LBRACE local_declarations statement_list RBRACE"""
        left = self.match(
            TokenType.LBRACE,
            "compound_stmt",
            frozenset(set(DECLARATION_STARTS) | set(STATEMENT_STARTS) | {TokenType.RBRACE}),
        )
        local_node = self.local_declarations()
        statement_node = self.statement_list()
        self.match(
            TokenType.RBRACE,
            "compound_stmt",
            frozenset(set(DECLARATION_STARTS) | set(STATEMENT_STARTS) | {TokenType.ENDFILE}),
        )
        return ASTNode(SyntaxNodeType.COMPOUND_STMT, children=[local_node, statement_node], line=left.line, column=left.column)

    def local_declarations(self) -> ASTNode:
        """local_declarations -> local_declarations_prime"""
        return ASTNode(SyntaxNodeType.LOCAL_DECLARATIONS, children=[self.local_declarations_prime()])

    def local_declarations_prime(self) -> ASTNode:
        """local_declarations_prime -> var_declaration local_declarations_prime | empty"""
        def var_declaration_tail() -> ASTNode:
            return ASTNode(
                SyntaxNodeType.LOCAL_DECLARATIONS_PRIME,
                children=[self.var_declaration(), self.local_declarations_prime()],
            )

        return self.choice(
            "local_declarations_prime",
            [
                var_declaration_tail,
                lambda: ASTNode(SyntaxNodeType.LOCAL_DECLARATIONS_PRIME, children=[self.empty()]),
            ],
            frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE}),
        )

    def statement_list(self) -> ASTNode:
        """statement_list -> statement_list_prime"""
        return ASTNode(SyntaxNodeType.STATEMENT_LIST, children=[self.statement_list_prime()])

    def statement_list_prime(self) -> ASTNode:
        """statement_list_prime -> statement statement_list_prime | empty"""
        def statement_tail() -> ASTNode:
            return ASTNode(
                SyntaxNodeType.STATEMENT_LIST_PRIME,
                children=[self.statement(), self.statement_list_prime()],
            )

        return self.choice(
            "statement_list_prime",
            [
                statement_tail,
                lambda: ASTNode(SyntaxNodeType.STATEMENT_LIST_PRIME, children=[self.empty()]),
            ],
            frozenset({TokenType.RBRACE, TokenType.ENDFILE}),
        )

    def statement(self) -> ASTNode:
        """statement -> expression_stmt | compound_stmt | selection_stmt | iteration_stmt | return_stmt"""
        return ASTNode(
            SyntaxNodeType.STATEMENT,
            children=[
                self.choice(
                    "statement",
                    [self.expression_stmt, self.compound_stmt, self.selection_stmt, self.iteration_stmt, self.return_stmt],
                    frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE, TokenType.ENDFILE}),
                )
            ],
        )

    def expression_stmt(self) -> ASTNode:
        """expression_stmt -> expression SEMI | SEMI"""
        def expression_semicolon() -> ASTNode:
            expression_node = self.expression()
            self.match(TokenType.SEMI, "expression_stmt", frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE}))
            return ASTNode(SyntaxNodeType.EXPRESSION_STMT, children=[expression_node])

        def semicolon_only() -> ASTNode:
            semi = self.match(TokenType.SEMI, "expression_stmt", STATEMENT_STARTS | {TokenType.RBRACE})
            return ASTNode(SyntaxNodeType.EXPRESSION_STMT, value=semi.lexeme, line=semi.line, column=semi.column)

        return self.choice(
            "expression_stmt",
            [expression_semicolon, semicolon_only],
            frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE}),
        )

    def selection_stmt(self) -> ASTNode:
        """selection_stmt -> IF LPAREN expression RPAREN statement | IF LPAREN expression RPAREN statement ELSE statement"""
        def if_else_statement() -> ASTNode:
            if_token = self.match(TokenType.IF, "selection_stmt", frozenset({TokenType.LPAREN}))
            self.match(TokenType.LPAREN, "selection_stmt", EXPRESSION_STARTS)
            condition = self.expression()
            self.match(TokenType.RPAREN, "selection_stmt", STATEMENT_STARTS)
            then_statement = self.statement()
            self.match(TokenType.ELSE, "selection_stmt", STATEMENT_STARTS)
            else_statement = self.statement()
            return ASTNode(
                SyntaxNodeType.SELECTION_STMT,
                children=[condition, then_statement, else_statement],
                line=if_token.line,
                column=if_token.column,
            )

        def if_statement() -> ASTNode:
            if_token = self.match(TokenType.IF, "selection_stmt", frozenset({TokenType.LPAREN}))
            self.match(TokenType.LPAREN, "selection_stmt", EXPRESSION_STARTS)
            condition = self.expression()
            self.match(TokenType.RPAREN, "selection_stmt", STATEMENT_STARTS)
            then_statement = self.statement()
            return ASTNode(
                SyntaxNodeType.SELECTION_STMT,
                children=[condition, then_statement],
                line=if_token.line,
                column=if_token.column,
            )

        return self.choice(
            "selection_stmt",
            [
                if_else_statement,
                if_statement,
            ],
            frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE, TokenType.ENDFILE}),
        )

    def iteration_stmt(self) -> ASTNode:
        """iteration_stmt -> WHILE LPAREN expression RPAREN statement"""
        while_token = self.match(TokenType.WHILE, "iteration_stmt", frozenset({TokenType.LPAREN}))
        self.match(TokenType.LPAREN, "iteration_stmt", EXPRESSION_STARTS)
        condition = self.expression()
        self.match(TokenType.RPAREN, "iteration_stmt", STATEMENT_STARTS)
        body = self.statement()
        return ASTNode(SyntaxNodeType.ITERATION_STMT, children=[condition, body], line=while_token.line, column=while_token.column)

    def return_stmt(self) -> ASTNode:
        """return_stmt -> RETURN SEMI | RETURN expression SEMI"""
        def return_expression() -> ASTNode:
            return_token = self.match(TokenType.RETURN, "return_stmt", frozenset(set(EXPRESSION_STARTS) | {TokenType.SEMI}))
            expression_node = self.expression()
            self.match(TokenType.SEMI, "return_stmt", frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE}))
            return ASTNode(SyntaxNodeType.RETURN_STMT, children=[expression_node], line=return_token.line, column=return_token.column)

        def return_semicolon() -> ASTNode:
            return_token = self.match(TokenType.RETURN, "return_stmt", frozenset({TokenType.SEMI}))
            self.match(TokenType.SEMI, "return_stmt", STATEMENT_STARTS | {TokenType.RBRACE})
            return ASTNode(SyntaxNodeType.RETURN_STMT, line=return_token.line, column=return_token.column)

        return self.choice(
            "return_stmt",
            [return_expression, return_semicolon],
            frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE}),
        )

    def expression(self) -> ASTNode:
        """expression -> var ASSIGN expression | simple_expression"""
        def assignment_expression() -> ASTNode:
            var_node = self.var()
            assign_token = self.match(TokenType.ASSIGN, "expression", EXPRESSION_STARTS)
            expression_node = self.expression()
            return ASTNode(
                SyntaxNodeType.EXPRESSION,
                value=assign_token.lexeme,
                children=[var_node, expression_node],
                line=assign_token.line,
                column=assign_token.column,
            )

        return self.choice(
            "expression",
            [
                assignment_expression,
                lambda: ASTNode(SyntaxNodeType.EXPRESSION, children=[self.simple_expression()]),
            ],
            frozenset({TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
        )

    def var(self) -> ASTNode:
        """var -> ID | ID LBRACKET expression RBRACKET"""
        def scalar_var() -> ASTNode:
            identifier = self.match(
                TokenType.ID,
                "var",
                frozenset(set(ADDOPS) | set(MULOPS) | set(RELOPS) | {TokenType.ASSIGN, TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
            )
            return ASTNode(SyntaxNodeType.VAR, value=identifier.lexeme, line=identifier.line, column=identifier.column)

        def array_var() -> ASTNode:
            identifier = self.match(TokenType.ID, "var", frozenset({TokenType.LBRACKET}))
            self.match(TokenType.LBRACKET, "var", EXPRESSION_STARTS)
            index = self.expression()
            self.match(
                TokenType.RBRACKET,
                "var",
                frozenset(set(ADDOPS) | set(MULOPS) | set(RELOPS) | {TokenType.ASSIGN, TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
            )
            return ASTNode(SyntaxNodeType.VAR, value=f"{identifier.lexeme}[]", children=[index], line=identifier.line, column=identifier.column)

        return self.choice(
            "var",
            [array_var, scalar_var],
            frozenset(set(ADDOPS) | set(MULOPS) | set(RELOPS) | {TokenType.ASSIGN, TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
        )

    def simple_expression(self) -> ASTNode:
        """simple_expression -> additive_expression simple_expression_prime"""
        return ASTNode(SyntaxNodeType.SIMPLE_EXPRESSION, children=[self.additive_expression(), self.simple_expression_prime()])

    def simple_expression_prime(self) -> ASTNode:
        """simple_expression_prime -> relop additive_expression | empty"""
        return self.choice(
            "simple_expression_prime",
            [
                lambda: ASTNode(SyntaxNodeType.SIMPLE_EXPRESSION_PRIME, children=[self.relop(), self.additive_expression()]),
                lambda: ASTNode(SyntaxNodeType.SIMPLE_EXPRESSION_PRIME, children=[self.empty()]),
            ],
            frozenset({TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
        )

    def relop(self, fn_name="relop") -> ASTNode:
        """relop -> LTE | LT | GT | GTE | EQ | NEQ"""
        return self.choice(
            fn_name,
            [
                lambda: self.operator_node(SyntaxNodeType.RELOP, TokenType.LTE, fn_name),
                lambda: self.operator_node(SyntaxNodeType.RELOP, TokenType.LT, fn_name),
                lambda: self.operator_node(SyntaxNodeType.RELOP, TokenType.GT, fn_name),
                lambda: self.operator_node(SyntaxNodeType.RELOP, TokenType.GTE, fn_name),
                lambda: self.operator_node(SyntaxNodeType.RELOP, TokenType.EQ, fn_name),
                lambda: self.operator_node(SyntaxNodeType.RELOP, TokenType.NEQ, fn_name),
            ],
            frozenset(EXPRESSION_STARTS),
        )

    def additive_expression(self) -> ASTNode:
        """additive_expression -> term additive_expression_prime"""
        return ASTNode(SyntaxNodeType.ADDITIVE_EXPRESSION, children=[self.term(), self.additive_expression_prime()])

    def additive_expression_prime(self) -> ASTNode:
        """additive_expression_prime -> addop term additive_expression_prime | empty"""
        return self.choice(
            "additive_expression_prime",
            [
                lambda:  ASTNode(SyntaxNodeType.ADDITIVE_EXPRESSION_PRIME, children=[self.addop(), self.term(), self.additive_expression_prime()]),
                lambda: ASTNode(SyntaxNodeType.ADDITIVE_EXPRESSION_PRIME, children=[self.empty()]),
            ],
            frozenset(set(RELOPS) | {TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
        )

    def addop(self, fn_name="addop") -> ASTNode:
        """addop -> PLUS | MINUS"""
        return self.choice(
            fn_name,
            [
                lambda: self.operator_node(SyntaxNodeType.ADDOP, TokenType.PLUS, fn_name),
                lambda: self.operator_node(SyntaxNodeType.ADDOP, TokenType.MINUS, fn_name),
            ],
            frozenset(EXPRESSION_STARTS),
        )

    def term(self) -> ASTNode:
        """term -> factor term_prime"""
        return ASTNode(SyntaxNodeType.TERM, children=[self.factor(), self.term_prime()])

    def term_prime(self) -> ASTNode:
        """term_prime -> mulop factor term_prime | empty"""
        def mulop_tail() -> ASTNode:
            return ASTNode(
                SyntaxNodeType.TERM_PRIME,
                children=[self.mulop(), self.factor(), self.term_prime()],
            )

        return self.choice(
            "term_prime",
            [
                lambda: ASTNode(SyntaxNodeType.TERM_PRIME, children=[self.mulop(), self.factor(), self.term_prime()]),
                lambda: ASTNode(SyntaxNodeType.TERM_PRIME, children=[self.empty()]),
            ],
            frozenset(set(ADDOPS) | set(RELOPS) | {TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
        )

    def mulop(self) -> ASTNode:
        """mulop -> TIMES | OVER"""
        return self.choice(
            "mulop",
            [
                lambda: self.operator_node(SyntaxNodeType.MULOP, TokenType.TIMES, "mulop"),
                lambda: self.operator_node(SyntaxNodeType.MULOP, TokenType.OVER, "mulop"),
            ],
            frozenset(EXPRESSION_STARTS),
        )

    def factor(self) -> ASTNode:
        """factor -> LPAREN expression RPAREN | var | call | NUM"""
        def grouped_expression() -> ASTNode:
            left = self.match(TokenType.LPAREN, "factor", EXPRESSION_STARTS)
            expression_node = self.expression()
            self.match(
                TokenType.RPAREN,
                "factor",
                frozenset(set(ADDOPS) | set(MULOPS) | set(RELOPS) | {TokenType.SEMI, TokenType.COMMA, TokenType.RBRACKET, TokenType.RPAREN}),
            )
            return ASTNode(SyntaxNodeType.FACTOR, value="()", children=[expression_node], line=left.line, column=left.column)

        def number_factor() -> ASTNode:
            number = self.match(TokenType.NUM, "factor")
            return ASTNode(SyntaxNodeType.FACTOR, value=number.lexeme, line=number.line, column=number.column)

        return self.choice(
            "factor",
            [
                grouped_expression,
                lambda: ASTNode(SyntaxNodeType.FACTOR, children=[self.call()]),
                lambda: ASTNode(SyntaxNodeType.FACTOR, children=[self.var()]),
                number_factor,
            ],
            frozenset(set(ADDOPS) | set(MULOPS) | set(RELOPS) | {TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
        )

    def call(self) -> ASTNode:
        """call -> ID LPAREN args RPAREN"""
        identifier = self.match(TokenType.ID, "call", frozenset({TokenType.LPAREN}))
        self.match(TokenType.LPAREN, "call", frozenset(set(EXPRESSION_STARTS) | {TokenType.RPAREN}))
        args_node = self.args()
        self.match(
            TokenType.RPAREN,
            "call",
            frozenset(set(ADDOPS) | set(MULOPS) | set(RELOPS) | {TokenType.SEMI, TokenType.COMMA, TokenType.RBRACKET, TokenType.RPAREN}),
        )
        return ASTNode(SyntaxNodeType.CALL, value=identifier.lexeme, children=[args_node], line=identifier.line, column=identifier.column)

    def args(self) -> ASTNode:
        """args -> arg_list | empty"""
        return self.choice(
            "args",
            [
                lambda: ASTNode(SyntaxNodeType.ARGS, children=[self.arg_list()]),
                lambda: ASTNode(SyntaxNodeType.ARGS, children=[self.empty()]),
            ],
            frozenset({TokenType.RPAREN}),
        )

    def arg_list(self) -> ASTNode:
        """arg_list -> expression arg_list_prime"""
        return ASTNode(SyntaxNodeType.ARG_LIST, children=[self.expression(), self.arg_list_prime()])

    def arg_list_prime(self) -> ASTNode:
        """arg_list_prime -> COMMA expression arg_list_prime | empty"""
        def comma_expression_tail() -> ASTNode:
            self.match(TokenType.COMMA, "arg_list_prime", EXPRESSION_STARTS)
            return ASTNode(
                SyntaxNodeType.ARG_LIST_PRIME,
                children=[self.expression(), self.arg_list_prime()],
            )

        return self.choice(
            "arg_list_prime",
            [
                comma_expression_tail,
                lambda: ASTNode(SyntaxNodeType.ARG_LIST_PRIME, children=[self.empty()]),
            ],
            frozenset({TokenType.RPAREN}),
        )

    def operator_node(self, node_type: SyntaxNodeType, token_type: TokenType, context: str) -> ASTNode:
        """Build a grammar node whose value is a consumed operator terminal."""
        token = self.match(token_type, context, EXPRESSION_STARTS)
        return ASTNode(node_type, value=token.lexeme, line=token.line, column=token.column)


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
