from __future__ import annotations

import ast
import collections
import enum
import importlib.metadata
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
        self._filename = filename
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
            '--override-import-policy',
            action='append',
            default=[],
            type='string',
            dest='import_policy_overrides',
            parse_from_config=True,
            help=(
                "Override default behavior for specific modules. "
                "Format `module-<allow:forbid>-policy`, e.g. `typing-allow-from-member`"
                " `django_rest_framework-forbid-absolute`"
            ),
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
        overrides: collections.defaultdict[
            str, config.Override
        ] = collections.defaultdict(config.Override)
        for override in options.import_policy_overrides:
            parts = override.split('-')
            module = parts[0]
            action = parts[1]
            policy = '_'.join(parts[2:])

            assert action in ('allow', 'forbid')
            overrides[module] = overrides[module].evolve(
                {f'allow_{policy}': action == 'allow'}
            )

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
        if self._filename.endswith('__init__.py') and not self._config.check_init:
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
            if self._is_module(full_imported_object_path):
                if not source_config.allow_from_module:
                    yield error_template.format(
                        f"from {source_module} import {imported_object}"
                    )
            elif not source_config.allow_from_member:
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
        parts = [p for p in self._filename.split('/') if p != '.']
        source_module = '.'.join(parts[: -node.level])
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
                    yield RELATIVE_IMPORT_VIOLATION.format(
                        f"from {'.' * node.level}{node.module or ''} import {imported_object}"
                    )
            elif not self._config.allow_relative_from_member:
                yield RELATIVE_IMPORT_VIOLATION.format(
                    f"from {'.' * node.level}{node.module or ''} import {imported_object}"
                )
            if (alias := imported_object_alias.asname) is not None:
                yield from self._check_alias(
                    module_name=full_imported_object_path, alias=alias
                )

    def _is_module(self, full_module_name: str) -> bool:
        try:
            __import__(full_module_name)
        except ImportError:
            return False
        return True
