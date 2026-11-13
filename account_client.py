"""Small HTTP client for the account API."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_API_URL = "http://127.0.0.1:5000"


class AccountServiceError(Exception):
    """Raised when an account request fails or the server cannot be reached."""


class AccountClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("GAME_API_URL", DEFAULT_API_URL)).rstrip("/")

    def request(
        self,
        endpoint: str,
        payload: dict[str, object] | None = None,
        token: str | None = None,
    ) -> dict[str, object]:
        headers = {"Accept": "application/json"}
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        request = Request(f"{self.base_url}{endpoint}", data=body, headers=headers)
        try:
            with urlopen(request, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            try:
                response_data = json.loads(error.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                response_data = {}
            message = response_data.get("error")
            raise AccountServiceError(
                message if isinstance(message, str) else f"Account request failed ({error.code})."
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise AccountServiceError(
                f"Cannot reach account server at {self.base_url}. "
                "For a local game, run python main.py (it starts the local account API), "
                "or run python auth_server.py in a separate terminal. "
                "For a hosted server, set GAME_API_URL to its base URL."
            ) from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AccountServiceError("The account server returned an invalid response.") from error

        if not isinstance(data, dict):
            raise AccountServiceError("The account server returned an invalid response.")
        return data

    def register(self, username: str, password: str) -> dict[str, object]:
        return self.request("/api/register", {"username": username, "password": password})

    def login(self, username: str, password: str) -> dict[str, object]:
        return self.request("/api/login", {"username": username, "password": password})

    def logout(self, token: str) -> None:
        self.request("/api/logout", token=token)

    def grant_speed_access(self, username: str, enabled: bool, token: str) -> None:
        self.request(
            "/api/admin/speed-access",
            {"username": username, "enabled": enabled},
            token,
        )

    def get_profile(self, token: str) -> dict[str, object]:
        return self.request("/api/profile", token=token)

    def save_loadout(self, unit_ids: list[str], token: str) -> dict[str, object]:
        return self.request("/api/profile/loadout", {"equipped_units": unit_ids}, token)

    def set_profile_credits(self, credits: int, token: str) -> dict[str, object]:
        return self.request("/api/profile/credits", {"credits": credits}, token)

    def roll_unit(self, token: str, count: int = 1) -> dict[str, object]:
        return self.request("/api/profile/roll", {"count": count}, token)

    def set_crates(self, crates: dict[str, int], token: str) -> dict[str, object]:
        return self.request("/api/profile/crates", {"crates": crates}, token)

    def set_battle_pass_xp(self, total_xp: int, token: str) -> dict[str, object]:
        return self.request("/api/profile/battle-pass/xp", {"total_xp": total_xp}, token)

    def claim_battle_pass_reward(self, level: int, token: str) -> dict[str, object]:
        return self.request("/api/profile/battle-pass/claim", {"level": level}, token)

    def claim_challenge_reward(
        self,
        mode: str,
        token: str,
        difficulty: str | None = None,
        story_level: int | None = None,
    ) -> dict[str, object]:
        return self.request(
            "/api/profile/challenge-reward",
            {
                "mode": mode,
                "difficulty": difficulty,
                "story_level": story_level,
            },
            token,
        )

    def open_crate(self, crate_id: str, token: str) -> dict[str, object]:
        return self.request("/api/profile/open-crate", {"crate_id": crate_id}, token)

    def roll_trait(
        self,
        unit_id: str,
        luck: int,
        count: int,
        token: str,
    ) -> dict[str, object]:
        return self.request(
            "/api/profile/trait-roll",
            {"unit_id": unit_id, "luck": luck, "count": count},
            token,
        )

    def apply_trait(
        self,
        unit_id: str,
        trait_id: str | None,
        token: str,
    ) -> dict[str, object]:
        return self.request(
            "/api/profile/apply-trait",
            {"unit_id": unit_id, "trait_id": trait_id},
            token,
        )

    def upgrade_unit(self, unit_id: str, token: str) -> dict[str, object]:
        return self.request("/api/profile/upgrade", {"unit_id": unit_id}, token)

    def list_admin_accounts(self, token: str) -> dict[str, object]:
        return self.request("/api/admin/accounts", token=token)

    def add_account_credits(self, username: str, amount: int, token: str) -> None:
        self.request("/api/admin/credits", {"username": username, "amount": amount}, token)

    def unlock_account_unit(self, username: str, unit_id: str, token: str) -> dict[str, object]:
        return self.request(
            "/api/admin/unlock-unit",
            {"username": username, "unit_id": unit_id},
            token,
        )

    def set_starting_cash(self, username: str, amount: int, token: str) -> dict[str, object]:
        return self.request(
            "/api/admin/starting-cash",
            {"username": username, "amount": amount},
            token,
        )

    def grant_account_crates(
        self,
        username: str,
        crate_id: str,
        amount: int,
        token: str,
    ) -> dict[str, object]:
        return self.request(
            "/api/admin/crates",
            {"username": username, "crate_id": crate_id, "amount": amount},
            token,
        )

    def unlock_all_account_units(self, username: str, token: str) -> dict[str, object]:
        return self.request(
            "/api/admin/unlock-all-units",
            {"username": username},
            token,
        )

    def set_account_story_level(
        self,
        username: str,
        level: int,
        token: str,
    ) -> dict[str, object]:
        return self.request(
            "/api/admin/story-level",
            {"username": username, "level": level},
            token,
        )

    def reset_account_daily_challenge(self, username: str, token: str) -> dict[str, object]:
        return self.request(
            "/api/admin/reset-daily",
            {"username": username},
            token,
        )
