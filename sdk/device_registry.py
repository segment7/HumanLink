from __future__ import annotations

from typing import Optional

from sdk.db.store import SQLiteStore


class DeviceRegistry:
    def __init__(self, store: SQLiteStore, configured_did: Optional[str] = None):
        self.store = store
        self.configured_did = configured_did

    def get_required_issuer_did(self, user_id: str | None = None) -> str:
        if self.configured_did:
            return self.configured_did
        stored = self.store.get_device_did()
        if stored:
            return stored
        raise ValueError("No device DID configured")

    def record_device_did(self, device_did: str) -> None:
        self.store.set_device_did(device_did)
