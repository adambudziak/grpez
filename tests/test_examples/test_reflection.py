import pathlib

import grpc.aio
from google.protobuf.json_format import MessageToDict
from grpc_reflection.v1alpha import reflection_pb2, reflection_pb2_grpc
from pytest import fixture, mark

import grpez
from tests.utils import run_server, AnyStr

hello_svc = grpez.Service("HelloService")


class HelloRequest(grpez.RequestModel):
    name: str


class HelloResponse(grpez.ResponseModel):
    greeting: str


@hello_svc.rpc()
async def get_greeting(hello: HelloRequest) -> HelloResponse:
    return HelloResponse(greeting=f"hello {hello.name}")


@fixture(scope="module")
async def server(port):
    app = grpez.Grpez(services=[hello_svc], reflection=True, gen_path=pathlib.Path(__file__).parent / "grpez_gen")
    async with run_server(app, port):
        yield


@mark.parametrize(
    "request_kwargs, expected_responses",
    (
        ({"list_services": ""}, [{"list_services_response": {"service": [{"name": "HelloService"}]}}]),
        ({"list_services": "HelloService"}, [{"list_services_response": {"service": [{"name": "HelloService"}]}}]),
        (
            {"file_containing_symbol": "HelloService"},
            [
                {
                    "file_descriptor_response": {
                        "file_descriptor_proto": [
                            AnyStr
                        ]
                    }
                }
            ],
        ),
    ),
)
@mark.usefixtures("server")
async def test_response_is_equal_to_request(port: int, request_kwargs, expected_responses):
    async with grpc.aio.insecure_channel(f"[::]:{port}") as channel:
        reflection_stub = reflection_pb2_grpc.ServerReflectionStub(channel)
        request = reflection_pb2.ServerReflectionRequest(**request_kwargs)
        responses = reflection_stub.ServerReflectionInfo([request])
        b = []
        async for response in responses:
            b.append(MessageToDict(response, preserving_proto_field_name=True))

        assert b == expected_responses
