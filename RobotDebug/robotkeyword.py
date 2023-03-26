import re
import tempfile
import time
from pathlib import Path
from typing import List, Tuple, Generator, Iterator

from robot.libdocpkg.model import LibraryDoc, KeywordDoc
from robot.libraries.BuiltIn import BuiltIn
from robot.parsing import get_model
from robot.running import TestSuite, UserLibrary
from robot.variables.search import is_variable

from .robotlib import ImportedLibraryDocBuilder, get_libs, get_resources, ImportedResourceDocBuilder

KEYWORD_SEP = re.compile("  +|\t")

_lib_keywords_cache = {}
_resource_keywords_cache = {}
temp_resources = []
last_keyword_exec_time = 0


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


def get_lib_keywords(library) -> List[KeywordDoc]:
    """Get keywords of imported library."""
    if library.name not in _lib_keywords_cache:
        if isinstance(library, UserLibrary):
            _lib_keywords_cache[library.name]: LibraryDoc = ImportedResourceDocBuilder().build(library)
        else:
            _lib_keywords_cache[library.name]: LibraryDoc = ImportedLibraryDocBuilder().build(library)
    return _lib_keywords_cache[library.name].keywords


# def get_resource_keywords(resource) -> List[KeywordDoc]:
#     """Get keywords of imported resource."""
#     if resource.name not in _resource_keywords_cache:
#         _resource_keywords_cache[resource.name]: LibraryDoc = ImportedResourceDocBuilder().build(resource)
#     return _resource_keywords_cache[resource.name].keywords


def get_keywords() -> Iterator[KeywordDoc]:
    """Get all keywords of libraries."""
    for lib in get_libs():
        yield from get_lib_keywords(lib)


# def get_res_keywords() -> Iterator[KeywordDoc]:
#     """Get all keywords of resources."""
#     for resource in get_resources():
#         yield from get_resource_keywords(resource)


def find_keyword(keyword_name) -> List[KeywordDoc]:
    keyword_name = keyword_name.lower()
    return [
        keyword
        for lib in get_libs()
        for keyword in get_lib_keywords(lib)
        if normalize_kw(keyword.name) == normalize_kw(keyword_name)
    ]


def normalize_kw(keyword_name):
    return keyword_name.lower().replace("_", "").replace(" ", "")


def run_command(builtin, command: str) -> List[Tuple[str, str]]:
    """Run a command in robotframewrk environment."""
    global last_keyword_exec_time
    last_keyword_exec_time = 0
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
        start = time.monotonic()
        for kw in test.body:
            kw.run(ctx)
        last_keyword_exec_time = time.monotonic() - start
        return_val = None
    else:
        kw = test.body[0]
        start = time.monotonic()
        return_val = kw.run(ctx)
        last_keyword_exec_time = time.monotonic() - start
    assign = set(_get_assignments(test))
    if not assign and return_val is not None:
        return [("<", repr(return_val))]
    elif assign:
        output = []  # [("<", repr(return_val))] if return_val is not None else []
        for variable in assign:
            variable = variable.rstrip("=").strip()
            val = BuiltIn().get_variable_value(variable)
            output.append(("#", f"{variable} = {val!r}"))
        return output
    else:
        return []


def get_rprompt_text():
    """Get text for bottom toolbar."""
    if last_keyword_exec_time == 0:
        return
    return [("class:pygments.comment", f"# ΔT: {last_keyword_exec_time:.3f}s")]


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
    res_file = tempfile.NamedTemporaryFile(
        mode="w", prefix="RobotDebug_keywords_", suffix=".resource", encoding="utf-8", delete=False
    )
    resource_path = Path(res_file.name)
    try:
        res_file.write(command)
        res_file.close()
        global temp_resources
        temp_resources.insert(0, str(resource_path.stem))
        BuiltIn().import_resource(resource_path.resolve().as_posix())
        BuiltIn().set_library_search_order(*temp_resources)
    finally:
        resource_path.unlink(missing_ok=True)


def _get_assignments(body_elem):
    if hasattr(body_elem, "assign"):
        yield from body_elem.assign
    else:
        for child in body_elem.body:
            yield from _get_assignments(child)


def run_debug_if(condition, *args):
    """Runs DEBUG if condition is true."""

    return BuiltIn().run_keyword_if(condition, "RobotDebug.DEBUG", *args)
