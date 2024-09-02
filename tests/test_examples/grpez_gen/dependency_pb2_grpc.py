# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc
import warnings

from . import dependency_pb2 as dependency__pb2

GRPC_GENERATED_VERSION = '1.66.1'
GRPC_VERSION = grpc.__version__
_version_not_supported = False

try:
    from grpc._utilities import first_version_is_lower
    _version_not_supported = first_version_is_lower(GRPC_VERSION, GRPC_GENERATED_VERSION)
except ImportError:
    _version_not_supported = True

if _version_not_supported:
    raise RuntimeError(
        f'The grpc package installed is at version {GRPC_VERSION},'
        + f' but the generated code in dependency_pb2_grpc.py depends on'
        + f' grpcio>={GRPC_GENERATED_VERSION}.'
        + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}'
        + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.'
    )


class DependencyStub(object):
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Foo = channel.unary_unary(
                '/Dependency/Foo',
                request_serializer=dependency__pb2.Message.SerializeToString,
                response_deserializer=dependency__pb2.Message.FromString,
                _registered_method=True)
        self.Bar = channel.unary_unary(
                '/Dependency/Bar',
                request_serializer=dependency__pb2.Message.SerializeToString,
                response_deserializer=dependency__pb2.Message.FromString,
                _registered_method=True)
        self.Baz = channel.unary_unary(
                '/Dependency/Baz',
                request_serializer=dependency__pb2.Message.SerializeToString,
                response_deserializer=dependency__pb2.Message.FromString,
                _registered_method=True)


class DependencyServicer(object):
    """Missing associated documentation comment in .proto file."""

    def Foo(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Bar(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Baz(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_DependencyServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'Foo': grpc.unary_unary_rpc_method_handler(
                    servicer.Foo,
                    request_deserializer=dependency__pb2.Message.FromString,
                    response_serializer=dependency__pb2.Message.SerializeToString,
            ),
            'Bar': grpc.unary_unary_rpc_method_handler(
                    servicer.Bar,
                    request_deserializer=dependency__pb2.Message.FromString,
                    response_serializer=dependency__pb2.Message.SerializeToString,
            ),
            'Baz': grpc.unary_unary_rpc_method_handler(
                    servicer.Baz,
                    request_deserializer=dependency__pb2.Message.FromString,
                    response_serializer=dependency__pb2.Message.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'Dependency', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('Dependency', rpc_method_handlers)


 # This class is part of an EXPERIMENTAL API.
class Dependency(object):
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def Foo(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/Dependency/Foo',
            dependency__pb2.Message.SerializeToString,
            dependency__pb2.Message.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def Bar(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/Dependency/Bar',
            dependency__pb2.Message.SerializeToString,
            dependency__pb2.Message.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def Baz(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/Dependency/Baz',
            dependency__pb2.Message.SerializeToString,
            dependency__pb2.Message.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)
