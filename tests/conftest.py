import pathlib

import pytest


@pytest.fixture
def data_dir() -> pathlib.Path:
    tests_dir = pathlib.Path(__file__).parent
    return tests_dir / 'data'
