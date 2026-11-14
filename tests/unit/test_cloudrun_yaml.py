"""Offline structural guard over deploy/cloudrun (INFRA-04): the two Cloud Run service templates.

The templates carry ${PLACEHOLDER} markers that scripts/render-cloudrun.sh fills from environment
variables, so yaml.safe_load reads them as they are in git. A live `gcloud run services replace
--dry-run` runs in CI (04-09) and live in 04-13; this guard keeps the scale, secret, privacy and
cross-service rules from regressing without it.
"""

import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CLOUDRUN = ROOT / "deploy" / "cloudrun"
MCP_FILE = CLOUDRUN / "mcp-server.yaml"
BOT_FILE = CLOUDRUN / "chat-bot.yaml"
MERIDIAN_VERSION_FILE = ROOT / "deploy" / "meridian.version"
RENDER_SCRIPT = ROOT / "scripts" / "render-cloudrun.sh"

REGION_IMAGE_HOST = "europe-west8-docker.pkg.dev"
REGION_URL_SUFFIX = ".europe-west8.run.app"
SECRET_SUFFIXES = ("_KEY", "_SECRET", "_TOKEN")
# 04-01-SUMMARY decision billing_mode: (a) request-based billing, so no cpu-throttling annotation.
BILLING_MODE = "a"
# The real project id is private: the repository is public and only env values carry it. The literal
# is assembled here so this file does not contain it.
PROJECT_ID_LITERAL = "ai-buddy-" + "dev"

Doc = dict[str, Any]


def _load(path: Path) -> Doc:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path.name}: the template is one mapping"
    return loaded


def _template_annotations(service: Doc) -> dict[str, str]:
    return dict(service["spec"]["template"]["metadata"].get("annotations", {}))


def _pod_spec(service: Doc) -> Doc:
    spec = service["spec"]["template"]["spec"]
    assert isinstance(spec, dict)
    return spec


def _containers(service: Doc) -> dict[str, Doc]:
    return {str(container["name"]): container for container in _pod_spec(service)["containers"]}


def _env(container: Doc) -> dict[str, Doc]:
    return {str(entry["name"]): entry for entry in container.get("env", [])}


def _mcp() -> Doc:
    return _load(MCP_FILE)


def _mcp_container() -> Doc:
    return _containers(_mcp())["mcp-server"]


def _bot() -> Doc:
    return _load(BOT_FILE)


def _bot_container(name: str) -> Doc:
    return _containers(_bot())[name]


def _volumes(service: Doc) -> dict[str, Doc]:
    return {str(volume["name"]): volume for volume in _pod_spec(service).get("volumes", [])}


def test_mcp_server_is_a_knative_service_for_europe_west8() -> None:
    service = _mcp()
    assert service["apiVersion"] == "serving.knative.dev/v1"
    assert service["kind"] == "Service"
    assert service["metadata"]["name"] == "mcp-server"
    image = str(_mcp_container()["image"])
    assert image.startswith(f"{REGION_IMAGE_HOST}/"), "D-03: the image lives in the Milan registry"
    url = str(_env(_mcp_container())["MCP_PUBLIC_BASE_URL"]["value"])
    assert url.startswith("https://mcp-server-${PROJECT_NUMBER}")
    assert url.endswith(REGION_URL_SUFFIX), "D-03: deterministic europe-west8 URL"


def test_mcp_server_scales_to_zero_and_never_beyond_one_instance() -> None:
    annotations = _template_annotations(_mcp())
    assert annotations["autoscaling.knative.dev/minScale"] == "0", "D-01: scale to zero"
    assert annotations["autoscaling.knative.dev/maxScale"] == "1", "T-04-32: cost and abuse cap"


def test_mcp_server_is_stateless_and_leaves_the_port_to_cloud_run() -> None:
    pod = _pod_spec(_mcp())
    assert "volumes" not in pod, "MCP_SERVERS_GUIDE 11.6: no volume on a stateless server"
    assert "volumeMounts" not in _mcp_container()
    assert "PORT" not in _env(_mcp_container()), "Cloud Run injects PORT from containerPort"
    ports = _mcp_container()["ports"]
    assert [port["containerPort"] for port in ports] == [8000]


