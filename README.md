# grpez

gRPC in Python made EZ.

## Rationale

Python community puts a lot of effort to make developing REST APIs as good as
it currently is. If you get used to using FastAPI and Pydantic for your APIs, and then
suddenly decide that you want to use gRPC for whatever reason, that is going to be a disappointment.

The goal of `grpez` is to bring gRPC development in Python on similar modern level
as what you can get with REST.


## Features

The library is in a very early stage, so most of those features are in-progress at the moment.

The library has a lot of opinions, but one of its design rules is to not force any one of them on you.
If you dislike any of the features, there are ways to just use old-style grpc/proto approaches.

### Drive on top of ASGI

You can mix grpez with any other ASGI application and run them together. You can even mix it with FastAPI.

One caveat: gRPC needs HTTP/2 and currently hypercorn is the only ASGI implementation
that supports that.

TODO example

### Native integration with Pydantic

Classes generated from protobuf are terrible in all kinds of ways. They have
ambiguous `__repr__`, it's hard to see their internals, they don't play nicely with
types, it's impossible to add an extra parsing stage. With grpez, you just define a Pydantic
model that will be your interface when reading request contents. 

The generated proto class is still there, but you never need to see it (if you do for whatever reason,
there are ways).

TODO example


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

### Natural streaming

You want your endpoint to return a unary response? Just return a pydantic model.
You want it to stream results? Just make it an async generator. You want it to receive a stream?
Make the stream an async generator.

TODO examples


### Middlewares instead of interceptors

Interceptors don't have access to the request or response objects. grpez middlewares are
a thin wrapper around interceptors that gives you the full context.

TODO examples


### Classic Servicer classes are also supported

If you have a servicer class that you want to include in grpez (for the migration period only, right?)
then you can do it exactly the same way like you'd do it with classic server:

```python
app = grpez.Grpez(...)
add_YourServicer_to_server(servicer, app)
```