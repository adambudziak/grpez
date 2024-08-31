import pathlib
from collections.abc import AsyncGenerator

import grpc.aio
from pytest import fixture, mark

import grpez
from tests.utils import run_server

streaming_svc = grpez.Service("Streaming")


class GetRangeRequest(grpez.RequestModel):
    min_value: int
    max_value: int


class GetRangeResponse(grpez.ResponseModel):
    value: int


class SumNumbersRequest(grpez.RequestModel):
    number: int


class SumNumbersResponse(grpez.ResponseModel):
    total: int


class DoubleNumber(grpez.RequestModel, grpez.ResponseModel):
    number: int


@streaming_svc.rpc()
async def get_range(r: GetRangeRequest) -> AsyncGenerator[GetRangeResponse, None]:
    for i in range(r.min_value, r.max_value + 1):
        yield GetRangeResponse(value=i)


@streaming_svc.rpc()
async def sum_numbers(rs: AsyncGenerator[SumNumbersRequest, None]) -> SumNumbersResponse:
    total = 0
    async for r in rs:
        total += r.number

    return SumNumbersResponse(total=total)


@streaming_svc.rpc()
async def double_numbers(rs: AsyncGenerator[DoubleNumber, None]) -> AsyncGenerator[DoubleNumber, None]:
    async for r in rs:
        yield DoubleNumber(number=r.number * 2)


@fixture(scope="module")
async def server(port):
    app = grpez.Grpez(services=[streaming_svc], reflection=True, gen_path=pathlib.Path(__file__).parent / "grpez_gen")
    async with run_server(app, port):
        yield


@fixture(scope="module")
async def stub(port, server):
    from tests.test_examples.grpez_gen import streaming_pb2_grpc as pb_grpc

    async with grpc.aio.insecure_channel(f"[::]:{port}") as channel:
        yield pb_grpc.StreamingStub(channel)


@mark.parametrize("min_, max_", ((1, 5), (2_000_000, 2_010_000), (0, 1)))
async def test_get_streaming_response(min_, max_, stub):
    from tests.test_examples.grpez_gen import streaming_pb2 as pb

    values_received = []
    async for response in stub.GetRange(pb.GetRangeRequest(min_value=min_, max_value=max_)):
        values_received.append(response.value)

    assert values_received == list(range(min_, max_ + 1))


@mark.parametrize("min_, max_", ((1, 5), (1, 10_000)))
async def test_send_streaming_request(min_, max_, stub):
    from tests.test_examples.grpez_gen import streaming_pb2 as pb

    async def gen():
        for i in range(min_, max_ + 1):
            yield pb.SumNumbersRequest(number=i)

    response = await stub.SumNumbers(gen())
    assert response.total == sum(range(min_, max_ + 1))


@mark.parametrize("min_, max_", ((1, 5), (20, 100), (10_000, 15_000)))
async def test_bidirectional_stream(min_, max_, stub):
    from tests.test_examples.grpez_gen import streaming_pb2 as pb

    async def gen():
        for i in range(min_, max_ + 1):
            yield pb.DoubleNumber(number=i)

    i = min_
    async for r in stub.DoubleNumbers(gen()):
        assert r.number == i * 2
        i += 1

    assert i == max_ + 1
