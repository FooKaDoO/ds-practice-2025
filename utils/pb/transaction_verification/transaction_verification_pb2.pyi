from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class TransactionRequest(_message.Message):
    __slots__ = ("order_id",)
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    def __init__(self, order_id: _Optional[str] = ...) -> None: ...

class Item(_message.Message):
    __slots__ = ("name", "quantity")
    NAME_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    name: str
    quantity: int
    def __init__(self, name: _Optional[str] = ..., quantity: _Optional[int] = ...) -> None: ...

class TransactionResponse(_message.Message):
    __slots__ = ("valid", "reason")
    VALID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    valid: bool
    reason: str
    def __init__(self, valid: bool = ..., reason: _Optional[str] = ...) -> None: ...

class OrderData(_message.Message):
    __slots__ = ("items", "creditCardNumber", "expirationDate", "cvv")
    ITEMS_FIELD_NUMBER: _ClassVar[int]
    CREDITCARDNUMBER_FIELD_NUMBER: _ClassVar[int]
    EXPIRATIONDATE_FIELD_NUMBER: _ClassVar[int]
    CVV_FIELD_NUMBER: _ClassVar[int]
    items: _containers.RepeatedCompositeFieldContainer[Item]
    creditCardNumber: str
    expirationDate: str
    cvv: str
    def __init__(self, items: _Optional[_Iterable[_Union[Item, _Mapping]]] = ..., creditCardNumber: _Optional[str] = ..., expirationDate: _Optional[str] = ..., cvv: _Optional[str] = ...) -> None: ...

class InitOrderRequest(_message.Message):
    __slots__ = ("order_id", "order_data")
    ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    ORDER_DATA_FIELD_NUMBER: _ClassVar[int]
    order_id: str
    order_data: OrderData
    def __init__(self, order_id: _Optional[str] = ..., order_data: _Optional[_Union[OrderData, _Mapping]] = ...) -> None: ...

class InitOrderConfirmationResponse(_message.Message):
    __slots__ = ("isCreated",)
    ISCREATED_FIELD_NUMBER: _ClassVar[int]
    isCreated: bool
    def __init__(self, isCreated: bool = ...) -> None: ...
