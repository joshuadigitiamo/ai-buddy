"""Offline structural guard over deploy/cloudrun (INFRA-04): the two Cloud Run service templates.

The templates carry ${PLACEHOLDER} markers that scripts/render-cloudrun.sh fills from environment
variables, so yaml.safe_load reads them as they are in git. A live `gcloud run services replace
--dry-run` runs in CI (04-09) and live in 04-13; this guard keeps the scale, secret, privacy and
cross-service rules from regressing without it.
"""

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CLOUDRUN = ROOT / "deploy" / "cloudrun"
MCP_FILE = CLOUDRUN / "mcp-server.yaml"
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
