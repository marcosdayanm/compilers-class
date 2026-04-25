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
        ast = self._program()
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
        # This part will help to recover from an error by looking for an expected token for the grammar that called match() at last
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
        """Try grammar alternatives from left to right, backtracking until one succeeds."""
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

    def _empty(self) -> ASTNode:
        """Build the explicit epsilon node used by productions with an empty alternative."""
        return ASTNode(SyntaxNodeType.EMPTY)

    def _program(self) -> ASTNode:
        """program -> declaration_list"""
        return ASTNode(SyntaxNodeType.PROGRAM, children=[self._declaration_list()])

    def _declaration_list(self) -> ASTNode:
        """declaration_list -> declaration declaration_list_prime"""
        return ASTNode(
            SyntaxNodeType.DECLARATION_LIST,
            children=[self._declaration(), self._declaration_list_prime()],
        )

    def _declaration_list_prime(self, fn_name="declaration_list_prime") -> ASTNode:
        """declaration_list_prime -> declaration declaration_list_prime | empty"""
        return self.choice(
            fn_name,
            [
                lambda: ASTNode(
                    SyntaxNodeType.DECLARATION_LIST_PRIME, children=[self._declaration(), self._declaration_list_prime()]
                ),
                lambda: ASTNode(SyntaxNodeType.DECLARATION_LIST_PRIME, children=[self._empty()]),
            ],
            frozenset({TokenType.ENDFILE}),
        )

    def _declaration(self, fn_name="declaration") -> ASTNode:
        """declaration -> var_declaration | fun_declaration"""
        return ASTNode(
            SyntaxNodeType.DECLARATION,
            children=[
                self.choice(
                    fn_name,
                    [self._var_declaration, self._fun_declaration],
                    frozenset(set(DECLARATION_STARTS) | {TokenType.ENDFILE}),
                )
            ],
        )

    def _var_declaration(self, fn_name="var_declaration") -> ASTNode:
        """var_declaration -> type_specifier ID SEMI | type_specifier ID LBRACKET NUM RBRACKET SEMI"""
        def _scalar_var_declaration() -> ASTNode:
            type_node = self._type_specifier()
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

        def _array_var_declaration() -> ASTNode:
            type_node = self._type_specifier()
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
            [_array_var_declaration, _scalar_var_declaration],
            frozenset(set(DECLARATION_STARTS) | set(STATEMENT_STARTS) | {TokenType.RBRACE}),
        )

    def _type_specifier(self) -> ASTNode:
        """type_specifier -> INT | VOID"""
        def _token_node(token_type: TokenType) -> ASTNode:
            token = self.match(token_type, "type_specifier", frozenset({TokenType.ID}))
            return ASTNode(SyntaxNodeType.TYPE_SPECIFIER, value=token.lexeme, line=token.line, column=token.column)

        return self.choice(
            "type_specifier",
            [
                lambda: _token_node(TokenType.INT),
                lambda: _token_node(TokenType.VOID),
            ],
            frozenset({TokenType.ID, TokenType.ENDFILE}),
        )

    def _fun_declaration(self) -> ASTNode:
        """fun_declaration -> type_specifier ID LPAREN params RPAREN compound_stmt"""
        type_node = self._type_specifier()
        identifier = self.match(TokenType.ID, "fun_declaration", frozenset({TokenType.LPAREN}))
        self.match(TokenType.LPAREN, "fun_declaration", frozenset(set(TYPE_SPECIFIERS) | {TokenType.RPAREN}))
        params_node = self._params()
        self.match(TokenType.RPAREN, "fun_declaration", frozenset({TokenType.LBRACE}))
        compound_node = self._compound_stmt()
        return ASTNode(
            SyntaxNodeType.FUN_DECLARATION,
            value=identifier.lexeme,
            children=[type_node, params_node, compound_node],
            line=identifier.line,
            column=identifier.column,
        )

    def _params(self) -> ASTNode:
        """params -> param_list | VOID"""
        def void_params() -> ASTNode:
            void_token = self.match(TokenType.VOID, "params", frozenset({TokenType.RPAREN}))
            return ASTNode(SyntaxNodeType.PARAMS, value=void_token.lexeme, line=void_token.line, column=void_token.column)

        return self.choice(
            "params",
            [
                lambda: ASTNode(SyntaxNodeType.PARAMS, children=[self._param_list()]),
                void_params,
            ],
            frozenset({TokenType.RPAREN, TokenType.ENDFILE}),
        )

    def _param_list(self) -> ASTNode:
        """param_list -> param param_list_prime"""
        return ASTNode(SyntaxNodeType.PARAM_LIST, children=[self._param(), self._param_list_prime()])

    def _param_list_prime(self) -> ASTNode:
        """param_list_prime -> COMMA param param_list_prime | empty"""
        return self.choice(
            "param_list_prime",
            [
                lambda: (
                    self.match(TokenType.COMMA, "param_list_prime", TYPE_SPECIFIERS), 
                    ASTNode(SyntaxNodeType.PARAM_LIST_PRIME, children=[self._param(), self._param_list_prime()],
                ))[-1],
                lambda: ASTNode(SyntaxNodeType.PARAM_LIST_PRIME, children=[self._empty()]),
            ],
            frozenset({TokenType.RPAREN}),
        )

    def _param(self) -> ASTNode:
        """param -> type_specifier ID | type_specifier ID LBRACKET RBRACKET"""
        def _scalar_param() -> ASTNode:
            type_node = self._type_specifier()
            identifier = self.match(TokenType.ID, "param", frozenset({TokenType.COMMA, TokenType.RPAREN}))
            return ASTNode(
                SyntaxNodeType.PARAM,
                value=identifier.lexeme,
                children=[type_node],
                line=identifier.line,
                column=identifier.column,
            )

        def _array_param() -> ASTNode:
            type_node = self._type_specifier()
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
            [_array_param, _scalar_param],
            frozenset({TokenType.COMMA, TokenType.RPAREN}),
        )

    def _compound_stmt(self) -> ASTNode:
        """compound_stmt -> LBRACE local_declarations statement_list RBRACE"""
        left = self.match(
            TokenType.LBRACE,
            "compound_stmt",
            frozenset(set(DECLARATION_STARTS) | set(STATEMENT_STARTS) | {TokenType.RBRACE}),
        )
        local_node = self._local_declarations()
        statement_node = self._statement_list()
        self.match(
            TokenType.RBRACE,
            "compound_stmt",
            frozenset(set(DECLARATION_STARTS) | set(STATEMENT_STARTS) | {TokenType.ENDFILE}),
        )
        return ASTNode(SyntaxNodeType.COMPOUND_STMT, children=[local_node, statement_node], line=left.line, column=left.column)

    def _local_declarations(self) -> ASTNode:
        """local_declarations -> local_declarations_prime"""
        return ASTNode(SyntaxNodeType.LOCAL_DECLARATIONS, children=[self._local_declarations_prime()])

    def _local_declarations_prime(self) -> ASTNode:
        """local_declarations_prime -> var_declaration local_declarations_prime | empty"""
        return self.choice(
            "local_declarations_prime",
            [
                lambda: ASTNode(
                    SyntaxNodeType.LOCAL_DECLARATIONS_PRIME,
                    children=[self._var_declaration(), self._local_declarations_prime()],
                ),
                lambda: ASTNode(SyntaxNodeType.LOCAL_DECLARATIONS_PRIME, children=[self._empty()]),
            ],
            frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE}),
        )

    def _statement_list(self) -> ASTNode:
        """statement_list -> statement_list_prime"""
        return ASTNode(SyntaxNodeType.STATEMENT_LIST, children=[self._statement_list_prime()])

    def _statement_list_prime(self) -> ASTNode:
        """statement_list_prime -> statement statement_list_prime | empty"""
        return self.choice(
            "statement_list_prime",
            [
                lambda: ASTNode(
                    SyntaxNodeType.STATEMENT_LIST_PRIME,
                    children=[self._statement(), self._statement_list_prime()],
                ),
                lambda: ASTNode(SyntaxNodeType.STATEMENT_LIST_PRIME, children=[self._empty()]),
            ],
            frozenset({TokenType.RBRACE, TokenType.ENDFILE}),
        )

    def _statement(self, fn_name="statement") -> ASTNode:
        """statement -> expression_stmt | compound_stmt | selection_stmt | iteration_stmt | return_stmt"""
        return ASTNode(
            SyntaxNodeType.STATEMENT,
            children=[
                self.choice(
                    fn_name,
                    [self._expression_stmt, self._compound_stmt, self._selection_stmt, self._iteration_stmt, self._return_stmt],
                    frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE, TokenType.ENDFILE}),
                )
            ],
        )

    def _expression_stmt(self, fn_name="expression_stmt") -> ASTNode:
        """expression_stmt -> expression SEMI | SEMI"""
        def expression_semicolon() -> ASTNode:
            expression_node = self._expression()
            self.match(TokenType.SEMI, fn_name, frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE}))
            return ASTNode(SyntaxNodeType.EXPRESSION_STMT, children=[expression_node])

        def semicolon_only() -> ASTNode:
            semi = self.match(TokenType.SEMI, fn_name, STATEMENT_STARTS | {TokenType.RBRACE})
            return ASTNode(SyntaxNodeType.EXPRESSION_STMT, value=semi.lexeme, line=semi.line, column=semi.column)

        return self.choice(
            fn_name,
            [expression_semicolon, semicolon_only],
            frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE}),
        )

    def _selection_stmt(self, fn_name="selection_stmt") -> ASTNode:
        """selection_stmt -> IF LPAREN expression RPAREN statement | IF LPAREN expression RPAREN statement ELSE statement"""
        def _if_else_statement() -> ASTNode:
            if_token = self.match(TokenType.IF, fn_name, frozenset({TokenType.LPAREN}))
            self.match(TokenType.LPAREN, fn_name, EXPRESSION_STARTS)
            condition = self._expression()
            self.match(TokenType.RPAREN, fn_name, STATEMENT_STARTS)
            then_statement = self._statement(fn_name)
            self.match(TokenType.ELSE, fn_name, STATEMENT_STARTS)
            else_statement = self._statement(fn_name)
            return ASTNode(
                SyntaxNodeType.SELECTION_STMT,
                children=[condition, then_statement, else_statement],
                line=if_token.line,
                column=if_token.column,
            )

        def _if_statement() -> ASTNode:
            if_token = self.match(TokenType.IF, fn_name, frozenset({TokenType.LPAREN}))
            self.match(TokenType.LPAREN, fn_name, EXPRESSION_STARTS)
            condition = self._expression()
            self.match(TokenType.RPAREN, fn_name, STATEMENT_STARTS)
            then_statement = self._statement(fn_name)
            return ASTNode(
                SyntaxNodeType.SELECTION_STMT,
                children=[condition, then_statement],
                line=if_token.line,
                column=if_token.column,
            )

        return self.choice(
            fn_name,
            [
                _if_else_statement,
                _if_statement,
            ],
            frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE, TokenType.ENDFILE}),
        )

    def _iteration_stmt(self, fn_name="iteration_stmt") -> ASTNode:
        """iteration_stmt -> WHILE LPAREN expression RPAREN statement"""
        while_token = self.match(TokenType.WHILE, fn_name, frozenset({TokenType.LPAREN}))
        self.match(TokenType.LPAREN, fn_name, EXPRESSION_STARTS)
        condition = self._expression()
        self.match(TokenType.RPAREN, fn_name, STATEMENT_STARTS)
        body = self._statement(fn_name)
        return ASTNode(SyntaxNodeType.ITERATION_STMT, children=[condition, body], line=while_token.line, column=while_token.column)

    def _return_stmt(self, fn_name="return_stmt") -> ASTNode:
        """return_stmt -> RETURN SEMI | RETURN expression SEMI"""
        def return_expression() -> ASTNode:
            return_token = self.match(TokenType.RETURN, fn_name, frozenset(set(EXPRESSION_STARTS) | {TokenType.SEMI}))
            expression_node = self._expression()
            self.match(TokenType.SEMI, fn_name, frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE}))
            return ASTNode(SyntaxNodeType.RETURN_STMT, children=[expression_node], line=return_token.line, column=return_token.column)

        def return_semicolon() -> ASTNode:
            return_token = self.match(TokenType.RETURN, fn_name, frozenset({TokenType.SEMI}))
            self.match(TokenType.SEMI, fn_name, STATEMENT_STARTS | {TokenType.RBRACE})
            return ASTNode(SyntaxNodeType.RETURN_STMT, line=return_token.line, column=return_token.column)

        return self.choice(
            fn_name,
            [return_expression, return_semicolon],
            frozenset(set(STATEMENT_STARTS) | {TokenType.RBRACE}),
        )

    def _expression(self, fn_name="expression") -> ASTNode:
        """expression -> var ASSIGN expression | simple_expression"""
        def assignment_expression() -> ASTNode:
            var_node = self._var()
            assign_token = self.match(TokenType.ASSIGN, fn_name, EXPRESSION_STARTS)
            expression_node = self._expression(fn_name)
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
                lambda: ASTNode(SyntaxNodeType.EXPRESSION, children=[self._simple_expression()]),
            ],
            frozenset({TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
        )

    def _var(self, fn_name="var") -> ASTNode:
        """var -> ID | ID LBRACKET expression RBRACKET"""
        def scalar_var() -> ASTNode:
            identifier = self.match(
                TokenType.ID,
                fn_name,
                frozenset(set(ADDOPS) | set(MULOPS) | set(RELOPS) | {TokenType.ASSIGN, TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
            )
            return ASTNode(SyntaxNodeType.VAR, value=identifier.lexeme, line=identifier.line, column=identifier.column)

        def array_var() -> ASTNode:
            identifier = self.match(TokenType.ID, fn_name, frozenset({TokenType.LBRACKET}))
            self.match(TokenType.LBRACKET, fn_name, EXPRESSION_STARTS)
            index = self._expression(fn_name)
            self.match(
                TokenType.RBRACKET,
                fn_name,
                frozenset(set(ADDOPS) | set(MULOPS) | set(RELOPS) | {TokenType.ASSIGN, TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
            )
            return ASTNode(SyntaxNodeType.VAR, value=f"{identifier.lexeme}[]", children=[index], line=identifier.line, column=identifier.column)

        return self.choice(
            fn_name,
            [array_var, scalar_var],
            frozenset(set(ADDOPS) | set(MULOPS) | set(RELOPS) | {TokenType.ASSIGN, TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
        )

    def _simple_expression(self) -> ASTNode:
        """simple_expression -> additive_expression simple_expression_prime"""
        return ASTNode(SyntaxNodeType.SIMPLE_EXPRESSION, children=[self._additive_expression(), self._simple_expression_prime()])

    def _simple_expression_prime(self) -> ASTNode:
        """simple_expression_prime -> relop additive_expression | empty"""
        return self.choice(
            "simple_expression_prime",
            [
                lambda: ASTNode(SyntaxNodeType.SIMPLE_EXPRESSION_PRIME, children=[self._relop(), self._additive_expression()]),
                lambda: ASTNode(SyntaxNodeType.SIMPLE_EXPRESSION_PRIME, children=[self._empty()]),
            ],
            frozenset({TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
        )

    def _relop(self, fn_name="relop") -> ASTNode:
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

    def _additive_expression(self) -> ASTNode:
        """additive_expression -> term additive_expression_prime"""
        return ASTNode(SyntaxNodeType.ADDITIVE_EXPRESSION, children=[self._term(), self._additive_expression_prime()])

    def _additive_expression_prime(self) -> ASTNode:
        """additive_expression_prime -> addop term additive_expression_prime | empty"""
        return self.choice(
            "additive_expression_prime",
            [
                lambda:  ASTNode(SyntaxNodeType.ADDITIVE_EXPRESSION_PRIME, children=[self._addop(), self._term(), self._additive_expression_prime()]),
                lambda: ASTNode(SyntaxNodeType.ADDITIVE_EXPRESSION_PRIME, children=[self._empty()]),
            ],
            frozenset(set(RELOPS) | {TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
        )

    def _addop(self, fn_name="addop") -> ASTNode:
        """addop -> PLUS | MINUS"""
        return self.choice(
            fn_name,
            [
                lambda: self.operator_node(SyntaxNodeType.ADDOP, TokenType.PLUS, fn_name),
                lambda: self.operator_node(SyntaxNodeType.ADDOP, TokenType.MINUS, fn_name),
            ],
            frozenset(EXPRESSION_STARTS),
        )

    def _term(self) -> ASTNode:
        """term -> factor term_prime"""
        return ASTNode(SyntaxNodeType.TERM, children=[self._factor(), self._term_prime()])

    def _term_prime(self) -> ASTNode:
        """term_prime -> mulop factor term_prime | empty"""
        def mulop_tail() -> ASTNode:
            return ASTNode(
                SyntaxNodeType.TERM_PRIME,
                children=[self._mulop(), self._factor(), self._term_prime()],
            )

        return self.choice(
            "term_prime",
            [
                lambda: ASTNode(SyntaxNodeType.TERM_PRIME, children=[self._mulop(), self._factor(), self._term_prime()]),
                lambda: ASTNode(SyntaxNodeType.TERM_PRIME, children=[self._empty()]),
            ],
            frozenset(set(ADDOPS) | set(RELOPS) | {TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
        )

    def _mulop(self) -> ASTNode:
        """mulop -> TIMES | OVER"""
        return self.choice(
            "mulop",
            [
                lambda: self.operator_node(SyntaxNodeType.MULOP, TokenType.TIMES, "mulop"),
                lambda: self.operator_node(SyntaxNodeType.MULOP, TokenType.OVER, "mulop"),
            ],
            frozenset(EXPRESSION_STARTS),
        )

    def _factor(self) -> ASTNode:
        """factor -> LPAREN expression RPAREN | var | call | NUM"""
        def grouped_expression() -> ASTNode:
            left = self.match(TokenType.LPAREN, "factor", EXPRESSION_STARTS)
            expression_node = self._expression()
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
                lambda: ASTNode(SyntaxNodeType.FACTOR, children=[self._call()]),
                lambda: ASTNode(SyntaxNodeType.FACTOR, children=[self._var()]),
                number_factor,
            ],
            frozenset(set(ADDOPS) | set(MULOPS) | set(RELOPS) | {TokenType.SEMI, TokenType.COMMA, TokenType.RPAREN, TokenType.RBRACKET}),
        )

    def _call(self) -> ASTNode:
        """call -> ID LPAREN args RPAREN"""
        identifier = self.match(TokenType.ID, "call", frozenset({TokenType.LPAREN}))
        self.match(TokenType.LPAREN, "call", frozenset(set(EXPRESSION_STARTS) | {TokenType.RPAREN}))
        args_node = self._args()
        self.match(
            TokenType.RPAREN,
            "call",
            frozenset(set(ADDOPS) | set(MULOPS) | set(RELOPS) | {TokenType.SEMI, TokenType.COMMA, TokenType.RBRACKET, TokenType.RPAREN}),
        )
        return ASTNode(SyntaxNodeType.CALL, value=identifier.lexeme, children=[args_node], line=identifier.line, column=identifier.column)

    def _args(self) -> ASTNode:
        """args -> arg_list | empty"""
        return self.choice(
            "args",
            [
                lambda: ASTNode(SyntaxNodeType.ARGS, children=[self._arg_list()]),
                lambda: ASTNode(SyntaxNodeType.ARGS, children=[self._empty()]),
            ],
            frozenset({TokenType.RPAREN}),
        )

    def _arg_list(self) -> ASTNode:
        """arg_list -> expression arg_list_prime"""
        return ASTNode(SyntaxNodeType.ARG_LIST, children=[self._expression(), self._arg_list_prime()])

    def _arg_list_prime(self) -> ASTNode:
        """arg_list_prime -> COMMA expression arg_list_prime | empty"""
        return self.choice(
            "arg_list_prime",
            [
                lambda: (
                    self.match(TokenType.COMMA, "arg_list_prime", EXPRESSION_STARTS),
                    ASTNode(
                        SyntaxNodeType.ARG_LIST_PRIME,
                        children=[self._expression(), self._arg_list_prime()],
                    )
                )[-1],
                lambda: ASTNode(SyntaxNodeType.ARG_LIST_PRIME, children=[self._empty()]),
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
