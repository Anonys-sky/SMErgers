"""The shared workspace/published launcher must supervise both services."""
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

import pytest

pytestmark = pytest.mark.skipif(
    not hasattr(os, "killpg"), reason="the launcher script needs a POSIX shell (Linux or macOS)"
)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "start-application.sh"


def wait_for(predicate, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for child services")


def is_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


@pytest.fixture
def launcher(tmp_path):
    binaries = tmp_path / "bin"
    binaries.mkdir()
    for service in ("node", "python"):
        executable = binaries / service
        executable.write_text(
            f"#!{shutil.which('bash')}\n"
            f'service="{service}"\n'
            'echo $$ > "$SERVICE_TEST_DIR/$service.pid"\n'
            "trap 'exit 0' TERM INT\n"
            'if [[ "${FAIL_SERVICE:-}" == "$service" ]]; then\n'
            '  while [[ ! -f "$SERVICE_TEST_DIR/node.pid" || ! -f "$SERVICE_TEST_DIR/python.pid" ]]; do sleep 0.02; done\n'
            '  exit "${FAIL_STATUS:-7}"\n'
            "fi\n"
            "while :; do sleep 0.02; done\n"
        )
        executable.chmod(0o755)
    processes = []

    def start(**extra_env):
        env = dict(os.environ, PATH=f"{binaries}{os.pathsep}{os.environ['PATH']}",
                   SERVICE_TEST_DIR=str(tmp_path), **extra_env)
        proc = subprocess.Popen(["bash", str(SCRIPT)], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                start_new_session=True)
        processes.append(proc)
        return proc

    yield start, tmp_path
    for proc in processes:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate(timeout=5)


@pytest.mark.parametrize("service", ["node", "python"])
@pytest.mark.parametrize("exit_status", [0, 7])
def test_either_service_exit_stops_the_other(launcher, service, exit_status):
    start, directory = launcher
    proc = start(FAIL_SERVICE=service, FAIL_STATUS=str(exit_status))
    output, _ = proc.communicate(timeout=5)
    assert proc.returncode == (exit_status or 1), output
    for service_name in ("node", "python"):
        pid = int((directory / f"{service_name}.pid").read_text())
        assert not is_alive(pid)


def test_termination_stops_both_services(launcher):
    start, directory = launcher
    proc = start()
    wait_for(lambda: all((directory / f"{s}.pid").exists() for s in ("node", "python")))
    proc.terminate()
    output, _ = proc.communicate(timeout=5)
    assert proc.returncode == 143, output
    for service in ("node", "python"):
        pid = int((directory / f"{service}.pid").read_text())
        assert not is_alive(pid)


def test_the_app_keeps_serving_when_only_the_bridge_stops_if_asked_to(launcher):
    start, directory = launcher
    proc = start(FAIL_SERVICE="node", FAIL_STATUS="7", SMERGERS_KEEP_APP_UP="1")
    wait_for(lambda: all((directory / f"{s}.pid").exists() for s in ("node", "python")))
    time.sleep(0.5)                                         # the fake bridge exits as soon as both are up
    assert proc.poll() is None                              # the launcher is still supervising the app
    assert is_alive(int((directory / "python.pid").read_text()))
    proc.terminate()
    output, _ = proc.communicate(timeout=5)
    assert proc.returncode == 143, output
    assert not is_alive(int((directory / "python.pid").read_text()))
