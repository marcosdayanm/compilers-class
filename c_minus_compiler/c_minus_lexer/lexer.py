from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from globalTypes import (
    CHAR_TO_INPUT_SYMBOL,
    DIGIT_CHARS,
    FINAL_STATES,
    InputSymbol,
    LETTER_CHARS,
    LexerState,
    NONCONSUMING_FINAL_STATES,
    RESERVED_LOOKUP,
    START_STATE,
    TokenType,
    TRANSITION_TABLE,
    WHITESPACE_CHARS,
)


@dataclass(frozen=True)
class ScanResult:
    token: TokenType | None
    lexeme: str


@dataclass(frozen=True)
class FinalContext:
    """Dataclass that will contain all the information for calling each one of the final state handlers methods by accesing them at runtime by a key."""
    final_state: LexerState
    lexeme: str
    start_line: int
    start_column: int
    token_start_index: int
    num_error_column: int


class Lexer:
    def __init__(self, prog: str, pos: int, long: int) -> None:
        self.program: str = ""
        self.position: int = 0
        self.prog_len: int = 0
        self.curr_line: int = 1
        self.curr_col: int = 1
        self.line_starts: list[int] = [0]
        self._final_state_handlers: dict[LexerState, Callable[[FinalContext], ScanResult]] = {
            LexerState.FINAL_ID: self._handle_id_reserved,
            LexerState.FINAL_INT: self._handle_int,
            LexerState.FINAL_NUM_ERROR: self._handle_num_error,
            LexerState.FINAL_NEQ: self._handle_sign,
            LexerState.FINAL_EQ: self._handle_sign,
            LexerState.FINAL_ASSIGN: self._handle_sign,
            LexerState.FINAL_LTE: self._handle_sign,
            LexerState.FINAL_LT: self._handle_sign,
            LexerState.FINAL_GT: self._handle_sign,
            LexerState.FINAL_GTE: self._handle_sign,
            LexerState.FINAL_SIMPLE_SIGN: self._handle_sign,
            LexerState.FINAL_OVER: self._handle_sign,
            LexerState.FINAL_EXCL_ERROR: self._handle_excl_error,
            LexerState.FINAL_COMMENT: self._handle_comment,
            LexerState.FINAL_COMMENT_ERROR: self._handle_comment_error,
            LexerState.FINAL_EOF: self._handle_eof,
            LexerState.FINAL_GENERIC_ERROR: self._handle_generic_error,
        }
        self._reset(prog, pos, long)

    def tokenize_all(self, print_tokens: bool = False) -> list[tuple[str, TokenType]]:
        tokens: list[tuple[str, TokenType]] = []
        while True:
            token, lexeme = self._get_token(print_tokens)
            tokens.append((lexeme, token))
            if token == TokenType.ENDFILE:
                return tokens

    def _reset(self, prog: str, pos: int, long: int) -> None:
        self.program = prog
        self.position = pos
        self.prog_len = long
        self.curr_line = 1
        self.curr_col = 1
        self.line_starts = [0]
        for idx, char in enumerate(self.program[: self.prog_len]):
            if char == "\n":
                self.line_starts.append(idx + 1)
        self._recalculate_position_coordinates()

    def _get_token(self, print_token: bool = True) -> tuple[TokenType, str]:
        while True:
            result = self._scan_with_dfa()
            if result.token is None:
                continue
            if print_token:
                print(result.token.name, " = ", result.lexeme)
            return result.token, result.lexeme

    def _reserved_lookup(self, token_string: str) -> TokenType:
        return RESERVED_LOOKUP.get(token_string, TokenType.ID)

    def _peek(self, offset: int = 0) -> str:
        index = self.position + offset
        if index >= len(self.program):
            return "$"
        return self.program[index]

    def _advance(self) -> str:
        char = self._peek(0)
        if char == "$":
            return char

        self.position += 1
        if char == "\n":
            self.curr_line += 1
            self.curr_col = 1
        else:
            self.curr_col += 1
        return char

    def _line_slice(self, line_number: int) -> str:
        start = self.line_starts[line_number - 1]
        if line_number < len(self.line_starts):
            end = self.line_starts[line_number] - 1
        else:
            end = self.prog_len
        return self.program[start:end]

    def _print_error(self, message: str, line_number: int, column_number: int) -> None:
        # Rebuild the source line and point to the exact column that triggered the error.
        source_line = self._line_slice(line_number)
        pointer = " " * max(column_number - 1, 0) + "^"
        print(f"Line {line_number}: {message}")
        print(source_line)
        print(pointer)

    def _classify_char(self, char: str) -> InputSymbol:
        if char in LETTER_CHARS:
            return InputSymbol.LETTER
        if char in DIGIT_CHARS:
            return InputSymbol.DIGIT
        if char in WHITESPACE_CHARS:
            return InputSymbol.WHITESPACE
        return CHAR_TO_INPUT_SYMBOL.get(char, InputSymbol.OTHER)

    def _next_state(self, state: LexerState, input_symbol: InputSymbol) -> LexerState:
        transitions = TRANSITION_TABLE[state]
        if input_symbol in transitions:
            return transitions[input_symbol]
        # Most states collapse everything else into OTHER.
        fallback = transitions.get(InputSymbol.OTHER)
        if fallback is None:
            raise RuntimeError(
                f"Scanner bug: missing transition for state={int(state)} and input={input_symbol.name}"
            )
        return fallback

    def _handle_id_reserved(self, context: FinalContext) -> ScanResult:
        return ScanResult(self._reserved_lookup(context.lexeme), context.lexeme)

    def _handle_int(self, context: FinalContext) -> ScanResult:
        return ScanResult(TokenType.NUM, context.lexeme)

    def _handle_num_error(self, context: FinalContext) -> ScanResult:
        self._print_error("Malformed integer.", context.start_line, context.num_error_column)
        return ScanResult(TokenType.ERROR, context.lexeme)

    def _handle_sign(self, context: FinalContext) -> ScanResult:
        return ScanResult(TokenType(context.lexeme), context.lexeme)

    def _handle_excl_error(self, context: FinalContext) -> ScanResult:
        self._print_error("Invalid '!' operator. Expected '!='.", context.start_line, context.start_column)
        return ScanResult(TokenType.ERROR, context.lexeme)

    def _handle_comment(self, context: FinalContext) -> ScanResult:
        del context
        return ScanResult(None, "")

    def _handle_comment_error(self, context: FinalContext) -> ScanResult:
        self._print_error("Unclosed comment.", context.start_line, context.start_column)
        return ScanResult(TokenType.ERROR, context.lexeme)

    def _handle_eof(self, context: FinalContext) -> ScanResult:
        del context
        return ScanResult(TokenType.ENDFILE, "$")

    def _handle_generic_error(self, context: FinalContext) -> ScanResult:
        self._print_error(f"Unexpected symbol '{context.lexeme}'.", context.start_line, context.start_column)
        return ScanResult(TokenType.ERROR, context.lexeme)

    def _dispatch_final_state(self, context: FinalContext) -> ScanResult:
        # Keep final-state behavior out of the scan loop; each final goes through one handler.
        handler = self._final_state_handlers.get(context.final_state)
        if handler is None:
            raise RuntimeError(f"Scanner bug: unhandled final state {int(context.final_state)}")
        return handler(context)

    def _scan_with_dfa(self) -> ScanResult:
        state = START_STATE
        token_start_index = self.position
        start_line = self.curr_line
        start_column = self.curr_col
        num_error_column: int | None = None

        while True:
            current_char = self._peek(0)
            input_symbol = self._classify_char(current_char)
            next_state = self._next_state(state, input_symbol)

            if state == LexerState.START and next_state != LexerState.START:
                # The token starts on the first transition that leaves START.
                token_start_index = self.position
                start_line = self.curr_line
                start_column = self.curr_col

            if state == LexerState.IN_INT and next_state == LexerState.IN_BAD_NUM and num_error_column is None:
                num_error_column = self.curr_col

            # Finals listed here implement the classic lookahead/backtrack step of the DFA.
            consume_char = next_state not in NONCONSUMING_FINAL_STATES
            if consume_char:
                self._advance()

            if next_state in FINAL_STATES:
                lexeme = self.program[token_start_index:self.position]
                return self._dispatch_final_state(
                    FinalContext(
                        final_state=next_state,
                        lexeme=lexeme,
                        start_line=start_line,
                        start_column=start_column,
                        token_start_index=token_start_index,
                        num_error_column=num_error_column if num_error_column is not None else start_column,
                    )
                )

            state = next_state

    def _recalculate_position_coordinates(self) -> None:
        # Used when the runtime is reset with an initial position other than zero.
        line_number = 1
        column_number = 1
        for char in self.program[: self.position]:
            if char == "\n":
                line_number += 1
                column_number = 1
            else:
                column_number += 1
        self.curr_line = line_number
        self.curr_col = column_number


_lexer: Lexer | None = None


def globales(prog: str, pos: int, long: int) -> None:
    # I prefer to use a singleton class instance with all its methods and attributes to keep track of the lexer state, instead of having global variables and separate functions. So I'm preserving this interface so the homework can be graded as specified, but the file internal behavior is implemented with a class.
    global _lexer
    if _lexer is None:
        _lexer = Lexer(prog, pos, long)
    else:
        _lexer._reset(prog, pos, long)


def getToken(imprime: bool = True) -> tuple[TokenType, str]:
    # Using lexer singleton instance private _get_token method (for the full project we will be using Lexer.tokenize_all() instead)
    if _lexer is None:
        raise RuntimeError("The lexer has not been initialized. Call globales() first.")
    return _lexer._get_token(imprime)
