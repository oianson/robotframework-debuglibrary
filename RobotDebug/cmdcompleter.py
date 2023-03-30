import re

from prompt_toolkit.completion import Completer, Completion
from robot.libraries.BuiltIn import BuiltIn
from robot.parsing.parser.parser import _tokens_to_statements

from .lexer import get_robot_token, get_variable_token
from .prompttoolkitcmd import set_toolbar_key
from .robotkeyword import normalize_kw
from .styles import _get_style_completions


def find_token_at_cursor(cursor_col, cursor_row, statement):
    statement_type = None
    for token in statement.tokens:
        if token.type in ["KEYWORD", "IF", "FOR", "ELSE", "ELSE IF"]:
            statement_type = token.type
        if (
            token.lineno == cursor_row + 1
            and token.col_offset <= cursor_col <= token.end_col_offset
        ):
            return statement_type, token, cursor_col - token.col_offset
    return None, None, None


def find_statement_details_at_cursor(cursor_col, cursor_row, statements):
    for statement in statements:
        if not statement:
            continue
        if (
            statement.lineno <= cursor_row + 1 <= statement.end_lineno
            and statement.col_offset <= cursor_col <= statement.end_col_offset
        ):
            statement_type, token, cursor_pos = find_token_at_cursor(
                cursor_col, cursor_row, statement
            )
            if token:
                return statement, statement_type, token, cursor_pos
    return None, None, None, None


class CmdCompleter(Completer):
    """Completer for debug shell."""

    def __init__(self, commands, cmd_repl=None):
        self.names = []
        self.displays = {}
        self.display_metas = {}
        for name, display, display_meta in commands:
            self.names.append(name)
            self.displays[name] = display
            self.display_metas[name] = display_meta
        self.cmd_repl = cmd_repl

    def _get_command_completions(self, text):
        content = text.strip().split("  ")[-1].lower().strip()
        suffix_len = len(text) - len(text.rstrip())
        return (
            Completion(
                f"{name}{' ' * suffix_len}",
                -len(content),
                display=self.displays.get(name, ""),
                display_meta=self.display_metas.get(name, ""),
            )
            for name in self.names
            if (
                (("." not in name and "." not in text) or ("." in name and "." in text))
                and normalize_kw(name).startswith(normalize_kw(content))
            )  # root level  # library level
        )

    def _get_resource_completions(self, text):
        return (
            Completion(
                name,
                -len(text.lstrip()),
                display=name,
                display_meta="",
            )
            for name in [
                "*** Settings ***",
                "*** Variables ***",
                "*** Keywords ***",
            ]
            if (name.lower().strip().startswith(text.strip()))
        )

    def get_completions(self, document, complete_event):
        """Compute suggestions."""
        # RobotFrameworkLocalLexer().parse_doc(document)
        text = document.current_line_before_cursor
        cursor_col = document.cursor_position_col
        cursor_row = document.cursor_position_row
        token_list = list(get_robot_token(document.text))
        statements = list(_tokens_to_statements(token_list))
        statement, statement_type, token, cursor_pos = find_statement_details_at_cursor(
            cursor_col, cursor_row, statements
        )

        # variables, keyword, args = parse_keyword(text.strip())
        if "FOR".startswith(text):
            yield from [
                Completion(
                    "FOR    ${var}    IN    @{list}\n    Log    ${var}\nEND",
                    -len(text),
                    display="FOR IN",
                    display_meta="For-Loop over all items in a list",
                ),
                Completion(
                    "FOR    ${var}    IN RANGE    5\n    Log    ${var}\nEND",
                    -len(text),
                    display="FOR IN RANGE",
                    display_meta="For-Loop over a range of numbers",
                ),
                Completion(
                    "FOR    ${index}    ${var}    IN ENUMERATE"
                    "    @{list}\n    Log    ${index} - ${var}n\nEND",
                    -len(text),
                    display="FOR IN ENUMERATE",
                    display_meta="For-Loop over all items in a list with index",
                ),
            ]
        elif "IF".startswith(text):
            yield from [
                Completion(
                    "IF    <py-eval>    Log    None",
                    -len(text),
                    display="IF (one line)",
                    display_meta="If-Statement as one line",
                ),
                Completion(
                    "IF    <py-eval>\n    Log    if-branche\nEND",
                    -len(text),
                    display="IF (multi line)",
                    display_meta="If-Statement as multi line",
                ),
            ]
        elif re.fullmatch(r"style {2,}.*", text):
            yield from _get_style_completions(text.lower())
        elif text.startswith("*"):
            yield from self._get_resource_completions(text.lower())
        elif token:
            for var in list(get_variable_token([token])):
                if var.col_offset <= cursor_col <= var.end_col_offset:
                    token = var
                    cursor_pos = cursor_col - var.col_offset
            set_toolbar_key(statement_type, token, cursor_pos)
            if token.type in ["ASSIGN", "VARIABLE"] or (
                token.type == "KEYWORD" and re.fullmatch(r"[$&@]\{[^}]*}", token.value)
            ):
                yield from [
                    Completion(
                        f"{var[:-1]}",
                        -cursor_pos,
                        display=var,
                        display_meta=repr(val),
                    )
                    for var, val in BuiltIn().get_variables().items()
                    if normalize_kw(var[1:]).startswith(normalize_kw(token.value[1:cursor_pos]))
                ]
            elif token.type == "KEYWORD":
                yield from self._get_command_completions(token.value.lower())
