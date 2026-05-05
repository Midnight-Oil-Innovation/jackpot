"""I-3b: ``run_seqsender`` async subprocess wrapper.

These tests do NOT call the real Seqsender. They mock
``asyncio.create_subprocess_exec`` so the wrapper is exercised end-to-end
without depending on Seqsender being installed.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.submission_executors.seqsender import SeqsenderRunResult, run_seqsender


class _FakeProcess:
    """Stand-in for asyncio.subprocess.Process."""

    def __init__(
        self,
        *,
        exit_code: int = 0,
        stdout: bytes = b"",
        stderr: bytes = b"",
        delay_seconds: float = 0.0,
    ) -> None:
        self._exit_code = exit_code
        self._stdout = stdout
        self._stderr = stderr
        self._delay = delay_seconds
        self.returncode: int | None = None
        self.killed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        if self._delay:
            await asyncio.sleep(self._delay)
        if not self.killed:
            self.returncode = self._exit_code
        return self._stdout, self._stderr

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


@pytest.fixture
def working_dir(tmp_path):
    d = tmp_path / "wd"
    d.mkdir()
    return d


@pytest.fixture
def package_dir(tmp_path):
    d = tmp_path / "pkg"
    d.mkdir()
    return d


@pytest.fixture
def config_path(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text("Submission:\n  NCBI:\n    Username: u\n    Password: p\n")
    return p


async def _patched_run(*, fake: _FakeProcess, **kwargs):
    async def _spawn(*args, **kw):
        return fake

    with patch("asyncio.create_subprocess_exec", AsyncMock(side_effect=_spawn)):
        return await run_seqsender(**kwargs)


@pytest.mark.asyncio
async def test_successful_run(working_dir, package_dir, config_path):
    fake = _FakeProcess(exit_code=0, stdout=b"ok\n", stderr=b"")
    result = await _patched_run(
        fake=fake,
        working_dir=working_dir,
        config_path=config_path,
        package_dir=package_dir,
        target_repo="NCBI",
        binary_path="/opt/seqsender/seqsender-kickoff",
        timeout_seconds=60,
    )
    assert isinstance(result, SeqsenderRunResult)
    assert result.exit_code == 0
    assert result.stdout_bytes == b"ok\n"
    assert result.stderr_bytes == b""
    assert result.timed_out is False
    assert result.invocation_command[0] == "/opt/seqsender/seqsender-kickoff"
    assert "submit" in result.invocation_command
    assert str(config_path) in result.invocation_command
    assert str(package_dir) in result.invocation_command
    assert result.wall_time_seconds >= 0


@pytest.mark.asyncio
async def test_failed_run_captures_output(working_dir, package_dir, config_path):
    fake = _FakeProcess(exit_code=1, stdout=b"partial output\n", stderr=b"Error: bad creds\n")
    result = await _patched_run(
        fake=fake,
        working_dir=working_dir,
        config_path=config_path,
        package_dir=package_dir,
        target_repo="NCBI",
        binary_path="seqsender-kickoff",
        timeout_seconds=60,
    )
    assert result.exit_code == 1
    assert result.stdout_bytes == b"partial output\n"
    assert b"bad creds" in result.stderr_bytes
    assert result.timed_out is False


@pytest.mark.asyncio
async def test_timeout_kills_subprocess(working_dir, package_dir, config_path):
    fake = _FakeProcess(exit_code=0, stdout=b"slow", stderr=b"", delay_seconds=2.0)
    result = await _patched_run(
        fake=fake,
        working_dir=working_dir,
        config_path=config_path,
        package_dir=package_dir,
        target_repo="NCBI",
        binary_path="seqsender-kickoff",
        timeout_seconds=1,  # sub-process delay > timeout
    )
    assert result.timed_out is True
    assert fake.killed is True


@pytest.mark.asyncio
async def test_argv_includes_test_flag_when_test_mode(working_dir, package_dir, config_path):
    fake = _FakeProcess(exit_code=0)
    result = await _patched_run(
        fake=fake,
        working_dir=working_dir,
        config_path=config_path,
        package_dir=package_dir,
        target_repo="NCBI",
        binary_path="seqsender-kickoff",
        timeout_seconds=60,
        test_mode=True,
    )
    assert "--test" in result.invocation_command


@pytest.mark.asyncio
async def test_argv_omits_test_flag_when_not_test_mode(working_dir, package_dir, config_path):
    fake = _FakeProcess(exit_code=0)
    result = await _patched_run(
        fake=fake,
        working_dir=working_dir,
        config_path=config_path,
        package_dir=package_dir,
        target_repo="NCBI",
        binary_path="seqsender-kickoff",
        timeout_seconds=60,
        test_mode=False,
    )
    assert "--test" not in result.invocation_command


@pytest.mark.asyncio
async def test_non_ncbi_target_raises_value_error(working_dir, package_dir, config_path):
    """run_seqsender is the last line of defense — execute_submission
    rejects non-NCBI earlier, but if a future call site forgets, this
    raises rather than silently dispatching to a wrong tool."""
    with pytest.raises(ValueError):
        await run_seqsender(
            working_dir=working_dir,
            config_path=config_path,
            package_dir=package_dir,
            target_repo="ENA",
            binary_path="seqsender-kickoff",
            timeout_seconds=60,
        )


@pytest.mark.asyncio
async def test_invocation_command_includes_database_flags(working_dir, package_dir, config_path):
    fake = _FakeProcess(exit_code=0)
    result = await _patched_run(
        fake=fake,
        working_dir=working_dir,
        config_path=config_path,
        package_dir=package_dir,
        target_repo="NCBI",
        binary_path="seqsender-kickoff",
        timeout_seconds=60,
    )
    cmd = result.invocation_command
    for flag in ("--biosample", "--sra", "--genbank"):
        assert flag in cmd
