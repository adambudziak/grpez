from collections import namedtuple
from collections.abc import Callable
from dataclasses import dataclass
from typing import (
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
    async_callable: Callable
    request_type: type[RequestModel]
    response_type: type[ResponseModel]


Serde = namedtuple("Serde", "serializer deserializer")


@dataclass
class HandlerContext:
    handler: Handler
    serializer: Callable
    deserializer: Callable
