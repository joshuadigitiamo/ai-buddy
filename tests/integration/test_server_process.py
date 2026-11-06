"""MCP-01 and MCP-05 end to end: ``python -m buddy_mcp`` as a real process on the emulator."""

import os
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastmcp import Client
from google.cloud import firestore
from tests.unit.mcp_server.conftest import MAPPED, WEB_BASE, make_content, make_page, write_index

pytestmark = [
    pytest.mark.firestore,
    pytest.mark.anyio,
    pytest.mark.skipif(
        not os.environ.get("FIRESTORE_EMULATOR_HOST"),
        reason="needs the Firestore emulator: run ./run-unit-tests.sh --emulator",
    ),
]

QUESTION = "Domanda sintetica senza risposta nel processo reale?"
PAGE_ID = "02-ferie"
STARTUP_TIMEOUT_SECONDS = 30
_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "0"},
    },
}
D10_KEYS = {"question", "marker", "created_at", "expire_at", "build_id", "tried"}


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _wait_for_port(port: int, process: subprocess.Popen[bytes], stderr_path: Path) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(
                f"server exited with {process.returncode}: {stderr_path.read_text()[-2000:]}"
            )
        with socket.socket() as probe:
            probe.settimeout(0.5)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    raise AssertionError(f"server did not listen within {STARTUP_TIMEOUT_SECONDS} s")


@pytest.fixture
def server_process(
    tmp_path: Path, unique_collection: str, firestore_project: str
) -> Iterator[tuple[int, Path]]:
    """Start the server process on a free port; yields (port, stderr file)."""
    artifacts = tmp_path / "artifacts"
    page = make_page(PAGE_ID, 0, "Ferie e permessi", "Come richiedere le ferie.", "2026-10-03")
    write_index(artifacts, make_content(pages=(page,), chunks=(MAPPED,)))
    port = _free_port()
    env = {key: value for key, value in os.environ.items() if key != "K_SERVICE"}
    env.update(
        {
            "ARTIFACT_DIR": str(artifacts),
            "AUTH_MODE": "off",
            "MCP_HOST": "127.0.0.1",
            "PORT": str(port),
            "GUIDES_WEB_BASE": WEB_BASE,
            "GOOGLE_CLOUD_PROJECT": firestore_project,
            "GAP_COLLECTION": unique_collection,
        }
    )
    stderr_path = tmp_path / "server.stderr"
    with stderr_path.open("wb") as stderr_file:
        process = subprocess.Popen(
            [sys.executable, "-m", "buddy_mcp"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=stderr_file,
        )
        try:
            _wait_for_port(port, process, stderr_path)
            yield port, stderr_path
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


async def test_real_process_serves_five_tools_and_records_a_gap(
    server_process: tuple[int, Path],
    firestore_client_factory: Callable[[], firestore.AsyncClient],
    unique_collection: str,
) -> None:
    port, stderr_path = server_process
    base = f"http://127.0.0.1:{port}"

    async with httpx2.AsyncClient(base_url=base) as http:
        initialized = await http.post("/mcp", json=_INITIALIZE, headers=_HEADERS)
        assert initialized.status_code == 200
        assert initialized.headers["content-type"].startswith("application/json")
        assert "mcp-session-id" not in initialized.headers

        rebinding = await http.post(
            "/mcp", json=_INITIALIZE, headers={**_HEADERS, "Host": "evil.example"}
        )
        assert 400 <= rebinding.status_code < 500

    async with Client(f"{base}/mcp") as client:
        assert len(await client.list_tools()) == 5

        search = await client.call_tool("handbook_search", {"query": "ferie"})
        assert search.structured_content is not None
        first: dict[str, Any] = search.structured_content["results"][0]
        assert first["source_url"] == f"handbook://{PAGE_ID}"

        report = await client.call_tool(
            "buddy_report_gap", {"question": QUESTION, "tried": ["handbook_search: ferie"]}
        )
        assert report.structured_content is not None
        assert report.structured_content["status"] == "recorded"
        gap_id = report.structured_content["gap_id"]

    reader = firestore_client_factory()
    try:
        docs = [d async for d in reader.collection(unique_collection).stream()]
        assert [d.id for d in docs] == [gap_id]
        data = docs[0].to_dict()
        assert data is not None
        assert set(data) == D10_KEYS
        assert data["question"] == QUESTION
        await reader.collection(unique_collection).document(gap_id).delete()
    finally:
        reader.close()  # type: ignore[no-untyped-call]  # sync close, untyped in google-cloud-core

    assert QUESTION not in stderr_path.read_text()
