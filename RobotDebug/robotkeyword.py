import re
import tempfile
from pathlib import Path
from typing import Tuple, List

from robot.libraries.BuiltIn import BuiltIn
from robot.parsing import get_model, get_resource_model
from robot.running import TestSuite, ResourceFileBuilder
from robot.running.model import If, For, While, Keyword, ResourceFile
from robot.running.builder.transformers import ResourceBuilder
from robot.variables.search import is_variable

from .robotlib import ImportedLibraryDocBuilder, get_libs
from .robotvar import assign_variable

KEYWORD_SEP = re.compile("  +|\t")

_lib_keywords_cache = {}
temp_resources = []


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


def run_command(builtin, command: str) -> List[Tuple[str, str]]:
    """Run a command in robotframewrk environment."""
    if not command:
        return []
    if is_variable(command):
        return [("#", f"{command} = {builtin.get_variable_value(command)!r}")]
    ctx = BuiltIn()._get_context()
    if command.startswith("***"):
        _import_resource_from_string(command)
        return []

    test = get_test_body_from_string(command)
    if len(test.body) > 1:
        for kw in test.body:
            kw.run(ctx)
        return_val = None
    else:
        kw = test.body[0]
        return_val = kw.run(ctx)
    assign = set(_get_assignments(test))
    if not assign and return_val is not None:
        return [("<", repr(return_val))]
    elif assign:
        output = [("<", repr(return_val))] if return_val is not None else []
        for variable in assign:
            variable = variable.rstrip("=").strip()
            val = BuiltIn().get_variable_value(variable)
            output.append(("#", f"{variable} = {val!r}"))
        return output
    else:
        return []


def get_test_body_from_string(command):
    if "\n" in command:
        command = "\n  ".join(command.split("\n"))
    suite_str = f"""
*** Test Cases ***
Fake Test
  {command}
"""
    model = get_model(suite_str)
    suite: TestSuite = TestSuite.from_model(model)
    return suite.tests[0]


def _import_resource_from_string(command):
    with tempfile.NamedTemporaryFile(
        mode="w", prefix="keywords", suffix=".resource", encoding="utf-8"
    ) as res_file:
        res_file.write(command)
        res_file.seek(0)
        global temp_resources
        temp_resources.insert(0, str(Path(res_file.name).stem))
        BuiltIn().import_resource(str(Path(res_file.name).resolve()))
        BuiltIn().set_library_search_order(*temp_resources)


def _get_assignments(body_elem):
    if hasattr(body_elem, "assign"):
        yield from body_elem.assign
    else:
        for child in body_elem.body:
            yield from _get_assignments(child)


def run_debug_if(condition, *args):
    """Runs DEBUG if condition is true."""

    return BuiltIn().run_keyword_if(condition, "RobotDebug.DEBUG", *args)
