from __future__ import annotations

import ast
import textwrap

import flake8_import_policy
from flake8_import_policy import config


def create_config(
    registered_aliases: dict[str, str] | None = None,
    overrides: dict[str, config.Override] | None = None,
) -> config.Config:
    return config.Config(
        registered_aliases=registered_aliases or {},
        overrides=overrides or {},
    )


def get_errors(
    code: str,
    filename: str = 'tests/test_import_policy.py',
    plugin_config: config.Config | None = None,
) -> set[str]:
    tree = ast.parse(code)
    plugin = flake8_import_policy.Plugin(
        tree=tree, filename=filename, plugin_config=plugin_config
    )
    return {f'{line}:{col} {msg}' for line, col, msg, _ in plugin.run()}


def test_correct_stdlib_import():
    code = textwrap.dedent(
        """\
        import asyncio
        import time
        import typing
        """
    )
    errors = get_errors(code)
    assert not errors


def test_override_stdlib_import():
    code = textwrap.dedent(
        """\
        import datetime
        from datetime import datetime
        """
    )
    errors = get_errors(
        code,
        plugin_config=create_config(
            overrides={'datetime': config.Override(allow_from_member=True)}
        ),
    )
    assert not errors


def test_stdlib_import_policy_violation():
    code = "from os import path"
    errors = get_errors(code)
    assert errors == {"1:0 FIP001 stdlib module import policy violation"}


def test_correct_third_party_import():
    code = textwrap.dedent(
        """\
        import isort.main
        import pytest
        """
    )
    errors = get_errors(code)
    assert not errors


def test_third_party_import_policy_violation():
    code = "from pytest import fixture"
    errors = get_errors(code)
    assert errors == {"1:0 FIP002 third-party module import policy violation"}


def test_correct_local_module_import():
    code = textwrap.dedent(
        """\
        import flake8_import_policy
        import flake8_import_policy.plugin
        from flake8_import_policy import plugin
        from flake8_import_policy import config, plugin
        """
    )
    errors = get_errors(code)
    assert not errors


def test_forbid_local_module_member_import():
    code = textwrap.dedent(
        """\
        from flake8_import_policy import Plugin
        """
    )
    errors = get_errors(code)
    assert errors == {"1:0 FIP003 first-party module import policy violation"}


def test_forbid_import_member_when_importing_multiple_from_local_module():
    code = textwrap.dedent(
        """\
        from flake8_import_policy import plugin, Plugin
        """
    )
    errors = get_errors(code)
    assert errors == {"1:0 FIP003 first-party module import policy violation"}


def test_relative_module_import():
    code = textwrap.dedent(
        """\
        from .local_package import module
        """
    )
    errors = get_errors(code)
    assert not errors


def test_forbid_import_member_from_relative_module():
    code = textwrap.dedent(
        """\
        from .local_package import member
        """
    )
    errors = get_errors(code)
    assert errors == {"1:0 FIP004 relative module import policy violation"}


def test_forbid_absolute_alias():
    code = textwrap.dedent(
        """\
        import datetime as dt
        """
    )
    errors = get_errors(code)
    assert errors == {"1:0 FIP005 use of unregistered alias"}


def test_allow_absolute_alias():
    code = textwrap.dedent(
        """\
        import datetime as dt
        """
    )
    errors = get_errors(
        code, plugin_config=create_config(registered_aliases={'datetime': 'dt'})
    )
    assert not errors


def test_allow_alias_but_forbid_from_member():
    code = textwrap.dedent(
        """\
        from datetime import datetime as dt
        """
    )
    errors = get_errors(
        code,
        plugin_config=create_config(registered_aliases={'datetime.datetime': 'dt'}),
    )
    assert errors == {'1:0 FIP001 stdlib module import policy violation'}


def test_allow_from_member_but_forbid_alias():
    code = textwrap.dedent(
        """\
        from datetime import datetime as dt
        """
    )
    errors = get_errors(
        code,
        plugin_config=create_config(
            overrides={'datetime': config.Override(allow_from_member=True)},
        ),
    )
    assert errors == {'1:0 FIP005 use of unregistered alias'}


def test_allow_from_member_alias():
    code = textwrap.dedent(
        """\
        from datetime import datetime as dt
        """
    )
    errors = get_errors(
        code,
        plugin_config=create_config(
            registered_aliases={'datetime.datetime': 'dt'},
            overrides={'datetime': config.Override(allow_from_member=True)},
        ),
    )
    assert not errors


def test_forbid_relative_alias():
    code = textwrap.dedent(
        """\
        from .local_package import module as alias
        """
    )
    errors = get_errors(code)
    assert errors == {'1:0 FIP005 use of unregistered alias'}


def test_allow_relative_alias():
    code = textwrap.dedent(
        """\
        from .local_package import module as alias
        """
    )
    errors = get_errors(
        code,
        plugin_config=create_config(
            registered_aliases={'tests.local_package.module': 'alias'}
        ),
    )
    assert not errors
