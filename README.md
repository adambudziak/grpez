# grpez

gRPC in Python made EZ.

## Rationale

Python community puts a lot of effort to make developing REST APIs as good as
it currently is. If you get used to using FastAPI and Pydantic for your APIs, and then
suddenly decide that you want to use gRPC for whatever reason, that is going to be a disappointment.

The goal of `grpez` is to bring gRPC development in Python on similar modern level
as what you can get with REST.

[Examples](tests/test_examples)

## Installation

```shell
pip install 'git+https://github.com/adambudziak/grpez'  # pypi coming soon
```

## Quickstart

```python
# server.py
import asyncio
import hypercorn.asyncio
import pathlib
import grpez

svc = grpez.Service("HelloWorld")


class GreetingRequest(grpez.RequestModel):
    name: str


class GreetingResponse(grpez.ResponseModel):
    greeting: str


@svc.rpc()
async def greeting(r: GreetingRequest) -> GreetingResponse:
    return GreetingResponse(greeting=f'hello, {r.name}')


app = grpez.Grpez(
    services=[svc],
    reflection=True,
    gen_path=pathlib.Path(__file__) / "grpez_gen",  # where the proto will land
)

asyncio.run(hypercorn.asyncio.serve(app, hypercorn.Config()))
```

If you run the script above, grpez will do a few things:

#### 1. generate a proto file from your endpoints. 

It's contents will look as follows, it's stored in the `grpez_gen` directory.

```protobuf
syntax = "proto3";
    
service HelloWorld {
    rpc Greeting(GreetingRequest) returns (GreetingResponse) {}
}

message GreetingRequest {
    string name = 1;
}

message GreetingResponse {
    string greeting = 1;
}
```

#### 2. generate python grpc files from the proto

They're stored right besides the proto file.

#### 3. hook it all together at startup, so your endpoints are called on requests

Most of the heavy lifting is done eagerly, so handling requests is as lightweight as possible.

#### 4. run a server on port 8000 with reflection enabled

## Features

The library is in a very early stage, so most of those features are in-progress at the moment.

The library has a lot of opinions, but one of its design rules is to not force any one of them on you.
If you dislike any of the features, there are ways to just use old-style grpc/proto approaches.

### Drive on top of ASGI

You can mix grpez with any other ASGI application and run them together. You can even mix it with FastAPI.

One caveat: gRPC needs HTTP/2 and currently hypercorn is the only ASGI implementation
that supports that. Granian might also be used once it supports HTTP/2 trailers.


```python
import pathlib

import grpez
import prometheus_client
from hypercorn.middleware import DispatcherMiddleware
from hypercorn.asyncio import serve
from hypercorn import Config

svc = grpez.Service("ServiceWithMetrics")


class Thing(grpez.RequestModel, grpez.ResponseModel):
    value: int


@svc.rpc()
async def do_thing(r: Thing) -> Thing:
    return Thing(value=r.value * 3)


async def main():
    app = grpez.Grpez(
        services=[svc], 
        reflection=True, 
        gen_path=pathlib.Path(__file__).parent / "grpez_gen"
    )
    dispatcher_app = DispatcherMiddleware({
        "/metrics": prometheus_client.make_asgi_app(),
        "": app
    })
    await serve(dispatcher_app, Config())
    

```

### Native integration with Pydantic

Classes generated from protobuf are terrible in all kinds of ways. They have
ambiguous `__repr__`, it's hard to see their internals, they don't play nicely with
types, it's impossible to add an extra parsing stage. With grpez, you just define a Pydantic
model that will be your interface when reading request contents. 

The generated proto class is still there, but you never need to see it (if you do for whatever reason,
there are ways).

### Define endpoints in code, generate proto from that

Instead of writing a .proto file first, then generating code from it, and then writing Pydantic
models to wrap it all into something usable, you can first define endpoints using Pydantic and grpez,
and then generate .proto from it.

The reason for that is that .proto is way more limited than what Pydantic gives you. For example,
there is no way to explain that an `email` field in a message must pass some kind of validation, besides writing 
a comment.

With grpez's approach, you can define the models, with as rich validation as you want,
and generate a proto file from it, that will include comments extracted from validators.

