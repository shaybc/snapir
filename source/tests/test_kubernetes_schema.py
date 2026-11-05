"""Verify bundled Kubernetes validation without public network access."""

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest
from jsonschema import ValidationError

from tools.deployment_tools import kubernetes_schema


def test_bundled_schema_validates_and_populates_cache_without_network(tmp_path):
    document = dict(apiVersion="v1", kind="ConfigMap", metadata=dict(name="offline"), data=dict(key="value"))
    with patch("socket.socket", side_effect=AssertionError("Network access is forbidden")):
        report = kubernetes_schema.validate_kubernetes([document], tmp_path)
    bundled = Path(kubernetes_schema.__file__).parent / "schemas/kubernetes-1.34.0.json"
    assert (tmp_path / bundled.name).read_bytes() == bundled.read_bytes()
    assert report["passed"] is True
    assert report["kinds"] == ["ConfigMap"]
    assert report["schema_hash"] == hashlib.sha256(bundled.read_bytes()).hexdigest()


def test_bundled_schema_still_rejects_invalid_resources(tmp_path):
    with pytest.raises(ValidationError):
        kubernetes_schema.validate_kubernetes([
            dict(apiVersion="v1", kind="ConfigMap", data=dict(key=123))
        ], tmp_path)


def test_unavailable_schema_version_fails_without_network(tmp_path):
    with patch("socket.socket", side_effect=AssertionError("Network access is forbidden")):
        with pytest.raises(ValueError, match="not bundled or cached"):
            kubernetes_schema.validate_kubernetes([], tmp_path, version="0.0.0")
