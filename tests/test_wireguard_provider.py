from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config.models import ProviderConfig, ProviderType
from app.core.executors.base import BaseExecutor
from app.core.executors.models import CommandResult
from app.providers import ProviderFactory, ProviderRegistry
from app.providers.wireguard import WireGuardProvider, WireGuardProviderSettings


class FakeExecutor(BaseExecutor):
    def __init__(self, results: Mapping[tuple[str, ...], CommandResult]) -> None:
        self.results = dict(results)
        self.commands: list[tuple[str, ...]] = []
        self.inputs: list[str | None] = []

    async def run(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: int | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        input_text: str | None = None,
    ) -> CommandResult:
        normalized = self.normalize_command(command)
        self.commands.append(normalized)
        self.inputs.append(input_text)
        return self.results[normalized]


def _result(command: tuple[str, ...], stdout: str = "", exit_code: int = 0) -> CommandResult:
    return CommandResult(
        command=command,
        exit_code=exit_code,
        stdout=stdout,
        stderr="",
        duration_ms=5,
    )


def _provider_config(settings: dict[str, object] | None = None) -> ProviderConfig:
    return ProviderConfig(
        type=ProviderType.WIREGUARD,
        settings={
            "wireguard_interface": "wg0",
            "runtime": "systemd",
            "systemd_service_name": "wg-quick@wg0",
            "client_config_dir": "/etc/wireguard/clients",
            **(settings or {}),
        },
    )


def test_wireguard_settings_validate_save_config_strategy() -> None:
    settings = WireGuardProviderSettings.model_validate(
        {"wireguard_interface": "wg0", "apply_strategy": "wg_quick_save"}
    )

    assert settings.apply_strategy == "wg_quick_save"


def test_wireguard_settings_validate_docker_runtime_requires_container() -> None:
    with pytest.raises(ValidationError):
        WireGuardProviderSettings.model_validate(
            {"wireguard_interface": "wg0", "runtime": "docker"}
        )


@pytest.mark.asyncio
async def test_wireguard_healthcheck_uses_systemd_service_status() -> None:
    command = ("systemctl", "is-active", "wg-quick@wg0")
    executor = FakeExecutor({command: _result(command, stdout="active\n")})
    provider = WireGuardProvider(_provider_config(), executor=executor)

    assert await provider.healthcheck() is True
    assert executor.commands == [command]


@pytest.mark.asyncio
async def test_wireguard_healthcheck_uses_docker_container_status() -> None:
    command = ("docker", "inspect", "-f", "{{.State.Running}}", "wireguard")
    executor = FakeExecutor({command: _result(command, stdout="true\n")})
    provider = WireGuardProvider(
        _provider_config(
            {
                "runtime": "docker",
                "docker_container_name": "wireguard",
            }
        ),
        executor=executor,
    )

    assert await provider.healthcheck() is True
    assert executor.commands == [command]


@pytest.mark.asyncio
async def test_wireguard_list_clients_parses_peer_dump() -> None:
    command = ("wg", "show", "wg0", "dump")
    dump = "\n".join(
        [
            "priv\tserverpub\t51820\toff",
            "pub1\tpsk\t1.2.3.4:50000\t10.0.0.2/32\t1713950000\t100\t200\t25",
            "pub2\t(none)\t(none)\t10.0.0.3/32\t0\t0\t0\toff",
        ]
    )
    executor = FakeExecutor({command: _result(command, stdout=dump)})
    provider = WireGuardProvider(_provider_config(), executor=executor)

    clients = await provider.list_clients()

    assert clients == [
        {
            "provider_client_id": "pub1",
            "display_name": "10.0.0.2/32",
            "status": "active",
            "metadata": {
                "allowed_ips": "10.0.0.2/32",
                "endpoint": "1.2.3.4:50000",
                "latest_handshake": 1713950000,
                "persistent_keepalive": "25",
                "public_key": "pub1",
            },
        },
        {
            "provider_client_id": "pub2",
            "display_name": "10.0.0.3/32",
            "status": "disabled",
            "metadata": {
                "allowed_ips": "10.0.0.3/32",
                "endpoint": None,
                "latest_handshake": 0,
                "persistent_keepalive": "off",
                "public_key": "pub2",
            },
        },
    ]


