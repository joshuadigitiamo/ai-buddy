"""Offline structural guard over deploy/k8s (INFRA-03): the kind base and the dev overlay.

The Kustomize build and the kubeconform schema check need kubectl and Docker, so they run in
scripts/validate-infra.sh. This guard parses the YAML sources directly and keeps the security,
resource and secret rules from regressing without either tool.
"""

import re
import shlex
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
K8S = ROOT / "deploy" / "k8s"
BASE = K8S / "base"
DEV = K8S / "overlays" / "dev"
KIND_CONFIG = K8S / "kind-config.yaml"
README = K8S / "README.md"
MERIDIAN_VERSION_FILE = ROOT / "deploy" / "meridian.version"
COMPOSE_FILE = ROOT / "docker-compose.yml"
KIND_UP = ROOT / "scripts" / "kind-up.sh"
KIND_SMOKE = ROOT / "scripts" / "kind-smoke.sh"
VALIDATE_INFRA = ROOT / "scripts" / "validate-infra.sh"

APP_UID = 10001
SECRET_SUFFIXES = ("_KEY", "_SECRET", "_TOKEN")
WORKLOAD_KINDS = ("Deployment", "Job")
LOCAL_ONLY_KNOBS = {"DEPLOY_ENV": "local", "AUTH_MODE": "off", "MCP_AUTH": "none"}

Doc = dict[str, Any]


def _documents(path: Path) -> list[Doc]:
    loaded = [doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc]
    assert all(isinstance(doc, dict) for doc in loaded), f"{path.name}: every document is a mapping"
    return loaded


def _manifest_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.yaml"))


def _base_resources() -> list[Doc]:
    docs: list[Doc] = []
    for path in _manifest_files(BASE):
        if path.name != "kustomization.yaml":
            docs.extend(_documents(path))
    return docs


def _workloads() -> dict[str, Doc]:
    return {
        str(doc["metadata"]["name"]): doc
        for doc in _base_resources()
        if doc["kind"] in WORKLOAD_KINDS
    }


def _pod_spec(workload: Doc) -> Doc:
    spec = workload["spec"]["template"]["spec"]
    assert isinstance(spec, dict)
    return spec


def _containers(workload: Doc) -> Iterator[Doc]:
    spec = _pod_spec(workload)
    yield from spec.get("initContainers", [])
    yield from spec["containers"]


def _container(workload: str, name: str) -> Doc:
    for container in _containers(_workloads()[workload]):
        if container["name"] == name:
            return container
    raise AssertionError(f"{workload} has no container {name}")


def _env(container: Doc) -> dict[str, Doc]:
    return {str(entry["name"]): entry for entry in container.get("env", [])}


def _overlay() -> Doc:
    docs = _documents(DEV / "kustomization.yaml")
    assert len(docs) == 1
    return docs[0]


def _overlay_literals() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for generator in _overlay()["configMapGenerator"]:
        pairs = (str(item).split("=", 1) for item in generator["literals"])
        result[str(generator["name"])] = {key: value for key, value in pairs}
    return result


def test_every_container_has_cpu_and_memory_requests_and_limits() -> None:
    workloads = _workloads()
    assert workloads, "no Deployment or Job found under deploy/k8s/base"
    for workload_name, workload in workloads.items():
        for container in _containers(workload):
            resources = container.get("resources", {})
            for section in ("requests", "limits"):
                for resource in ("cpu", "memory"):
                    assert resources.get(section, {}).get(resource), (
                        f"{workload_name}/{container['name']} lacks {section}.{resource}"
                    )


def test_app_containers_run_restricted_as_the_image_user() -> None:
    for app in ("mcp-server", "chat-bot"):
        context = _container(app, app)["securityContext"]
        assert context["runAsNonRoot"] is True
        assert context["runAsUser"] == APP_UID, "the images end with USER 10001 (04-05)"
        assert context["allowPrivilegeEscalation"] is False
        assert context["capabilities"]["drop"] == ["ALL"]
        assert context["readOnlyRootFilesystem"] is True
    for workload_name, workload in _workloads().items():
        for container in _containers(workload):
            context = container["securityContext"]
            assert context["allowPrivilegeEscalation"] is False, (workload_name, container["name"])
            assert context["capabilities"]["drop"] == ["ALL"], (workload_name, container["name"])


