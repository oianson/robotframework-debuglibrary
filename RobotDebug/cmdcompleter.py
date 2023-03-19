import re

from prompt_toolkit.completion import Completer, Completion

from .robotkeyword import parse_keyword


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

    def _get_argument_completions(self, completer, document):
        """Using Cmd.py's completer to complete arguments."""
        end_idx = document.cursor_position_col
        line = document.current_line
        if line[:end_idx].rfind(" ") >= 0:
            begin_idx = line[:end_idx].rfind(" ") + 1
        else:
            begin_idx = 0
        prefix = line[begin_idx:end_idx]

        completions = completer(prefix, line, begin_idx, end_idx)
        for comp in completions:
            yield Completion(comp, begin_idx - end_idx, display=comp)

    def _get_custom_completions(self, cmd_name, document):
        completer = getattr(
            self.cmd_repl,
            "complete_{0}".format(cmd_name),
            None,
        )
        if completer:
            yield from self._get_argument_completions(completer, document)

    def _get_command_completions(self, text):
        prefix_len = len(text) - len(text.lstrip())
        content = text.strip()
        suffix_len = len(text) - len(text.rstrip())
        return (
            Completion(
                f"{name}{' ' * suffix_len}",
                -len(text.lstrip()),
                display=self.displays.get(name, ""),
                display_meta=self.display_metas.get(name, ""),
            )
            for name in self.names
            if (
                (
                    ("." not in name and "." not in text)  # root level
                    or ("." in name and "." in text)
                )  # library level
                and name.lower().strip().startswith(content)
            )
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
        text = document.current_line_before_cursor
        variables, keyword, args = parse_keyword(text.strip())
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
                    "FOR    ${index}    ${var}    IN ENUMERATE    @{list}\n    Log    ${index} - ${var}n\nEND",
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
        elif text.startswith("*"):
            yield from self._get_resource_completions(text.lower())
        elif keyword and not args:
            yield from self._get_command_completions(text.lower())
