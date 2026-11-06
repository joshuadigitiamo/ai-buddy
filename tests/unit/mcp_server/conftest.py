"""Synthetic fixtures only: no handbook text, no names."""

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastmcp import FastMCP
from fastmcp.server.auth import AuthProvider
from fastmcp.server.auth.providers.jwt import RSAKeyPair
from key_value.aio.protocols import AsyncKeyValue
from key_value.aio.stores.memory import MemoryStore

from buddy_core.index_writer import build_index
from buddy_core.models import GuideChunk, HandbookPage, IndexContent, VideoLink, make_chunk_key
from buddy_mcp.auth import ServiceAccountIdTokenVerifier, build_auth
from buddy_mcp.config import McpSettings
from buddy_mcp.gaplog import InMemoryGapLog
from buddy_mcp.server import build_server
from buddy_mcp.snapshot import IndexSnapshot, load_snapshot

NOW = datetime(2026, 11, 3, 10, 0, 0, tzinfo=UTC)
PUBLIC_BASE_URL = "http://localhost"
BOT_EMAIL = "buddy-bot@demo-ai-buddy.iam.gserviceaccount.com"
GOOGLE_ISSUER = "https://accounts.google.com"
# Obviously fake values: nothing here is a credential.
FAKE_CLIENT_ID = "test-client.apps.googleusercontent.com"
FAKE_CLIENT_SECRET = "fake-client-secret-for-tests"
FAKE_SIGNING_KEY = "fake-signing-key-for-tests-only"
WEB_BASE = "https://github.com/example-org/guides"
SHA = "1" * 40
FILE = "AI-Engineering/DEMO_GUIDE.md"

_PAGES: tuple[tuple[str, str, str, str], ...] = (
    (
        "01-benvenuto",
        "Benvenuto",
        "Benvenuto in azienda. Qui trovi le regole di base e i primi passi.",
        "2026-09-01T00:00:00+00:00",
    ),
    (
        "02-ferie",
        "Ferie e permessi",
        "Come richiedere le ferie: invia la richiesta al responsabile con due settimane di "
        "anticipo.",
        "2026-10-03T00:00:00+00:00",
    ),
    (
        "03-malattia",
        "Malattia",
        "In caso di malattia comunica a HR il numero di protocollo del certificato.",
        "2026-08-15T00:00:00+00:00",
    ),
    (
        "04-sede",
        "Sede e città",
        "La sede è in città. Perché arrivare in orario: le riunioni iniziano alle nove.",
        "2026-07-01T00:00:00+00:00",
    ),
)


def make_page(
    page_id: str, position: int, title: str, text: str, revision: str | None
) -> HandbookPage:
    return HandbookPage(
        page_id=page_id,
        parent_id=None,
        position=position,
        depth=0,
        title=title,
        url=f"handbook://{page_id}",
        date_edited_raw=None,
        date_created_raw=None,
        revision_date_iso=revision,
        content_md=text,
        content_hash=f"hash-{page_id}",
    )


def make_chunk(
    h2: str,
    h3: str | None,
    line_start: int,
    line_end: int,
    text: str,
    *,
    file: str = FILE,
    part_index: int = 0,
    occurrence: int = 1,
) -> GuideChunk:
    return GuideChunk(
        chunk_key=make_chunk_key(file, h2, h3, part_index, occurrence),
        file=file,
        h2=h2,
        h3=h3,
        heading=h3 or h2,
        line_start=line_start,
        line_end=line_end,
        part_index=part_index,
        text=text,
    )


MAPPED = make_chunk(
    "Retrieval", "Chunking", 10, 14, "Chunking splits documents into heading sections."
)
PLAIN = make_chunk("Serving", None, 30, 34, "Deploy the server behind a gateway.")
SINGLE = make_chunk("Glossary", None, 40, 40, "Embedding means a dense vector.")
VIDEO = VideoLink("https://videos.example.invalid/demo.mp4", 1, 12.0, "scene")


def make_content(
    *,
    pages: tuple[HandbookPage, ...] | None = None,
    chunks: tuple[GuideChunk, ...] | None = None,
    videos: dict[str, VideoLink] | None = None,
) -> IndexContent:
    """Fixture content; every argument overrides the default synthetic set."""
    default_pages = tuple(
        make_page(pid, pos, title, text, rev) for pos, (pid, title, text, rev) in enumerate(_PAGES)
    )
    return IndexContent(
        handbook=default_pages if pages is None else pages,
        chunks=(MAPPED, PLAIN, SINGLE) if chunks is None else chunks,
        videos={MAPPED.chunk_key: VIDEO} if videos is None else videos,
        source_doc_id="handbook-local-synthetic",
        guides_commit_sha=SHA,
        pipeline_version="test-1",
        redaction_version="test-1",
    )


