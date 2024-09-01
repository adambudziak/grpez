"""
This example shows how grpez can be combined with any other
ASGI app and run together. This example is ASGI-server-specific.
"""

import pathlib

import grpc.aio
import httpx
import prometheus_client
from hypercorn.middleware import DispatcherMiddleware
from pytest import fixture

import grpez
from tests.utils import run_server

svc = grpez.Service("ServiceWithMetrics")


class Thing(grpez.RequestModel, grpez.ResponseModel):
    value: int


@svc.rpc()
async def do_thing(r: Thing) -> Thing:
    return Thing(value=r.value * 3)


@fixture(scope="module")
async def server(port):
    app = grpez.Grpez(services=[svc], reflection=True, gen_path=pathlib.Path(__file__).parent / "grpez_gen")
    dispatcher_app = DispatcherMiddleware({"/metrics": prometheus_client.make_asgi_app(), "": app})
    async with run_server(dispatcher_app, port):
        yield


@fixture(scope="module")
async def stub(port, server):
    from tests.test_examples.grpez_gen import servicewithmetrics_pb2_grpc as pb_grpc

    async with grpc.aio.insecure_channel(f"[::]:{port}") as channel:
        yield pb_grpc.ServiceWithMetricsStub(channel)


async def test_both_apps_are_accessible(stub, port):
    from tests.test_examples.grpez_gen import servicewithmetrics_pb2 as pb

    result = await stub.DoThing(pb.Thing(value=5))
    assert result.value == 15

    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
        response = await client.get("/metrics")
        assert "HELP python_info Python platform information" in response.text
        # randomly-selected part of prometheus response
