"""Start a loopback-only Network Lens server."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Network Lens V0.1 — 本机 TCP 快照观察")
    parser.add_argument("--port", type=int, default=8080, help="本机端口（默认 8080）")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    arguments = parser.parse_args()
    if not 1 <= arguments.port <= 65535:
        parser.error("端口必须在 1 到 65535 之间")

    from .ui import serve

    serve(arguments.port, show=not arguments.no_browser)


if __name__ == "__main__":
    main()
