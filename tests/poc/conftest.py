"""PoC test fixtures — shared HTTP clients, telemetry."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from telemetry import Telemetry

PNEURAL_URL = os.environ.get("PNEURAL_POC_URL", "http://localhost:8779")
OPENCODE_URL = os.environ.get("OPENCODE_URL", "http://localhost:4096")
PROJECT = os.environ.get("PNEURAL_POC_PROJECT", "poc-test")
TIMEOUT = 30.0

telemetry = Telemetry()


@pytest.fixture(scope="session")
def tel():
    return telemetry


@pytest.fixture(scope="session")
def api():
    with httpx.Client(base_url=PNEURAL_URL, timeout=TIMEOUT) as c:
        yield c


@pytest.fixture(scope="session")
def oc():
    with httpx.Client(base_url=OPENCODE_URL, timeout=120.0) as c:
        yield c


@pytest.fixture(scope="session")
def llm_url(api):
    r = api.get("/api/config")
    assert r.status_code == 200
    return r.json()["llm_url"]


@pytest.fixture(scope="session")
def embed_url(api):
    r = api.get("/api/config")
    assert r.status_code == 200
    return r.json()["embed_url"]


@pytest.fixture(autouse=True)
def record_test_timing(request):
    test_name = request.node.name
    telemetry.record(test_name, "start_time", time.monotonic())
    yield
    # finish_test is called by the pytest_runtest_makereport hook below


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when == "call":
        test_name = item.name
        passed = report.passed
        telemetry.finish_test(test_name, passed)


@pytest.fixture(scope="session", autouse=True)
def export_telemetry():
    yield
    telemetry.export()
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"PoC Telemetry Report: {telemetry.run_id}")
    print(sep)
    for name, metrics in telemetry.tests.items():
        status = "PASS" if metrics.get("pass") else "FAIL"
        dur = metrics.get("duration_seconds", "?")
        print(f"  {name}: {status} ({dur}s)")
    print(sep)
    print(f"Report saved to: tests/poc/reports/{telemetry.run_id}.json")
