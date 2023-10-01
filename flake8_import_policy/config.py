import typing


class SourceConfig(typing.NamedTuple):
    allow_absolute: bool = False
    allow_from_module: bool = False
    allow_from_member: bool = False


class Config(typing.NamedTuple):
    future: SourceConfig = SourceConfig(allow_absolute=True, allow_from_member=True)
    stdlib: SourceConfig = SourceConfig(allow_absolute=True)
    third_party: SourceConfig = SourceConfig(allow_absolute=True)
    first_party: SourceConfig = SourceConfig(
        allow_absolute=True, allow_from_module=True
    )

    max_relative_level: int = 1
    allow_relative_from_module: bool = True
    allow_relative_from_member: bool = False
