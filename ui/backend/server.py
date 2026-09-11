"""Async WebSocket and HTTP REST server for NOVA UI V1 communication."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import struct
import threading
import time
from typing import Any

from core.logger import get_logger
from ui.backend.command_gateway import command_gateway
from ui.backend.event_bridge import event_bridge
from ui.backend.models import AvatarState, CommandRequest, UIEvent, UIEventType

logger = get_logger(__name__)


def _create_ws_accept_token(key: str) -> str:
    """Compute Sec-WebSocket-Accept token according to RFC 6455."""
    guid = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    sha1 = hashlib.sha1((key + guid).encode("utf-8")).digest()
    return base64.b64encode(sha1).decode("utf-8")


def _encode_ws_frame(message: str) -> bytes:
    """Encode text string into a standard WebSocket unmasked text frame."""
    payload = message.encode("utf-8")
    payload_len = len(payload)
    header = bytearray()
    header.append(0x81)  # FIN + opcode 1 (text)

    if payload_len <= 125:
        header.append(payload_len)
    elif payload_len <= 65535:
        header.append(126)
        header.extend(struct.pack("!H", payload_len))
    else:
        header.append(127)
        header.extend(struct.pack("!Q", payload_len))

    return bytes(header) + payload


def _decode_ws_frame(data: bytes) -> tuple[str | None, int]:
    """Decode a masked WebSocket frame received from client. Returns (decoded_text, bytes_consumed)."""
    if len(data) < 2:
        return None, 0

    first_byte = data[0]
    second_byte = data[1]
    opcode = first_byte & 0x0F
    is_masked = bool(second_byte & 0x80)
    payload_len = second_byte & 0x7F

    offset = 2
    if payload_len == 126:
        if len(data) < 4:
            return None, 0
        payload_len = struct.unpack("!H", data[2:4])[0]
        offset = 4
    elif payload_len == 127:
        if len(data) < 10:
            return None, 0
        payload_len = struct.unpack("!Q", data[2:10])[0]
        offset = 10

    mask_key = b""
    if is_masked:
        if len(data) < offset + 4:
            return None, 0
        mask_key = data[offset : offset + 4]
        offset += 4

    if len(data) < offset + payload_len:
        return None, 0

    payload = bytearray(data[offset : offset + payload_len])
    if is_masked:
        for i in range(len(payload)):
            payload[i] ^= mask_key[i % 4]

    consumed = offset + payload_len

    if opcode == 0x8:  # Close frame
        return "CLOSE", consumed
    elif opcode == 0x9:  # Ping frame
        return "PING", consumed
    elif opcode == 0x1:  # Text frame
        return payload.decode("utf-8", errors="ignore"), consumed

    return None, consumed


class NovaUIServer:
    """Local async server providing HTTP REST endpoints and WebSocket event streams on 127.0.0.1."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._server: asyncio.Server | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def start_background(self) -> None:
        """Start the async server in a dedicated background daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_server_thread, name="nova-ui-server", daemon=True)
        self._thread.start()
        logger.info("NOVA UI Server started at http://%s:%d", self.host, self.port)

    def stop(self) -> None:
        """Stop the UI server."""
        self._running = False
        if self._loop and self._server:
            self._loop.call_soon_threadsafe(self._server.close)

    def _run_server_thread(self) -> None:
        """Main thread loop running the asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        event_bridge.set_event_loop(self._loop)

        async def _main():
            self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
            logger.info("NOVA UI Gateway listening on %s:%d", self.host, self.port)
            async with self._server:
                await self._server.serve_forever()

        try:
            self._loop.run_until_complete(_main())
        except Exception as exc:
            logger.debug("NOVA UI Server loop ended: %s", exc)

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Route client connection between WebSocket upgrade and HTTP REST requests."""
        try:
            request_data = await reader.read(4096)
            if not request_data:
                writer.close()
                return

            header_text = request_data.decode("utf-8", errors="ignore")
            lines = header_text.split("\r\n")
            if not lines:
                writer.close()
                return

            request_line = lines[0]
            parts = request_line.split(" ")
            if len(parts) < 2:
                writer.close()
                return

            method, path = parts[0], parts[1]

            # Check for WebSocket Upgrade
            headers = {}
            for line in lines[1:]:
                if ": " in line:
                    k, v = line.split(": ", 1)
                    headers[k.lower()] = v.strip()

            if headers.get("upgrade", "").lower() == "websocket" and "sec-websocket-key" in headers:
                await self._handle_websocket_connection(reader, writer, headers["sec-websocket-key"])
                return

            # Handle HTTP REST Endpoints
            await self._handle_http_request(reader, writer, method, path, headers, request_data)

        except Exception as exc:
            logger.debug("Error handling client connection: %s", exc)
            try:
                writer.close()
            except Exception:
                pass

    async def _handle_websocket_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, ws_key: str
    ) -> None:
        """Perform WebSocket handshake and stream real-time events."""
        accept_token = _create_ws_accept_token(ws_key)
        handshake_resp = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_token}\r\n"
            "\r\n"
        )
        writer.write(handshake_resp.encode("utf-8"))
        await writer.drain()

        client_queue: asyncio.Queue[str] = asyncio.Queue()
        event_bridge.register_client(client_queue)

        # Send initial status snapshot
        init_event = UIEvent(
            event_type=UIEventType.NOVA_READY,
            avatar_state=event_bridge.current_avatar_state,
            message="Connected to NOVA backend.",
            data={"activity_history": event_bridge.activity_history},
            privacy=event_bridge.privacy_state,
        )
        writer.write(_encode_ws_frame(init_event.model_dump_json()))
        await writer.drain()

        # Task 1: Stream outgoing events from queue to WebSocket
        async def _sender():
            try:
                while self._running:
                    msg = await client_queue.get()
                    frame = _encode_ws_frame(msg)
                    writer.write(frame)
                    await writer.drain()
            except Exception:
                pass

        # Task 2: Read incoming client messages (e.g. user typed commands over WS)
        async def _receiver():
            buffer = bytearray()
            try:
                while self._running:
                    chunk = await reader.read(2048)
                    if not chunk:
                        break
                    buffer.extend(chunk)
                    while buffer:
                        msg_text, consumed = _decode_ws_frame(bytes(buffer))
                        if consumed == 0:
                            break
                        buffer = buffer[consumed:]
                        if msg_text == "CLOSE":
                            return
                        elif msg_text and msg_text != "PING":
                            try:
                                payload = json.loads(msg_text)
                                if "text" in payload:
                                    cmd_req = CommandRequest(text=payload["text"], source=payload.get("source", "ui_ws"))
                                    command_gateway.submit_command(cmd_req)
                            except Exception as exc:
                                logger.debug("Failed parsing WS message: %s", exc)
            except Exception:
                pass

        send_task = asyncio.create_task(_sender())
        recv_task = asyncio.create_task(_receiver())

        await asyncio.wait([send_task, recv_task], return_when=asyncio.FIRST_COMPLETED)
        send_task.cancel()
        recv_task.cancel()
        event_bridge.unregister_client(client_queue)
        writer.close()

    async def _handle_http_request(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        method: str,
        path: str,
        headers: dict[str, str],
        initial_data: bytes,
    ) -> None:
        """Handle JSON REST API endpoints."""
        cors_headers = (
            "Access-Control-Allow-Origin: *\r\n"
            "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
            "Access-Control-Allow-Headers: Content-Type\r\n"
        )

        if method == "OPTIONS":
            resp = f"HTTP/1.1 200 OK\r\n{cors_headers}Content-Length: 0\r\n\r\n"
            writer.write(resp.encode("utf-8"))
            await writer.drain()
            writer.close()
            return

        # Read body if present
        body = b""
        content_len = int(headers.get("content-length", 0))
        if content_len > 0:
            if b"\r\n\r\n" in initial_data:
                body = initial_data.split(b"\r\n\r\n", 1)[1]
            while len(body) < content_len:
                chunk = await reader.read(content_len - len(body))
                if not chunk:
                    break
                body += chunk

        response_body: dict[str, Any] = {}
        status_code = 200

        if path == "/health":
            response_body = {
                "status": "online",
                "backend": "nova_v3_5",
                "avatar_state": event_bridge.current_avatar_state.value,
                "timestamp": time.time(),
            }

        elif path == "/system/status":
            sys_info = command_gateway.get_system_status()
            sys_info["permissions"] = self._check_system_permissions().get("permissions", {})
            response_body = sys_info

        elif path == "/permissions":
            response_body = self._check_system_permissions()

        elif path == "/activity":
            response_body = {
                "history": event_bridge.activity_history,
                "avatar_state": event_bridge.current_avatar_state.value,
            }

        elif path.startswith("/logs"):
            from ui.health_checker import DashboardStatsManager

            if method == "POST" and path == "/logs/clear":
                DashboardStatsManager.clear_logs()
                response_body = {"status": "cleared"}
            elif method == "POST" and path == "/logs/copy":
                success = DashboardStatsManager.copy_to_clipboard()
                response_body = {"status": "copied" if success else "failed"}
            else:
                raw_logs = DashboardStatsManager.get_logs()
                response_body = {
                    "logs": [
                        {
                            "timestamp": entry.timestamp,
                            "time_str": entry.time_str,
                            "level": entry.level,
                            "message": entry.message,
                            "logger_name": entry.logger_name,
                        }
                        for entry in raw_logs
                    ],
                    "total": len(raw_logs),
                }

        elif path == "/command" and method == "POST":
            try:
                data = json.loads(body.decode("utf-8"))
                cmd_req = CommandRequest(text=data.get("text", ""), source=data.get("source", "ui_http"))
                cmd_res = command_gateway.submit_command(cmd_req)
                response_body = cmd_res.model_dump()
            except Exception as exc:
                status_code = 400
                response_body = {"error": f"Invalid request body: {exc}"}

        elif path == "/cancel" and method == "POST":
            response_body = command_gateway.cancel_active_tasks()

        elif path == "/voice/trigger" and method == "POST":
            response_body = command_gateway.trigger_voice_listening()

        else:
            status_code = 404
            response_body = {"error": "Endpoint not found"}

        body_bytes = json.dumps(response_body).encode("utf-8")
        resp = (
            f"HTTP/1.1 {status_code} OK\r\n"
            f"{cors_headers}"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n"
            "\r\n"
        )
        writer.write(resp.encode("utf-8") + body_bytes)
        await writer.drain()
        writer.close()

    def _check_system_permissions(self) -> dict[str, Any]:
        """Detect live status of macOS permissions where possible."""
        perms = {
            "accessibility": "UNKNOWN",
            "microphone": "GRANTED",
            "screen_recording": "GRANTED",
            "camera": "GRANTED",
            "automation": "GRANTED",
        }
        try:
            import ApplicationServices
            is_trusted = ApplicationServices.AXIsProcessTrusted()
            perms["accessibility"] = "GRANTED" if is_trusted else "MISSING"
        except Exception:
            perms["accessibility"] = "UNKNOWN"

        return {"permissions": perms, "platform": "macOS"}


# Global singleton UI server
ui_server = NovaUIServer()
