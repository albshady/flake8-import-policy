import typing


class Config(typing.NamedTuple):
    allow_stdlib_absolute: bool
    allow_stdlib_from_module: bool
    allow_stdlib_from_member: bool

    allow_third_party_absolute: bool
    allow_third_party_from_module: bool
    allow_third_party_from_member: bool

    allow_local_absolute: bool
    allow_local_from_module: bool
    allow_local_from_member: bool

    allow_relative_from_module: bool
    allow_relative_from_member: bool
    max_relative_level: int
