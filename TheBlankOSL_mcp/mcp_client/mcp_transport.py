import asyncio
import json
from typing import Dict, Any, Optional

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

                # 2. Handle Server Requests (Sampling/Elicitation - To be implemented)
                elif "method" in message:
                    # For now, just log or ignore
                    pass

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
