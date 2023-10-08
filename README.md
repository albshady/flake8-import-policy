# flake8-import-policy

A [flake8](https://flake8.pycqa.org/en/latest/index.html)
plugin to enforce specific import policies in your Python codebase.

## Features

- Validate built-in, third-party, and local module import styles
- Enforce policies on absolute imports, relative imports, and aliasing
- Easily configurable through `flake8` configuration or CLI

**NOTE**: `__future__` imports are ignored.

## Installation

Not published to [pypi.org](https://pypi.org/) yet,
install directly from [github](https://github.com/albshady/flake8-import-policy).

## Configuration

You can configure the plugin using the standard `flake8` configuration methods.
Below are the supported configuration options:

- `--forbid-stdlib-absolute`: Forbid absolute imports for standard library modules
- `--allow-stdlib-from-module`: Allow `from module import ...` for standard library modules
- `--forbid-third-party-absolute`: Forbid absolute imports for third-party modules
- `--allow-third-party-from-module`: Allow `from module import ...` for third-party modules
- `--forbid-local-absolute`: Forbid absolute imports for local library modules
- `--forbid-local-from-module`: Forbid `from module import ...` for local modules
- `--forbid-relative-from-module`: Forbid `from .module import ...` for relative modules
- `--max-relative-level`: Specify the maximum level for relative imports. Default: `1`
- `--init-must-follow-import-policy`: Whether `__init__.py` shall follow import policies. Default: `False`
- `--register-import-aliases`: Register allowed aliases for modules. Format: `original=alias,module.nested=another_alias`

### Overriding rules

You can override rules for specific modules:

- `--allow-absolute`: List of modules to always allow `import module.nested`
- `--forbid-absolute`: List of modules to always forbid `import module.nested`
- `--allow-from-module`: List of modules to always allow `from module import ...`
- `--forbid-from-module`: List of modules to always forbid `from module import ...`

### Example

Example configuration in `setup.cfg`:

```ini
[flake8]
register-import-aliases = numpy=np, redis.asyncio=aioredis, sqlalchemy=sa
allow-from-module = typing, backports, redis
```

## License

[MIT](LICENSE)
