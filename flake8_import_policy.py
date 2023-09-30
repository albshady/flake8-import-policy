from __future__ import annotations

import ast
import sys

import isort
import pkg_resources

if sys.version_info < (3, 8):
    import importlib.metadata
else:
    import importlib.metadata as importlib_metadata


class Plugin:
    name = __name__
    version = importlib_metadata.version(__name__)
    policies = {
        "built-ins": {"type": "absolute", "exceptions": ["datetime"]},
        "third-party": {"type": "absolute"},
        "local": {"type": "from-or-absolute", "disallowed_members": True},
    }

    def __init__(self, tree: ast.AST) -> None:
        self._tree = tree

    def run(self):
        for node in ast.walk(self._tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                yield from self.check_policy(node)

    def check_policy(self, node: ast.Import | ast.ImportFrom):
        module_name = (
            node.module if isinstance(node, ast.ImportFrom) else node.names[0].name
        )
        module_type = isort.place_module(module_name)
        if module_type == "STDLIB":
            policy = self.policies["built-ins"]
            if (
                policy["type"] == "absolute"
                and isinstance(node, ast.ImportFrom)
                and module_name not in policy["exceptions"]
            ):
                yield (
                    node.lineno,
                    node.col_offset,
                    "FIP001 Use absolute imports for built-in modules.",
                    type(self),
                )

        elif module_type == "THIRDPARTY":
            policy = self.policies["third-party"]
            if policy["type"] == "absolute" and isinstance(node, ast.ImportFrom):
                yield (
                    node.lineno,
                    node.col_offset,
                    "FIP002 Use absolute imports for third-party modules.",
                    type(self),
                )

        else:  # Local import
            policy = self.policies["local"]
            if (
                policy["disallowed_members"]
                and isinstance(node, ast.ImportFrom)
                and node.level == 0
            ):
                for n in node.names:
                    if not n.name == "*":
                        yield (
                            node.lineno,
                            node.col_offset,
                            f"FIP003 Do not import members from {module_name}.",
                            type(self),
                        )

    def is_builtin(self, module_name: str) -> bool:
        return module_name in sys.builtin_module_names

    def is_third_party(self, module_name: str) -> bool:
        try:
            pkg_resources.get_distribution(module_name)
            return True
        except pkg_resources.DistributionNotFound:
            return False
