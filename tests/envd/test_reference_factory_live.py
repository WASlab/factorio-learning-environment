"""Opt-in native reference factory acceptance test; never uses eval servers."""

import os

import pytest


@pytest.mark.skipif(
    os.environ.get("FLE_RUN_REFERENCE_FACTORY") != "1",
    reason="Set FLE_RUN_REFERENCE_FACTORY=1 to run the dedicated Docker pair",
)
def test_reference_factory_native_lifecycle():
    from scripts.validate_reference_factory import validate

    assert validate()["passed"]
