import json

from robot.libdocpkg.model import LibraryDoc
from robot.libdocpkg.robotbuilder import KeywordDocBuilder, LibraryDocBuilder, ResourceDocBuilder
from robot.libraries import STDLIBS
from robot.libraries.BuiltIn import BuiltIn
from robot.running.namespace import IMPORTER


def get_builtin_libs():
    """Get robotframework builtin library names."""
    return list(STDLIBS)


def get_libs():
    """Get imported robotframework library names."""
    libs = [lib for lib in BuiltIn()._namespace._kw_store.libraries.values() if lib.name != "Reserved"]
    resources = BuiltIn()._namespace._kw_store.resources._items
    libs.extend(resources)
    # print("----LIbraries----")
    # print(json.dumps(libs, indent=4, default=lambda _: _.name))
    return sorted(libs, key=lambda _: _.name)


def get_resources():
    """Get imported robotframework resource names."""
    resources = BuiltIn()._namespace._kw_store.resources._items
    # print("----Resources----")
    # print(json.dumps(resources, indent=4, default=lambda _: _.name))
    return sorted(resources, key=lambda _: _.name)


# def get_libs_dict():
#     """Get imported robotframework libraries as a name -> lib dict"""
#     return {lib.name: lib for lib in BuiltIn()._namespace._kw_store.libraries.values() if lib.name != "Reserved"}
#
# def get_resources_dict():
#     """Get imported robotframework resources as a name -> lib dict"""
#     return {res.name: res for res in BuiltIn()._namespace._kw_store.resources._items}


def match_libs(name=""):
    """Find libraries by prefix of library name, default all"""
    # return [lib for lib in [*get_libs(), *get_resources()] if lib.name.lower().startswith(name.lower())]
    return [lib for lib in get_libs() if lib.name.lower().startswith(name.lower())]


class ImportedResourceDocBuilder(ResourceDocBuilder):
    def build(self, resource):
        libdoc = LibraryDoc(
            name=resource.name,
            doc=self._get_doc(resource, resource.name),
            type='RESOURCE',
            scope="GLOBAL",
        )
        libdoc.keywords = KeywordDocBuilder().build_keywords(resource)
        return libdoc


class ImportedLibraryDocBuilder(LibraryDocBuilder):
    def build(self, lib):
        libdoc = LibraryDoc(
            name=lib.name,
            doc=self._get_doc(lib),
            doc_format=lib.doc_format,
        )
        libdoc.inits = self._get_initializers(lib)
        libdoc.keywords = KeywordDocBuilder().build_keywords(lib)
        return libdoc
