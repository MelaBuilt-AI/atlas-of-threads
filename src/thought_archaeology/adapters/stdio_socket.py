"""Bridge a native stdio MCP client to a private SSH-forwarded Unix socket.

Standalone standard-library helper for Linux/macOS/WSL hosts. The socket is
created by SSH inside a private directory; this opens no TCP listener.
"""
import argparse
import os
import select
import socket
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("socket_path")
    args = parser.parse_args()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(args.socket_path)
        inputs = [sys.stdin.fileno(), connection]
        while True:
            ready, _, _ = select.select(inputs, [], [])
            if sys.stdin.fileno() in ready:
                data = os.read(sys.stdin.fileno(), 65536)
                if data:
                    connection.sendall(data)
                else:
                    inputs.remove(sys.stdin.fileno())
                    connection.shutdown(socket.SHUT_WR)
            if connection in ready:
                data = connection.recv(65536)
                if not data:
                    return 0
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()


if __name__ == "__main__":
    raise SystemExit(main())