@pytest.mark.asyncio
async def test_wireguard_collect_client_stats_returns_cumulative_payloads() -> None:
    command = ("wg", "show", "wg0", "dump")
    dump = "\n".join(
        [
            "priv\tserverpub\t51820\toff",
            "pub1\tpsk\t1.2.3.4:50000\t10.0.0.2/32\t1713950000\t100\t200\t25",
        ]
    )
    executor = FakeExecutor({command: _result(command, stdout=dump)})
    provider = WireGuardProvider(_provider_config(), executor=executor)

    stats = await provider.collect_client_stats()

    assert stats == [
        {
            "provider_client_id": "pub1",
            "counter_mode": "cumulative",
            "rx_bytes_total": 100,
            "tx_bytes_total": 200,
            "metadata": {
                "allowed_ips": "10.0.0.2/32",
                "endpoint": "1.2.3.4:50000",
                "latest_handshake": 1713950000,
                "persistent_keepalive": "25",
                "public_key": "pub1",
            },
        }
    ]


@pytest.mark.asyncio
async def test_wireguard_export_client_config_reads_sanitized_client_file() -> None:
    command = ("cat", "/etc/wireguard/clients/alice.conf")
    executor = FakeExecutor({command: _result(command, stdout="[Interface]\nPrivateKey = x\n")})
    provider = WireGuardProvider(_provider_config(), executor=executor)

    config = await provider.export_client_config("alice")

    assert config == b"[Interface]\nPrivateKey = x\n"
    assert executor.commands == [command]


def test_provider_factory_passes_executor_to_wireguard_provider() -> None:
    command = ("systemctl", "is-active", "wg-quick@wg0")
    executor = FakeExecutor({command: _result(command, stdout="active\n")})

    provider = ProviderFactory(ProviderRegistry.with_builtin_providers()).create(
        _provider_config(),
        executor=executor,
    )

    assert isinstance(provider, WireGuardProvider)
    assert provider.executor is executor


@pytest.mark.asyncio
async def test_wireguard_create_client_adds_peer_and_saves_systemd_config() -> None:
    set_command = (
        "wg",
        "set",
        "wg0",
        "peer",
        "pub1",
        "allowed-ips",
        "10.0.0.2/32",
        "persistent-keepalive",
        "25",
    )
    save_command = ("wg-quick", "save", "wg0")
    executor = FakeExecutor(
        {
            set_command: _result(set_command),
            save_command: _result(save_command),
        }
    )
    provider = WireGuardProvider(_provider_config(), executor=executor)

    client = await provider.create_client(
        {
            "provider_client_id": "pub1",
            "allowed_ips": "10.0.0.2/32",
            "persistent_keepalive": 25,
        }
    )

    assert client == {
        "provider_client_id": "pub1",
        "display_name": "10.0.0.2/32",
        "status": "active",
        "metadata": {
            "allowed_ips": "10.0.0.2/32",
            "persistent_keepalive": "25",
            "public_key": "pub1",
        },
    }
    assert executor.commands == [set_command, save_command]


