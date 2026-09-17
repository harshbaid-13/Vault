"""`python -m app` — start the vault web server.

Bad configuration ends here with one readable sentence and exit code 1, not a traceback.
"""
import argparse
import logging
import sys

import uvicorn

from app.config import ConfigError, Settings
from app.main import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app", description="Run the vault web server.")
    # 127.0.0.1 by default so a run outside Docker is never reachable from the network.
    # The Docker image passes --host 0.0.0.0; compose publishes it on 127.0.0.1 only.
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        app = create_app(Settings.from_env())
    except ConfigError as exc:
        print(f"Vault cannot start: {exc}", file=sys.stderr)
        return 1

    # No access log: request lines carry search terms and file names (TECH_PLAN §8 gotcha 17).
    uvicorn.run(app, host=args.host, port=args.port, access_log=False, server_header=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
