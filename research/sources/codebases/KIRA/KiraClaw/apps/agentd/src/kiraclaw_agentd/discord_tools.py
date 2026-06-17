from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import re
from typing import Any, Callable
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

import aiohttp

from krim_sdk.tools import Tool
from kiraclaw_agentd.settings import KiraClawSettings


DiscordRequester = Callable[[str, int | str, dict[str, Any], str | None], dict[str, Any]]


def _build_result(success: bool, **payload: Any) -> str:
    body = {"success": success, **payload}
    return json.dumps(body, ensure_ascii=False, indent=2)


DiscordChannelResolver = Callable[[str], str | None]


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w.\-]+", "_", name.strip())
    return cleaned or "discord_file"


def _resolve_output_path(workspace_dir: Path, *, url: str, channel_id: str | None, file_path: str | None) -> Path:
    if file_path:
        candidate = Path(file_path).expanduser()
        return candidate if candidate.is_absolute() else workspace_dir / candidate
    filename = _sanitize_filename(Path(unquote(urlparse(url).path)).name)
    channel_segment = channel_id or "downloads"
    return workspace_dir / "files" / "discord" / channel_segment / filename


_DISCORD_CHANNEL_ID_PATTERN = re.compile(r"^\d+$")
_DISCORD_CHANNEL_REF_PATTERN = re.compile(r"^<#(\d+)>$")
_DISCORD_CHANNEL_TOKEN_PATTERN = re.compile(r"(?<![\w/])#([a-zA-Z0-9._-]+)")


def _extract_channel_id(value: str) -> str | None:
    stripped = value.strip()
    mention = _DISCORD_CHANNEL_REF_PATTERN.match(stripped)
    if mention:
        return mention.group(1)
    if _DISCORD_CHANNEL_ID_PATTERN.fullmatch(stripped):
        return stripped
    return None


def _normalize_discord_channel_ref(value: str) -> str:
    return value.strip().lstrip("#").lower()


def _discord_get_json(bot_token: str, url: str) -> Any:
    request = Request(url, headers={"Authorization": f"Bot {bot_token}"})
    with urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def _make_channel_resolver(bot_token: str) -> DiscordChannelResolver:
    cache: dict[str, str] = {}

    def _resolve(channel_ref: str) -> str | None:
        key = _normalize_discord_channel_ref(channel_ref)
        if not key:
            return None
        if key in cache:
            return cache[key]

        guilds = _discord_get_json(bot_token, "https://discord.com/api/v10/users/@me/guilds")
        for guild in guilds:
            guild_id = str(guild.get("id", "")).strip()
            if not guild_id:
                continue
            channels = _discord_get_json(
                bot_token,
                f"https://discord.com/api/v10/guilds/{guild_id}/channels",
            )
            for channel in channels:
                if str(channel.get("type")) not in {"0", "5", "15"}:
                    continue
                name = _normalize_discord_channel_ref(str(channel.get("name", "")))
                channel_id = str(channel.get("id", "")).strip()
                if name and channel_id:
                    cache.setdefault(name, channel_id)
                    if name == key:
                        return channel_id
        return cache.get(key)

    return _resolve


def _make_requester(bot_token: str) -> DiscordRequester:
    base_url = "https://discord.com/api/v10/channels"
    headers = {"Authorization": f"Bot {bot_token}"}

    async def _request_async(
        method: str,
        channel_id: int | str,
        payload: dict[str, Any],
        file_path: str | None = None,
    ) -> dict[str, Any]:
        async with aiohttp.ClientSession(headers=headers) as session:
            target_url = f"{base_url}/{channel_id}/messages"
            if file_path:
                form = aiohttp.FormData()
                form.add_field("payload_json", json.dumps(payload, ensure_ascii=False))
                with open(file_path, "rb") as handle:
                    form.add_field(
                        "files[0]",
                        handle,
                        filename=os.path.basename(file_path),
                        content_type="application/octet-stream",
                    )
                    async with session.request(method, target_url, data=form) as response:
                        return {"status": response.status, "body": await response.json()}

            async with session.request(method, target_url, json=payload) as response:
                return {"status": response.status, "body": await response.json()}

    def _request(
        method: str,
        channel_id: int | str,
        payload: dict[str, Any],
        file_path: str | None = None,
    ) -> dict[str, Any]:
        return asyncio.run(_request_async(method, channel_id, payload, file_path))

    return _request


class _DiscordToolBase(Tool):
    def __init__(self, requester: DiscordRequester, channel_resolver: DiscordChannelResolver | None = None) -> None:
        self._requester = requester
        self._channel_resolver = channel_resolver

    def _run_with_error_boundary(self, fn: Callable[[], str]) -> str:
        try:
            return fn()
        except Exception as exc:
            return _build_result(False, error=str(exc))

    def _resolve_channel_target(self, channel_ref: str) -> str:
        extracted = _extract_channel_id(channel_ref)
        if extracted:
            return extracted
        if self._channel_resolver is None:
            return channel_ref
        resolved = self._channel_resolver(channel_ref)
        return resolved or channel_ref

    def _format_text(self, text: str) -> str:
        if self._channel_resolver is None:
            return text

        def replace_channel(match: re.Match[str]) -> str:
            name = match.group(1)
            resolved = self._channel_resolver(name)
            if not resolved:
                return match.group(0)
            return f"<#{resolved}>"

        return _DISCORD_CHANNEL_TOKEN_PATTERN.sub(replace_channel, text)


