"""Fixtures for tests that need the Firestore emulator.

These tests are skipped unless FIRESTORE_EMULATOR_HOST is set, which only
`./run-unit-tests.sh --emulator` does (through docker-compose.test.yml). The offline
`--all` gate therefore stays network-free and never reaches a real Firestore project.
"""

import os
import uuid
from collections.abc import Callable

import pytest
from google.cloud import firestore


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def firestore_project() -> str:
    return os.environ.get("GOOGLE_CLOUD_PROJECT", "demo-ai-buddy")


@pytest.fixture
def firestore_client_factory(firestore_project: str) -> Callable[[], firestore.AsyncClient]:
    def build() -> firestore.AsyncClient:
        return firestore.AsyncClient(project=firestore_project)

    return build


@pytest.fixture
def unique_collection() -> str:
    return f"gaps-test-{uuid.uuid4().hex}"
