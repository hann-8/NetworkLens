"""Hold two loopback TCP connections for manual Network Lens verification."""

import os
import socket
from contextlib import ExitStack


def main() -> None:
    with ExitStack() as sockets:
        listener = sockets.enter_context(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        listener.bind(("127.0.0.1", 0))
        listener.listen(2)
        listener.settimeout(3)
        endpoint = listener.getsockname()
        for _ in range(2):
            client = sockets.enter_context(socket.create_connection(endpoint, timeout=3))
            accepted, _ = listener.accept()
            sockets.enter_context(accepted)
            print(f"Client: {client.getsockname()[0]}:{client.getsockname()[1]}")
        print(f"PID: {os.getpid()} | LISTEN: {endpoint[0]}:{endpoint[1]}", flush=True)
        print("Expected: 1 LISTEN + 4 ESTABLISHED rows (both ends are in this process).")
        try:
            input("Press Enter to close all demo sockets and exit... ")
        except (KeyboardInterrupt, EOFError):
            pass


if __name__ == "__main__":
    main()
