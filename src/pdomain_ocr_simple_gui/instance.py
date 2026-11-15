"""Private runtime records and operating-system locks for desktop discovery."""

from __future__ import annotations

import http.client
import ipaddress
import json
import os
import secrets
from typing import TYPE_CHECKING, ClassVar, Literal
from urllib.parse import urlsplit
from uuid import uuid4

from filelock import FileLock
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from pdomain_ocr_simple_gui.constants import APP_ID

if TYPE_CHECKING:
    from pathlib import Path


class InstanceRecord(BaseModel):
    """Describe one loopback server without exposing its capability in repr."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = 1
    app_id: Literal["pdomain-ocr-simple-gui"] = "pdomain-ocr-simple-gui"
    instance_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    pid: int = Field(gt=0)
    origin: str
    capability: SecretStr = Field(min_length=64, max_length=64)

    @field_validator("origin")
    @classmethod
    def validate_origin(cls, value: str) -> str:
        """Accept only an HTTP origin with a numeric loopback address."""
        parsed = urlsplit(value)
        if (
            parsed.scheme != "http"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.hostname is None
            or parsed.port is None
            or not 1 <= parsed.port <= 65535
            or not ipaddress.ip_address(parsed.hostname).is_loopback
        ):
            raise ValueError("Desktop instance origin must be HTTP on numeric loopback")
        return value

    def private_json(self) -> str:
        """Serialize the capability only for its owner-private runtime file."""
        payload = self.model_dump(mode="json")
        payload["capability"] = self.capability.get_secret_value()
        return json.dumps(payload)


def new_instance_record(origin: str) -> InstanceRecord:
    """Create a fresh identity and capability for this process."""
    return InstanceRecord(
        app_id=APP_ID,
        instance_id=uuid4().hex,
        pid=os.getpid(),
        origin=origin,
        capability=SecretStr(secrets.token_hex(32)),
    )


class InstanceReply(BaseModel):
    """Authenticate a discovery reply and describe a command's outcome."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    app_id: Literal["pdomain-ocr-simple-gui"]
    instance_id: str
    challenge: str
    accepted: bool
    message: str = ""
    live_tabs: int = Field(default=0, ge=0)
    active_operations: int = Field(default=0, ge=0)


def request_instance(
    record: InstanceRecord,
    action: Literal["status", "show", "quit"],
    *,
    confirm_other_tabs: bool = False,
    timeout: float = 2.0,
) -> InstanceReply:
    """Send a bounded, direct loopback request and verify the reply identity."""
    parsed = urlsplit(record.origin)
    if parsed.hostname is None:
        raise ValueError("Desktop instance origin is missing its host")
    challenge = secrets.token_hex(32)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=timeout)
    try:
        headers = {
            "Authorization": f"Bearer {record.capability.get_secret_value()}",
            "X-Pdomain-Challenge": challenge,
        }
        if action == "status":
            connection.request("GET", "/api/lifecycle/instance", headers=headers)
        else:
            headers["Content-Type"] = "application/json"
            connection.request(
                "POST",
                f"/api/lifecycle/{action}",
                body=json.dumps({"confirm_other_tabs": confirm_other_tabs}),
                headers=headers,
            )
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("Desktop instance rejected the authenticated request")
        body = response.read(16_385)
        if len(body) > 16_384:
            raise ValueError("Desktop instance response exceeds size limit")
        reply = InstanceReply.model_validate_json(body)
        if reply.instance_id != record.instance_id:
            raise ValueError("Desktop instance identity does not match its runtime record")
        if not secrets.compare_digest(reply.challenge, challenge):
            raise ValueError("Desktop instance challenge does not match")
        return reply
    finally:
        connection.close()


class InstanceStore:
    """Serialize startup and retain instance ownership until server exit."""

    def __init__(self, state_root: Path) -> None:
        if state_root.is_symlink():
            raise ValueError("Desktop state directory must not be a symlink")
        state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        (state_root / ".nobackup").touch(exist_ok=True)
        self.record_path: Path = state_root / "instance.json"
        self.startup_lock: FileLock = FileLock(state_root / "startup.lock", mode=0o600)
        self.lifetime_lock: FileLock = FileLock(state_root / "instance.lock", mode=0o600)

    def read(self) -> InstanceRecord | None:
        """Read a complete record, rejecting malformed or redirected files."""
        if self.record_path.is_symlink():
            raise ValueError("Desktop instance record must not be a symlink")
        try:
            text = self.record_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        if os.name != "nt" and self.record_path.stat().st_mode & 0o077:
            raise ValueError("Desktop instance record must be owner-private")
        return InstanceRecord.model_validate_json(text)

    def publish(self, record: InstanceRecord) -> None:
        """Publish a private record while holding startup and lifetime locks."""
        if not self.startup_lock.is_locked or not self.lifetime_lock.is_locked:
            raise RuntimeError("Publishing requires startup and lifetime locks")
        staged = self.record_path.with_name(f".instance-{uuid4().hex}.tmp")
        try:
            fd = os.open(staged, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                _ = stream.write(record.private_json())
                stream.flush()
                os.fsync(stream.fileno())
            _ = staged.replace(self.record_path)
        finally:
            staged.unlink(missing_ok=True)

    def remove_owned(self, record: InstanceRecord) -> bool:
        """Remove only this instance's record while its lifetime lock is held."""
        if not self.lifetime_lock.is_locked:
            raise RuntimeError("Removing an instance requires its lifetime lock")
        current = self.read()
        if current is None or current.instance_id != record.instance_id:
            return False
        self.record_path.unlink()
        return True
