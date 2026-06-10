"""Shared pytest fixtures"""
import pytest
from pathlib import Path


@pytest.fixture
def erp_samples_dir() -> Path:
    return Path(__file__).parent.parent / "data" / "erp_samples"


@pytest.fixture
def techflow_case_id() -> str:
    return "techflow_q1_2026"
