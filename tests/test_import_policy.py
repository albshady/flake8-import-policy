import ast
import datetime
import textwrap
import typing

import flake8_import_policy


def main(numbers: typing.List[int]) -> None:
    now = datetime.datetime.now()
    print(numbers, now)


def get_errors(code: str):
    tree = ast.parse(code)
    plugin = flake8_import_policy.Plugin(tree=tree)
    return list(plugin.run())


def test_correct_stdlib_import():
    code = textwrap.dedent(
        """
        import asyncio
        import time
        import typing
        from datetime import datetime
        """
    )
    errors = get_errors(code)
    assert not errors


def test_stdlib_import_policy_violation():
    code = "from os import path"
    errors = get_errors(code)
    assert len(errors) == 1
    assert "FIP001" in errors[0][2]


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
    assert len(errors) == 1
    assert "FIP002" in errors[0][2]


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
    assert "FIP003" in errors[0][2]