def test_chat_bot_runs_meridian_as_a_loopback_native_sidecar() -> None:
    meridian = _container("chat-bot", "meridian")
    assert meridian in _pod_spec(_workloads()["chat-bot"])["initContainers"]
    assert meridian["restartPolicy"] == "Always", (
        "a native sidecar is an init container that keeps running"
    )
    assert meridian["startupProbe"], "the bot must not start before Meridian answers"
    environment = _env(meridian)
    assert environment["MERIDIAN_HOST"]["value"] == "127.0.0.1", "no other pod may reach Meridian"
    assert environment["MERIDIAN_SILENT"]["value"] == "1", "BOT-11: no per-request lines in logs"
    assert environment["MERIDIAN_CREDENTIALS_READONLY"]["value"] == "1", "04-01 token_chain"
    bot_env = _env(_container("chat-bot", "chat-bot"))
    assert bot_env["LLM_BASE_URL"]["value"] == "http://localhost:3456", (
        "same as the Cloud Run sidecar"
    )
    assert bot_env["LLM_BACKEND"]["value"] == "meridian"


def test_meridian_credentials_arrive_only_through_secret_references() -> None:
    spec = _pod_spec(_workloads()["chat-bot"])
    seed = _container("chat-bot", "seed-credentials")
    mounts = {mount["name"]: mount for mount in seed["volumeMounts"]}
    assert mounts["meridian-credentials"]["readOnly"] is True
    volumes = {volume["name"]: volume for volume in spec["volumes"]}
    assert volumes["meridian-credentials"]["secret"]["secretName"] == "meridian-credentials"
    assert "emptyDir" in volumes["meridian-home"], "the copy lands in an emptyDir, not a host path"
    for name in ("MERIDIAN_API_KEY", "THREAD_KEY_SECRET"):
        reference = _env(_container("chat-bot", "chat-bot"))[name]["valueFrom"]["secretKeyRef"]
        assert reference == {"name": "bot-secrets", "key": name}
    key_reference = _env(_container("chat-bot", "meridian"))["MERIDIAN_API_KEY"]["valueFrom"]
    assert key_reference["secretKeyRef"] == {"name": "bot-secrets", "key": "MERIDIAN_API_KEY"}


def test_mcp_server_probes_call_healthz_with_the_service_host_header() -> None:
    container = _container("mcp-server", "mcp-server")
    for probe in ("readinessProbe", "livenessProbe"):
        http_get = container[probe]["httpGet"]
        assert http_get["path"] == "/healthz"
        assert {"name": "Host", "value": "mcp-server"} in http_get["httpHeaders"], (
            "the Host guard rejects the pod IP kubelet would send (04-02)"
        )


def test_every_workload_carries_the_recommended_labels() -> None:
    for name, workload in _workloads().items():
        template = workload["spec"]["template"]["metadata"]["labels"]
        for labels in (workload["metadata"]["labels"], template):
            assert labels["app.kubernetes.io/name"] == name
            assert labels["app.kubernetes.io/part-of"] == "ai-buddy"
        if workload["kind"] == "Deployment":
            selector = workload["spec"]["selector"]["matchLabels"]
            assert selector == {"app.kubernetes.io/name": name}
    for doc in _base_resources():
        if doc["kind"] == "Service":
            assert doc["metadata"]["labels"]["app.kubernetes.io/part-of"] == "ai-buddy"


def test_no_secret_object_and_no_literal_secret_value_anywhere_under_deploy_k8s() -> None:
    files = [path for path in K8S.rglob("*.yaml") if path.name != "kind-config.yaml"]
    assert files
    for path in files:
        for doc in _documents(path):
            assert doc.get("kind") != "Secret", f"{path}: Secrets are created by kind-up.sh (D-15)"
            if doc.get("kind") == "Kustomization":
                assert "secretGenerator" not in doc, f"{path}: no secretGenerator"
    literals = _overlay_literals()
    for name, pairs in literals.items():
        for key in pairs:
            assert not key.endswith(SECRET_SUFFIXES), (
                f"ConfigMap {name} carries a secret-named key {key}"
            )
    for workload_name, workload in _workloads().items():
        for container in _containers(workload):
            for env_name, entry in _env(container).items():
                if env_name.endswith(SECRET_SUFFIXES):
                    assert "value" not in entry, f"{workload_name}: {env_name} has a literal value"
                    assert "secretKeyRef" in entry["valueFrom"]


