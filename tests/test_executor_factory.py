from app.core.config.models import ConnectionConfig, TransportsConfig
from app.core.executors import ExecutorFactory, LocalExecutor, SSHExecutor


def test_executor_factory_returns_local_executor() -> None:
    factory = ExecutorFactory(TransportsConfig())

    executor = factory.create(ConnectionConfig(mode="local"))

    assert isinstance(executor, LocalExecutor)


def test_executor_factory_returns_ssh_executor() -> None:
    factory = ExecutorFactory(TransportsConfig())

    executor = factory.create(ConnectionConfig(mode="ssh", ssh_alias="my-host"))

    assert isinstance(executor, SSHExecutor)
