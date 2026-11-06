"""Shared fixtures. Everything runs on the mock backend: no AWS, no network."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml

from aidlc_common.clock import FixedClock
from aidlc_common.events import InMemoryEventBus

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_RULES = ROOT / "aidlc-docs" / "inception" / "policy-rules.example.yaml"
TODAY = "2026-11-04"


@pytest.fixture(autouse=True)
def _mock_backend(monkeypatch):
    """Every test runs mock unless it sets the flag itself. Also stops any env file leaking in."""
    monkeypatch.setenv("AIDLC_BACKEND", "mock")
    monkeypatch.setenv("AIDLC_ENV_FILE", ".env.test-does-not-exist")


@pytest.fixture
def clock():
    return FixedClock(datetime(2026, 11, 4, 9, 0, tzinfo=UTC))


@pytest.fixture
def bus():
    return InMemoryEventBus()


@pytest.fixture
def example_rules():
    doc = yaml.safe_load(EXAMPLE_RULES.read_text())
    doc["effective_from"] = TODAY
    return copy.deepcopy(doc)