def test_images_are_pinned_and_the_overlay_meridian_tag_equals_the_approved_commit() -> None:
    overlay_tags = {str(item["name"]): str(item["newTag"]) for item in _overlay()["images"]}
    used: set[str] = set()
    for workload in _workloads().values():
        for container in _containers(workload):
            image = str(container["image"])
            name, _, tag = image.partition(":")
            used.add(name)
            effective = tag or overlay_tags.get(name, "")
            assert effective and effective != "latest", f"{image} must resolve to a pinned tag"
    assert set(overlay_tags) <= used, "the overlay pins an image no workload uses"
    assert {tag for tag in overlay_tags.values() if tag == "latest"} == set()
    pinned = MERIDIAN_VERSION_FILE.read_text(encoding="utf-8").strip()
    assert overlay_tags["ai-buddy/meridian"] == pinned, "must equal deploy/meridian.version (D-14)"


def test_base_is_fail_closed_and_only_the_dev_overlay_sets_the_local_knobs() -> None:
    for doc in _base_resources():
        text = yaml.safe_dump(doc)
        for name, value in LOCAL_ONLY_KNOBS.items():
            assert not re.search(rf"name: {name}\s+value: {value}\b", text), (
                f"base sets {name}={value}: only an overlay may"
            )
        assert doc["kind"] != "ConfigMap", "base carries no configuration an overlay would override"
        assert "hostPath" not in text, "hostPath belongs to the dev overlay (D-10)"
    literals = _overlay_literals()
    assert literals["mcp-server-local"]["DEPLOY_ENV"] == "local"
    assert literals["chat-bot-local"]["DEPLOY_ENV"] == "local"
    assert literals["mcp-server-local"]["AUTH_MODE"] == "off"
    assert literals["chat-bot-local"]["MCP_AUTH"] == "none"
    assert literals["chat-bot-local"]["CHAT_API"] == "recording"
    assert literals["chat-bot-local"]["CHAT_RECORD_PATH"].startswith("/tmp/"), (
        "emptyDir /tmp exists"
    )


def test_bot_reaches_the_server_by_service_name_and_the_server_admits_that_host() -> None:
    bot_env = _env(_container("chat-bot", "chat-bot"))
    assert bot_env["MCP_URL"]["value"] == "http://mcp-server:8000/mcp"
    allowed = _overlay_literals()["mcp-server-local"]["MCP_ALLOWED_HOSTS"].split(",")
    assert "mcp-server" in allowed
    services = {
        str(doc["metadata"]["name"]): doc for doc in _base_resources() if doc["kind"] == "Service"
    }
    assert services["mcp-server"]["spec"]["ports"][0]["port"] == 8000
    assert bot_env["INTAKE"]["value"] == "pubsub"
    literals = _overlay_literals()["chat-bot-local"]
    assert literals["PUBSUB_EMULATOR_HOST"] == "pubsub-emulator:8085"
    assert literals["FIRESTORE_EMULATOR_HOST"] == "firestore-emulator:8080"
    assert "pubsub-emulator" in services and "firestore-emulator" in services


def test_emulators_match_the_compose_image_and_commands() -> None:
    compose = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))["services"]
    for workload, service in (("firestore-emulator", "firestore"), ("pubsub-emulator", "pubsub")):
        container = _container(workload, workload)
        assert container["image"] == compose[service]["image"]
        assert container["command"] == shlex.split(compose[service]["command"])
        assert container["readinessProbe"]["tcpSocket"]["port"] in (8080, 8085)