def test_mcp_server_uses_request_based_billing() -> None:
    assert BILLING_MODE == "a", "04-01 billing_mode changed: revisit this annotation rule"
    for annotations in (_template_annotations(_mcp()), _mcp()["metadata"]["annotations"]):
        assert "run.googleapis.com/cpu-throttling" not in annotations, (
            "the fallback needs Joshua's consent (RESEARCH Pitfall 1)"
        )


def test_mcp_server_is_public_at_the_edge_and_verifies_tokens_in_the_app() -> None:
    assert _mcp()["metadata"]["annotations"]["run.googleapis.com/invoker-iam-disabled"] == "true"
    environment = _env(_mcp_container())
    assert environment["DEPLOY_ENV"]["value"] == "production", "T-04-27"
    assert environment["AUTH_MODE"]["value"] == "on", "T-04-27"
    assert environment["OAUTH_STORAGE"]["value"] == "firestore"


def test_mcp_server_reads_its_index_from_the_private_bucket() -> None:
    environment = _env(_mcp_container())
    assert environment["ARTIFACT_STORE"]["value"] == "gcs", "D-06"
    assert environment["ARTIFACT_BUCKET"]["value"] == "${PROJECT_ID}-ai-buddy-index"
    assert environment["ARTIFACT_PREFIX"]["value"] == "index/"
    assert "ARTIFACT_DIR" not in environment, "the bucket copy lands in the default cache directory"


def test_mcp_server_image_is_pinned_by_a_tag_placeholder_never_latest() -> None:
    image = str(_mcp_container()["image"])
    assert image.endswith(":${IMAGE_TAG}")
    assert not image.endswith(":latest")
    assert "/ai-buddy/mcp-server:" in image


def test_mcp_server_secrets_come_only_from_secret_manager() -> None:
    environment = _env(_mcp_container())
    expected = {
        "GOOGLE_CLIENT_SECRET": "google-client-secret",
        "OAUTH_JWT_SIGNING_KEY": "oauth-jwt-signing-key",
        "OAUTH_STORAGE_ENCRYPTION_KEY": "oauth-storage-encryption-key",
    }
    for name, secret in expected.items():
        reference = environment[name]["valueFrom"]["secretKeyRef"]
        assert reference == {"name": secret, "key": "latest"}, name
        assert "value" not in environment[name], f"{name} has a literal value"
    for name, entry in environment.items():
        if name.endswith(SECRET_SUFFIXES):
            assert "secretKeyRef" in entry.get("valueFrom", {}), f"{name} must be a secretKeyRef"


def test_mcp_server_names_the_bot_service_account_and_uses_no_key_file() -> None:
    environment = _env(_mcp_container())
    assert environment["BOT_SA_EMAILS"]["value"] == (
        "sa-chat-bot@${PROJECT_ID}.iam.gserviceaccount.com"
    )
    assert _pod_spec(_mcp())["serviceAccountName"] == (
        "sa-mcp-server@${PROJECT_ID}.iam.gserviceaccount.com"
    )
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in environment, "keyless: no key file anywhere"
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in MCP_FILE.read_text(encoding="utf-8")


def test_mcp_server_startup_probe_is_a_tcp_check_on_the_container_port() -> None:
    probe = _mcp_container()["startupProbe"]
    assert probe["tcpSocket"]["port"] == 8000
    limits = _mcp_container()["resources"]["limits"]
    assert limits == {"cpu": "1", "memory": "512Mi"}


def test_templates_hold_no_project_identifier() -> None:
    twelve_digits = re.compile(r"(?<![0-9])[0-9]{12}(?![0-9])")
    for path in [*CLOUDRUN.glob("*"), RENDER_SCRIPT]:
        if path.name == ".gitkeep" or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        assert PROJECT_ID_LITERAL not in text, f"{path.name}: a project id leaked"
        assert not twelve_digits.search(text), f"{path.name}: a project number leaked"