@pytest.mark.asyncio
async def test_wireguard_create_client_writes_rendered_config() -> None:
    set_command = (
        "wg",
        "set",
        "wg0",
        "peer",
        "pub1",
        "allowed-ips",
        "10.0.0.2/32",
    )
    write_command = ("install", "-m", "600", "/dev/stdin", "/etc/wireguard/clients/alice.conf")
    save_command = ("wg-quick", "save", "wg0")
    executor = FakeExecutor(
        {
            set_command: _result(set_command),
            write_command: _result(write_command),
            save_command: _result(save_command),
        }
    )
    provider = WireGuardProvider(_provider_config(), executor=executor)

    client = await provider.create_client(
        {
            "client_id": "alice",
            "provider_client_id": "pub1",
            "private_key": "client-private-key",
            "server_public_key": "server-public-key",
            "endpoint": "vpn.example.com:51820",
            "allowed_ips": "10.0.0.2/32",
            "dns": ["1.1.1.1", "8.8.8.8"],
        }
    )

    assert client["metadata"]["config_path"] == "/etc/wireguard/clients/alice.conf"
    assert executor.commands == [set_command, write_command, save_command]
    assert executor.inputs[1] == (
        "[Interface]\n"
        "PrivateKey = client-private-key\n"
        "Address = 10.0.0.2/32\n"
        "DNS = 1.1.1.1, 8.8.8.8\n"
        "\n"
        "[Peer]\n"
        "PublicKey = server-public-key\n"
        "Endpoint = vpn.example.com:51820\n"
        "AllowedIPs = 0.0.0.0/0, ::/0\n"
        "PersistentKeepalive = 25\n"
    )


@pytest.mark.asyncio
async def test_wireguard_create_client_uses_docker_runtime_commands() -> None:
    set_command = (
        "docker",
        "exec",
        "wireguard",
        "wg",
        "set",
        "wg0",
        "peer",
        "pub1",
        "allowed-ips",
        "10.0.0.2/32",
    )
    save_command = ("docker", "exec", "wireguard", "wg-quick", "save", "wg0")
    executor = FakeExecutor(
        {
            set_command: _result(set_command),
            save_command: _result(save_command),
        }
    )
    provider = WireGuardProvider(
        _provider_config(
            {
                "runtime": "docker",
                "docker_container_name": "wireguard",
            }
        ),
        executor=executor,
    )

    await provider.create_client(
        {
            "provider_client_id": "pub1",
            "allowed_ips": "10.0.0.2/32",
        }
    )

    assert executor.commands == [set_command, save_command]


@pytest.mark.asyncio
async def test_wireguard_create_client_writes_config_inside_docker_container() -> None:
    set_command = (
        "docker",
        "exec",
        "wireguard",
        "wg",
        "set",
        "wg0",
        "peer",
        "pub1",
        "allowed-ips",
        "10.0.0.2/32",
    )
    write_command = (
        "docker",
        "exec",
        "-i",
        "wireguard",
        "install",
        "-m",
        "600",
        "/dev/stdin",
        "/etc/wireguard/clients/alice.conf",
    )
    save_command = ("docker", "exec", "wireguard", "wg-quick", "save", "wg0")
    executor = FakeExecutor(
        {
            set_command: _result(set_command),
            write_command: _result(write_command),
            save_command: _result(save_command),
        }
    )
    provider = WireGuardProvider(
        _provider_config(
            {
                "runtime": "docker",
                "docker_container_name": "wireguard",
            }
        ),
        executor=executor,
    )

    await provider.create_client(
        {
            "client_id": "alice",
            "provider_client_id": "pub1",
            "private_key": "client-private-key",
            "server_public_key": "server-public-key",
            "endpoint": "vpn.example.com:51820",
            "allowed_ips": "10.0.0.2/32",
        }
    )

    assert executor.commands == [set_command, write_command, save_command]
    assert executor.inputs[1] is not None


@pytest.mark.asyncio
async def test_wireguard_delete_client_removes_peer_and_saves_config() -> None:
    remove_command = ("wg", "set", "wg0", "peer", "pub1", "remove")
    save_command = ("wg-quick", "save", "wg0")
    executor = FakeExecutor(
        {
            remove_command: _result(remove_command),
            save_command: _result(save_command),
        }
    )
    provider = WireGuardProvider(_provider_config(), executor=executor)

    await provider.delete_client("pub1")

    assert executor.commands == [remove_command, save_command]


@pytest.mark.asyncio
async def test_wireguard_create_client_rejects_unsafe_public_key() -> None:
    provider = WireGuardProvider(_provider_config(), executor=FakeExecutor({}))

    with pytest.raises(ValueError):
        await provider.create_client(
            {
                "provider_client_id": "pub 1",
                "allowed_ips": "10.0.0.2/32",
            }
        )
