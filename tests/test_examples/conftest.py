import asyncio
import random

from pytest import fixture


@fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@fixture(scope="module")
def port():
    return random.randint(40_000, 50_000)
