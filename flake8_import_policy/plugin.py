from __future__ import annotations

import ast
import collections
import enum
import importlib.metadata
import importlib.util
import pathlib
import sys
import typing

import flake8.options.manager  # type: ignore[import]
import isort
import isort.sections

from . import config


FUTURE_IMPORT_VIOLATION = "FIP000 __future__ module import policy violation"
STDLIB_IMPORT_VIOLATION = "FIP001 `{}` is forbidden"
THIRD_PARTY_IMPORT_VIOLATION = "FIP002 `{}` is forbidden"
FIRST_PARTY_IMPORT_VIOLATION = "FIP003 `{}` is forbidden"
RELATIVE_IMPORT_VIOLATION = "FIP004 `{}` is forbidden"
UNREGISTERED_ALIAS_ABUSE = (
    "FIP005 use of unregistered alias: `{module_name}` -> `{alias}`"
)


class SourceType(enum.Enum):
    FUTURE = enum.auto()
    STDLIB = enum.auto()
    THIRD_PARTY = enum.auto()
    FIRST_PARTY = enum.auto()


class Plugin:
    name = __package__
    version = importlib.metadata.version(__package__)

    _config: config.Config

    def __init__(self, tree: ast.AST, filename: str) -> None:
        self._tree = tree
        self._filepath = pathlib.Path(filename)
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
            '--register-import-alias',
            action='append',
            default=[],
            type='string',
            dest='registered_import_aliases',
            parse_from_config=True,
            help=(
                "Register an allowed alias for a module. "
                "Format `original=alias`, e.g. `sqlalchemy=sa`, `matplotlib.pyplot=plt`"
            ),
        )
        parser.add_option(
            '--allow-from-module',
            default='',
            dest='allow_from_module',
            parse_from_config=True,
            comma_separated_list=True,
            help="List of modules to always allow `from module import ...`",
        )
        parser.add_option(
            '--forbid-from-module',
            default='',
            dest='forbid_from_module',
            parse_from_config=True,
            comma_separated_list=True,
            help="List of modules to always forbid `from module import ...`",
        )
        parser.add_option(
            '--allow-absolute',
            default='',
            dest='allow_absolute',
            parse_from_config=True,
            comma_separated_list=True,
            help="List of modules to always allow `import module.something`",
        )
        parser.add_option(
            '--forbid-absolute',
            default='',
            dest='forbid_absolute',
            parse_from_config=True,
            comma_separated_list=True,
            help="List of modules to always forbid `import module.something`",
        )
        parser.add_option(
            '--init-must-follow-import-policy',
            action='store_true',
            default=False,
            parse_from_config=True,
            help="Whether `__init__.py` shall follow import policies",
        )

    @classmethod
    def parse_options(cls, options: flake8.options.manager.OptionManager) -> None:
        allow_from_module = set(options.allow_from_module)
        forbid_from_module = set(options.forbid_from_module)
        if allowed_and_forbidden := allow_from_module & forbid_from_module:
            raise ValueError(
                f"Can't simultaniously allow and forbid "
                f"from_module import for: {allowed_and_forbidden}"
            )
        allow_absolute = set(options.allow_absolute)
        forbid_absolute = set(options.forbid_absolute)
        if allowed_and_forbidden := allow_absolute & forbid_absolute:
            raise ValueError(
                f"Can't simultaniously allow and forbid "
                f"absolute import for: {allowed_and_forbidden}"
            )
        overrides: collections.defaultdict[
            str, config.Override
        ] = collections.defaultdict(config.Override)
        for module in allow_from_module:
            overrides[module] = overrides[module].evolve(allow_from_module=True)
        for module in forbid_from_module:
            overrides[module] = overrides[module].evolve(allow_from_module=False)
        for module in allow_absolute:
            overrides[module] = overrides[module].evolve(allow_absolute=True)
        for module in forbid_absolute:
            overrides[module] = overrides[module].evolve(allow_absolute=False)

        registered_aliases: dict[str, str] = {}
        for raw_alias in options.registered_import_aliases:
            full_module_path, _, alias = raw_alias.partition('=')
            registered_aliases[full_module_path] = alias

        cls._config = config.Config(
            overrides=overrides,
            registered_aliases=registered_aliases,
            check_init=options.init_must_follow_import_policy,
            stdlib=config.SourceConfig(
                allow_absolute=not options.forbid_stdlib_absolute,
                allow_from_module=options.allow_stdlib_from_module,
            ),
            third_party=config.SourceConfig(
                allow_absolute=not options.forbid_third_party_absolute,
                allow_from_module=options.allow_third_party_from_module,
            ),
            first_party=config.SourceConfig(
                allow_absolute=not options.forbid_local_absolute,
                allow_from_module=not options.forbid_local_from_module,
            ),
            max_relative_level=options.max_relative_level,
            allow_relative_from_module=not options.forbid_relative_from_module,
        )

    def run(self) -> typing.Iterator[tuple[int, int, str, type[Plugin]]]:
        sys.path.append(str(pathlib.Path.cwd()))
        if self._filepath.name.startswith('.'):
            return
        if self._filepath.name == '__init__.py' and not self._config.check_init:
            return
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
            alias = imported_module.asname
            source_config, error_template = self._get_config_and_error_template(
                module_name
            )
            if not source_config.allow_absolute:
                yield error_template.format(module_name)
            if alias is not None:
                yield from self._check_alias(module_name, alias)

    def _check_alias(self, module_name: str, alias: str) -> typing.Iterator[str]:
        if self._config.registered_aliases.get(module_name) != alias:
            yield UNREGISTERED_ALIAS_ABUSE.format(module_name=module_name, alias=alias)

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
        source_config, error_template = self._get_config_and_error_template(
            source_module=source_module
        )
        for imported_object_alias in node.names:
            imported_object = imported_object_alias.name
            if imported_object == '*':
                # Let flake8 handle wildcard import itself
                return
            full_imported_object_path = f'{source_module}.{imported_object}'
            if not source_config.allow_from_module:
                yield error_template.format(
                    f"from {source_module} import {imported_object}"
                )
            if (alias := imported_object_alias.asname) is not None:
                yield from self._check_alias(
                    module_name=full_imported_object_path, alias=alias
                )

    def _get_config_and_error_template(
        self, source_module: str
    ) -> tuple[config.SourceConfig, str]:
        source_type = self._determine_source_type(module_name=source_module)
        source_config = self._config_by_source[source_type]
        override = self._config.overrides.get(source_module, config.Override())
        source_config = override | source_config
        return source_config, self._error_by_source[source_type]

    def _check_relative_import(self, node: ast.ImportFrom) -> typing.Iterator[str]:
        assert node.level > 0, "Relative import's node.level must not be 0"
        if node.level > self._config.max_relative_level:
            return iter(RELATIVE_IMPORT_VIOLATION)
        source_module = str(self._filepath.parents[node.level - 1]).replace('/', '.')
        if node.module is not None:
            source_module = f'{source_module}.{node.module}'

        for imported_object_alias in node.names:
            imported_object = imported_object_alias.name
            if imported_object == '*':
                # Let flake8 handle wildcard import itself
                return
            if not self._config.allow_relative_from_module:
                yield RELATIVE_IMPORT_VIOLATION.format(
                    f"from {'.' * node.level}{node.module or ''} import {imported_object}"
                )
            full_imported_object_path = f'{source_module}.{imported_object}'
            if (alias := imported_object_alias.asname) is not None:
                yield from self._check_alias(
                    module_name=full_imported_object_path, alias=alias
                )
