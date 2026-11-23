# tests/conftest.py
import pytest
from indatapilot.workspace import Workspace


@pytest.fixture
def ws(tmp_path):
    return Workspace.create(tmp_path / "w1", name="w1")
