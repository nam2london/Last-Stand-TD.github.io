"""Start the Last Stand tower-defense game."""

import json
import os
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from auth_server import create_app
from game import TowerDefenseGame
from werkzeug.serving import make_server

HEALTH_CHECK_TIMEOUT = 1
STARTUP_ATTEMPTS = 20
STARTUP_RETRY_DELAY = 0.1


def _account_api_is_healthy(health_url: str, timeout: float) -> bool:
    with urlopen(health_url, timeout=timeout) as response:
        health = json.loads(response.read().decode("utf-8"))
    return isinstance(health, dict) and health.get("status") == "ok"


def ensure_local_account_server() -> None:
    """Start the local account API when the configured loopback server is down."""
    api_url = os.environ.get("GAME_API_URL", "http://127.0.0.1:5000").rstrip("/")
    parsed_url = urlparse(api_url)
    if parsed_url.scheme != "http" or parsed_url.hostname not in (
        "localhost",
        "127.0.0.1",
        "::1",
    ):
        return
    if parsed_url.path not in ("", "/") or parsed_url.query or parsed_url.fragment:
        raise RuntimeError(
            "GAME_API_URL must be the account server base URL without a path, query, or fragment."
        )

    host = parsed_url.hostname
    try:
        port = parsed_url.port
    except ValueError as error:
        raise RuntimeError("GAME_API_URL must use a valid port number.") from error
    if port is None:
        port = 5000
        url_host = f"[{host}]" if ":" in host else host
        api_url = f"http://{url_host}:{port}"
        os.environ["GAME_API_URL"] = api_url

    health_url = f"{api_url}/api/health"
    try:
        if _account_api_is_healthy(health_url, HEALTH_CHECK_TIMEOUT):
            return
        raise RuntimeError(f"Account API at {api_url} returned an invalid health response.")
    except HTTPError as error:
        raise RuntimeError(
            f"Service at {health_url} responded with HTTP {error.code}, "
            "but it is not the expected account API."
        ) from error
    except (URLError, TimeoutError, OSError):
        pass
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Account API at {api_url} returned an invalid health response."
        ) from error

    try:
        server = make_server(host, port, create_app(), threaded=True)
    except OSError as error:
        raise RuntimeError(
            f"Cannot start the local account API at {api_url}. "
            "Check whether another service is using that port."
        ) from error
    threading.Thread(
        target=server.serve_forever,
        daemon=True,
        name="local-account-api",
    ).start()
    for _ in range(STARTUP_ATTEMPTS):
        try:
            if _account_api_is_healthy(health_url, timeout=0.5):
                print(f"Started local account server at {api_url}")
                return
        except (URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            time.sleep(STARTUP_RETRY_DELAY)
    server.shutdown()
    raise RuntimeError(f"Local account server did not become ready at {api_url}.")


def main() -> None:
    try:
        ensure_local_account_server()
    except RuntimeError as error:
        raise SystemExit(f"Unable to start the account API: {error}") from error
    TowerDefenseGame().run()


if __name__ == "__main__":
    main()