```python
import asyncio
import pathlib

import grpez
from hypercorn.asyncio import serve
from hypercorn import Config

hello_svc = grpez.Service("HelloService")


class HelloRequest(grpez.RequestModel):
    name: str


class HelloResponse(grpez.ResponseModel):
    greeting: str


@hello_svc.rpc()
async def get_greeting(hello: HelloRequest) -> HelloResponse:
    return HelloResponse(greeting=f"hello {hello.name}")


async def main():
    app = grpez.Grpez(
        services=[hello_svc], 
        reflection=True, 
        gen_path=pathlib.Path(__file__).parent / "grpez_gen"
    )
    await serve(app, Config())

asyncio.run(main())
```

When you run the server, it'll first generate proto files from your code, then generate
Python code using `protoc`, and finally hook it all together. It's possible to turn off generating
on startup, which should be the default for production environments.

If you want to stick to the "proto-first, code later" approach, that's still possible.


### Async-first

It would be possible to support both sync and async endpoints, but it's a lot of work.
Currently only async endpoints are supported.

### FastAPI-like Dependency Injection mechanism

It's somewhat limited at the moment, but you can define any callable that will be passed to your
endpoints at runtime

```python
import grpez
from typing import Annotated

svc = grpez.Service("Dependency")


class App:
    def __init__(self):
        self.counter = 0


async def get_app():
    return App()


class Message(grpez.RequestModel, grpez.ResponseModel):
    value: int


@svc.rpc()
async def foo(msg: Message, app: Annotated[App, grpez.D(get_app, scope="server")]) -> Message:
    app.counter += msg.value
    return Message(value=app.counter)


@svc.rpc()
async def bar(msg: Message, app: Annotated[App, grpez.D(get_app, scope="server")]) -> Message:
    app.counter += msg.value * 2
    return Message(value=app.counter)


@svc.rpc()
async def baz(msg: Message, app: Annotated[App, grpez.D(get_app)]) -> Message:
    app.counter += msg.value * 3
    return Message(value=app.counter)
```

In the example above, `foo` and `bar` will share the same `app` instance, and it will be created
at startup and once only. On the other hand, `baz` will get a fresh instance of `app` on every call.


### Natural streaming

You want your endpoint to return a unary response? Just return a pydantic model.
You want it to stream results? Just make it an async generator. You want it to receive a stream?
Make the stream an async generator.

```python
import grpez
from collections.abc import AsyncGenerator

streaming_svc = grpez.Service("StreamingExample")


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
    # example of streaming response (unary_stream)
    for i in range(r.min_value, r.max_value + 1):
        yield GetRangeResponse(value=i)


@streaming_svc.rpc()
async def sum_numbers(rs: AsyncGenerator[SumNumbersRequest, None]) -> SumNumbersResponse:
    # example of streaming request (stream_unary)
    total = 0
    async for r in rs:
        total += r.number

    return SumNumbersResponse(total=total)


@streaming_svc.rpc()
async def double_numbers(rs: AsyncGenerator[DoubleNumber, None]) -> AsyncGenerator[DoubleNumber, None]:
    # example of bidirectional streaming (stream_stream)
    async for r in rs:
        yield DoubleNumber(number=r.number * 2)
```


### Middlewares instead of interceptors

Interceptors don't have access to the request or response objects. grpez middlewares are
a thin wrapper around interceptors that gives you the full context.

TODO examples


### Interceptors are partially supported

Fully supporting interceptors is difficult as they can access the RPC handler, and
grpez uses a different implementation than plain gRPC. In general, you should prefer using
grpez middlewares instead of interceptors, but for the migration process, it's probably useful to be able
to just use what you already have.

Reading `handler_call_details` is fully supported (see [example](tests/test_examples/test_interceptor.py)), and
you don't need any changes to your interceptor to do it. If your interceptor changes the rpc_handler
used for the call, or accesses some properties of it, then it's currently not supported by the lib, so file an issue.


### Classic Servicer classes are also supported

If you have a servicer class that you want to include in grpez (for the migration period only, right?)
then you can do it exactly the same way, like you'd do it with a normal grpc server:

```python
app = grpez.Grpez(...)
add_YourServicer_to_server(servicer, app)
```

That way you gain ASGI support, and you can start the slow migration towards native-grpez.