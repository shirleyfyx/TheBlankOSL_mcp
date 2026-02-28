import asyncio
import json
from typing import Dict, Any, Optional, Callable, Awaitable

# Type for async request handler: (method, params) -> result
RequestHandler = Callable[[str, Dict[str, Any]], Awaitable[Any]]


class McpTransport:
    """
    Handles JSON-RPC 2.0 communication over asyncio streams.
    """
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self._pending_requests: Dict[int, asyncio.Future] = {}
        self._request_id = 0
        self._is_running = True
        self._request_handler: Optional[RequestHandler] = None

    def set_request_handler(self, handler: Optional[RequestHandler]) -> None:
        """Set handler for incoming server requests (e.g. roots/list, elicitation/create)."""
        self._request_handler = handler

    async def send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Sends a request and awaits the specific response matching the ID.
        """
        if params is None: params = {}
        
        rid = self._request_id
        self._request_id += 1
        
        # Create a Future to hold the eventual response
        response_future = asyncio.get_event_loop().create_future()
        self._pending_requests[rid] = response_future

        payload = {
            "jsonrpc": "2.0",
            "id": rid,
            "method": method,
            "params": params
        }

        try:
            data = json.dumps(payload).encode()
            self.writer.write(data + b"\n")
            await self.writer.drain()
        except Exception as e:
            if rid in self._pending_requests:
                del self._pending_requests[rid]
            raise ConnectionError(f"Failed to write to server: {e}")

        return await response_future

    def _send_json(self, obj: Dict[str, Any]) -> None:
        """Serialize and write one JSON-RPC message (no newline in spec; many impls use newline-delimited)."""
        data = json.dumps(obj).encode()
        self.writer.write(data + b"\n")

    async def send_response(self, msg_id: Any, result: Any) -> None:
        """Send a successful JSON-RPC response (e.g. to a server request)."""
        self._send_json({"jsonrpc": "2.0", "id": msg_id, "result": result})
        await self.writer.drain()

    async def send_error(self, msg_id: Any, code: int, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Send a JSON-RPC error response."""
        err = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        self._send_json({"jsonrpc": "2.0", "id": msg_id, "error": err})
        await self.writer.drain()

    async def send_notification(self, method: str, params: Optional[Dict[str, Any]] = None):
        """
        Sends a notification (no ID, no response expected).
        """
        if params is None: params = {}
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params
        }

        try:
            data = json.dumps(payload).encode()
            self.writer.write(data + b"\n")
            await self.writer.drain()
        except Exception as e:
            raise ConnectionError(f"Failed to send notification: {e}")

    async def start_listening(self):
        """
        Background loop to read responses from the server.
        """
        while self._is_running and not self.reader.at_eof():
            try:
                line = await self.reader.readline()
                if not line: break

                message = json.loads(line.decode())

                # 1. Handle Responses (Requests we sent)
                if "id" in message and message["id"] in self._pending_requests:
                    future = self._pending_requests.pop(message["id"])
                    
                    if "error" in message:
                        future.set_exception(RuntimeError(message["error"].get("message", "Unknown Error")))
                    elif "result" in message:
                        future.set_result(message["result"])
                    else:
                        future.set_result({})

                # 2. Handle server requests (roots/list, elicitation/create, etc.)
                elif "method" in message and "id" in message:
                    msg_id = message["id"]
                    method = message.get("method", "")
                    params = message.get("params") or {}
                    if self._request_handler:
                        try:
                            result = await self._request_handler(method, params)
                            await self.send_response(msg_id, result)
                        except Exception as e:
                            err_msg = str(e)
                            code = getattr(e, "code", -32603)
                            if code == -32603 and (
                                "not found" in err_msg.lower() or "not supported" in err_msg.lower()
                            ):
                                code = -32601
                            await self.send_error(msg_id, code, err_msg)
                            await self.writer.drain()
                    else:
                        await self.send_error(
                            msg_id, -32601,
                            f"Method not handled: {method}",
                            data={"reason": "No request handler registered"}
                        )
                        await self.writer.drain()

            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            except Exception as e:
                print(f"Transport Error: {e}")
                break

    async def close(self):
        """Closes the streams."""
        self._is_running = False
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except Exception:
            pass
