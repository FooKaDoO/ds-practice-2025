# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: transaction_verification.proto
# Protobuf Python Version: 4.25.0
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1etransaction_verification.proto\x12\x0btransaction\"u\n\x12TransactionRequest\x12\x18\n\x10\x63reditCardNumber\x18\x01 \x01(\t\x12\x16\n\x0e\x65xpirationDate\x18\x02 \x01(\t\x12\x0b\n\x03\x63vv\x18\x03 \x01(\t\x12 \n\x05items\x18\x04 \x03(\x0b\x32\x11.transaction.Item\"@\n\x16InitializeOrderRequest\x12\x0f\n\x07orderId\x18\x01 \x01(\t\x12\x15\n\rorderDataJson\x18\x02 \x01(\t\";\n\x17InitializeOrderResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0f\n\x07message\x18\x02 \x01(\t\"&\n\x04Item\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x10\n\x08quantity\x18\x02 \x01(\x05\"4\n\x13TransactionResponse\x12\r\n\x05valid\x18\x01 \x01(\x08\x12\x0e\n\x06reason\x18\x02 \x01(\t\":\n\x12VerifyItemsRequest\x12\x0f\n\x07orderId\x18\x01 \x01(\t\x12\x13\n\x0bvectorClock\x18\x02 \x03(\x05\"L\n\x13VerifyItemsResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0e\n\x06reason\x18\x02 \x01(\t\x12\x14\n\x0cupdatedClock\x18\x03 \x03(\x05\"=\n\x15VerifyUserDataRequest\x12\x0f\n\x07orderId\x18\x01 \x01(\t\x12\x13\n\x0bvectorClock\x18\x02 \x03(\x05\"O\n\x16VerifyUserDataResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0e\n\x06reason\x18\x02 \x01(\t\x12\x14\n\x0cupdatedClock\x18\x03 \x03(\x05\"=\n\x15VerifyCardInfoRequest\x12\x0f\n\x07orderId\x18\x01 \x01(\t\x12\x13\n\x0bvectorClock\x18\x02 \x03(\x05\"O\n\x16VerifyCardInfoResponse\x12\x0f\n\x07success\x18\x01 \x01(\x08\x12\x0e\n\x06reason\x18\x02 \x01(\t\x12\x14\n\x0cupdatedClock\x18\x03 \x03(\x05\x32\xde\x03\n\x1eTransactionVerificationService\x12V\n\x11VerifyTransaction\x12\x1f.transaction.TransactionRequest\x1a .transaction.TransactionResponse\x12\\\n\x0fInitializeOrder\x12#.transaction.InitializeOrderRequest\x1a$.transaction.InitializeOrderResponse\x12P\n\x0bVerifyItems\x12\x1f.transaction.VerifyItemsRequest\x1a .transaction.VerifyItemsResponse\x12Y\n\x0eVerifyUserData\x12\".transaction.VerifyUserDataRequest\x1a#.transaction.VerifyUserDataResponse\x12Y\n\x0eVerifyCardInfo\x12\".transaction.VerifyCardInfoRequest\x1a#.transaction.VerifyCardInfoResponseb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'transaction_verification_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _globals['_TRANSACTIONREQUEST']._serialized_start=47
  _globals['_TRANSACTIONREQUEST']._serialized_end=164
  _globals['_INITIALIZEORDERREQUEST']._serialized_start=166
  _globals['_INITIALIZEORDERREQUEST']._serialized_end=230
  _globals['_INITIALIZEORDERRESPONSE']._serialized_start=232
  _globals['_INITIALIZEORDERRESPONSE']._serialized_end=291
  _globals['_ITEM']._serialized_start=293
  _globals['_ITEM']._serialized_end=331
  _globals['_TRANSACTIONRESPONSE']._serialized_start=333
  _globals['_TRANSACTIONRESPONSE']._serialized_end=385
  _globals['_VERIFYITEMSREQUEST']._serialized_start=387
  _globals['_VERIFYITEMSREQUEST']._serialized_end=445
  _globals['_VERIFYITEMSRESPONSE']._serialized_start=447
  _globals['_VERIFYITEMSRESPONSE']._serialized_end=523
  _globals['_VERIFYUSERDATAREQUEST']._serialized_start=525
  _globals['_VERIFYUSERDATAREQUEST']._serialized_end=586
  _globals['_VERIFYUSERDATARESPONSE']._serialized_start=588
  _globals['_VERIFYUSERDATARESPONSE']._serialized_end=667
  _globals['_VERIFYCARDINFOREQUEST']._serialized_start=669
  _globals['_VERIFYCARDINFOREQUEST']._serialized_end=730
  _globals['_VERIFYCARDINFORESPONSE']._serialized_start=732
  _globals['_VERIFYCARDINFORESPONSE']._serialized_end=811
  _globals['_TRANSACTIONVERIFICATIONSERVICE']._serialized_start=814
  _globals['_TRANSACTIONVERIFICATIONSERVICE']._serialized_end=1292
# @@protoc_insertion_point(module_scope)