import asyncio
from contextlib import asynccontextmanager

from hypercorn import Config
from hypercorn.asyncio import serve

from grpez import Grpez


@asynccontextmanager
async def run_server(app: Grpez, port: int):
    shutdown_event = asyncio.Event()
    _ = asyncio.create_task(serve(app, Config.from_mapping(bind=f"[::]:{port}"), shutdown_trigger=shutdown_event.wait))
    await asyncio.sleep(0.2)
    yield
    shutdown_event.set()
    await asyncio.sleep(0.2)
