"""Read-only command-line account and profile summary."""

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

DEFAULT_DATABASE = Path(__file__).with_name("tower_defense_accounts.sqlite3")


def list_accounts(database_path: Path) -> list[dict[str, object]]:
    if not database_path.is_file():
        raise FileNotFoundError(f"Account database not found: {database_path}")

    database_uri = f"{database_path.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(database_uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if "accounts" not in tables:
            raise ValueError(f"No accounts table found in {database_path}")

        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(accounts)")
        }
        optional_columns = (
            "credits",
            "unlocked_units",
            "unit_levels",
        )
        selected_columns = [
            "id",
            "username",
            "is_admin",
            "custom_speed_access",
            *(column for column in optional_columns if column in columns),
        ]
        rows = connection.execute(
            f"SELECT {', '.join(selected_columns)} FROM accounts ORDER BY id"
        ).fetchall()

    accounts: list[dict[str, object]] = []
    for row in rows:
        unlocked = json.loads(row["unlocked_units"]) if "unlocked_units" in columns else []
        accounts.append(
            {
                "id": row["id"],
                "username": row["username"],
                "admin": bool(row["is_admin"]),
                "custom_speed_access": bool(row["custom_speed_access"]),
                "credits": row["credits"] if "credits" in columns else 0,
                "unlocked_units": len(unlocked),
                "upgraded_units": (
                    sum(
                        1
                        for level in json.loads(row["unit_levels"]).values()
                        if isinstance(level, int) and level > 1
                    )
                    if "unit_levels" in columns
                    else 0
                ),
            }
        )
    return accounts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List registered accounts without displaying passwords or tokens."
    )
    parser.add_argument(
        "database",
        nargs="?",
        type=Path,
        default=DEFAULT_DATABASE,
        help=f"SQLite account database (default: {DEFAULT_DATABASE})",
    )
    arguments = parser.parse_args()

    try:
        accounts = list_accounts(arguments.database)
    except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    if not accounts:
        print("No registered accounts.")
        return 0

    headers = ("ID", "USERNAME", "ADMIN", "CUSTOM SPEED", "CREDITS", "UNITS", "UPGRADED")
    rows = [
        (
            str(account["id"]),
            str(account["username"]),
            "yes" if account["admin"] else "no",
            "yes" if account["custom_speed_access"] else "no",
            str(account["credits"]),
            str(account["unlocked_units"]),
            str(account["upgraded_units"]),
        )
        for account in accounts
    ]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in rows))
        for index in range(len(headers))
    ]
    print("  ".join(value.ljust(widths[index]) for index, value in enumerate(headers)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))
    print(f"\n{len(accounts)} registered account(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
