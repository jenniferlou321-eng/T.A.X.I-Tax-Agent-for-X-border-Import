"""Shared pytest fixtures"""
import pytest
from pathlib import Path


@pytest.fixture
def erp_samples_dir() -> Path:
    return Path(__file__).parent.parent / "data" / "erp_samples"


@pytest.fixture
def case_a_uk_subsidiary_id() -> str:
    return "case-a-uk-subsidiary"