def write_index(directory: Path, content: IndexContent) -> Path:
    """Build `<directory>/index.db` from `content` and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "index.db"
    build_index(content, path, now=NOW)
    return path


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def index_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "artifacts"
    write_index(directory, make_content())
    return directory


@pytest.fixture
def snapshot(index_dir: Path) -> Iterator[IndexSnapshot]:
    loaded = load_snapshot(index_dir / "index.db")
    yield loaded
    loaded.reader.close()
    loaded.handbook_index.close()


@pytest.fixture
def server_for(tmp_path: Path) -> Iterator[Callable[[IndexContent], FastMCP]]:
    """Factory: build a server over a fresh tmp index made from `content`."""
    opened: list[IndexSnapshot] = []
    counter = 0

    def factory(content: IndexContent) -> FastMCP:
        nonlocal counter
        counter += 1
        directory = tmp_path / f"extra-{counter}"
        write_index(directory, content)
        loaded = load_snapshot(directory / "index.db")
        opened.append(loaded)
        config = McpSettings(artifact_dir=directory, guides_web_base=WEB_BASE, auth_mode="off")
        return build_server(config, snapshot=loaded, gaplog=InMemoryGapLog(), now=lambda: NOW)

    yield factory
    for loaded in opened:
        loaded.reader.close()
        loaded.handbook_index.close()


@pytest.fixture
def settings(index_dir: Path) -> McpSettings:
    return McpSettings(artifact_dir=index_dir, guides_web_base=WEB_BASE, auth_mode="off")


@pytest.fixture
def gaplog() -> InMemoryGapLog:
    return InMemoryGapLog()


@pytest.fixture
def make_server(
    settings: McpSettings, snapshot: IndexSnapshot, gaplog: InMemoryGapLog
) -> Callable[..., FastMCP]:
    def factory(**overrides: Any) -> FastMCP:
        params: dict[str, Any] = {"gaplog": gaplog, "now": lambda: NOW}
        params.update(overrides)
        return build_server(settings, snapshot=snapshot, **params)

    return factory


@pytest.fixture
def server(make_server: Callable[..., FastMCP]) -> FastMCP:
    return make_server()


@pytest.fixture
def bot_key() -> RSAKeyPair:
    """Stands in for Google's signing key; tests never reach the network."""
    return RSAKeyPair.generate()


@pytest.fixture
def auth_settings(index_dir: Path) -> McpSettings:
    return McpSettings(
        artifact_dir=index_dir,
        guides_web_base=WEB_BASE,
        auth_mode="on",
        mcp_public_base_url=PUBLIC_BASE_URL,
        google_client_id=FAKE_CLIENT_ID,
        google_client_secret=FAKE_CLIENT_SECRET,
        oauth_jwt_signing_key=FAKE_SIGNING_KEY,
        bot_sa_emails=frozenset({BOT_EMAIL}),
    )


@pytest.fixture
def sign_bot_token(bot_key: RSAKeyPair) -> Callable[..., str]:
    """Mint an ID token like Google would for a service account."""

    def sign(
        *,
        email: str = BOT_EMAIL,
        aud: str = PUBLIC_BASE_URL,
        verified: bool = True,
        expires_in: int = 300,
        issuer: str = GOOGLE_ISSUER,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        claims: dict[str, Any] = {"email": email, "email_verified": verified}
        claims.update(extra_claims or {})
        return bot_key.create_token(
            subject="1234567890",
            issuer=issuer,
            audience=aud,
            expires_in_seconds=expires_in,
            additional_claims=claims,
        )

    return sign


@pytest.fixture
def make_auth_server(
    auth_settings: McpSettings,
    snapshot: IndexSnapshot,
    gaplog: InMemoryGapLog,
    bot_key: RSAKeyPair,
) -> Callable[..., FastMCP]:
    """Server with auth on; the bot verifier trusts `bot_key` instead of Google's JWKS."""

    def factory(
        *, storage: AsyncKeyValue | None = None, settings: McpSettings | None = None
    ) -> FastMCP:
        config = settings or auth_settings
        verifier = ServiceAccountIdTokenVerifier(
            allowed_emails=config.bot_sa_emails,
            granted_scopes=["openid", "https://www.googleapis.com/auth/userinfo.email"],
            audience=config.mcp_public_base_url or PUBLIC_BASE_URL,
            public_key=bot_key.public_key,
        )
        provider: AuthProvider | None = build_auth(
            config, storage=storage or MemoryStore(), sa_verifier=verifier
        )
        return build_server(
            config, snapshot=snapshot, gaplog=gaplog, auth=provider, now=lambda: NOW
        )

    return factory
