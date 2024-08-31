import asyncio
import pathlib
import random

import grpc.aio
from hypercorn import Config
from hypercorn.asyncio import serve
from pytest import fixture, mark

import grpez
from tests.test_examples.grpez_gen import echoservice_pb2 as pb
from tests.test_examples.grpez_gen import echoservice_pb2_grpc as pb_grpc

echo_svc = grpez.Service("EchoService")


class Echo(grpez.RequestModel, grpez.ResponseModel):
    message: str


@echo_svc.rpc()
async def get_echo(echo: Echo) -> Echo:
    return echo


@fixture(scope="module")
def port():
    return random.randint(40_000, 50_000)


@fixture(scope="module")
async def server(port):
    app = grpez.Grpez(services=[echo_svc], reflection=True, gen_path=pathlib.Path(__file__).parent / "grpez_gen")
    task = asyncio.create_task(serve(app, Config.from_mapping(bind=f"[::]:{port}")))
    await asyncio.sleep(1)
    yield
    task.cancel()  # TODO very noisy, find a better way to shut it down gracefully


@mark.parametrize("message", ("hello world", "general kenobi", "something longer" * 100))
@mark.usefixtures("server")
async def test_response_is_equal_to_request(message, port: int):
    async with grpc.aio.insecure_channel(f"[::]:{port}") as channel:
        stub = pb_grpc.EchoServiceStub(channel)
        response = await stub.GetEcho(pb.Echo(message=message))
        assert response.message == message
