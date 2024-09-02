from collections.abc import Awaitable, Callable
from typing import Any, Literal

_globals = {}


class D:
    Scope = Literal["function", "global"]

    def __init__(self, factory: Callable[[], Awaitable[Any]], *, scope: Scope = "function"):
        self._dep_id = hash(factory)
        self._factory = factory
        self._scope = scope

    async def get(self) -> Any:
        if self._scope == "function":
            return await self._factory()
        else:
            try:
                dep = _globals[self._dep_id]
            except KeyError:
                dep = await self._factory()
                _globals[self._dep_id] = dep
            return dep
