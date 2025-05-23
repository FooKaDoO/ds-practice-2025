# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc

import books_pb2 as books__pb2


class BooksDatabaseStub(object):
    """gRPC service for a replicated book-stock database
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.Read = channel.unary_unary(
                '/books.BooksDatabase/Read',
                request_serializer=books__pb2.ReadRequest.SerializeToString,
                response_deserializer=books__pb2.ReadResponse.FromString,
                )
        self.Write = channel.unary_unary(
                '/books.BooksDatabase/Write',
                request_serializer=books__pb2.WriteRequest.SerializeToString,
                response_deserializer=books__pb2.WriteResponse.FromString,
                )
        self.DecrementStock = channel.unary_unary(
                '/books.BooksDatabase/DecrementStock',
                request_serializer=books__pb2.DecrementRequest.SerializeToString,
                response_deserializer=books__pb2.WriteResponse.FromString,
                )
        self.PrepareDecrement = channel.unary_unary(
                '/books.BooksDatabase/PrepareDecrement',
                request_serializer=books__pb2.DecrementRequest.SerializeToString,
                response_deserializer=books__pb2.WriteResponse.FromString,
                )
        self.CommitDecrement = channel.unary_unary(
                '/books.BooksDatabase/CommitDecrement',
                request_serializer=books__pb2.CommitRequest.SerializeToString,
                response_deserializer=books__pb2.WriteResponse.FromString,
                )
        self.AbortDecrement = channel.unary_unary(
                '/books.BooksDatabase/AbortDecrement',
                request_serializer=books__pb2.CommitRequest.SerializeToString,
                response_deserializer=books__pb2.WriteResponse.FromString,
                )


class BooksDatabaseServicer(object):
    """gRPC service for a replicated book-stock database
    """

    def Read(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def Write(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def DecrementStock(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def PrepareDecrement(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def CommitDecrement(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def AbortDecrement(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_BooksDatabaseServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'Read': grpc.unary_unary_rpc_method_handler(
                    servicer.Read,
                    request_deserializer=books__pb2.ReadRequest.FromString,
                    response_serializer=books__pb2.ReadResponse.SerializeToString,
            ),
            'Write': grpc.unary_unary_rpc_method_handler(
                    servicer.Write,
                    request_deserializer=books__pb2.WriteRequest.FromString,
                    response_serializer=books__pb2.WriteResponse.SerializeToString,
            ),
            'DecrementStock': grpc.unary_unary_rpc_method_handler(
                    servicer.DecrementStock,
                    request_deserializer=books__pb2.DecrementRequest.FromString,
                    response_serializer=books__pb2.WriteResponse.SerializeToString,
            ),
            'PrepareDecrement': grpc.unary_unary_rpc_method_handler(
                    servicer.PrepareDecrement,
                    request_deserializer=books__pb2.DecrementRequest.FromString,
                    response_serializer=books__pb2.WriteResponse.SerializeToString,
            ),
            'CommitDecrement': grpc.unary_unary_rpc_method_handler(
                    servicer.CommitDecrement,
                    request_deserializer=books__pb2.CommitRequest.FromString,
                    response_serializer=books__pb2.WriteResponse.SerializeToString,
            ),
            'AbortDecrement': grpc.unary_unary_rpc_method_handler(
                    servicer.AbortDecrement,
                    request_deserializer=books__pb2.CommitRequest.FromString,
                    response_serializer=books__pb2.WriteResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'books.BooksDatabase', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))


 # This class is part of an EXPERIMENTAL API.
class BooksDatabase(object):
    """gRPC service for a replicated book-stock database
    """

    @staticmethod
    def Read(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/books.BooksDatabase/Read',
            books__pb2.ReadRequest.SerializeToString,
            books__pb2.ReadResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def Write(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/books.BooksDatabase/Write',
            books__pb2.WriteRequest.SerializeToString,
            books__pb2.WriteResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def DecrementStock(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/books.BooksDatabase/DecrementStock',
            books__pb2.DecrementRequest.SerializeToString,
            books__pb2.WriteResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def PrepareDecrement(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/books.BooksDatabase/PrepareDecrement',
            books__pb2.DecrementRequest.SerializeToString,
            books__pb2.WriteResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def CommitDecrement(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/books.BooksDatabase/CommitDecrement',
            books__pb2.CommitRequest.SerializeToString,
            books__pb2.WriteResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)

    @staticmethod
    def AbortDecrement(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(request, target, '/books.BooksDatabase/AbortDecrement',
            books__pb2.CommitRequest.SerializeToString,
            books__pb2.WriteResponse.FromString,
            options, channel_credentials,
            insecure, call_credentials, compression, wait_for_ready, timeout, metadata)
