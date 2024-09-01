import asyncio
from contextlib import asynccontextmanager

from hypercorn import Config
from hypercorn.asyncio import serve


@asynccontextmanager
async def run_server(app, port: int):
    shutdown_event = asyncio.Event()
    _ = asyncio.create_task(serve(app, Config.from_mapping(bind=f"[::]:{port}"), shutdown_trigger=shutdown_event.wait))
    await asyncio.sleep(0.2)
    yield
    shutdown_event.set()
    await asyncio.sleep(0.2)


class _AnyStr:
    def __eq__(self, other):
        return isinstance(other, str)

    def __repr__(self):
        return "<AnyStr>"


AnyStr = _AnyStr()