def test_render_script_substitutes_an_explicit_variable_list_and_refuses_leftovers() -> None:
    script = RENDER_SCRIPT.read_text(encoding="utf-8")
    assert "set -euo pipefail" in script
    assert "envsubst " in script
    assert 'envsubst "${SUBSTITUTIONS}"' in script, "an explicit variable list, never bare envsubst"
    assert "deploy/meridian.version" in script, "MERIDIAN_TAG defaults to the approved commit"
    assert "unrendered placeholder" in script
    assert "set -x" not in script, "tracing would print rendered values"
    for name in (
        "PROJECT_ID",
        "PROJECT_NUMBER",
        "IMAGE_TAG",
        "MERIDIAN_TAG",
        "GOOGLE_CLIENT_ID",
        "GUIDES_WEB_BASE",
        "CHAT_JWT_ISSUER_EMAIL",
        "VIDEO_THUMBNAIL_URL",
        "HELP_COMMAND_ID",
    ):
        assert re.search(rf"^\s+{name}$", script, re.MULTILINE), f"{name} not in the fixed list"


def test_chat_bot_is_a_knative_service_with_exactly_one_port_on_the_ingress_container() -> None:
    service = _bot()
    assert service["apiVersion"] == "serving.knative.dev/v1"
    assert service["kind"] == "Service"
    assert service["metadata"]["name"] == "chat-bot"
    assert service["metadata"]["annotations"]["run.googleapis.com/invoker-iam-disabled"] == "true"
    declared = {
        name: [port["containerPort"] for port in container.get("ports", [])]
        for name, container in _containers(service).items()
    }
    assert declared == {"chat-bot": [8080], "meridian": []}, "only the ingress container has a port"
    assert "PORT" not in _env(_bot_container("chat-bot")), "Cloud Run injects PORT"
    assert _pod_spec(service)["serviceAccountName"] == (
        "sa-chat-bot@${PROJECT_ID}.iam.gserviceaccount.com"
    )


def test_chat_bot_sidecar_starts_first_on_gen2_and_scales_to_zero() -> None:
    annotations = _template_annotations(_bot())
    assert annotations["run.googleapis.com/execution-environment"] == "gen2", "FUSE needs gen2"
    assert annotations["autoscaling.knative.dev/minScale"] == "0", "D-01"
    assert annotations["autoscaling.knative.dev/maxScale"] == "1", "one Meridian, one token writer"
    assert annotations["run.googleapis.com/startup-cpu-boost"] == "true"
    dependencies = json.loads(annotations["run.googleapis.com/container-dependencies"])
    assert dependencies == {"chat-bot": ["meridian"]}, "meridian must start before the bot"


def test_chat_bot_uses_request_based_billing_and_names_the_fallback() -> None:
    assert BILLING_MODE == "a", "04-01 billing_mode changed: revisit this annotation rule"
    assert "run.googleapis.com/cpu-throttling" not in _template_annotations(_bot())
    comments = "\n".join(
        line for line in BOT_FILE.read_text(encoding="utf-8").splitlines() if "#" in line
    )
    assert "cpu-throttling" in comments, "the prepared fallback is named in a comment"
    assert "consent" in comments, "and says it needs Joshua's consent (RESEARCH Pitfall 1)"


def test_chat_bot_single_user_guards_hold_while_the_llm_is_meridian() -> None:
    environment = _env(_bot_container("chat-bot"))
    assert environment["LLM_BACKEND"]["value"] == "meridian"
    assert _template_annotations(_bot())["autoscaling.knative.dev/maxScale"] == "1", (
        "D1a: never more than one instance on one person's Max login"
    )
    reference = environment["ALLOWED_USERS"]["valueFrom"]["secretKeyRef"]
    assert reference == {"name": "allowed-users", "key": "latest"}, "one entry, from a secret"
    assert "value" not in environment["ALLOWED_USERS"], "no personal id in a public repo"


