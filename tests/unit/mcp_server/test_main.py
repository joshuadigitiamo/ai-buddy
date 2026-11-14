"""Composition root: startup failures are loud and safe, a valid config builds the server."""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastmcp import Client, FastMCP
from google.api_core.exceptions import Forbidden
from google.cloud import firestore
from tests.unit.buddy_core.conftest import FakeBucket
from tests.unit.mcp_server.conftest import NOW, WEB_BASE, make_content

from buddy_core.gcs_bucket import GcsBucket
from buddy_core.index_writer import build_index
from buddy_core.store import GcsArtifactStore
from buddy_mcp.cli import main
from buddy_mcp.config import McpSettings

SECRET_SENTINEL = "sentinel-secret-value-9f3a"

_SETTING_VARIABLES = tuple(name.upper() for name in McpSettings.model_fields) + ("K_SERVICE",)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from an empty server environment."""
    for name in _SETTING_VARIABLES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def no_firestore_client(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Fail the test if a Firestore client is constructed; the list stays empty."""
    built: list[str] = []

    def refuse(*args: Any, **kwargs: Any) -> None:
        built.append("AsyncClient")
        raise AssertionError("a Firestore client must not be built at startup")

    monkeypatch.setattr(firestore, "AsyncClient", refuse)
    return built


class ServeStub:
    """Records the arguments of the serve hook and the tools of the server it receives."""

    def __init__(self) -> None:
        self.calls = 0
        self.settings: McpSettings | None = None
        self.tool_names: list[str] = []

    def __call__(self, mcp: FastMCP, settings: McpSettings) -> None:
        self.calls += 1
        self.settings = settings

        async def list_names() -> list[str]:
            async with Client(mcp) as client:
                return [tool.name for tool in await client.list_tools()]

        self.tool_names = asyncio.run(list_names())


@pytest.fixture
def serve_stub() -> ServeStub:
    return ServeStub()


@pytest.fixture
def valid_env(monkeypatch: pytest.MonkeyPatch, index_dir: Path) -> Callable[..., None]:
    """Set a valid offline configuration; keyword arguments override or add variables."""

    def apply(**overrides: str) -> None:
        values = {
            "ARTIFACT_DIR": str(index_dir),
            "GUIDES_WEB_BASE": WEB_BASE,
            "AUTH_MODE": "off",
            "DEPLOY_ENV": "local",
            "GOOGLE_CLOUD_PROJECT": "demo-ai-buddy",
        }
        values.update(overrides)
        for name, value in values.items():
            monkeypatch.setenv(name, value)

    return apply


def _error_lines(captured: str) -> list[str]:
    return [line for line in captured.splitlines() if line.startswith("ERROR")]


def test_missing_artifact_dir_names_the_variable(
    valid_env: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    serve_stub: ServeStub,
    capsys: pytest.CaptureFixture[str],
) -> None:
    valid_env()
    monkeypatch.delenv("ARTIFACT_DIR")

    assert main([], serve=serve_stub) == 1

    errors = _error_lines(capsys.readouterr().err)
    assert len(errors) == 1
    assert "ARTIFACT_DIR" in errors[0]
    assert "Traceback" not in errors[0]
    assert serve_stub.calls == 0


def test_missing_artifact_directory_is_not_created(
    valid_env: Callable[..., None],
    tmp_path: Path,
    serve_stub: ServeStub,
    capsys: pytest.CaptureFixture[str],
) -> None:
    missing = tmp_path / "does-not-exist"
    valid_env(ARTIFACT_DIR=str(missing))

    assert main([], serve=serve_stub) == 1

    assert len(_error_lines(capsys.readouterr().err)) == 1
    assert not missing.exists()
    assert serve_stub.calls == 0


