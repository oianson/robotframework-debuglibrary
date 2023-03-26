import cmd
import os
import re

from prompt_toolkit import HTML
from prompt_toolkit.application import get_app
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.clipboard.pyperclip import PyperclipClipboard
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.filters import (
    Condition,
    has_completions,
    has_selection,
    in_paste_mode,
    is_multiline,
)
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.shortcuts import CompleteStyle, prompt
from pygments.lexer import Lexer
from pygments.lexers.robotframework import (
    ARGUMENT,
    GHERKIN,
    KEYWORD,
    SEPARATOR,
    SYNTAX,
    RowSplitter,
    Tokenizer,
    VariableTokenizer,
    _Table,
)

from .robotkeyword import get_rprompt_text


class KeywordCall(Tokenizer):
    _tokens = (KEYWORD, ARGUMENT)
    _gherkin_prefix = re.compile("^(Given|When|Then|And|But) ", re.IGNORECASE)

    def __init__(self):
        Tokenizer.__init__(self)
        self._keyword_found = False
        self._assigns = 0

    def _tokenize(self, value, index):
        match = self._gherkin_prefix.match(value)
        if not self._keyword_found and match:
            end = match.end()
            self._keyword_found = True
            return [(value[:end], GHERKIN), (value[end:], KEYWORD)]
        if not self._keyword_found and self._is_assign(value):
            self._assigns += 1
            return SYNTAX  # VariableTokenizer tokenizes this later.
        if self._keyword_found:
            return Tokenizer._tokenize(self, value, index - self._assigns)
        self._keyword_found = True
        return [(value, KEYWORD)]


class TestCaseTable(_Table):
    _test_template = None
    _default_template = None
    _gherkin_found = False

    @property
    def _tokenizer_class(self):
        return KeywordCall

    def _continues(self, value, index):
        return index > 0 and _Table._continues(self, value, index)

    def _tokenize(self, value, index):
        if index == 0 and self._is_empty(value):
            return [(value, SYNTAX)]
        return _Table._tokenize(self, value, index)


class RowTokenizer:
    def __init__(self):
        self._table = TestCaseTable()
        self._splitter = RowSplitter()

    def tokenize(self, row):
        for index, value in enumerate(self._splitter.split(row)):
            # First value, and every second after that, is a separator.
            index, separator = divmod(index - 1, 2)
            yield from self._tokenize(value, index, separator)
        self._table.end_row()

    def _tokenize(self, value, index, separator):
        if separator:
            yield value, SEPARATOR
        else:
            yield from self._table.tokenize(value, index)


class RobotFrameworkLexer(Lexer):
    """
    For Robot Framework test data.

    Supports both space and pipe separated plain text formats.

    .. versionadded:: 1.6
    """

    name = "RobotFramework"
    url = "http://robotframework.org"
    aliases = ["robotframework"]
    filenames = ["*.robot", "*.resource"]
    mimetypes = ["text/x-robotframework"]

    def __init__(self, **options):
        options["tabsize"] = 2
        options["encoding"] = "UTF-8"
        Lexer.__init__(self, **options)

    def get_tokens_unprocessed(self, text):
        index = 0
        # for row in text.splitlines():
        for value, token in RowTokenizer().tokenize(text):
            for value, token in VariableTokenizer().tokenize(value, token):
                if value:
                    yield index, token, str(value)
                    index += len(value)


kb = KeyBindings()


@kb.add("c-space")
def _(event):
    """
    Start auto completion. If the menu is showing already, select the next
    completion.
    """
    b: Buffer = event.app.current_buffer
    if b.complete_state:
        b.complete_next()
    else:
        b.start_completion(select_first=False)


@kb.add("escape", filter=has_completions)
def _(event):
    """
    Closes auto completion.
    """
    b: Buffer = event.app.current_buffer
    b.cancel_completion()


@kb.add("escape", filter=~has_completions | ~has_selection)
def _(event):
    b: Buffer = event.app.current_buffer
    b.reset()


@kb.add("tab")
def _(event):
    """
    Accepts completion.
    """
    b: Buffer = event.app.current_buffer
    if b.complete_state:
        completion = b.complete_state.current_completion
        if completion:
            b.apply_completion(completion)
        else:
            b.cancel_completion()
    else:
        b.insert_text("    ")


@kb.add("enter")
def _(event):
    """
    Closes auto completion.
    """
    b: Buffer = event.app.current_buffer
    if b.complete_state:
        completion = b.complete_state.current_completion
        if completion:
            b.apply_completion(completion)
        else:
            b.cancel_completion()
    else:
        if re.fullmatch(r"(FOR|IF|WHILE|TRY|\*\*).*", b.text):
            b.newline(False)
        elif b.cursor_position == len(b.text) and re.fullmatch(r".*\n", b.text, re.DOTALL):
            b.validate_and_handle()
        elif re.search(r"\n", b.text):
            b.newline(False)
        else:
            b.validate_and_handle()


@Condition
def has_line_break():
    b = get_app().current_buffer
    return not re.search(r"\n", b.text)


@kb.add("s-down", filter=has_line_break)
@kb.add("c-down", filter=has_line_break)
def _(event):
    b: Buffer = event.app.current_buffer
    b.newline()


@kb.add("c-insert", filter=has_selection)
@kb.add("c-c", filter=has_selection)
def _(event):
    b: Buffer = event.app.current_buffer
    get_app().clipboard.set_data(b.copy_selection())