def test_chat_bot_serves_http_intake_and_verifies_the_chat_jwt() -> None:
    environment = _env(_bot_container("chat-bot"))
    assert environment["INTAKE"]["value"] == "http", "D-13"
    assert environment["MCP_AUTH"]["value"] == "google_id_token", "T-04-27"
    assert environment["BOT_HOST"]["value"] == "0.0.0.0"
    assert environment["CHAT_JWT_ISSUER_EMAIL"]["value"] == "${CHAT_JWT_ISSUER_EMAIL}"
    assert environment["LLM_BASE_URL"]["value"] == "http://localhost:3456"
    assert "PUBSUB_SUBSCRIPTION" not in environment, "the Pub/Sub intake never runs on Cloud Run"
    probe = _bot_container("chat-bot")["startupProbe"]
    assert probe["tcpSocket"]["port"] == 8080


def test_chat_bot_fails_closed_on_cloud_run_through_the_unset_production_marker() -> None:
    environment = _env(_bot_container("chat-bot"))
    assert "DEPLOY_ENV" not in environment, "04-03: unset means production (fail closed)"
    assert environment.get("CHAT_API", {"value": "google"})["value"] == "google", "T-04-10"
    assert "CHAT_RECORD_PATH" not in environment, "the recording adapter is local only"
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in BOT_FILE.read_text(encoding="utf-8")


def test_chat_bot_secrets_come_only_from_secret_manager() -> None:
    expected = {
        "ALLOWED_USERS": "allowed-users",
        "THREAD_KEY_SECRET": "thread-key-secret",
        "MERIDIAN_API_KEY": "meridian-api-key",
    }
    for container_name in ("chat-bot", "meridian"):
        environment = _env(_bot_container(container_name))
        for name, entry in environment.items():
            if name.endswith(SECRET_SUFFIXES) or name in expected:
                reference = entry["valueFrom"]["secretKeyRef"]
                assert reference == {"name": expected[name], "key": "latest"}, name
                assert "value" not in entry, f"{container_name}: {name} has a literal value"
    assert BOT_FILE.read_text(encoding="utf-8").count("secretKeyRef") >= 4


def test_chat_bot_logs_no_question_text_with_a_user_identity() -> None:
    bot = _env(_bot_container("chat-bot"))
    meridian = _env(_bot_container("meridian"))
    assert bot["LANGSMITH_TRACING"]["value"] == "false", "BOT-11: prompts stay on the host"
    assert meridian["MERIDIAN_SILENT"]["value"] == "1", "BOT-11: no per-request log lines"
    for container_name in ("chat-bot", "meridian"):
        for name in _env(_bot_container(container_name)):
            assert "DEBUG" not in name.upper(), f"{container_name}: {name} would log requests"
            assert not name.startswith("LANGCHAIN_"), f"{name} could re-enable tracing"


def test_meridian_sidecar_is_loopback_only_and_has_no_exposed_port() -> None:
    meridian = _bot_container("meridian")
    environment = _env(meridian)
    assert "ports" not in meridian, "T-04-28: no port on the sidecar"
    assert environment["MERIDIAN_HOST"]["value"] == "127.0.0.1", "T-04-28"
    assert environment["MERIDIAN_PORT"]["value"] == "3456"
    assert environment["MERIDIAN_HOST_ID"]["value"] == "meridian-cloudrun"
    assert "MERIDIAN_CREDENTIALS_READONLY" not in environment, "only this instance refreshes"
    assert meridian["resources"]["limits"] == {"cpu": "1", "memory": "1Gi"}


def test_meridian_sidecar_startup_probe_is_a_supported_http_probe_on_the_health_route() -> None:
    probe = _bot_container("meridian")["startupProbe"]
    assert set(probe) - {"periodSeconds", "timeoutSeconds", "failureThreshold"} == {"httpGet"}, (
        "Cloud Run supports httpGet, tcpSocket and grpc probes, never exec (04-07 used exec on kind)"
    )
    assert probe["httpGet"]["port"] == 3456
    assert probe["httpGet"]["path"] == "/health", (
        "/readyz answers 503 'no profiles configured' for the single credentials file this "
        "deployment seeds, exactly as on kind (04-07); /health is 200 once the login is read"
    )


