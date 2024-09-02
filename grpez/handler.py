from collections import namedtuple
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import (
    Literal,
    Self,
)

from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel


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


@dataclass
class Handler:
    rpc_type: Literal["unary_unary", "unary_stream", "stream_unary", "stream_stream"]
    async_callable: Callable
    request_type: type[RequestModel]
    response_type: type[ResponseModel]


Serde = namedtuple("Serde", "serializer deserializer")


@dataclass
class HandlerContext:
    handler: Handler
    serializer: Callable
    deserializer: Callable


class GrpezUnaryUnary:
    def __init__(self, deserializer, serializer, cb, request_type, result_type):
        self._serializer = serializer
        self._deserializer = deserializer
        self._cb = cb

        self.request_type = request_type
        self.result_type = result_type

    async def __call__(self, raw_request: bytes) -> bytes:
        request = self._deserializer(raw_request)
        response = await self._cb(request)
        return self._serializer(response)

    @staticmethod
    def is_streaming_request() -> bool:
        return False

    @staticmethod
    def is_streaming_response() -> bool:
        return False


class CompatUnaryUnary:
    def __init__(self, deserializer, serializer, cb):
        self._serializer = serializer
        self._deserializer = deserializer
        self._cb = cb

    async def __call__(self, raw_request: bytes) -> bytes:
        request = self._deserializer(raw_request)
        response = await self._cb(request)
        return self._serializer(response)

    @staticmethod
    def is_streaming_request() -> bool:
        return False

    @staticmethod
    def is_streaming_response() -> bool:
        return False


class GrpezStreamUnary:
    def __init__(self, deserializer, serializer, cb, request_type, result_type):
        self._serializer = serializer
        self._deserializer = deserializer
        self._cb = cb

        self.request_type = request_type
        self.result_type = result_type

    async def __call__(self, raw_requests: AsyncGenerator[bytes, None]) -> bytes:
        async def stream_deserialized():
            async for r in raw_requests:
                yield self._deserializer(r)

        # requests = (self._deserializer(r) async for r in raw_requests)
        # response = await self._cb(requests)
        response = await self._cb(stream_deserialized())
        return self._serializer(response)

    @staticmethod
    def is_streaming_request() -> bool:
        return True

    @staticmethod
    def is_streaming_response() -> bool:
        return False


class CompatStreamUnary:
    def __init__(self, deserializer, serializer, cb):
        self._serializer = serializer
        self._deserializer = deserializer
        self._cb = cb

    async def __call__(self, raw_requests: AsyncGenerator[bytes, None]) -> bytes:
        requests = (self._deserializer(r) async for r in raw_requests)
        response = await self._cb(requests)
        return self._serializer(response)

    @staticmethod
    def is_streaming_request() -> bool:
        return True

    @staticmethod
    def is_streaming_response() -> bool:
        return False


class GrpezUnaryStream:
    def __init__(self, deserializer, serializer, cb, request_type, result_type):
        self._serializer = serializer
        self._deserializer = deserializer
        self._cb = cb

        self.request_type = request_type
        self.result_type = result_type

    async def __call__(self, raw_request: bytes) -> AsyncGenerator[bytes, None]:
        request = self._deserializer(raw_request)
        async for response in self._cb(request):
            yield self._serializer(response)

    @staticmethod
    def is_streaming_request() -> bool:
        return False

    @staticmethod
    def is_streaming_response() -> bool:
        return True


class CompatUnaryStream:
    def __init__(self, deserializer, serializer, cb):
        self._serializer = serializer
        self._deserializer = deserializer
        self._cb = cb

    async def __call__(self, raw_request: bytes) -> AsyncGenerator[bytes, None]:
        request = self._deserializer(raw_request)
        async for response in self._cb(request):
            yield self._serializer(response)

    @staticmethod
    def is_streaming_request() -> bool:
        return False

    @staticmethod
    def is_streaming_response() -> bool:
        return True


class GrpezStreamStream:
    def __init__(self, deserializer, serializer, cb, request_type, result_type):
        self._serializer = serializer
        self._deserializer = deserializer
        self._cb = cb

        self.request_type = request_type
        self.result_type = result_type

    async def __call__(self, raw_requests: AsyncGenerator[bytes, None]) -> AsyncGenerator[bytes, None]:
        requests = (self._deserializer(r) async for r in raw_requests)
        async for response in self._cb(requests):
            yield self._serializer(response)

    @staticmethod
    def is_streaming_request() -> bool:
        return True

    @staticmethod
    def is_streaming_response() -> bool:
        return True


class CompatStreamStream:
    def __init__(self, deserializer, serializer, cb):
        self._serializer = serializer
        self._deserializer = deserializer
        self._cb = cb

    async def __call__(self, raw_requests: AsyncGenerator[bytes, None]) -> AsyncGenerator[bytes, None]:
        requests = (self._deserializer(r) async for r in raw_requests)
        async for response in self._cb(requests):
            yield self._serializer(response)

    @staticmethod
    def is_streaming_request() -> bool:
        return True

    @staticmethod
    def is_streaming_response() -> bool:
        return True


RpcHandler = (
    GrpezUnaryUnary
    | CompatUnaryUnary
    | GrpezStreamUnary
    | CompatStreamUnary
    | GrpezUnaryStream
    | CompatUnaryStream
    | GrpezStreamStream
    | CompatStreamStream
)