@kb.add("c-x", filter=has_selection)
def _(event):
    b: Buffer = event.app.current_buffer
    get_app().clipboard.set_data(b.cut_selection())


@kb.add("c-insert")
@kb.add("c-v")
def _(event):
    b: Buffer = event.app.current_buffer
    data = get_app().clipboard.get_data()
    b.paste_clipboard_data(data)


@kb.add("c-z")
def _(event):
    b: Buffer = event.app.current_buffer
    b.undo()


@kb.add("c-y")
def _(event):
    b: Buffer = event.app.current_buffer
    b.redo()


@kb.add("c-a")
def _(event):
    b: Buffer = event.app.current_buffer
    b.cursor_position = 0
    b.start_selection()
    b.cursor_position = len(b.text)


@kb.add("c-e")
def _(event):
    b: Buffer = event.app.current_buffer
    b.cursor_position = len(b.text)
    b.start_selection()
    b.cursor_position = 0


@kb.add("left", filter=has_selection)
@kb.add("right", filter=has_selection)
@kb.add("up", filter=has_selection)
@kb.add("down", filter=has_selection)
@kb.add("escape", filter=has_selection)
def _(event):
    b: Buffer = event.app.current_buffer
    b.exit_selection()


class BaseCmd(cmd.Cmd):
    """Basic REPL tool."""

    prompt = "> "
    repeat_last_nonempty_command = False

    def emptyline(self):
        """Do not repeat the last command if input empty unless forced to."""
        if self.repeat_last_nonempty_command:
            return super(BaseCmd, self).emptyline()

    def do_exit(self, arg):
        """Exit the interpreter. You can also use the Ctrl-D shortcut."""

        return True

    do_EOF = do_exit

    def help_help(self):
        """Help of Help command"""

        print("Show help message.")

    def do_pdb(self, arg):
        """Enter the python debuger pdb. For development only."""
        print("break into python debugger: pdb")
        import pdb

        pdb.set_trace()

    def get_cmd_names(self):
        """Get all command names of CMD shell."""
        pre = "do_"
        cut = len(pre)
        return [_[cut:] for _ in self.get_names() if _.startswith(pre)]

    def get_help_string(self, command_name):
        """Get help document of command."""
        func = getattr(self, "do_{0}".format(command_name), None)
        if not func:
            return ""
        return func.__doc__

    def get_helps(self):
        """Get all help documents of commands."""
        return [(name, self.get_help_string(name) or name) for name in self.get_cmd_names()]

    def get_completer(self):
        """Get completer instance."""

    def pre_loop_iter(self):
        """Excute before every loop iteration."""

    def _get_input(self):
        if self.cmdqueue:
            return self.cmdqueue.pop(0)
        else:
            try:
                return self.get_input()
            except KeyboardInterrupt:
                return

    def loop_once(self):
        self.pre_loop_iter()
        line = self._get_input()
        if line is None:
            return

        if line == "exit":
            line = "EOF"

        line = self.precmd(line)
        if line == "EOF":
            # do not run 'EOF' command to avoid override 'lastcmd'
            stop = True
        else:
            stop = self.onecmd(line)
        stop = self.postcmd(stop, line)
        return stop

    def cmdloop(self, intro=None):
        """Better command loop.

        override default cmdloop method
        """
        if intro is not None:
            self.intro = intro
        if self.intro:
            self.stdout.write(self.intro)
            self.stdout.write("\n")

        self.preloop()

        stop = None
        while not stop:
            stop = self.loop_once()

        self.postloop()

    def get_input(self):
        return input(prompt=self.prompt)


class PromptToolkitCmd(BaseCmd):
    """CMD shell using prompt-toolkit."""

    get_prompt_tokens = None
    prompt_style = None
    intro = """\
iRobot can interpret single or multiple keyword calls,
as well as FOR, IF, WHILE, TRY
and resource file syntax like *** Keywords*** or *** Variables ***.

Press Shift+ArrowDown to insert a new line.

Type "help" for more information.\
"""

    def __init__(self, completekey="tab", stdin=None, stdout=None, history_path=""):
        BaseCmd.__init__(self, completekey, stdin, stdout)
        self.history = FileHistory(os.path.expanduser(history_path))

    def prompt_continuation(self, width, line_number, is_soft_wrap):
        return " " * width

    def bottom_toolbar(self):
        return [('class:bottom-toolbar-key', 'exit'), ('class:bottom-toolbar', ' to close... ')]

    def get_input(self):
        kwargs = {}
        if self.get_prompt_tokens:
            kwargs["style"] = self.prompt_style
            prompt_str = self.get_prompt_tokens(self.prompt)
        else:
            prompt_str = self.prompt
        try:
            line = prompt(
                auto_suggest=AutoSuggestFromHistory(),
                bottom_toolbar=self.bottom_toolbar,
                clipboard=PyperclipClipboard(),
                color_depth=ColorDepth.DEPTH_24_BIT,
                completer=self.get_completer(),
                complete_style=CompleteStyle.COLUMN,
                cursor=CursorShape.BLINKING_BEAM,
                enable_history_search=True,
                history=self.history,
                include_default_pygments_style=False,
                key_bindings=kb,
                lexer=PygmentsLexer(RobotFrameworkLexer),
                message=prompt_str,
                mouse_support=True,
                prompt_continuation=self.prompt_continuation,
                rprompt=get_rprompt_text(),
                **kwargs
            )
        except EOFError:
            line = "EOF"
        return line
