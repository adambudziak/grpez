import pathlib

import grpc.aio
from pytest import fixture, mark

import grpez
from tests.test_examples.grpez_gen import echoservice_pb2 as pb
from tests.test_examples.grpez_gen import echoservice_pb2_grpc as pb_grpc
from tests.test_examples.utils import run_server

echo_svc = grpez.Service("EchoService")


class Echo(grpez.RequestModel, grpez.ResponseModel):
    message: str


@echo_svc.rpc()
async def get_echo(echo: Echo) -> Echo:
    return echo


@fixture(scope="module")
async def server(port):
    app = grpez.Grpez(services=[echo_svc], reflection=True, gen_path=pathlib.Path(__file__).parent / "grpez_gen")
    async with run_server(app, port):
        yield


@mark.parametrize("message", ("hello world", "general kenobi", "something longer" * 100))
@mark.usefixtures("server")
async def test_response_is_equal_to_request(message, port: int):
    async with grpc.aio.insecure_channel(f"[::]:{port}") as channel:
        stub = pb_grpc.EchoServiceStub(channel)
        response = await stub.GetEcho(pb.Echo(message=message))
        assert response.message == message
