from __future__ import annotations

import sys

import pytest

from app.core.executors import LocalExecutor


@pytest.mark.asyncio
async def test_local_executor_runs_command() -> None:
    executor = LocalExecutor()

    result = await executor.run([sys.executable, "-c", "print('executor-ok')"])

    assert result.ok is True
    assert result.exit_code == 0
    assert "executor-ok" in result.stdout


@pytest.mark.asyncio
async def test_local_executor_returns_nonzero_exit_code() -> None:
    executor = LocalExecutor()

    result = await executor.run([sys.executable, "-c", "import sys; sys.exit(3)"])

    assert result.ok is False
    assert result.exit_code == 3
