import importlib
import importlib.util
import os
import pathlib
import re
import sys
import typing
from collections.abc import AsyncGenerator
from functools import wraps
from typing import get_args

import grpc._utilities
import grpc_tools.protoc
from pydantic import BaseModel

from grpez.dep import D
from grpez.handler import (
    CompatStreamStream,
    CompatStreamUnary,
    CompatUnaryStream,
    CompatUnaryUnary,
    GrpezStreamStream,
    GrpezStreamUnary,
    GrpezUnaryStream,
    GrpezUnaryUnary,
    Handler,
    RequestModel,
    ResponseModel,
    RpcHandler,
    Serde,
)
from grpez.proto import emit_proto_service


class Service:
    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__ + "Service"
        self._handlers: dict[str, Handler] = {}
        self._rpc_handlers: dict[str, RpcHandler] = {}
        self._message_types: set[type[BaseModel]] = set()
        self._handlers_serdes: dict[str, Serde] = {}
        self._message_proto_types = {}

    def rpc_handler(self, path: str) -> RpcHandler | None:
        return self._rpc_handlers.get(path)

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

            match h.rpc_type:
                case "unary_unary":
                    self._rpc_handlers[path] = GrpezUnaryUnary(
                        deserializer=self._message_proto_types[h.request_type].FromString,
                        serializer=self._message_proto_types[h.response_type].SerializeToString,
                        request_type=h.request_type,
                        result_type=h.response_type,
                        cb=h.async_callable,
                    )
                case "unary_stream":
                    self._rpc_handlers[path] = GrpezUnaryStream(
                        deserializer=self._message_proto_types[h.request_type].FromString,
                        serializer=self._message_proto_types[h.response_type].SerializeToString,
                        request_type=h.request_type,
                        result_type=h.response_type,
                        cb=h.async_callable,
                    )
                case "stream_unary":
                    self._rpc_handlers[path] = GrpezStreamUnary(
                        deserializer=self._message_proto_types[h.request_type].FromString,
                        serializer=self._message_proto_types[h.response_type].SerializeToString,
                        request_type=h.request_type,
                        result_type=h.response_type,
                        cb=h.async_callable,
                    )
                case "stream_stream":
                    self._rpc_handlers[path] = GrpezStreamStream(
                        deserializer=self._message_proto_types[h.request_type].FromString,
                        serializer=self._message_proto_types[h.response_type].SerializeToString,
                        request_type=h.request_type,
                        result_type=h.response_type,
                        cb=h.async_callable,
                    )

    def rpc(self, path: str = ""):
        def decorator(fn):
            request_type = None
            result_type = None

            streaming_request = False
            streaming_response = False

            dependencies = {}

            for name, ann in fn.__annotations__.items():
                if name != "return":
                    if getattr(ann, "__origin__", None) is AsyncGenerator:
                        request_name = name
                        request_type, send_t = get_args(ann)
                        if not issubclass(request_type, RequestModel):
                            raise ValueError("grpez only supports requests in async generators")
                        if send_t is not None:
                            raise ValueError("grpez doesn't support sending to endpoints")
                        streaming_request = True
                    elif typing.get_origin(ann) is typing.Annotated:
                        for ann_ in typing.get_args(ann):
                            if isinstance(ann_, D):
                                dependencies[name] = ann_
                    elif issubclass(ann, RequestModel):
                        if request_type is None or ann == request_type:
                            request_name, request_type = name, ann
                        else:
                            raise ValueError("you can only set one request model for an endpoint")

                elif name == "return":
                    if getattr(ann, "__origin__", None) is AsyncGenerator:
                        result_type, send_t = get_args(ann)
                        if send_t is not None:
                            raise ValueError("grpez doesn't support sending to endpoints")
                        streaming_response = True
                    elif issubclass(ann, ResponseModel):
                        result_type = ann

            if request_type is None:
                raise ValueError("you must set request type for an endpoint")

            if result_type is None:
                raise ValueError("you forgot result type annotation")

            self._message_types.add(request_type)
            self._message_types.add(result_type)

            path_ = path or fn.__name__.title().replace("_", "")

            if not streaming_request and not streaming_response:

                @wraps(fn)
                async def inner(request):
                    new_kwargs = {request_name: request_type.from_protobuf(request)} | {
                        dep_name: await dep.get() for dep_name, dep in dependencies.items()
                    }
                    result = await fn(**new_kwargs)
                    return result.to_protobuf(self._message_proto_types[result_type])

                self._handlers[path_] = Handler(
                    request_type=request_type, response_type=result_type, async_callable=inner, rpc_type="unary_unary"
                )

            elif not streaming_request and streaming_response:

                @wraps(fn)
                async def inner(request):
                    new_kwargs = {request_name: request_type.from_protobuf(request)} | {
                        dep_name: await dep.get() for dep_name, dep in dependencies.items()
                    }
                    result_type_ = self._message_proto_types[result_type]
                    async for result in fn(**new_kwargs):
                        yield result.to_protobuf(result_type_)

                self._handlers[path_] = Handler(
                    request_type=request_type, response_type=result_type, async_callable=inner, rpc_type="unary_stream"
                )
            elif streaming_request and not streaming_response:

                @wraps(fn)
                async def inner(request_gen):
                    new_kwargs = {request_name: (request_type.from_protobuf(r) async for r in request_gen)} | {
                        dep_name: await dep.get() for dep_name, dep in dependencies.items()
                    }
                    result_type_ = self._message_proto_types[result_type]
                    result = await fn(**new_kwargs)
                    return result.to_protobuf(result_type_)

                self._handlers[path_] = Handler(
                    request_type=request_type, response_type=result_type, async_callable=inner, rpc_type="stream_unary"
                )

            else:

                @wraps(fn)
                async def inner(request_gen):
                    result_type_ = self._message_proto_types[result_type]
                    new_kwargs = {request_name: (request_type.from_protobuf(r) async for r in request_gen)} | {
                        dep_name: await dep.get() for dep_name, dep in dependencies.items()
                    }
                    async for result in fn(**new_kwargs):
                        yield result.to_protobuf(result_type_)

                self._handlers[path_] = Handler(
                    request_type=request_type, response_type=result_type, async_callable=inner, rpc_type="stream_stream"
                )

            return inner

        return decorator