def test_empty_artifact_directory_exits_one(
    valid_env: Callable[..., None],
    tmp_path: Path,
    serve_stub: ServeStub,
    capsys: pytest.CaptureFixture[str],
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    valid_env(ARTIFACT_DIR=str(empty))

    assert main([], serve=serve_stub) == 1

    assert len(_error_lines(capsys.readouterr().err)) == 1
    assert serve_stub.calls == 0


def test_auth_off_on_cloud_run_is_refused(
    valid_env: Callable[..., None],
    serve_stub: ServeStub,
    capsys: pytest.CaptureFixture[str],
) -> None:
    valid_env(K_SERVICE="buddy-mcp")

    assert main([], serve=serve_stub) == 1

    errors = _error_lines(capsys.readouterr().err)
    assert len(errors) == 1
    assert "DEPLOY_ENV" in errors[0]
    assert "K_SERVICE" in errors[0]
    assert serve_stub.calls == 0


def test_auth_off_without_deploy_env_is_refused_on_any_host(
    valid_env: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    serve_stub: ServeStub,
    capsys: pytest.CaptureFixture[str],
) -> None:
    valid_env()
    monkeypatch.delenv("DEPLOY_ENV")

    assert main([], serve=serve_stub) == 1

    errors = _error_lines(capsys.readouterr().err)
    assert len(errors) == 1
    assert "AUTH_MODE" in errors[0]
    assert "DEPLOY_ENV" in errors[0]
    assert serve_stub.calls == 0


def test_missing_google_cloud_project_names_the_variable(
    valid_env: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    serve_stub: ServeStub,
    capsys: pytest.CaptureFixture[str],
) -> None:
    valid_env()
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT")

    assert main([], serve=serve_stub) == 1

    errors = _error_lines(capsys.readouterr().err)
    assert len(errors) == 1
    assert "GOOGLE_CLOUD_PROJECT" in errors[0]
    assert serve_stub.calls == 0


def test_incompatible_index_exits_one(
    valid_env: Callable[..., None],
    tmp_path: Path,
    serve_stub: ServeStub,
    capsys: pytest.CaptureFixture[str],
) -> None:
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "index.db").write_bytes(b"this is not a sqlite database at all")
    valid_env(ARTIFACT_DIR=str(broken))

    assert main([], serve=serve_stub) == 1

    err = capsys.readouterr().err
    assert len(_error_lines(err)) == 1
    assert "Traceback" not in err
    assert serve_stub.calls == 0


def test_valid_offline_config_serves_five_tools_without_firestore(
    valid_env: Callable[..., None],
    no_firestore_client: list[str],
    serve_stub: ServeStub,
    capsys: pytest.CaptureFixture[str],
) -> None:
    valid_env()

    assert main([], serve=serve_stub) == 0

    assert serve_stub.calls == 1
    assert len(serve_stub.tool_names) == 5
    assert no_firestore_client == []
    err = capsys.readouterr().err
    assert _error_lines(err) == []
    startup = [line for line in err.splitlines() if "serving" in line]
    assert len(startup) == 1
    assert "4 handbook pages" in startup[0]
    assert "3 guides sections" in startup[0]
    assert "auth off" in startup[0]


def test_missing_signing_key_never_prints_the_secret(
    valid_env: Callable[..., None],
    serve_stub: ServeStub,
    capsys: pytest.CaptureFixture[str],
) -> None:
    valid_env(
        AUTH_MODE="on",
        MCP_PUBLIC_BASE_URL="https://buddy.example.invalid",
        GOOGLE_CLIENT_ID="test-client.apps.googleusercontent.com",
        GOOGLE_CLIENT_SECRET=SECRET_SENTINEL,
    )

    assert main([], serve=serve_stub) == 1

    captured = capsys.readouterr()
    assert SECRET_SENTINEL not in captured.out + captured.err
    errors = _error_lines(captured.err)
    assert len(errors) == 1
    assert "OAUTH_JWT_SIGNING_KEY" in errors[0]
    assert serve_stub.calls == 0


def test_firestore_oauth_store_without_key_exits_one(
    valid_env: Callable[..., None],
    serve_stub: ServeStub,
    capsys: pytest.CaptureFixture[str],
) -> None:
    valid_env(OAUTH_STORAGE="firestore")

    assert main([], serve=serve_stub) == 1

    errors = _error_lines(capsys.readouterr().err)
    assert len(errors) == 1
    assert "OAUTH_STORAGE_ENCRYPTION_KEY" in errors[0]


def test_default_serve_runs_stateless_json_http(
    valid_env: Callable[..., None], monkeypatch: pytest.MonkeyPatch
) -> None:
    valid_env(MCP_HOST="127.0.0.1", PORT="8123", MCP_PUBLIC_BASE_URL="http://localhost:8123")
    seen: dict[str, Any] = {}

    def fake_run(self: FastMCP, *args: Any, **kwargs: Any) -> None:
        seen.update(kwargs)

    monkeypatch.setattr(FastMCP, "run", fake_run)

    assert main([]) == 0

    assert seen["transport"] == "http"
    assert seen["host"] == "127.0.0.1"
    assert seen["port"] == 8123
    assert seen["stateless_http"] is True
    assert seen["json_response"] is True
    assert seen["host_origin_protection"] is True
    assert "localhost" in seen["allowed_hosts"]


