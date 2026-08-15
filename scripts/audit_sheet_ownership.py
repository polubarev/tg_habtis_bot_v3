"""Detect diary sheets bound to more than one account (SEC-1).

The ownership check in /config stops *new* hijacks, but any bind that happened
before the fix shipped is still in Firestore. This script is read-only: it lists
every sheet_id held by more than one profile so you can investigate.

Usage:
    python scripts/audit_sheet_ownership.py

Requires the same credentials the bot uses (GOOGLE_CREDENTIALS_PATH, or
application default credentials with access to the Firestore database).
"""

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict

from src.config.settings import get_settings
from src.services.storage.firestore.client import FirestoreClient
from src.services.storage.firestore.user_repo import UserRepository


async def main() -> int:
    settings = get_settings()
    client = FirestoreClient(settings.google_credentials_path, settings.gcp_project_id)
    if not client.is_ready:
        print("ERROR: Firestore is not reachable; check credentials and GCP_PROJECT_ID.")
        return 2

    repo = UserRepository(client)
    profiles = await repo.list_all()

    owners_by_sheet: dict[str, list[int]] = defaultdict(list)
    for profile in profiles:
        if profile.sheet_id:
            owners_by_sheet[profile.sheet_id].append(profile.telegram_user_id)

    shared = {
        sheet_id: user_ids
        for sheet_id, user_ids in owners_by_sheet.items()
        if len(user_ids) > 1
    }

    print(f"Scanned {len(profiles)} profiles, {len(owners_by_sheet)} with a sheet bound.")
    if not shared:
        print("OK: every bound sheet belongs to exactly one account.")
        return 0

    print(f"\n⚠ {len(shared)} sheet(s) bound to multiple accounts:\n")
    for sheet_id, user_ids in shared.items():
        print(f"  sheet ...{sheet_id[-8:]}  ->  telegram_user_ids {sorted(user_ids)}")
    print(
        "\nInvestigate each one. The earliest-created profile is usually the real owner;\n"
        "compare UserProfile.created_at to decide, then unbind the others."
    )
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
