import re
from typing import Tuple, List

from robot.libraries.BuiltIn import BuiltIn
from robot.variables.search import is_variable

from .robotlib import ImportedLibraryDocBuilder, get_libs
from .robotvar import assign_variable

KEYWORD_SEP = re.compile("  +|\t")

_lib_keywords_cache = {}


def parse_keyword(command) -> Tuple[List[str], str, List[str]]:
    """Split a robotframework keyword string."""
    # TODO use robotframework functions
    variables = []
    keyword = ""
    args = []
    parts = KEYWORD_SEP.split(command)
    for part in parts:
        if not keyword and is_variable(part.rstrip("=").strip()):
            variables.append(part.rstrip("=").strip())
        elif not keyword:
            keyword = part
        else:
            args.append(part)
    return variables, keyword, args


def get_lib_keywords(library):
    """Get keywords of imported library."""
    if library.name in _lib_keywords_cache:
        return _lib_keywords_cache[library.name]

    lib = ImportedLibraryDocBuilder().build(library)
    keywords = []
    for keyword in lib.keywords:
        keywords.append(
            {
                "name": keyword.name,
                "lib": library.name,
                "doc": keyword.doc,
                "summary": keyword.doc.split("\n")[0],
            }
        )

    _lib_keywords_cache[library.name] = keywords
    return keywords


def get_keywords():
    """Get all keywords of libraries."""
    for lib in get_libs():
        yield from get_lib_keywords(lib)


def find_keyword(keyword_name):
    keyword_name = keyword_name.lower()
    return [
        keyword
        for lib in get_libs()
        for keyword in get_lib_keywords(lib)
        if keyword["name"].lower() == keyword_name
    ]


def _execute_variable(robot_instance: BuiltIn, variables, keyword, args) -> List[Tuple[str, str]]:
    if not keyword:
        logs = []
        for variable in variables:
            value = robot_instance.get_variable_value(variable)
            logs.append(("#", f"{variable} = {value!r}"))
        return logs
    else:
        return_values = robot_instance.run_keyword(keyword, *args)
        if len(variables) == 1:
            robot_instance.set_local_variable(variables[0], return_values)
            return [("#", f"{variables[0]} = {return_values!r}")]
        logs = []
        for variable, value in zip(variables, return_values):
            robot_instance.set_local_variable(variable, value)
            logs.append(("#", f"{variable} = {value!r}"))
        return logs


def run_keyword(robot_instance, keyword) -> List[Tuple[str, str]]:
    """Run a keyword in robotframewrk environment."""
    if not keyword:
        return []

    variables, keyword, args = parse_keyword(keyword)

    is_comment = keyword.strip().startswith("#")
    if is_comment:
        return []

    if variables:
        return _execute_variable(robot_instance, variables, keyword, args)
    else:
        output = robot_instance.run_keyword(keyword, *args)
        if output is not None:
            return [("<", repr(output))]
        else:
            return []


def run_debug_if(condition, *args):
    """Runs DEBUG if condition is true."""

    return BuiltIn().run_keyword_if(condition, "RobotDebug.DEBUG", *args)
