"""Remote orchestration: payload contents, target selection, and the
crs-app tiny-YAML fallback parser."""

import importlib.machinery
import importlib.util
import io
import os
import tarfile

import pytest

from mu2edaq_controlroom_setup.config import load_config
from mu2edaq_controlroom_setup.remote import PAYLOAD_FILES, RemoteRunner

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def runner():
    return RemoteRunner(load_config(os.path.join(REPO_ROOT, "config",
                                                 "controlroom.yaml")))


def test_payload_contains_everything(runner):
    payload = runner._build_payload()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as tar:
        names = {os.path.basename(m.name) for m in tar.getmembers()}
    for fname in PAYLOAD_FILES:
        assert fname in names, "missing %s from install payload" % fname
    assert "controlroom.yaml" in names
    assert "apps.yaml" in names


def test_select_by_session(runner):
    sessions = runner.select(session="daq-main")
    assert [s.name for s in sessions] == ["daq-main"]


def test_select_by_host(runner):
    sessions = runner.select(host="mu2e-mgr-01")
    assert {s.name for s in sessions} == {"shift-main", "shift-aux"}


def test_select_all(runner):
    assert len(runner.select(all_sessions=True)) == 6


def test_select_requires_target(runner):
    with pytest.raises(ValueError):
        runner.select()


def test_select_unknown_host(runner):
    with pytest.raises(KeyError):
        runner.select(host="mu2e-nope-99")


def test_tiny_yaml_matches_pyyaml():
    """crs-app's fallback parser must agree with PyYAML on apps.yaml."""
    import yaml
    apps_yaml = os.path.join(REPO_ROOT, "config", "apps.yaml")
    loader = importlib.machinery.SourceFileLoader(
        "crs_app", os.path.join(REPO_ROOT, "server", "crs-app"))
    spec = importlib.util.spec_from_loader("crs_app", loader)
    crs_app = importlib.util.module_from_spec(spec)
    loader.exec_module(crs_app)

    with open(apps_yaml) as fh:
        reference = yaml.safe_load(fh)["apps"]
    fallback = crs_app._tiny_yaml(apps_yaml)["apps"]

    assert len(fallback) == len(reference)
    for ref, fb in zip(reference, fallback):
        assert fb["id"] == ref["id"]
        assert fb["start"] == ref["start"]
        assert fb["stop"] == ref["stop"]
        assert fb.get("ports", {}) == ref.get("ports", {})
        assert fb.get("sessions", []) == ref.get("sessions", [])
