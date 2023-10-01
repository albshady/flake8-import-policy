from __future__ import annotations

import ast
import textwrap

import flake8_import_policy
from flake8_import_policy import config


def get_default_config():
    return config.Config(
        allow_local_absolute=True,
    )


def get_errors(
    code: str,
    filename: str = 'module.py',
    plugin_config: config.Config | None = None,
) -> set[str]:
    tree = ast.parse(code)
    plugin = flake8_import_policy.Plugin(
        tree=tree, filename=filename, plugin_config=plugin_config
    )
    return {f'{line}:{col} {msg}' for line, col, msg, _ in plugin.run()}


def test_correct_stdlib_import():
    code = textwrap.dedent(
        """
        import asyncio
        import time
        import typing
        """
    )
    errors = get_errors(code)
    assert not errors


def test_stdlib_import_policy_violation():
    code = "from os import path"
    errors = get_errors(code)
    assert errors == {"1:0 FIP001 stdlib module import policy violation"}


def test_correct_third_party_import():
    code = textwrap.dedent(
        """
        import isort.main
        import pytest
        """
    )
    errors = get_errors(code)
    assert not errors


def test_third_party_import_policy_violation():
    code = "from pytest import fixture"
    errors = get_errors(code)
    assert errors == {"1:0 FIP002 third-party imports policy violation"}


def test_correct_local_module_import():
    code = textwrap.dedent(
        """
        import flake8_import_policy
        from flake8_import_policy import plugin
        """
    )
    errors = get_errors(code)
    assert not errors


def test_forbid_module_member_import():
    code = textwrap.dedent(
        """
        from flake8_import_policy import Plugin
        """
    )
    errors = get_errors(code)
    assert len(errors) == 1
    assert "1:0 FIP003 Do not import members from `flake8_import_policy`" in errors


def test_relative_module_import():
    code = textwrap.dedent(
        """
        from .local_package import module
        """
    )
    errors = get_errors(code)
    assert not errors


def test_forbid_import_member_from_relative_module():
    code = textwrap.dedent(
        """
        from .local_package import member
        """
    )
    errors = get_errors(code)
    assert len(errors) == 1
    assert "1:0 FIP003 Do not import members from `local_package`" in errors
