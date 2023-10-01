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


class Plugin:
    name = __package__
    version = importlib_metadata.version(__package__)
    policies = {
        "built-ins": {"type": "absolute", "exceptions": ["datetime"]},
        "third-party": {"type": "absolute"},
        "local": {"type": "from-or-absolute", "disallowed_members": True},
    }
    config: config.Config

    def __init__(self, tree: ast.AST, filename: str) -> None:
        self._tree = tree
        self._filename = filename

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
        cls.config = config.Config(
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
        print(f"loaded {self.config=}")
        for node in ast.walk(self._tree):
            continue
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
        assert module_name is not None  # FIXME
        module_type = isort.place_module(module_name)
        print(f"{module_name=}, {module_type=}, {node=}")
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            if self._filename.endswith('__init__.py'):
                return None
            for n in node.names:
                if n.name == "*":
                    continue
                print(f"{n.name=}")
                full_module_name = f".{module_name}.{n.name}"
                if not self.is_module(full_module_name):
                    return (
                        node.lineno,
                        node.col_offset,
                        f"FIP003 Do not import members from `{module_name}`.",
                        type(self),
                    )
        if module_type == "FUTURE":
            return None
        elif module_type == "STDLIB":
            policy = self.policies["built-ins"]
            if (
                policy["type"] == "absolute"  # type: ignore
                and isinstance(node, ast.ImportFrom)
                and module_name not in policy["exceptions"]  # type: ignore
            ):
                return (
                    node.lineno,
                    node.col_offset,
                    "FIP001 Use absolute imports for built-in modules.",
                    type(self),
                )

        elif module_type == "THIRDPARTY":
            policy = self.policies["third-party"]
            if policy["type"] == "absolute" and isinstance(node, ast.ImportFrom):  # type: ignore
                return (
                    node.lineno,
                    node.col_offset,
                    "FIP002 Use absolute imports for third-party modules.",
                    type(self),
                )

        elif module_type in {"LOCALFOLDER", "FIRSTPARTY"}:
            policy = self.policies["local"]
            if (
                policy["disallowed_members"]  # type: ignore
                and isinstance(node, ast.ImportFrom)
                and node.level == 0
            ):
                for n in node.names:
                    if n.name == "*":
                        continue
                    full_module_name = f"{module_name}.{n.name}"
                    if not self.is_module(full_module_name):
                        return (
                            node.lineno,
                            node.col_offset,
                            f"FIP003 Do not import members from {module_name}.",
                            type(self),
                        )
        else:
            print(f"unknown {module_type=}")
        return None

    def is_module(self, full_module_name: str) -> bool:
        try:
            __import__(full_module_name)
            return True
        except ImportError:
            return False
