import contextvars
import pathlib
from collections.abc import Awaitable, Callable

import grpc.aio
from pytest import fixture

import grpez
from tests.utils import run_server

rpc_id_var = contextvars.ContextVar("ctx_var", default="default")


class CtxVarInterceptor(grpc.aio.ServerInterceptor):
    def __init__(self, name: str):
        self.name = name

    async def intercept_service(
        self,
        continuation: Callable[[grpc.HandlerCallDetails], Awaitable[grpc.RpcMethodHandler]],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler:
        if rpc_id_var.get() == "default":
            _metadata = dict(handler_call_details.invocation_metadata)
            rpc_id = _metadata["client-rpc-id"]
        else:
            rpc_id = rpc_id_var.get()

        rpc_id_var.set(f"{self.name}.{rpc_id}")
        return await continuation(handler_call_details)

    def __repr__(self):
        return f"{self.__class__.__name__}({repr(self.name)})"


svc = grpez.Service("Interceptor")


class InterceptorExample(grpez.RequestModel, grpez.ResponseModel):
    greeting: str


@svc.rpc()
async def hello(msg: InterceptorExample) -> InterceptorExample:
    return InterceptorExample(greeting=f"{msg.greeting}.{rpc_id_var.get()}")


@fixture(scope="module")
async def server(port):
    app = grpez.Grpez(
        services=[svc],
        reflection=True,
        gen_path=pathlib.Path(__file__).parent / "grpez_gen",
        interceptors=[CtxVarInterceptor("intercept-1"), CtxVarInterceptor("intercept-2")],
    )
    async with run_server(app, port):
        yield


@fixture(scope="module")
async def stub(port, server):
    from tests.test_examples.grpez_gen import interceptor_pb2_grpc as pb_grpc

    async with grpc.aio.insecure_channel(f"[::]:{port}") as channel:
        yield pb_grpc.InterceptorStub(channel)


async def test_interceptor(stub):
    from tests.test_examples.grpez_gen import interceptor_pb2 as pb

    response = await stub.Hello(
        pb.InterceptorExample(greeting="hello world"), metadata=grpc.aio.Metadata(("client-rpc-id", "grpez"))
    )
    assert response.greeting == "hello world.intercept-2.intercept-1.grpez"
