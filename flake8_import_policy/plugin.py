from __future__ import annotations

import ast
import pathlib
import sys
import typing

import isort
import toml


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

    def __init__(
        self, tree: ast.AST, filename: str, config: dict[str, typing.Any] | None = None
    ) -> None:
        self._tree = tree
        self._filename = filename
        self._config = config or self.load_config()

    @classmethod
    def load_config(cls) -> dict[str, typing.Any]:
        config_path = pathlib.Path('pyproject.toml')
        if not config_path.exists():
            return {}
        full_config = toml.load(config_path)
        return full_config.get('tool', {}).get('flake8-import-policy', {})

    def run(self) -> typing.Iterator[tuple[int, int, str, type[Plugin]]]:
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
