import importlib
import importlib.util
import os
import pathlib
import re
import sys
from collections.abc import AsyncGenerator
from functools import wraps

import grpc._utilities
import grpc_tools.protoc
from pydantic import BaseModel

from grpez.handler import Handler, RequestModel, ResponseModel, Serde
from grpez.proto import emit_proto_service


class UnaryUnary:
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


class StreamUnary:
    def __init__(self, deserializer, serializer, cb):
        self._serializer = serializer
        self._deserializer = deserializer
        self._cb = cb

    async def __call__(self, raw_requests: AsyncGenerator[bytes]) -> bytes:
        requests = (self._deserializer(r) async for r in raw_requests)
        response = await self._cb(requests)
        return self._serializer(response)

    @staticmethod
    def is_streaming_request() -> bool:
        return True

    @staticmethod
    def is_streaming_response() -> bool:
        return False


class UnaryStream:
    def __init__(self, deserializer, serializer, cb):
        self._serializer = serializer
        self._deserializer = deserializer
        self._cb = cb

    async def __call__(self, raw_request: bytes) -> AsyncGenerator[bytes, None]:
        request = self._deserializer(raw_request)
        async for response in self._cb(request):
            yield response

    @staticmethod
    def is_streaming_request() -> bool:
        return False

    @staticmethod
    def is_streaming_response() -> bool:
        return True


class StreamStream:
    def __init__(self, deserializer, serializer, cb):
        self._serializer = serializer
        self._deserializer = deserializer
        self._cb = cb

    async def __call__(self, raw_requests: AsyncGenerator[bytes]) -> AsyncGenerator[bytes, None]:
        requests = (self._deserializer(r) async for r in raw_requests)
        async for response in self._cb(requests):
            yield self._serializer(response)

    @staticmethod
    def is_streaming_request() -> bool:
        return True

    @staticmethod
    def is_streaming_response() -> bool:
        return True


RpcHandler = UnaryUnary | StreamUnary | UnaryStream | StreamStream


class Service:
    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__ + "Service"
        self._handlers: dict[str, Handler] = {}
        self._message_types: set[type[BaseModel]] = set()
        self._handlers_serdes: dict[str, Serde] = {}
        self._message_proto_types = {}

    def rpc_handler(self, path: str) -> RpcHandler | None:
        try:
            handler = self._handlers[path]
            serde = self._handlers_serdes[path]
        except KeyError:
            return None

        return UnaryUnary(cb=handler.async_callable, serializer=serde.serializer, deserializer=serde.deserializer)

    def compile(self, gen_path: pathlib.Path):
        os.makedirs(gen_path, exist_ok=True)
        proto_name = f"{self.name}.proto".lower()
        with open(gen_path / proto_name, "w") as proto_f:
            proto_f.write(emit_proto_service(self.name, self._handlers))
            proto_f.flush()

            protoc_params = [
                "protoc",
                f"-I{gen_path}",
                f"--python_out={gen_path}",
                f"--grpc_python_out={gen_path}",
                proto_name,
            ]
            grpc_tools.protoc.main(protoc_params)

        # workaround for https://github.com/protocolbuffers/protobuf/issues/1491
        pattern = r"^import (\w+_pb2) as (\w+__pb2)$"
        with open(f"{gen_path}/{self.name.lower()}_pb2_grpc.py") as grpc_f:
            content = grpc_f.read()

        def replace(m):
            return f"from . import {m.group(1)} as {m.group(2)}"

        modified_content = re.sub(pattern, replace, content, flags=re.MULTILINE)
        with open(f"{gen_path}/{self.name.lower()}_pb2_grpc.py", "w") as grpc_f:
            grpc_f.write(modified_content)

        # end of workaround

        module_name = self.name.lower() + "_pb2"
        spec = importlib.util.spec_from_file_location(module_name, gen_path / (module_name + ".py"))
        pb_mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = pb_mod
        spec.loader.exec_module(pb_mod)

        for mt in self._message_types:
            self._message_proto_types[mt] = getattr(pb_mod, mt.__name__)

        for path, h in self._handlers.items():
            self._handlers_serdes[path] = Serde(
                deserializer=self._message_proto_types[h.request_type].FromString,
                serializer=self._message_proto_types[h.response_type].SerializeToString,
            )

    def rpc(self, path: str = ""):
        def decorator(fn):
            request_type = None
            result_type = None

            for name, ann in fn.__annotations__.items():
                if name != "return" and issubclass(ann, RequestModel):
                    if request_type is None or ann == request_type:
                        request_name, request_type = name, ann
                    else:
                        raise ValueError("you can only set one request model for an endpoint")
                elif name == "return" and issubclass(ann, ResponseModel):
                    result_type = ann

            if request_type is None:
                raise ValueError("you must set request type for an endpoint")

            if result_type is None:
                raise ValueError("you forgot result type annotation")

            self._message_types.add(request_type)
            self._message_types.add(result_type)

            @wraps(fn)
            async def inner(request):
                new_kwargs = {request_name: request_type.from_protobuf(request)}
                result = await fn(**new_kwargs)
                return result.to_protobuf(self._message_proto_types[result_type])

            path_ = path or fn.__name__.title().replace("_", "")
            self._handlers[path_] = Handler(async_callable=inner, request_type=request_type, response_type=result_type)
            return inner

        return decorator


class GrpcServiceWrapper:
    def __init__(self, handlers: dict[str, grpc._utilities.RpcMethodHandler]):
        self._rpc_handlers = {path: _convert_handler(handler) for path, handler in handlers.items()}

    def rpc_handler(self, path: str) -> RpcHandler | None:
        return self._rpc_handlers.get(path)


def _convert_handler(grpc_handler: grpc._utilities.RpcMethodHandler) -> RpcHandler:
    if grpc_handler.unary_unary:
        return UnaryUnary(
            serializer=grpc_handler.response_serializer,
            deserializer=grpc_handler.request_deserializer,
            cb=lambda r: grpc_handler.unary_unary(r, None),
        )
    elif grpc_handler.unary_stream:
        return UnaryStream(
            serializer=grpc_handler.response_serializer,
            deserializer=grpc_handler.request_deserializer,
            cb=lambda r: grpc_handler.unary_stream(r, None),
        )
    elif grpc_handler.stream_unary:
        return StreamUnary(
            serializer=grpc_handler.response_serializer,
            deserializer=grpc_handler.request_deserializer,
            cb=lambda r: grpc_handler.stream_unary(r, None),
        )
    elif grpc_handler.stream_stream:
        return StreamStream(
            serializer=grpc_handler.response_serializer,
            deserializer=grpc_handler.request_deserializer,
            cb=lambda r: grpc_handler.stream_stream(r, None),
        )
