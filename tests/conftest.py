import random
from pathlib import Path

import pytest

from albumgen.config import Config
from albumgen.library import Library
from albumgen.memory import Memory

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def cfg(tmp_path):
    c = Config.load(ROOT / "config.yaml")
    c.data_dir = str(ROOT / "data")
    c.out_dir = str(tmp_path / "out")
    c.memory.db_path = str(tmp_path / "test.db")
    return c


@pytest.fixture
def lib():
    return Library.load(ROOT / "data")


@pytest.fixture
def mem(cfg):
    return Memory(cfg.memory.db_path)


@pytest.fixture
def rng():
    return random.Random(1234)
