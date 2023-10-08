from __future__ import annotations

import typing


class SourceConfig(typing.NamedTuple):
    allow_absolute: bool = False
    allow_from_module: bool = False
    allow_from_member: bool = False

    def asdict(self) -> dict[str, bool]:
        return self._asdict()


class Override(typing.NamedTuple):
    allow_absolute: bool | None = None
    allow_from_module: bool | None = None
    allow_from_member: bool | None = None

    def omit_nones(self) -> dict[str, bool]:
        return {k: v for k, v in self._asdict().items() if v is not None}

    def evolve(self, **update: bool) -> Override:
        return Override(**{**self.omit_nones(), **update})

    def __or__(self, source_config: SourceConfig) -> SourceConfig:
        return SourceConfig(**{**source_config.asdict(), **self.omit_nones()})


class Config(typing.NamedTuple):
    overrides: typing.Mapping[str, Override]
    registered_aliases: typing.Mapping[str, str]
    check_init: bool = False

    future: SourceConfig = SourceConfig(
        allow_absolute=True, allow_from_module=True, allow_from_member=True
    )
    stdlib: SourceConfig = SourceConfig(allow_absolute=True)
    third_party: SourceConfig = SourceConfig(allow_absolute=True)
    first_party: SourceConfig = SourceConfig(
        allow_absolute=True, allow_from_module=True
    )

    max_relative_level: int = 1
    allow_relative_from_module: bool = True
    allow_relative_from_member: bool = False
