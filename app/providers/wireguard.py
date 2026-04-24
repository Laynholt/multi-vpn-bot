"""WireGuard provider implementation."""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass
from ipaddress import ip_network
from typing import TYPE_CHECKING, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config.models import ProviderConfig, ProviderType
from app.providers.base import BaseProvider
from app.providers.capabilities import ProviderCapabilities

if TYPE_CHECKING:
    from app.core.executors.base import BaseExecutor
    from app.core.executors.models import CommandResult


class WireGuardProviderSettings(BaseModel):
    """Validated WireGuard provider settings."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    wireguard_interface: str = Field(default="wg0", min_length=1)
    runtime: Literal["systemd", "docker"] = "systemd"
    systemd_service_name: str | None = None
    docker_container_name: str | None = None
    wireguard_folder: str | None = None
    wireguard_config_filepath: str | None = None
    client_config_dir: str | None = None
    server_public_key: str | None = None
    endpoint: str | None = None
    server_ip: str | None = None
    server_port: str | int | None = None
    client_allowed_ips: str = "0.0.0.0/0, ::/0"
    dns_servers: tuple[str, ...] = ()
    persistent_keepalive: int | None = 25
    allowed_username_pattern: str = r"a-zA-Z0-9_.@-"
    allowed_public_key_pattern: str = r"a-zA-Z0-9+/=_.@-"
    apply_strategy: Literal["wg_quick_save", "none"] = "wg_quick_save"

    @model_validator(mode="after")
    def validate_runtime_settings(self) -> Self:
        if self.runtime == "docker" and not self.docker_container_name:
            raise ValueError("docker_container_name is required for docker WireGuard runtime")
        return self

    @property
    def resolved_systemd_service_name(self) -> str:
        return self.systemd_service_name or f"wg-quick@{self.wireguard_interface}"

    @property
    def resolved_client_config_dir(self) -> str:
        if self.client_config_dir is not None:
            return self.client_config_dir.rstrip("/")
        if self.wireguard_folder is not None:
            return posixpath.join(self.wireguard_folder.rstrip("/"), "config", "wg_confs")
        return "/etc/wireguard/clients"

    @property
    def resolved_endpoint(self) -> str | None:
        if self.endpoint:
            return self.endpoint
        if self.server_ip and self.server_port:
            return f"{self.server_ip}:{self.server_port}"
        return None


@dataclass(frozen=True, slots=True)
class WireGuardPeerDump:
    public_key: str
    endpoint: str | None
    allowed_ips: str
    latest_handshake: int
    rx_bytes_total: int
    tx_bytes_total: int
    persistent_keepalive: str

    @property
    def status(self) -> str:
        return "active" if self.latest_handshake > 0 else "disabled"

    @property
    def metadata(self) -> dict[str, Any]:
        return {
            "allowed_ips": self.allowed_ips,
            "endpoint": self.endpoint,
            "latest_handshake": self.latest_handshake,
            "persistent_keepalive": self.persistent_keepalive,
            "public_key": self.public_key,
        }


class WireGuardProvider(BaseProvider):
    """WireGuard provider backed by local or remote executor commands."""

    provider_type = ProviderType.WIREGUARD
    capabilities = ProviderCapabilities(
        list_clients=True,
        create_client=True,
        enable_client=False,
        disable_client=False,
        delete_client=True,
        export_client_config=True,
        collect_client_stats=True,
    )

    def __init__(
        self,
        config: ProviderConfig,
        executor: BaseExecutor | None = None,
    ) -> None:
        super().__init__(config, executor=executor)
        self.settings = WireGuardProviderSettings.model_validate(config.settings)

    async def healthcheck(self) -> bool:
        if self.settings.runtime == "docker":
            assert self.settings.docker_container_name is not None
            result = await self._run(
                (
                    "docker",
                    "inspect",
                    "-f",
                    "{{.State.Running}}",
                    self.settings.docker_container_name,
                )
            )
            return result.ok and result.stdout.strip().lower() == "true"

        result = await self._run(
            ("systemctl", "is-active", self.settings.resolved_systemd_service_name)
        )
        return result.ok and result.stdout.strip() == "active"

    async def list_clients(self) -> list[dict[str, Any]]:
        peers = await self._load_peer_dump()
        return [
            {
                "provider_client_id": peer.public_key,
                "display_name": peer.allowed_ips,
                "status": peer.status,
                "metadata": peer.metadata,
            }
            for peer in peers
        ]

    async def get_client(self, client_id: str) -> dict[str, Any] | None:
        for client in await self.list_clients():
            if client["provider_client_id"] == client_id:
                return client
        return None

    async def create_client(self, payload: dict[str, Any]) -> dict[str, Any]:
        public_key = self._validate_public_key(str(payload["provider_client_id"]))
        allowed_ips = self._validate_allowed_ips(str(payload["allowed_ips"]))
        persistent_keepalive = payload.get("persistent_keepalive")

        command: tuple[str, ...] = (
            "set",
            self.settings.wireguard_interface,
            "peer",
            public_key,
            "allowed-ips",
            allowed_ips,
        )
        if persistent_keepalive is not None:
            command = (
                *command,
                "persistent-keepalive",
                str(persistent_keepalive),
            )

        result = await self._run_wg(command)
        if not result.ok:
            raise RuntimeError(f"Failed to create WireGuard peer {public_key!r}")
        config_path = None
        if payload.get("private_key") is not None:
            client_id = self._validate_client_file_id(str(payload["client_id"]))
            client_config = self._render_client_config(payload, allowed_ips)
            config_path = await self._write_client_config(client_id, client_config)
        await self._apply_config()

        metadata = {
            "allowed_ips": allowed_ips,
            "persistent_keepalive": str(persistent_keepalive),
            "public_key": public_key,
        }
        if config_path is not None:
            metadata["config_path"] = config_path
        if persistent_keepalive is None:
            metadata.pop("persistent_keepalive")
        return {
            "provider_client_id": public_key,
            "display_name": str(payload.get("display_name") or allowed_ips),
            "status": "active",
            "metadata": metadata,
        }

    async def export_client_config(self, client_id: str) -> bytes:
        safe_client_id = self._validate_client_file_id(client_id)
        config_path = posixpath.join(
            self.settings.resolved_client_config_dir,
            f"{safe_client_id}.conf",
        )
        result = await self._run(("cat", config_path))
        if not result.ok:
            raise RuntimeError(f"Failed to export WireGuard config for {client_id!r}")
        return result.stdout.encode()

    async def collect_client_stats(self) -> list[dict[str, Any]]:
        peers = await self._load_peer_dump()
        return [
            {
                "provider_client_id": peer.public_key,
                "counter_mode": "cumulative",
                "rx_bytes_total": peer.rx_bytes_total,
                "tx_bytes_total": peer.tx_bytes_total,
                "metadata": peer.metadata,
            }
            for peer in peers
        ]

    async def delete_client(self, client_id: str) -> None:
        public_key = self._validate_public_key(client_id)
        result = await self._run_wg(
            ("set", self.settings.wireguard_interface, "peer", public_key, "remove")
        )
        if not result.ok:
            raise RuntimeError(f"Failed to delete WireGuard peer {public_key!r}")
        await self._apply_config()

    async def _load_peer_dump(self) -> list[WireGuardPeerDump]:
        result = await self._run_wg(("show", self.settings.wireguard_interface, "dump"))
        if not result.ok:
            raise RuntimeError("Failed to load WireGuard peer dump")
        return self._parse_peer_dump(result.stdout)

    async def _run_wg(self, args: tuple[str, ...]) -> CommandResult:
        if self.settings.runtime == "docker":
            assert self.settings.docker_container_name is not None
            return await self._run(
                ("docker", "exec", self.settings.docker_container_name, "wg", *args)
            )
        return await self._run(("wg", *args))

    async def _run_wg_quick(self, args: tuple[str, ...]) -> CommandResult:
        if self.settings.runtime == "docker":
            assert self.settings.docker_container_name is not None
            return await self._run(
                (
                    "docker",
                    "exec",
                    self.settings.docker_container_name,
                    "wg-quick",
                    *args,
                )
            )
        return await self._run(("wg-quick", *args))

    async def _apply_config(self) -> None:
        if self.settings.apply_strategy == "none":
            return
        result = await self._run_wg_quick(("save", self.settings.wireguard_interface))
        if not result.ok:
            raise RuntimeError("Failed to persist WireGuard runtime configuration")

    async def _write_client_config(self, client_id: str, config: str) -> str:
        config_path = posixpath.join(
            self.settings.resolved_client_config_dir,
            f"{client_id}.conf",
        )
        if self.settings.runtime == "docker":
            assert self.settings.docker_container_name is not None
            result = await self._run(
                (
                    "docker",
                    "exec",
                    "-i",
                    self.settings.docker_container_name,
                    "install",
                    "-m",
                    "600",
                    "/dev/stdin",
                    config_path,
                ),
                input_text=config,
            )
        else:
            result = await self._run(
                ("install", "-m", "600", "/dev/stdin", config_path),
                input_text=config,
            )
        if not result.ok:
            raise RuntimeError(f"Failed to write WireGuard client config for {client_id!r}")
        return config_path

    def _render_client_config(self, payload: dict[str, Any], address: str) -> str:
        private_key = str(payload["private_key"])
        server_public_key = str(
            payload.get("server_public_key") or self.settings.server_public_key or ""
        )
        endpoint = str(payload.get("endpoint") or self.settings.resolved_endpoint or "")
        if not server_public_key:
            raise ValueError("WireGuard client config requires server_public_key")
        if not endpoint:
            raise ValueError("WireGuard client config requires endpoint")

        dns_value = self._format_dns(payload.get("dns"))
        allowed_ips = str(payload.get("client_allowed_ips") or self.settings.client_allowed_ips)
        persistent_keepalive = payload.get(
            "client_persistent_keepalive",
            self.settings.persistent_keepalive,
        )

        lines = [
            "[Interface]",
            f"PrivateKey = {private_key}",
            f"Address = {address}",
        ]
        if dns_value:
            lines.append(f"DNS = {dns_value}")
        lines.extend(
            [
                "",
                "[Peer]",
                f"PublicKey = {server_public_key}",
                f"Endpoint = {endpoint}",
                f"AllowedIPs = {allowed_ips}",
            ]
        )
        if persistent_keepalive is not None:
            lines.append(f"PersistentKeepalive = {persistent_keepalive}")
        return "\n".join(lines) + "\n"

    def _format_dns(self, value: object) -> str:
        if value is None:
            return ", ".join(self.settings.dns_servers)
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)):
            return ", ".join(str(item) for item in value)
        raise ValueError("WireGuard DNS value must be a string or a list of strings")

    async def _run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
    ) -> CommandResult:
        if self.executor is None:
            raise RuntimeError("WireGuardProvider requires an executor")
        return await self.executor.run(command, input_text=input_text)

    def _parse_peer_dump(self, stdout: str) -> list[WireGuardPeerDump]:
        rows = [line.split("\t") for line in stdout.splitlines() if line.strip()]
        peers: list[WireGuardPeerDump] = []
        for row in rows[1:]:
            if len(row) < 8:
                continue
            peers.append(
                WireGuardPeerDump(
                    public_key=row[0],
                    endpoint=self._none_if_empty(row[2]),
                    allowed_ips=row[3],
                    latest_handshake=self._parse_int(row[4]),
                    rx_bytes_total=self._parse_int(row[5]),
                    tx_bytes_total=self._parse_int(row[6]),
                    persistent_keepalive=row[7],
                )
            )
        return peers

    def _validate_client_file_id(self, client_id: str) -> str:
        allowed = self.settings.allowed_username_pattern
        if not re.fullmatch(f"[{allowed}]+", client_id):
            raise ValueError(f"Unsafe WireGuard client config id: {client_id!r}")
        return client_id

    def _validate_public_key(self, public_key: str) -> str:
        allowed = self.settings.allowed_public_key_pattern
        if not re.fullmatch(f"[{allowed}]+", public_key):
            raise ValueError(f"Unsafe WireGuard public key: {public_key!r}")
        return public_key

    def _validate_allowed_ips(self, allowed_ips: str) -> str:
        networks = [item.strip() for item in allowed_ips.split(",")]
        if not networks or any(not item for item in networks):
            raise ValueError("WireGuard allowed_ips must not be empty")
        for network in networks:
            ip_network(network, strict=False)
        return ",".join(networks)

    @staticmethod
    def _none_if_empty(value: str) -> str | None:
        return None if value in {"", "(none)"} else value

    @staticmethod
    def _parse_int(value: str) -> int:
        try:
            return int(value)
        except ValueError:
            return 0
