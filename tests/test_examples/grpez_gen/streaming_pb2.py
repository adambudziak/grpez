# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: streaming.proto
# Protobuf Python Version: 5.27.2
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    27,
    2,
    '',
    'streaming.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0fstreaming.proto\"!\n\x10GetRangeResponse\x12\r\n\x05value\x18\x01 \x01(\x03\"\x1e\n\x0c\x44oubleNumber\x12\x0e\n\x06number\x18\x01 \x01(\x03\"#\n\x11SumNumbersRequest\x12\x0e\n\x06number\x18\x01 \x01(\x03\"#\n\x12SumNumbersResponse\x12\r\n\x05total\x18\x01 \x01(\x03\"7\n\x0fGetRangeRequest\x12\x11\n\tmin_value\x18\x01 \x01(\x03\x12\x11\n\tmax_value\x18\x02 \x01(\x03\x32\xb0\x01\n\tStreaming\x12\x33\n\x08GetRange\x12\x10.GetRangeRequest\x1a\x11.GetRangeResponse\"\x00\x30\x01\x12\x39\n\nSumNumbers\x12\x12.SumNumbersRequest\x1a\x13.SumNumbersResponse\"\x00(\x01\x12\x33\n\rDoubleNumbers\x12\r.DoubleNumber\x1a\r.DoubleNumber\"\x00(\x01\x30\x01\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'streaming_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_GETRANGERESPONSE']._serialized_start=19
  _globals['_GETRANGERESPONSE']._serialized_end=52
  _globals['_DOUBLENUMBER']._serialized_start=54
  _globals['_DOUBLENUMBER']._serialized_end=84
  _globals['_SUMNUMBERSREQUEST']._serialized_start=86
  _globals['_SUMNUMBERSREQUEST']._serialized_end=121
  _globals['_SUMNUMBERSRESPONSE']._serialized_start=123
  _globals['_SUMNUMBERSRESPONSE']._serialized_end=158
  _globals['_GETRANGEREQUEST']._serialized_start=160
  _globals['_GETRANGEREQUEST']._serialized_end=215
  _globals['_STREAMING']._serialized_start=218
  _globals['_STREAMING']._serialized_end=394
# @@protoc_insertion_point(module_scope)
