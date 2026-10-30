#!/usr/bin/env python3
"""Stdlib SMTP sink. Prints the bound port to stdout, then serves until killed."""

from __future__ import annotations

import socket
import sys
import threading


def _handle(conn: socket.socket) -> None:
    try:
        conn.sendall(b"220 hello-fake SMTP\r\n")
        buf = b""
        data_mode = False
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk
            while True:
                if data_mode:
                    idx = buf.find(b"\r\n.\r\n")
                    if idx < 0:
                        break
                    conn.sendall(b"250 OK\r\n")
                    buf = buf[idx + 5 :]
                    data_mode = False
                    continue
                if b"\r\n" not in buf:
                    break
                line, buf = buf.split(b"\r\n", 1)
                cmd = line.decode("utf-8", "replace").split(" ", 1)[0].upper()
                if cmd in {"HELO", "EHLO"}:
                    conn.sendall(b"250 hello\r\n")
                elif cmd == "DATA":
                    conn.sendall(b"354 end with .\r\n")
                    data_mode = True
                elif cmd == "QUIT":
                    conn.sendall(b"221 bye\r\n")
                    return
                else:
                    conn.sendall(b"250 OK\r\n")
    except OSError:
        return
    finally:
        try:
            conn.close()
        except OSError:
            pass


def main() -> None:
    # The container reaches this test-only server via host.docker.internal (docker0),
    # so it must listen beyond loopback. Random port; lives only for the steps run.
    # nosemgrep: python.lang.security.audit.network.bind.avoid-bind-to-all-interfaces
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", 0))
    sock.listen(5)
    print(sock.getsockname()[1], flush=True)
    while True:
        conn, _ = sock.accept()
        threading.Thread(target=_handle, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