# --- ARTIFACT_STORE=gcs: the same startup, the index read from a bucket ---------------------------


def _published_fake_bucket(tmp_path: Path) -> FakeBucket:
    bucket = FakeBucket()
    store = GcsArtifactStore(bucket, "idx/", tmp_path / "publisher")
    staged = store.staging_path()
    meta = build_index(make_content(), staged, now=NOW)
    store.publish(staged, meta)
    return bucket


def test_gcs_store_serves_the_bucket_index_and_names_no_bucket(
    valid_env: Callable[..., None],
    monkeypatch: pytest.MonkeyPatch,
    no_firestore_client: list[str],
    serve_stub: ServeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    valid_env(
        ARTIFACT_STORE="gcs",
        ARTIFACT_BUCKET="bucket-x",
        ARTIFACT_PREFIX="idx/",
        ARTIFACT_DIR=str(tmp_path / "server-cache"),
    )
    bucket = _published_fake_bucket(tmp_path)
    names: list[str] = []

    def factory(name: str) -> FakeBucket:
        names.append(name)
        return bucket

    assert main([], serve=serve_stub, bucket_factory=factory) == 0

    assert names == ["bucket-x"]
    assert serve_stub.calls == 1
    assert no_firestore_client == []
    err = capsys.readouterr().err
    assert _error_lines(err) == []
    assert "4 handbook pages" in err


def test_gcs_store_with_an_empty_bucket_exits_one_with_one_error_line(
    valid_env: Callable[..., None],
    serve_stub: ServeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    valid_env(
        ARTIFACT_STORE="gcs",
        ARTIFACT_BUCKET="bucket-x",
        ARTIFACT_DIR=str(tmp_path / "server-cache"),
    )

    assert main([], serve=serve_stub, bucket_factory=lambda _name: FakeBucket()) == 1

    err = capsys.readouterr().err
    errors = _error_lines(err)
    assert len(errors) == 1
    assert "artifact store" in errors[0]
    assert "bucket-x" not in err
    assert "Traceback" not in err
    assert serve_stub.calls == 0


def test_gcs_store_with_a_tampered_pointer_exits_one_without_serving(
    valid_env: Callable[..., None],
    serve_stub: ServeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    valid_env(
        ARTIFACT_STORE="gcs",
        ARTIFACT_BUCKET="bucket-x",
        ARTIFACT_PREFIX="idx/",
        ARTIFACT_DIR=str(tmp_path / "server-cache"),
    )
    bucket = _published_fake_bucket(tmp_path)
    pointer = json.loads(bucket.objects["idx/index.manifest.json"])
    pointer["sha256"] = "0" * 64
    bucket.objects["idx/index.manifest.json"] = json.dumps(pointer).encode("utf-8")

    assert main([], serve=serve_stub, bucket_factory=lambda _name: bucket) == 1

    errors = _error_lines(capsys.readouterr().err)
    assert len(errors) == 1
    assert "index checksum mismatch" in errors[0]
    assert serve_stub.calls == 0


def test_a_storage_failure_ends_startup_with_the_type_name_only(
    valid_env: Callable[..., None],
    serve_stub: ServeStub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    valid_env(
        ARTIFACT_STORE="gcs",
        ARTIFACT_BUCKET="bucket-x",
        ARTIFACT_DIR=str(tmp_path / "server-cache"),
    )

    def broken(name: str) -> GcsBucket:
        def client() -> Any:
            # api_core exception constructors carry no type hints
            raise Forbidden("token=secret-value https://storage.example/x")  # type: ignore[no-untyped-call]

        return GcsBucket(name, client_factory=client)

    assert main([], serve=serve_stub, bucket_factory=broken) == 1

    err = capsys.readouterr().err
    errors = _error_lines(err)
    assert len(errors) == 1
    assert "BucketError: Forbidden" in errors[0]
    assert "secret-value" not in err
    assert "https://" not in err
    assert serve_stub.calls == 0


def test_gcs_store_without_a_bucket_exits_one_naming_the_variable(
    valid_env: Callable[..., None],
    serve_stub: ServeStub,
    capsys: pytest.CaptureFixture[str],
) -> None:
    valid_env(ARTIFACT_STORE="gcs")

    assert main([], serve=serve_stub) == 1

    errors = _error_lines(capsys.readouterr().err)
    assert len(errors) == 1
    assert "ARTIFACT_BUCKET" in errors[0]
    assert serve_stub.calls == 0