class GrpcServiceWrapper:
    def __init__(self, handlers: dict[str, grpc._utilities.RpcMethodHandler]):
        self._rpc_handlers = {path: _convert_handler(handler) for path, handler in handlers.items()}

    def rpc_handler(self, path: str) -> RpcHandler | None:
        return self._rpc_handlers.get(path)


def _convert_handler(grpc_handler: grpc._utilities.RpcMethodHandler) -> RpcHandler:
    if grpc_handler.unary_unary:
        return CompatUnaryUnary(
            serializer=grpc_handler.response_serializer,
            deserializer=grpc_handler.request_deserializer,
            cb=lambda r: grpc_handler.unary_unary(r, None),
        )
    elif grpc_handler.unary_stream:
        return CompatUnaryStream(
            serializer=grpc_handler.response_serializer,
            deserializer=grpc_handler.request_deserializer,
            cb=lambda r: grpc_handler.unary_stream(r, None),
        )
    elif grpc_handler.stream_unary:
        return CompatStreamUnary(
            serializer=grpc_handler.response_serializer,
            deserializer=grpc_handler.request_deserializer,
            cb=lambda r: grpc_handler.stream_unary(r, None),
        )
    elif grpc_handler.stream_stream:
        return CompatStreamStream(
            serializer=grpc_handler.response_serializer,
            deserializer=grpc_handler.request_deserializer,
            cb=lambda r: grpc_handler.stream_stream(r, None),
        )
