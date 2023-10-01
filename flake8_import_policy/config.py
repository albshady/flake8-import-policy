import typing


class Config(typing.NamedTuple):
    allow_stdlib_absolute: bool = True
    allow_stdlib_from_module: bool = False
    allow_stdlib_from_member: bool = False

    allow_third_party_absolute: bool = True
    allow_third_party_from_module: bool = False
    allow_third_party_from_member: bool = False

    allow_local_absolute: bool = True
    allow_local_from_module: bool = True
    allow_local_from_member: bool = False

    allow_relative_from_module: bool = True
    allow_relative_from_member: bool = False
    max_relative_level: int = 1
