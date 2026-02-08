"""Embedded proxy forwarder for Selenium.

Spins up a local proxy thread that injects Proxy-Authorization into CONNECT
requests to an upstream authenticated proxy.  Selenium uses the local proxy
(no auth needed), and the thread cleans up when the context manager exits.

Usage:
    with LocalProxyForwarder("pr.oxylabs.io", 7777, "user", "pass") as local_url:
        options.add_argument(f"--proxy-server={local_url}")
        driver = webdriver.Chrome(options=options)
"""

import base64
import logging
import select
import socket
import threading

logger = logging.getLogger(__name__)


class LocalProxyForwarder:
    """Context manager that runs a local proxy forwarding to an authenticated upstream."""

    def __init__(self, upstream_host: str, upstream_port: int, username: str, password: str):
        self._upstream = (upstream_host, upstream_port)
        creds = f"{username}:{password}"
        self._auth_header = f"Proxy-Authorization: Basic {base64.b64encode(creds.encode()).decode()}\r\n".encode()
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._port = 0

    def __enter__(self) -> str:
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))  # OS picks a free port
        self._port = self._server.getsockname()[1]
        self._server.listen(20)
        self._server.settimeout(1.0)  # So accept() can be interrupted
        self._running = True
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        logger.debug("Local proxy forwarder started on 127.0.0.1:%d", self._port)
        return f"http://127.0.0.1:{self._port}"

    def __exit__(self, *exc):
        self._running = False
        if self._server:
            try:
                self._server.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=3)
        logger.debug("Local proxy forwarder stopped")

    def _serve(self):
        while self._running:
            try:
                client, _ = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle, args=(client,), daemon=True).start()

    def _handle(self, client: socket.socket):
        upstream = None
        try:
            # Read client request headers
            buf = b""
            while b"\r\n\r\n" not in buf:
                chunk = client.recv(4096)
                if not chunk:
                    return
                buf += chunk
                if len(buf) > 65536:
                    return

            header_end = buf.index(b"\r\n\r\n") + 4
            header_bytes = buf[:header_end]
            body_bytes = buf[header_end:]

            # Inject Proxy-Authorization after request line
            first_crlf = header_bytes.index(b"\r\n") + 2
            modified = header_bytes[:first_crlf] + self._auth_header + header_bytes[first_crlf:]

            # Connect to upstream
            upstream = socket.create_connection(self._upstream, timeout=30)
            upstream.sendall(modified + body_bytes)

            request_line = header_bytes[:first_crlf].decode("utf-8", errors="replace")
            if request_line.upper().startswith("CONNECT"):
                # Read upstream CONNECT response, forward to client, then relay
                resp = b""
                while b"\r\n\r\n" not in resp:
                    chunk = upstream.recv(4096)
                    if not chunk:
                        return
                    resp += chunk
                client.sendall(resp)
                if b"200" in resp.split(b"\r\n")[0]:
                    self._relay(client, upstream)
            else:
                self._relay(client, upstream)

        except (OSError, BrokenPipeError):
            pass
        finally:
            for s in (client, upstream):
                if s:
                    try:
                        s.close()
                    except OSError:
                        pass

    @staticmethod
    def _relay(a: socket.socket, b: socket.socket, timeout: float = 120):
        pair = [a, b]
        try:
            while True:
                readable, _, errored = select.select(pair, [], pair, timeout)
                if errored or not readable:
                    break
                for s in readable:
                    data = s.recv(65536)
                    if not data:
                        return
                    (b if s is a else a).sendall(data)
        except (OSError, BrokenPipeError):
            pass
