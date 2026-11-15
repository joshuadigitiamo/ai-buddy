"""Structural pins of scripts/sync-and-publish.sh: the forced Cloud Run revision (INFRA-05, 04-20).

The script cannot run in the test image (it needs docker and gcloud), so these tests read its
text. CI names its revisions `<service>-r<run id>-<attempt>`; a publish names its own
`p<build>-<epoch>`, so the two never collide, and a second publish of the same build id (after an
index-object repair) still gets a new name.

04-24 (WR-03) adds the credential pins: the owner's gcloud login reaches only the pinned gcloud
image that mints tokens; every other container gets a short-lived token file.
"""

import re
import subprocess

from tests.unit.test_repo_layout import ROOT

SCRIPT = ROOT / "scripts" / "sync-and-publish.sh"


def _code() -> str:
    lines = SCRIPT.read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def test_forced_revision_names_itself_after_the_build() -> None:
    code = _code()
    update = [line for line in code.splitlines() if "run services update" in line]
    assert len(update) == 1
    assert '--revision-suffix "${REVISION_SUFFIX}"' in update[0]
    assert "INDEX_BUILD_ID" in update[0], "D-08 kept: the build id still goes into the env"
    assert "^[a-z0-9]([a-z0-9-]*[a-z0-9])?$" in code, "the suffix is checked against a DNS label"
    assert not re.search(r"\bset\s+-[a-z]*x", code), "tracing would print the project id"


def test_forced_revision_suffix_is_unique_per_run() -> None:
    code = _code()
    assigned = re.search(r'^REVISION_SUFFIX="p\$\{BUILD_PART\}-\$\(date -u \+%s\)"$', code, re.M)
    assert assigned, "the suffix is p, the build part, a hyphen and the epoch seconds of this run"
    assert "${BUILD_PART:0:32}" in code, "the build part is cut to 32 characters"
    assert re.search(r"\$\{#REVISION_SUFFIX\}\s*-gt\s*44|\$\{#REVISION_SUFFIX\}\s*>\s*44", code)
    assert code.index("REVISION_SUFFIX=") < code.index("run services update")


def _traffic_mode(lines: str) -> subprocess.CompletedProcess[str]:
    """Run the script's traffic_mode function on gcloud's flattened `percent,latestRevision` CSV."""
    match = re.search(r"^traffic_mode\(\) \{\n.*?^\}$", _code(), re.M | re.S)
    assert match, "traffic_mode() is defined at the top level of the script"
    return subprocess.run(
        ["bash", "-c", f"{match.group(0)}\ntraffic_mode"],
        input=lines,
        capture_output=True,
        text=True,
        check=False,
    )


def test_traffic_mode_accepts_only_one_latest_target_at_100() -> None:
    """Live 04-26: the cloud-sdk image has no python3, so the guard parses gcloud's CSV in bash."""
    assert _traffic_mode("100,True\n").stdout.strip() == "latest"
    assert _traffic_mode("100,True\n,False\n").stdout.strip() == "latest", "0% candidate tag"
    assert _traffic_mode("100,False\n0,True\n").stdout.strip() == "pinned"
    assert _traffic_mode("50,True\n50,False\n").stdout.strip() == "pinned"
    assert _traffic_mode("").returncode != 0, "no traffic read is unreadable, not latest"
    assert _traffic_mode("abc,True\n").returncode != 0


def test_forced_revision_waits_for_latest_revision_traffic() -> None:
    """Traffic pinned by an unfinished staged deploy must stop the forced revision."""
    code = _code()
    update = code.index("run services update")
    before = code[:update]
    assert re.search(r"run services describe .*--flatten spec\.traffic", before), (
        "the guard reads spec.traffic before it forces a revision"
    )
    assert "csv[no-heading](spec.traffic.percent,spec.traffic.latestRevision)" in before
    assert "python3" not in code, "the pinned cloud-sdk image ships no python3"
    assert re.search(r'TRAFFIC_MODE.*!=\s*"latest"', before), "anything but latest stops the script"
    refusal = [line for line in before.splitlines() if "pinned to a named revision" in line]
    assert len(refusal) == 1
    assert "${SERVICE}" in refusal[0], "the message names the service"
    assert "index is already published" in refusal[0]
    assert "next successful ${SERVICE} deploy will load it" in refusal[0]
    assert 'echo "${TRAFFIC_LINES}"' not in code, "the describe output is never printed"


