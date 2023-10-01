from __future__ import annotations

import ast
import enum
import importlib.metadata
import typing

import flake8.options.manager  # type: ignore[import]
import isort
import isort.sections

from . import config


FUTURE_IMPORT_VIOLATION = "FIP000 __future__ module import policy violation"
STDLIB_IMPORT_VIOLATION = "FIP001 stdlib module import policy violation"
THIRD_PARTY_IMPORT_VIOLATION = "FIP002 third-party module import policy violation"
FIRST_PARTY_IMPORT_VIOLATION = "FIP003 first-party module import policy violation"
RELATIVE_IMPORT_VIOLATION = "FIP004 relative module import policy violation"


class SourceType(enum.Enum):
    FUTURE = enum.auto()
    STDLIB = enum.auto()
    THIRD_PARTY = enum.auto()
    FIRST_PARTY = enum.auto()


class Plugin:
    name = __package__
    version = importlib.metadata.version(__package__)

    _config = config.Config()

    def __init__(
        self, tree: ast.AST, filename: str, plugin_config: config.Config | None = None
    ) -> None:
        self._tree = tree
        self._filename = filename
        self._config = plugin_config or self._config
        self._config_by_source = {
            SourceType.FUTURE: self._config.future,
            SourceType.STDLIB: self._config.stdlib,
            SourceType.THIRD_PARTY: self._config.third_party,
            SourceType.FIRST_PARTY: self._config.first_party,
        }
        self._error_by_source = {
            SourceType.FUTURE: FUTURE_IMPORT_VIOLATION,
            SourceType.STDLIB: STDLIB_IMPORT_VIOLATION,
            SourceType.THIRD_PARTY: THIRD_PARTY_IMPORT_VIOLATION,
            SourceType.FIRST_PARTY: FIRST_PARTY_IMPORT_VIOLATION,
        }

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
            stdlib=config.SourceConfig(
                allow_absolute=not options.forbid_stdlib_absolute,
                allow_from_module=options.allow_stdlib_from_module,
                allow_from_member=options.allow_stdlib_from_member,
            ),
            third_party=config.SourceConfig(
                allow_absolute=not options.forbid_third_party_absolute,
                allow_from_module=options.allow_third_party_from_module,
                allow_from_member=options.allow_third_party_from_member,
            ),
            first_party=config.SourceConfig(
                allow_absolute=not options.forbid_local_absolute,
                allow_from_module=not options.forbid_local_from_module,
                allow_from_member=options.allow_local_from_member,
            ),
            max_relative_level=options.max_relative_level,
            allow_relative_from_module=not options.forbid_relative_from_module,
            allow_relative_from_member=options.allow_relative_from_member,
        )

    def run(self) -> typing.Iterator[tuple[int, int, str, type[Plugin]]]:
        for node in ast.walk(self._tree):
            if isinstance(node, ast.Import):
                errors = self._check_absolute_import(node)
            elif isinstance(node, ast.ImportFrom):
                errors = self._check_import_from(node)
            else:
                continue
            for msg in errors:
                yield (node.lineno, node.col_offset, msg, type(self))

    def _check_absolute_import(self, node: ast.Import) -> typing.Iterator[str]:
        for imported_module in node.names:
            module_name = imported_module.name
            source_type = self._determine_source_type(module_name)
            source_config = self._config_by_source[source_type]
            if not source_config.allow_absolute:
                yield self._error_by_source[source_type].format(module_name)

    def _determine_source_type(self, module_name: str) -> SourceType:
        isort_section = isort.place_module(module_name)
        return {
            isort.sections.FUTURE: SourceType.FUTURE,
            isort.sections.STDLIB: SourceType.STDLIB,
            isort.sections.THIRDPARTY: SourceType.THIRD_PARTY,
            isort.sections.FIRSTPARTY: SourceType.FIRST_PARTY,
            isort.sections.LOCALFOLDER: SourceType.FIRST_PARTY,
        }[isort_section]

    def _check_import_from(self, node: ast.ImportFrom) -> typing.Iterator[str]:
        if node.level > 0:
            yield from self._check_relative_import(node)
            return
        assert (
            node.module is not None
        ), "node.module can't be None when import is not relative"
        source_module = node.module
        source_type = self._determine_source_type(module_name=source_module)
        source_config = self._config_by_source[source_type]
        for imported_object_alias in node.names:
            imported_object = imported_object_alias.name
            if imported_object == '*':
                # Let flake8 handle wildcard import itself
                return
            full_imported_object_path = f'{source_module}.{imported_object}'
            if self._is_module(full_imported_object_path):
                if not source_config.allow_from_module:
                    yield self._error_by_source[source_type].format(
                        full_imported_object_path
                    )
            elif not source_config.allow_from_member:
                yield self._error_by_source[source_type].format(
                    full_imported_object_path
                )

    def _check_relative_import(self, node: ast.ImportFrom) -> typing.Iterator[str]:
        assert node.level > 0, "Relative import's node.level must not be 0"
        if node.level > self._config.max_relative_level:
            return iter(RELATIVE_IMPORT_VIOLATION)
        source_module = '.'.join(self._filename.split('/')[: node.level])
        if node.module is not None:
            source_module = f'{source_module}.{node.module}'

        for imported_object_alias in node.names:
            imported_object = imported_object_alias.name
            if imported_object == '*':
                # Let flake8 handle wildcard import itself
                return
            full_imported_object_path = f'{source_module}.{imported_object}'
            if self._is_module(full_imported_object_path):
                if not self._config.allow_relative_from_module:
                    yield RELATIVE_IMPORT_VIOLATION.format(full_imported_object_path)
            elif not self._config.allow_relative_from_member:
                yield RELATIVE_IMPORT_VIOLATION.format(full_imported_object_path)

    def _is_module(self, full_module_name: str) -> bool:
        try:
            __import__(full_module_name)
            return True
        except ImportError:
            return False
