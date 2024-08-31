import importlib
import importlib.util
import os
import pathlib
import re
import struct
import sys
from collections import namedtuple
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from functools import wraps
from typing import (
    Any,
    Literal,
    NotRequired,
    Self,
    TypedDict,
)

import grpc_tools.protoc
from google.protobuf.json_format import MessageToDict
from pydantic import BaseModel


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
    async_callable: Callable
    request_type: type[RequestModel]
    response_type: type[ResponseModel]


Serde = namedtuple("Serde", "serializer deserializer")


@dataclass
class HandlerContext:
    handler: Handler
    serializer: Callable
    deserializer: Callable


class Service:
    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__ + "Service"
        self._handlers: dict[str, Handler] = {}
        self._message_types: set[type[BaseModel]] = set()
        self._handlers_serdes: dict[str, Serde] = {}
        self._message_proto_types = {}

    def handler_context(self, path: str) -> HandlerContext | None:
        try:
            handler = self._handlers[path]
            serde = self._handlers_serdes[path]
        except KeyError:
            return None

        return HandlerContext(handler=handler, serializer=serde.serializer, deserializer=serde.deserializer)

    def compile(self, gen_path: pathlib.Path):
        os.makedirs(gen_path, exist_ok=True)
        proto_name = f"{self.name}.proto".lower()
        with open(gen_path / proto_name, "w") as proto_f:
            proto_f.write(emit_proto_service(self))
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
            async def inner(**kwargs):
                new_kwargs = {request_name: request_type.from_protobuf(kwargs["request"])}
                result = await fn(**new_kwargs)
                return result.to_protobuf(self._message_proto_types[result_type])

            path_ = path or fn.__name__.title().replace("_", "")
            self._handlers[path_] = Handler(async_callable=inner, request_type=request_type, response_type=result_type)
            return inner

        return decorator


def emit_proto_service(s: Service):
    rpcs = []
    msg_types = set()
    for path, handler in s._handlers.items():
        msg_types.add(handler.request_type)
        msg_types.add(handler.response_type)
        rpcs.append((path, handler.request_type.__name__, handler.response_type.__name__))

    svc = f"""
syntax = "proto3";
    
service {s.name} {{
    {'\n'.join(f'rpc {path}({req}) returns ({ret}) {{}}' for (path, req, ret) in rpcs)}
}}
""".strip()

    messages = "\n\n".join(emit_proto_message(m) for m in msg_types)

    return f"{svc}\n\n{messages}"


def emit_proto_message(m: type[BaseModel]):
    proto_fields = []
    type_mapping = {str: "string"}
    for name, field in m.model_fields.items():
        proto_fields.append((type_mapping[field.annotation], name))

    return f"""
message {m.__name__} {{
    {'\n'.join(f'{type_} {name_} = {idx};' for idx, (type_, name_) in enumerate(proto_fields, 1))}
}}
""".strip()


class Grpez:
    def __init__(self, services: Sequence[Service], *, reflection: bool = False, gen_path: pathlib.Path):
        self._services = {svc.name: svc for svc in services}
        self._reflection = reflection
        self._registered_method_handlers = {}
        for svc in self._services.values():
            svc.compile(gen_path)

    def add_generic_rpc_handlers(self, handlers):
        pass

    def add_registered_method_handlers(self, path: str, handlers: dict[str, Any]):
        for h_path, h in handlers.items():
            self._registered_method_handlers[f"/{path}/{h_path}"] = h

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
            context = self._services[svc_path].handler_context(handler_path)
            request_bytes = await build_message(receive)
            request = context.deserializer(request_bytes[5:])
            response = await context.handler.async_callable(request=request)
            response_bytes = context.serializer(response)

            response_data = create_grpc_message(response_bytes)

            headers = [
                (b"content-type", b"application/grpc+proto"),
                (b"grpc-encoding", b"identity"),
                (b"grpc-accept-encoding", b"identity"),
            ]

            await send({"type": "http.response.start", "status": 200, "headers": headers, "trailers": True})
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
    header = struct.pack(">?I", compressed_flag, message_length)
    return header + message


async def build_message(receive: Receive) -> bytes:
    buf = bytearray()
    while True:
        payload = await receive()
        if payload["type"] != "http.request":
            raise NotImplementedError(f"got unexpected payload {payload}")

        buf.extend(payload["body"])
        if not payload.get("more_body"):
            return bytes(buf)
