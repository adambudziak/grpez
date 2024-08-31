import struct
from functools import wraps
from typing import (
    TypedDict,
    Callable,
    Awaitable,
    Literal,
    Sequence,
    Any,
    Optional,
    NotRequired,
    Self,
)
from pydantic import BaseModel
from google.protobuf.json_format import MessageToDict


class Scope(TypedDict):
    type: str
    http_version: Literal["1.1", "2"]
    method: Literal[
        "CONNECT", "DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"
    ]
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


class RequestModel(BaseModel):
    @classmethod
    def from_protobuf(cls, r) -> Self:
        return cls(
            **MessageToDict(
                r,
                always_print_fields_with_no_presence=True,
                preserving_proto_field_name=True,
            )
        )


class ResponseModel(BaseModel):
    def to_protobuf(self, proto_t):
        return proto_t(**self.model_dump())


class Service:
    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self._handlers: dict = {}

    def rpc(self, path: str, *, response_type: Any):
        def decorator(fn):
            @wraps(fn)
            async def inner(**kwargs):
                new_kwargs = {}
                for name, ann in fn.__annotations__.items():
                    if issubclass(ann, RequestModel):
                        new_kwargs[name] = ann.from_protobuf(kwargs[name])
                result = await fn(**new_kwargs)
                return result.to_protobuf(response_type)

            self._handlers[path] = inner
            return inner

        return decorator


class Grpez:
    def __init__(self, services: Sequence[Service]):
        self._services = {svc.name: svc for svc in services}
        self._registered_method_handlers = {}

    def add_generic_rpc_handlers(self, handlers):
        pass

    def add_registered_method_handlers(self, path: str, handlers: dict[str, Any]):
        for h_path, h in handlers.items():
            self._registered_method_handlers[f"/{path}/{h_path}"] = h

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        print(scope)
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
        elif scope["type"] == "http":
            svc_path, handler_path = scope["path"].split("/")[1:]
            handler = self._services[svc_path]._handlers[handler_path]
            grpc_handler = self._registered_method_handlers[scope["path"]]
            request_bytes = await build_message(receive)
            request = grpc_handler.request_deserializer(
                request_bytes[5:]
            )  # TODO(adambudziak) fix [5:]
            response = await handler(request=request)  # TODO(adambudziak) fix context
            response_bytes = grpc_handler.response_serializer(
                response
            )

            response_data = create_grpc_message(response_bytes)

            headers = [
                (b"content-type", b"application/grpc+proto"),
                (b'grpc-encoding', b'identity'),
                (b'grpc-accept-encoding', b'identity'),
            ]

            await send(
                {"type": "http.response.start", "status": 200, "headers": headers, "trailers": True}
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": response_data,
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
    header = struct.pack('>?I', compressed_flag, message_length)
    return header + message


def encode_response(data: bytes, *, compress: bool) -> bytes:
    return struct.pack(">BI", int(compress), len(data)) + data


def encode_trailers(data: bytes, *, compress: bool) -> bytes:
    return struct.pack(">BI", 0x80 | compress, len(data)) + data


async def build_message(receive: Receive) -> bytes:
    buf = bytearray()
    while True:
        payload = await receive()
        if payload["type"] != "http.request":
            raise NotImplementedError(f"got unexpected payload {payload}")

        buf.extend(payload["body"])
        if not payload.get("more_body"):
            return bytes(buf)