def test_meridian_credentials_fuse_volume_is_mounted_read_write_in_meridian_only() -> None:
    volumes = _volumes(_bot())
    creds = volumes["claude-creds"]["csi"]
    assert creds["driver"] == "gcsfuse.run.googleapis.com"
    assert creds["readOnly"] is False, "the OAuth refresh must be written back"
    assert creds["volumeAttributes"]["bucketName"] == "${PROJECT_ID}-ai-buddy-claude"
    options = dict(item.split("=", 1) for item in creds["volumeAttributes"]["mountOptions"].split(","))
    assert options["uid"] == options["gid"] == "1000", "the Meridian image user owns the files"
    mounts = {
        name: {mount["name"]: mount["mountPath"] for mount in container.get("volumeMounts", [])}
        for name, container in _containers(_bot()).items()
    }
    assert mounts["meridian"]["claude-creds"] == "/home/claude/.claude"
    assert "claude-creds" not in mounts["chat-bot"], "T-04-29: the bot never sees the credentials"


def test_meridian_transcripts_expire_and_the_session_store_stays_in_memory() -> None:
    environment = _env(_bot_container("meridian"))
    retention = int(environment["MERIDIAN_TRANSCRIPT_RETENTION_DAYS"]["value"])
    assert 1 <= retention <= 30, "a retention period bounds the questions kept in the bucket"
    volumes = _volumes(_bot())
    memory = [name for name, volume in volumes.items() if "emptyDir" in volume]
    assert len(memory) == 1
    assert volumes[memory[0]]["emptyDir"]["medium"] == "Memory"
    assert volumes[memory[0]]["emptyDir"]["sizeLimit"]
    mounts = {m["name"]: m["mountPath"] for m in _bot_container("meridian")["volumeMounts"]}
    assert environment["MERIDIAN_SESSION_DIR"]["value"] == mounts[memory[0]]
    assert len(volumes) == 2, "the credentials volume and the in-memory volume only"


def test_meridian_image_tag_placeholder_is_rendered_from_the_approved_commit() -> None:
    image = str(_bot_container("meridian")["image"])
    assert image == "europe-west8-docker.pkg.dev/${PROJECT_ID}/ai-buddy/meridian:${MERIDIAN_TAG}"
    chat_image = str(_bot_container("chat-bot")["image"])
    assert chat_image.endswith("/ai-buddy/chat-bot:${IMAGE_TAG}")
    script = RENDER_SCRIPT.read_text(encoding="utf-8")
    assert "deploy/meridian.version" in script
    assert re.fullmatch(r"[0-9a-f]{40}\n?", MERIDIAN_VERSION_FILE.read_text(encoding="utf-8"))


def test_chat_bot_audience_calls_equal_the_server_public_url_and_its_mcp_endpoint() -> None:
    server_url = str(_env(_mcp_container())["MCP_PUBLIC_BASE_URL"]["value"])
    bot = _env(_bot_container("chat-bot"))
    assert bot["MCP_AUDIENCE"]["value"] == server_url, "audit warning 2: audience must match"
    assert bot["MCP_URL"]["value"] == f"{server_url}/mcp"


def test_chat_bot_audience_for_the_chat_jwt_is_its_own_deterministic_url() -> None:
    bot = _env(_bot_container("chat-bot"))
    audience = str(bot["CHAT_JWT_AUDIENCE"]["value"])
    assert audience == "https://chat-bot-${PROJECT_NUMBER}.europe-west8.run.app"
    assert audience.endswith(REGION_URL_SUFFIX)


def test_server_names_the_bot_runtime_service_account_as_an_allowed_caller() -> None:
    account = str(_pod_spec(_bot())["serviceAccountName"])
    allowed = str(_env(_mcp_container())["BOT_SA_EMAILS"]["value"])
    assert allowed.split(",") == [account]
