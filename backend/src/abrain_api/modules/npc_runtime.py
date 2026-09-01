"""In-process cache for durable NPC identities.

Sibyl is the source of truth when memory is enabled. This cache only avoids a
provider read for identities already used by the current process.
"""

from threading import RLock

from .npc_identity import NpcIdentity


class NpcRuntime:
    def __init__(self) -> None:
        self._items: dict[str, NpcIdentity] = {}
        self._lock = RLock()

    def create(self, npc: NpcIdentity) -> NpcIdentity:
        with self._lock:
            if npc.npc_id in self._items:
                raise ValueError("NPC identity already exists")
            self._items[npc.npc_id] = npc
        return npc

    def get(self, npc_id: str) -> NpcIdentity:
        with self._lock:
            try:
                return self._items[npc_id]
            except KeyError as exc:
                raise KeyError("NPC identity not found") from exc

    def restore(self, npc: NpcIdentity) -> NpcIdentity:
        """Hydrate an identity read and verified by the persistent adapter."""

        with self._lock:
            existing = self._items.get(npc.npc_id)
            if existing is not None and existing != npc:
                raise ValueError("NPC identity conflicts with the cached identity")
            self._items[npc.npc_id] = npc
        return npc

    def list(self, owner_id: str) -> list[NpcIdentity]:
        with self._lock:
            return sorted(
                (npc for npc in self._items.values() if npc.owner_id == owner_id),
                key=lambda npc: npc.npc_id,
            )
