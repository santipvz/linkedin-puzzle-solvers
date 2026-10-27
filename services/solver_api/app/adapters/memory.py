from __future__ import annotations

import copy
import threading
from collections import OrderedDict

from ..domain.models import JsonDict


class MemorySolutionCache:
    def __init__(self, max_entries: int = 96) -> None:
        if max_entries < 1:
            raise ValueError("Cache capacity must be positive.")
        self.max_entries = max_entries
        self._entries: OrderedDict[str, JsonDict] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> JsonDict | None:
        with self._lock:
            if key not in self._entries:
                return None
            self._entries.move_to_end(key)
            return copy.deepcopy(self._entries[key])

    def put(self, key: str, value: JsonDict) -> None:
        with self._lock:
            self._entries[key] = copy.deepcopy(value)
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
