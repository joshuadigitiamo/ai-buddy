"""Authentication (MCP-07): Google users of the allowed domain through the OAuth proxy, the
chat bot through Google-signed service-account ID tokens (D-12).

Guide exception (MCP_SERVERS_GUIDE.md section 17.5 advises against building an authorization
server): the fastmcp OAuth proxy is an authorization-server facade, needed because Google offers
neither dynamic client registration nor client-ID metadata documents and claude.ai needs one of
them. Incoming bearer tokens are never forwarded anywhere (section 18.1).
"""

from __future__ import annotations

from typing import Any, Final

from fastmcp.server.auth import AccessToken, AuthProvider, MultiAuth, OAuthProxy
from fastmcp.server.auth.providers.google import GoogleTokenVerifier
from fastmcp.server.auth.providers.jwt import JWTVerifier
from key_value.aio.protocols import AsyncKeyValue

from buddy_mcp.config import McpSettings

REQUIRED_SCOPES: Final = ["openid", "https://www.googleapis.com/auth/userinfo.email"]
GOOGLE_AUTHORIZE_URL: Final = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL: Final = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URI: Final = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS: Final = ["https://accounts.google.com", "accounts.google.com"]
CLAUDE_CALLBACK: Final = "https://claude.ai/api/mcp/auth_callback"
LOOPBACK_REDIRECTS: Final = ["http://localhost:*", "http://127.0.0.1:*"]
_CACHE_TTL_SECONDS: Final = 300
_MAX_CACHE_SIZE: Final = 100


def _is_true(value: object) -> bool:
    """True for the boolean or for Google's string form ("true"); the string "false" is false."""
    if isinstance(value, bool):
        return value
    return isinstance(value, str) and value.strip().lower() == "true"


def _email_domain(email: object) -> str | None:
    """Lowercased part after the last "@" of a non-empty address, else None."""
    if not isinstance(email, str):
        return None
    local, separator, domain = email.strip().lower().rpartition("@")
    if not separator or not local or not domain:
        return None
    return domain


class DomainRestrictedGoogleVerifier(GoogleTokenVerifier):
    """Google user tokens, accepted only for verified e-mails of exactly one domain.

    The ``hd`` authorize parameter is only a UI hint: any Google account can finish the login,
    so this check is the actual boundary (MCP-07, Pitfall 4).
    """

    def __init__(self, *, allowed_domain: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.allowed_domain = allowed_domain.strip().lower()

    async def verify_token(self, token: str) -> AccessToken | None:
        access = await super().verify_token(token)
        if access is None:
            return None
        claims = access.claims
        if not _is_true(claims.get("email_verified")):
            return None
        if _email_domain(claims.get("email")) != self.allowed_domain:
            return None
        profile = claims.get("google_user_data")
        hosted_domains = [claims.get("hd")]
        if isinstance(profile, dict):
            hosted_domains.append(profile.get("hd"))
        for hosted_domain in hosted_domains:
            if hosted_domain is None:
                continue
            if not isinstance(hosted_domain, str) or hosted_domain.lower() != self.allowed_domain:
                return None
        return access


class ServiceAccountIdTokenVerifier(JWTVerifier):
    """Google-signed ID tokens minted by an allowlisted service account (the bot, D-12).

    Signature, issuer, audience and expiry come from ``JWTVerifier``. On top: the e-mail must be
    on the allowlist, verified, and the token must expire. The returned access token carries
    ``granted_scopes`` because MultiAuth inherits the OAuth proxy's required scopes and would
    otherwise answer 403 (Pitfall 3).
    """

    def __init__(
        self,
        *,
        allowed_emails: frozenset[str],
        granted_scopes: list[str],
        audience: str,
        public_key: str | None = None,
        jwks_uri: str | None = None,
    ) -> None:
        super().__init__(
            public_key=public_key,
            jwks_uri=jwks_uri,
            issuer=list(GOOGLE_ISSUERS),
            audience=audience,
        )
        self.allowed_emails = frozenset(email.lower() for email in allowed_emails)
        self.granted_scopes = list(granted_scopes)

    async def verify_token(self, token: str) -> AccessToken | None:
        access = await super().verify_token(token)
        if access is None or access.expires_at is None:
            return None
        claims = access.claims
        email = claims.get("email")
        if not isinstance(email, str) or email.lower() not in self.allowed_emails:
            return None
        if not _is_true(claims.get("email_verified")):
            return None
        return AccessToken(
            token=access.token,
            client_id=email.lower(),
            scopes=list(self.granted_scopes),
            expires_at=access.expires_at,
            claims=claims,
        )


def build_auth(
    settings: McpSettings,
    *,
    storage: AsyncKeyValue,
    sa_verifier: ServiceAccountIdTokenVerifier | None = None,
) -> AuthProvider | None:
    """The auth provider for ``settings``: the OAuth proxy, plus the bot verifier if enabled.

    ``storage`` is always handed to the proxy, never fastmcp's default file store (MCP-01).
    """
    if settings.auth_mode == "off":
        return None
    # The validator guarantees these when auth is on; the asserts narrow the types.
    assert settings.mcp_public_base_url is not None
    assert settings.google_client_id is not None
    assert settings.google_client_secret is not None
    assert settings.oauth_jwt_signing_key is not None
    proxy = OAuthProxy(
        upstream_authorization_endpoint=GOOGLE_AUTHORIZE_URL,
        upstream_token_endpoint=GOOGLE_TOKEN_URL,
        upstream_client_id=settings.google_client_id,
        upstream_client_secret=settings.google_client_secret.get_secret_value(),
        token_verifier=DomainRestrictedGoogleVerifier(
            allowed_domain=settings.allowed_email_domain,
            audience=settings.google_client_id,
            cache_ttl_seconds=_CACHE_TTL_SECONDS,
            max_cache_size=_MAX_CACHE_SIZE,
            required_scopes=list(REQUIRED_SCOPES),
        ),
        base_url=settings.mcp_public_base_url,
        jwt_signing_key=settings.oauth_jwt_signing_key.get_secret_value(),
        client_storage=storage,
        allowed_client_redirect_uris=[CLAUDE_CALLBACK, *LOOPBACK_REDIRECTS],
        extra_authorize_params={
            "access_type": "offline",
            "prompt": "consent",
            "hd": settings.allowed_email_domain,
        },
        require_authorization_consent=True,
    )
    if not settings.bot_sa_emails:
        return proxy
    verifier = sa_verifier or ServiceAccountIdTokenVerifier(
        allowed_emails=settings.bot_sa_emails,
        granted_scopes=list(REQUIRED_SCOPES),
        audience=settings.mcp_public_base_url,
        jwks_uri=GOOGLE_JWKS_URI,
    )
    return MultiAuth(server=proxy, verifiers=[verifier])