def test_pubsub_init_is_a_retrying_job_that_accepts_created_and_existing() -> None:
    job = _workloads()["pubsub-init"]
    assert job["kind"] == "Job"
    assert job["spec"]["backoffLimit"] == 6
    script = "\n".join(_container("pubsub-init", "pubsub-init")["command"])
    assert "200|409" in script
    assert "projects/demo-ai-buddy/topics/chat-events" in script
    assert "topics/chat-events" in script and "subscriptions/chat-events" in script


def test_artifacts_hostpath_is_read_only_and_lives_in_the_dev_overlay() -> None:
    docs = _documents(DEV / "artifacts-hostpath.yaml")
    spec = docs[0]["spec"]["template"]["spec"]
    assert spec["volumes"][0]["hostPath"] == {"path": "/artifacts", "type": "Directory"}
    mount = spec["containers"][0]["volumeMounts"][0]
    assert mount["mountPath"] == "/artifacts" and mount["readOnly"] is True


def test_dev_namespace_reports_restricted_without_enforcing_it() -> None:
    namespace = _documents(DEV / "namespace.yaml")[0]
    labels = namespace["metadata"]["labels"]
    assert labels["pod-security.kubernetes.io/warn"] == "restricted"
    assert labels["pod-security.kubernetes.io/audit"] == "restricted"
    assert "pod-security.kubernetes.io/enforce" not in labels, "hostPath and root emulators (D-10)"
    assert _overlay()["namespace"] == "ai-buddy"


def test_kind_config_extra_mounts_are_read_only() -> None:
    config = _documents(KIND_CONFIG)[0]
    mounts = [mount for node in config["nodes"] for mount in node.get("extraMounts", [])]
    assert mounts, "the artifact directory is mounted into the node"
    for mount in mounts:
        assert mount["readOnly"] is True
        assert mount["containerPath"] == "/artifacts"
    assert mounts[0]["hostPath"] == "__ARTIFACTS_DIR__", "kind-up.sh renders the real path"


def test_base_kustomization_lists_every_manifest_in_the_directory() -> None:
    kustomization = _documents(BASE / "kustomization.yaml")[0]
    listed = set(kustomization["resources"])
    present = {path.name for path in _manifest_files(BASE)} - {"kustomization.yaml"}
    assert listed == present


def test_kind_up_verifies_the_download_and_creates_secrets_without_printing_them() -> None:
    script = KIND_UP.read_text(encoding="utf-8")
    assert script.count("set -euo pipefail") == 1
    assert re.search(r"^\s*set\s+-\w*x", script, re.MULTILINE) is None, (
        "no xtrace: it would print secrets"
    )
    assert "sha256sum" in script and "v0.33.0" in script and "kindest/node:v1.37.0" in script
    assert script.count("kubectl create secret generic") == 2
    assert "--from-literal" not in script, "values never appear in a command line"
    assert "meridian.version" in script and "kind-config.yaml" in script
    assert "kind-config.yaml" in script and "__ARTIFACTS_DIR__" in script
    smoke = KIND_SMOKE.read_text(encoding="utf-8")
    assert smoke.count("kind smoke ok") == 1 and "/healthz" in smoke and "guides_search" in smoke


def test_validate_infra_runs_kubeconform_strict_over_base_and_every_overlay() -> None:
    script = VALIDATE_INFRA.read_text(encoding="utf-8")
    assert script.count("ghcr.io/yannh/kubeconform:v0.8.0") == 1
    assert "-strict" in script and "-kubernetes-version 1.37.0" in script
    assert "kubectl kustomize" in script
    assert "deploy/k8s/base" in script and "deploy/k8s/overlays" in script
    assert "set -euo pipefail" in script


def test_gitkeep_is_gone_and_the_readme_documents_the_workflow() -> None:
    assert not (K8S / ".gitkeep").exists()
    readme = README.read_text(encoding="utf-8")
    for needle in (
        "scripts/kind-up.sh",
        "scripts/kind-smoke.sh",
        "scripts/validate-infra.sh",
        "Pod Security",
        "meridian-claude",
        "MERIDIAN_CREDENTIALS_READONLY",
        "ARTIFACTS_DIR",
    ):
        assert needle in readme, f"README does not mention {needle}"
