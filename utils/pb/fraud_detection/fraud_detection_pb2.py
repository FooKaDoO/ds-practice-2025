# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: fraud_detection.proto
# Protobuf Python Version: 4.25.0
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x15\x66raud_detection.proto\x12\x05\x66raud\"%\n\x11\x43heckOrderRequest\x12\x10\n\x08order_id\x18\x01 \x01(\t\"&\n\x04Item\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x10\n\x08quantity\x18\x02 \x01(\x05\"5\n\x12\x43heckOrderResponse\x12\x0f\n\x07isFraud\x18\x01 \x01(\x08\x12\x0e\n\x06reason\x18\x02 \x01(\t\"\'\n\tOrderData\x12\x1a\n\x05items\x18\x01 \x03(\x0b\x32\x0b.fraud.Item\"J\n\x10InitOrderRequest\x12\x10\n\x08order_id\x18\x01 \x01(\t\x12$\n\norder_data\x18\x02 \x01(\x0b\x32\x10.fraud.OrderData\"2\n\x1dInitOrderConfirmationResponse\x12\x11\n\tisCreated\x18\x01 \x01(\x08\x32\xa6\x01\n\x15\x46raudDetectionService\x12J\n\tInitOrder\x12\x17.fraud.InitOrderRequest\x1a$.fraud.InitOrderConfirmationResponse\x12\x41\n\nCheckOrder\x12\x18.fraud.CheckOrderRequest\x1a\x19.fraud.CheckOrderResponseb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'fraud_detection_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _globals['_CHECKORDERREQUEST']._serialized_start=32
  _globals['_CHECKORDERREQUEST']._serialized_end=69
  _globals['_ITEM']._serialized_start=71
  _globals['_ITEM']._serialized_end=109
  _globals['_CHECKORDERRESPONSE']._serialized_start=111
  _globals['_CHECKORDERRESPONSE']._serialized_end=164
  _globals['_ORDERDATA']._serialized_start=166
  _globals['_ORDERDATA']._serialized_end=205
  _globals['_INITORDERREQUEST']._serialized_start=207
  _globals['_INITORDERREQUEST']._serialized_end=281
  _globals['_INITORDERCONFIRMATIONRESPONSE']._serialized_start=283
  _globals['_INITORDERCONFIRMATIONRESPONSE']._serialized_end=333
  _globals['_FRAUDDETECTIONSERVICE']._serialized_start=336
  _globals['_FRAUDDETECTIONSERVICE']._serialized_end=502
# @@protoc_insertion_point(module_scope)
