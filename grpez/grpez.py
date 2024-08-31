import pathlib
import struct
from collections.abc import Awaitable, Callable, Generator, Sequence
from typing import (
    Literal,
    NotRequired,
    TypedDict,
)

from grpc_reflection.v1alpha import _async as reflection_aio
from grpc_reflection.v1alpha import reflection_pb2_grpc

from grpez.service import GrpcServiceWrapper, Service


class Scope(TypedDict):
    type: str
    http_version: Literal["1.1", "2"]
    method: Literal["CONNECT", "DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"]
    scheme: Literal["http"]
    path: str
    raw_path: bytes
    headers: Sequence[tuple[bytes, bytes]]


class Event(TypedDict):
    type: str
    body: NotRequired[bytes]
    more_body: NotRequired[bool]


Receive = Callable[[], Awaitable[Event]]
Send = Callable[[dict], Awaitable]


class Grpez:
    def __init__(self, services: Sequence[Service], *, reflection: bool = False, gen_path: pathlib.Path):
        self._services: dict[str, Service | GrpcServiceWrapper] = {svc.name: svc for svc in services}
        self._reflection = reflection

        self._generic_rpc_handlers = {}
        self._registered_method_handlers = {}

        for svc in self._services.values():
            svc.compile(gen_path)

        if self._reflection:
            reflection_pb2_grpc.add_ServerReflectionServicer_to_server(
                reflection_aio.ReflectionServicer(list(self._services)), self
            )

    def add_generic_rpc_handlers(self, *args):
        pass

    def add_registered_method_handlers(self, service: str, handlers):
        self._services[service] = GrpcServiceWrapper(handlers)

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
        elif scope["type"] == "http":
            svc_path, handler_path = scope["path"].split("/")[1:]
            rpc_handler = self._services[svc_path].rpc_handler(handler_path)

            if rpc_handler.is_streaming_request():
                # TODO(adambudziak) do proper async generator, pipe the messages as they come
                #  to the handler instead of aggregating them all first and then cutting
                raw_request_bytes = await build_message(receive)

                async def request_gen():
                    for chunk in cut_into_messages(raw_request_bytes):
                        yield chunk

                request = request_gen()

            else:
                request = (await build_message(receive))[5:]

            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [
                        (b"content-type", b"application/grpc+proto"),
                        (b"grpc-encoding", b"identity"),
                        (b"grpc-accept-encoding", b"identity"),
                    ],
                    "trailers": True,
                }
            )

            if rpc_handler.is_streaming_response():
                async for response in rpc_handler(request):
                    # TODO(adambudziak) check if it makes sense to do it like that for small messages
                    #  maybe it's better to chunk messages to send bigger frames?
                    #  Or hypercorn does it under the hood?
                    await send({"type": "http.response.body", "body": create_grpc_message(response), "more_body": True})
                await send({"type": "http.response.body", "body": b""})
            else:
                response = await rpc_handler(request)
                await send(
                    {
                        "type": "http.response.body",
                        "body": create_grpc_message(response),
                    }
                )

            await send(
                {
                    "type": "http.response.trailers",
                    "headers": [(b"grpc-status", b"0"), (b"grpc-message", b"OK")],
                }
            )


def create_grpc_message(message: bytes) -> bytes:
    compressed_flag = 0
    message_length = len(message)
    header = struct.pack(">?I", compressed_flag, message_length)
    return header + message


def cut_into_messages(data: bytes) -> Generator[bytes, None, None]:
    i = 0
    while i < len(data):
        _, length = struct.unpack(">BI", data[i : i + 5])
        yield data[i + 5 : i + 5 + length]
        i += 5 + length


async def build_message(receive: Receive) -> bytes:
    buf = bytearray()
    while True:
        payload = await receive()
        if payload["type"] != "http.request":
            raise NotImplementedError(f"got unexpected payload {payload}")

        buf.extend(payload["body"])
        if not payload.get("more_body"):
            return bytes(buf)
