import pathlib
from typing import Annotated

import grpc.aio
from pytest import fixture

import grpez
from tests.utils import run_server

svc = grpez.Service("Dependency")


class App:
    def __init__(self):
        self.counter = 0


async def get_app():
    return App()


class Message(grpez.RequestModel, grpez.ResponseModel):
    value: int


@svc.rpc()
async def foo(msg: Message, app: Annotated[App, grpez.D(get_app, scope="server")]) -> Message:
    app.counter += msg.value
    return Message(value=app.counter)


@svc.rpc()
async def bar(msg: Message, app: Annotated[App, grpez.D(get_app, scope="server")]) -> Message:
    app.counter += msg.value * 2
    return Message(value=app.counter)


@svc.rpc()
async def baz(msg: Message, app: Annotated[App, grpez.D(get_app)]) -> Message:
    app.counter += msg.value * 3
    return Message(value=app.counter)


@fixture(scope="module")
async def server(port):
    app = grpez.Grpez(services=[svc], reflection=True, gen_path=pathlib.Path(__file__).parent / "grpez_gen")
    async with run_server(app, port):
        yield


@fixture(scope="module")
async def stub(port, server):
    from tests.test_examples.grpez_gen import dependency_pb2_grpc as pb_grpc

    async with grpc.aio.insecure_channel(f"[::]:{port}") as channel:
        yield pb_grpc.DependencyStub(channel)


async def test_app_is_shared(stub):
    from tests.test_examples.grpez_gen import dependency_pb2 as pb

    response = await stub.Foo(pb.Message(value=1))
    assert response.value == 1
    response = await stub.Bar(pb.Message(value=2))
    assert response.value == 5
    response = await stub.Foo(pb.Message(value=5))
    assert response.value == 10
    response = await stub.Baz(pb.Message(value=10))
    assert response.value == 30
    response = await stub.Bar(pb.Message(value=3))
    assert response.value == 16
