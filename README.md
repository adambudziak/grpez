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

If you want to stick to the "proto-first, code later" approach, that's still possible.


TODO example


### Async-first

It would be possible to support both sync and async endpoints, but it's a lot of work.
Currently only async endpoints are supported.

TODO examples

### Natural streaming

You want your endpoint to return a unary response? Just return a pydantic model.
You want it to stream results? Just make it an async generator. You want it to receive a stream?
Make the stream an async generator.

TODO examples


### Middlewares instead of interceptors

Interceptors don't have access to the request or response objects. grpez middlewares are
a thin wrapper around interceptors that gives you the full context.

TODO examples