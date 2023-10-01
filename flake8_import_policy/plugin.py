from __future__ import annotations

import ast
import sys
import typing

import flake8.options.manager  # type: ignore[import]
import isort

from . import config


if sys.version_info < (3, 8):
    import importlib_metadata
else:
    import importlib.metadata as importlib_metadata


STDLIB_IMPORT_VIOLATION = "FIP001 stdlib module import policy violation"
THIRD_PARTY_IMPORT_VIOLATION = "FIP002 third-party module import policy violation"
FIRST_PARTY_IMPORT_VIOLATION = "FIP003 first-party module import policy violation"
RELATIVE_IMPORT_VIOLATION = "FIP004 relative module import policy violation"


class Plugin:
    name = __package__
    version = importlib_metadata.version(__package__)

    _config = config.Config()

    def __init__(
        self, tree: ast.AST, filename: str, plugin_config: config.Config | None = None
    ) -> None:
        self._tree = tree
        self._filename = filename
        self._config = plugin_config or self._config

    @classmethod
    def add_options(cls, parser: flake8.options.manager.OptionManager) -> None:
        parser.add_option(
            '--forbid-stdlib-absolute',
            action='store_true',
            default=False,
            parse_from_config=True,
            help="Forbid absolute imports for stdlib",
        )
        parser.add_option(
            '--allow-stdlib-from-module',
            action='store_true',
            default=False,
            parse_from_config=True,
            help="Allow `from ... import module` for stdlib",
        )
        parser.add_option(
            '--allow-stdlib-from-member',
            action='store_true',
            default=False,
            parse_from_config=True,
            help="Allow `from ... import member` for stdlib",
        )

        parser.add_option(
            '--forbid-third-party-absolute',
            action='store_true',
            default=False,
            parse_from_config=True,
            help="Forbid absolute imports for third-party",
        )
        parser.add_option(
            '--allow-third-party-from-module',
            action='store_true',
            default=False,
            parse_from_config=True,
            help="Allow `from ... import module` for third-party",
        )
        parser.add_option(
            '--allow-third-party-from-member',
            action='store_true',
            default=False,
            parse_from_config=True,
            help="Allow `from ... import member` for third-party",
        )

        parser.add_option(
            '--forbid-local-absolute',
            action='store_true',
            default=False,
            parse_from_config=True,
            help="Forbid absolute imports for local modules",
        )
        parser.add_option(
            '--forbid-local-from-module',
            action='store_true',
            default=False,
            parse_from_config=True,
            help="Forbid `from ... import module` for local modules",
        )
        parser.add_option(
            '--allow-local-from-member',
            action='store_true',
            default=False,
            parse_from_config=True,
            help="Allow `from ... import member` for local modules",
        )

        parser.add_option(
            '--max-relative-level',
            type='int',
            default=1,
            parse_from_config=True,
            help="Max allowed level for relative imoprts (e.g. 1 for `.`, 2 for `..`, etc.)",
        )
        parser.add_option(
            '--forbid-relative-from-module',
            action='store_true',
            default=False,
            parse_from_config=True,
            help="Forbid `from ... import module` for relative modules",
        )
        parser.add_option(
            '--allow-relative-from-member',
            action='store_true',
            default=False,
            parse_from_config=True,
            help="Allow `from ... import member` for relative modules",
        )

    @classmethod
    def parse_options(cls, options: flake8.options.manager.OptionManager) -> None:
        cls._config = config.Config(
            allow_stdlib_absolute=not options.forbid_stdlib_absolute,
            allow_stdlib_from_module=options.allow_stdlib_from_module,
            allow_stdlib_from_member=options.allow_stdlib_from_member,
            allow_third_party_absolute=not options.forbid_third_party_absolute,
            allow_third_party_from_module=options.allow_third_party_from_module,
            allow_third_party_from_member=options.allow_third_party_from_member,
            allow_local_absolute=not options.forbid_local_absolute,
            allow_local_from_module=not options.forbid_local_from_module,
            allow_local_from_member=options.allow_local_from_member,
            max_relative_level=options.max_relative_level,
            allow_relative_from_module=not options.forbid_relative_from_module,
            allow_relative_from_member=options.allow_relative_from_member,
        )

    def run(self) -> typing.Iterator[tuple[int, int, str, type[Plugin]]]:
        print(f"loaded {self._config=}")
        for node in ast.walk(self._tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                result = self.check_policy(node)
                if result is not None:
                    yield result

    def check_policy(
        self, node: ast.Import | ast.ImportFrom
    ) -> tuple[int, int, str, type[Plugin]] | None:
        module_name = (
            node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
        )
        module_type = (
            isort.place_module(module_name) if module_name is not None else "RELATIVE"
        )

        if isinstance(node, ast.ImportFrom) and node.level > 0:
            return self._check_relative_import(node=node)
        assert module_name is not None
        if module_type == "FUTURE":
            return None
        elif module_type == "STDLIB":
            if self._check_stdlib_import(node=node, module_name=module_name):
                return None
            return (
                node.lineno,
                node.col_offset,
                STDLIB_IMPORT_VIOLATION,
                type(self),
            )
        elif module_type == "THIRDPARTY":
            if self._check_third_party_import(node=node, module_name=module_name):
                return None
            return (
                node.lineno,
                node.col_offset,
                THIRD_PARTY_IMPORT_VIOLATION,
                type(self),
            )
        elif module_type in ("LOCALFOLDER", "FIRSTPARTY"):
            return self._check_local_import(node=node)
        else:
            raise ValueError(f"Unknown {module_type=}")

    def _check_relative_import(
        self, node: ast.ImportFrom
    ) -> tuple[int, int, str, type[Plugin]] | None:
        return None

    def _check_stdlib_import(
        self, node: ast.Import | ast.ImportFrom, module_name: str
    ) -> bool:
        if isinstance(node, ast.Import):
            return self._config.allow_stdlib_absolute
        if self._is_module(module_name):
            return self._config.allow_stdlib_from_module
        return self._config.allow_stdlib_from_member

    def _check_third_party_import(
        self, node: ast.Import | ast.ImportFrom, module_name: str
    ) -> bool:
        if isinstance(node, ast.Import):
            return self._config.allow_third_party_absolute
        if self._is_module(module_name):
            return self._config.allow_third_party_from_module
        return self._config.allow_third_party_from_member

    def _check_local_import(
        self, node: ast.Import | ast.ImportFrom
    ) -> tuple[int, int, str, type[Plugin]] | None:
        return None

        # print(f"{module_name=}, {module_type=}, {node=}")
        # if isinstance(node, ast.ImportFrom) and node.level == 1:
        #     if self._filename.endswith('__init__.py'):
        #         return None
        #     for n in node.names:
        #         if n.name == "*":
        #             continue
        #         print(f"{n.name=}")
        #         full_module_name = f".{module_name}.{n.name}"
        #         if not self.is_module(full_module_name):
        #             return (
        #                 node.lineno,
        #                 node.col_offset,
        #                 f"FIP003 Do not import members from `{module_name}`.",
        #                 type(self),
        #             )
        # if module_type == "FUTURE":
        #     return None
        # elif module_type == "STDLIB":
        #     policy = self.policies["built-ins"]
        #     if (
        #         policy["type"] == "absolute"  # type: ignore
        #         and isinstance(node, ast.ImportFrom)
        #         and module_name not in policy["exceptions"]  # type: ignore
        #     ):
        #         return (
        #             node.lineno,
        #             node.col_offset,
        #             "FIP001 Use absolute imports for built-in modules.",
        #             type(self),
        #         )
        #
        # elif module_type == "THIRDPARTY":
        #     policy = self.policies["third-party"]
        #     if policy["type"] == "absolute" and isinstance(node, ast.ImportFrom):  # type: ignore
        #         return (
        #             node.lineno,
        #             node.col_offset,
        #             "FIP002 Use absolute imports for third-party modules.",
        #             type(self),
        #         )
        #
        # elif module_type in {"LOCALFOLDER", "FIRSTPARTY"}:
        #     policy = self.policies["local"]
        #     if (
        #         policy["disallowed_members"]  # type: ignore
        #         and isinstance(node, ast.ImportFrom)
        #         and node.level == 0
        #     ):
        #         for n in node.names:
        #             if n.name == "*":
        #                 continue
        #             full_module_name = f"{module_name}.{n.name}"
        #             if not self.is_module(full_module_name):
        #                 return (
        #                     node.lineno,
        #                     node.col_offset,
        #                     f"FIP003 Do not import members from {module_name}.",
        #                     type(self),
        #                 )
        # else:
        #     print(f"unknown {module_type=}")
        # return None

    def _is_module(self, full_module_name: str) -> bool:
        try:
            __import__(full_module_name)
            return True
        except ImportError:
            return False
