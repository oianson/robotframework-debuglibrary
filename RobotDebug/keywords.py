import sys

from robot.libraries.BuiltIn import BuiltIn

from .debugcmd import DebugCmd
from .steplistener import RobotLibraryStepListenerMixin, is_step_mode
from .styles import print_output


class DebugKeywords(RobotLibraryStepListenerMixin):
    """Debug Keywords for RobotFramework."""

    def Library(self, name, *args):
        BuiltIn().import_library(name, *args)

    def Resource(self, path):
        BuiltIn().import_resource(path)

    def Variables(self, path, *args):
        BuiltIn().import_variables(path, *args)

    def debug(self):
        """Open a interactive shell, run any RobotFramework keywords.

        Keywords separated by two space or one tab, and Ctrl-D to exit.
        """
        # re-wire stdout so that we can use the cmd module and have readline
        # support
        old_stdout = sys.stdout
        sys.stdout = sys.__stdout__
        try:
            show_intro = not is_step_mode()
            if show_intro:
                print_output("\n>>>>>", "Enter interactive shell")

            self.debug_cmd = DebugCmd()
            if show_intro:
                self.debug_cmd.cmdloop()
            else:
                self.debug_cmd.cmdloop(intro="")

            show_intro = not is_step_mode()
            if show_intro:
                print_output("\n>>>>>", "Exit shell.")
        finally:
            # put stdout back where it was
            sys.stdout = old_stdout