# --- credentials (04-24, WR-03) ---------------------------------------------------------------


def _docker_runs() -> list[str]:
    """Every `docker run` command with its continuation lines joined into one line."""
    joined = re.sub(r"\\\n\s*", " ", _code())
    return [" ".join(line.split()) for line in joined.splitlines() if "docker run" in line]


def test_sync_image_never_receives_the_gcloud_config() -> None:
    code = _code()
    runs = _docker_runs()
    assert runs, "the script runs containers"
    mounting = [run for run in runs if ".config/gcloud" in run]
    assert len(mounting) == 2, "only the two token-minting containers mount the gcloud login"
    for run in mounting:
        assert "print-access-token" in run, "the login is mounted only to mint a token"
        assert '"${GCLOUD_IMAGE}"' in run, "and only into the pinned gcloud image"
        assert "IMAGE_NAME" not in run
    for run in runs:
        if "IMAGE_NAME" in run:
            assert "gcloud" not in run, "the sync image never sees the gcloud directory"
            assert "adc" not in run.lower()
    assert "GOOGLE_APPLICATION_CREDENTIALS" not in code
    assert "application_default_credentials" not in code
    assert "ADC_FILE" not in code


def test_sync_image_gets_the_publisher_token_as_a_read_only_file() -> None:
    runs = _docker_runs()
    for step in ("upload-videos", "publish"):
        (run,) = [r for r in runs if f'"${{IMAGE_NAME}}" {step}' in r]
        assert '-v "${TOKEN_DIR}/publisher:/run/gcs-token:ro"' in run
        assert "-e GCS_ACCESS_TOKEN_FILE=/run/gcs-token" in run
    code = _code()
    assert code.count("mint_publisher_token\n") == 2, "one fresh token before each bucket step"
    assert code.index("mint_publisher_token\n") < code.index('"${IMAGE_NAME}" upload-videos')
    assert "--impersonate-service-account=" in code
    assert 'PUBLISHER_SA="sa-publisher@${PROJECT_ID}.iam.gserviceaccount.com"' in code


def test_revision_step_runs_with_an_access_token_file() -> None:
    code = _code()
    (gcloud,) = [line for line in code.splitlines() if line.startswith("GCLOUD=(")]
    assert "--access-token-file=/run/owner-token" in gcloud
    assert '-v "${TOKEN_DIR}/owner:/run/owner-token:ro"' in gcloud
    assert "-e CLOUDSDK_CONFIG=/tmp/gcloud" in gcloud
    assert ".config/gcloud" not in gcloud, "the revision step never mounts the gcloud login"
    pinned = r'^GCLOUD_IMAGE="google/cloud-sdk:592\.0\.0-emulators@sha256:[0-9a-f]{64}"$'
    assert re.search(pinned, code, re.M)
    assert code.index("mint_owner_token\n") < code.index("GCLOUD=(")
    assert code.index("GCLOUD=(") < code.index("run services describe")


def test_token_files_live_in_a_private_directory_removed_on_exit_and_are_never_printed() -> None:
    code = _code()
    assert 'TOKEN_DIR="$(mktemp -d)"' in code
    assert 'chmod 700 "${TOKEN_DIR}"' in code
    assert 'chmod 600 "${token_file}"' in code
    assert "trap cleanup EXIT" in code
    assert 'rm -rf "${TOKEN_DIR}"' in code
    for line in code.splitlines():
        if "TOKEN_DIR" in line or "token_file" in line:
            assert not re.search(r"\b(echo|cat|printf|log)\b", line.replace("log()", "")), line
    assert "service-accounts keys" not in code, "no service account key is ever created"
