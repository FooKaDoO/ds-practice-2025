import sys
import os
import grpc
from concurrent import futures

# Import the generated gRPC stubs
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
suggestions_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/suggestions'))
sys.path.insert(0, suggestions_grpc_path)

import suggestions_pb2 as sug_pb2
import suggestions_pb2_grpc as sug_pb2_grpc

log_tools_path = os.path.abspath(os.path.join(FILE, '../../../utils/log_tools'))
sys.path.insert(0, log_tools_path)
import log_tools

class SuggestionsServiceServicer(sug_pb2_grpc.SuggestionsServiceServicer):
    """
    Implements the SuggestionsService gRPC methods.
    """

    @log_tools.log_decorator("Suggestions Service")
    def GetBookSuggestions(self, request, context):
        """
        Suggest books based on the items in the order.
        """

        # Dummy book database
        book_recommendations = {
            "Book A": [
                {"bookId": "101", "title": "The Sequel to Book A", "author": "Author A"},
                {"bookId": "102", "title": "A Similar Book", "author": "Author X"}
            ],
            "Book B": [
                {"bookId": "201", "title": "Another Great Read", "author": "Author B"},
                {"bookId": "202", "title": "Something You'll Love", "author": "Author Y"}
            ]
        }

        suggested_books = []
        log_tools.debug("[Suggestions Service] Iterating over book_recommendations.")
        for item in request.items:
            if item.name in book_recommendations:
                suggested_books.extend(book_recommendations[item.name])

        # Create response
        log_tools.debug("[Suggestions Service] Creating response.")
        response = sug_pb2.SuggestionsResponse()
        for book in suggested_books:
            book_proto = response.books.add()
            book_proto.bookId = book["bookId"]
            book_proto.title = book["title"]
            book_proto.author = book["author"]

        log_tools.debug(f"[Suggestions Service] Suggested {len(suggested_books)} books.")
        return response

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    sug_pb2_grpc.add_SuggestionsServiceServicer_to_server(
        SuggestionsServiceServicer(), server
    )

    port = "50053"
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    log_tools.info(f"[Suggestions Service] Listening on port {port}...")
    server.wait_for_termination()

if __name__ == '__main__':
    log_tools.info("[Suggestions Service] Starting...")
    serve()
    log_tools.info("[Suggestions Service] Stopped.")