class DiscordSendMessageTool(_DiscordToolBase):
    name = "discord_send_message"
    description = "Send a message to any Discord channel or DM when Discord is enabled as an allowed channel."
    parameters = {
        "channel_id": {
            "type": "string",
            "description": "Discord channel ID to send to.",
        },
        "text": {
            "type": "string",
            "description": "Message text to send.",
        },
        "reply_to_message_id": {
            "type": "integer",
            "description": "Optional Discord message ID to reply to.",
            "optional": True,
        },
    }

    def run(self, channel_id: str, text: str, reply_to_message_id: int | None = None) -> str:
        def _send() -> str:
            resolved_channel = self._resolve_channel_target(channel_id)
            payload: dict[str, Any] = {"content": self._format_text(text)}
            if reply_to_message_id is not None:
                payload["message_reference"] = {"message_id": str(reply_to_message_id)}
                payload["allowed_mentions"] = {"replied_user": False}
            response = self._requester("POST", resolved_channel, payload, None)
            if response.get("status", 500) >= 400:
                return _build_result(False, error=str(response.get("body")))
            body = response.get("body", {})
            return _build_result(True, channel_id=resolved_channel, message_id=body.get("id"))

        return self._run_with_error_boundary(_send)


class DiscordUploadFileTool(_DiscordToolBase):
    name = "discord_upload_file"
    description = (
        "Upload a local file to a Discord channel or DM when the file already exists on disk and the user wants it sent."
    )
    parameters = {
        "channel_id": {
            "type": "string",
            "description": "Discord channel ID to upload into.",
        },
        "file_path": {
            "type": "string",
            "description": "Absolute local file path to upload.",
        },
        "caption": {
            "type": "string",
            "description": "Optional text to send with the file.",
            "optional": True,
        },
        "reply_to_message_id": {
            "type": "integer",
            "description": "Optional Discord message ID to reply to.",
            "optional": True,
        },
    }

    def run(
        self,
        channel_id: str,
        file_path: str,
        caption: str | None = None,
        reply_to_message_id: int | None = None,
    ) -> str:
        def _upload() -> str:
            if not os.path.isfile(file_path):
                return _build_result(False, error=f"file_not_found: {file_path}")

            resolved_channel = self._resolve_channel_target(channel_id)
            payload: dict[str, Any] = {}
            if caption:
                payload["content"] = self._format_text(caption)
            if reply_to_message_id is not None:
                payload["message_reference"] = {"message_id": str(reply_to_message_id)}
                payload["allowed_mentions"] = {"replied_user": False}
            response = self._requester("POST", resolved_channel, payload, file_path)
            if response.get("status", 500) >= 400:
                return _build_result(False, error=str(response.get("body")))
            body = response.get("body", {})
            attachments = body.get("attachments", [])
            attachment = attachments[0] if attachments else {}
            return _build_result(
                True,
                channel_id=resolved_channel,
                message_id=body.get("id"),
                file_name=attachment.get("filename") or os.path.basename(file_path),
                url=attachment.get("url"),
            )

        return self._run_with_error_boundary(_upload)


class DiscordDownloadAttachmentTool(Tool):
    name = "discord_download_attachment"
    description = "Download a Discord attachment URL into the local workspace so you can inspect or process it."
    parameters = {
        "url": {
            "type": "string",
            "description": "Discord attachment URL from an incoming message.",
        },
        "channel_id": {
            "type": "string",
            "description": "Optional channel ID for organizing the download path.",
            "optional": True,
        },
        "file_path": {
            "type": "string",
            "description": "Optional output path. Relative paths are resolved from FILESYSTEM_BASE_DIR.",
            "optional": True,
        },
    }

    def __init__(self, bot_token: str, workspace_dir: Path) -> None:
        self._bot_token = bot_token
        self._workspace_dir = workspace_dir

    def run(self, url: str, channel_id: str | None = None, file_path: str | None = None) -> str:
        try:
            target = _resolve_output_path(self._workspace_dir, url=url, channel_id=channel_id, file_path=file_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            request = Request(url, headers={"Authorization": f"Bot {self._bot_token}"})
            with urlopen(request) as response:
                body = response.read()
            target.write_bytes(body)
            return _build_result(True, path=str(target), size_bytes=len(body), channel_id=channel_id, url=url)
        except Exception as exc:
            return _build_result(False, error=str(exc))


def build_discord_tools(
    settings: KiraClawSettings,
    *,
    requester: DiscordRequester | None = None,
    channel_resolver: DiscordChannelResolver | None = None,
) -> list[Tool]:
    if not settings.discord_enabled or not settings.discord_bot_token:
        return []

    request_fn = requester or _make_requester(settings.discord_bot_token)
    resolver = channel_resolver or _make_channel_resolver(settings.discord_bot_token)
    return [
        DiscordSendMessageTool(request_fn, channel_resolver=resolver),
        DiscordUploadFileTool(request_fn, channel_resolver=resolver),
        DiscordDownloadAttachmentTool(settings.discord_bot_token, settings.workspace_dir),
    ]
