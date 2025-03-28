import sys
import os
import grpc
from concurrent import futures
import cohere

# Import the generated gRPC stubs
FILE = __file__ if "__file__" in globals() else os.getenv("PYTHONFILE", "")
suggestions_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/suggestions'))
sys.path.insert(0, suggestions_grpc_path)

import suggestions_pb2 as sug_pb2
import suggestions_pb2_grpc as sug_pb2_grpc

co = cohere.Client(os.getenv("COHERE_API_KEY"))

log_tools_path = os.path.abspath(os.path.join(FILE, '../../../utils/log_tools'))
sys.path.insert(0, log_tools_path)
import log_tools

microservice_path = os.path.abspath(os.path.join(FILE, '../../../utils/microservice'))
sys.path.insert(0, microservice_path)
from microservice import MicroService


class SuggestionsServiceServicer(sug_pb2_grpc.SuggestionsServiceServicer, MicroService):
    """
    Implements the SuggestionsService gRPC methods.
    """

    @log_tools.log_decorator("Suggestions Service")
    def InitOrder(self, request, context):
        response = sug_pb2.InitOrderConfirmationResponse()

        self.init_order(request.order_id, request.order_data)

        response.isCreated = True
        return response

    @log_tools.log_decorator("Suggestions Service")
    def GetBookSuggestions(self, request, context):
        
        order_id = request.order_id

        entry = self.orders[order_id]

        # Build a list of ordered items
        items_ordered = [f"{i.name} (x{i.quantity})" for i in entry["order_data"].items]

        # Updated prompt: force EXACTLY 3 lines
        prompt = (
            f"User ordered these books: {', '.join(items_ordered)}.\n"
            "Suggest EXACTLY 3 new similar books, each on its own line.\n"
            "Example:\n"
            "Book 1\n"
            "Book 2\n"
            "Book 3\n"
        )

        log_tools.debug("[Suggestions Service] Generating suggestions using Cohere.")
        try:
            response = co.generate(
                model='command-r-plus',  # or whichever model you have access to
                prompt=prompt,
                max_tokens=100,
                temperature=1.0,
                k=0,
                p=0.75
            )

            suggestions_text = response.generations[0].text.strip()
            log_tools.debug(f"[Suggestions Service] Cohere suggestions:\n{suggestions_text}")

            # Split by lines, ignoring empty ones
            lines = [line.strip() for line in suggestions_text.splitlines() if line.strip()]
            
            # Build the gRPC response
            response_proto = sug_pb2.SuggestionsResponse()

            # Only take up to 3 lines
            for idx, line in enumerate(lines[:3], start=1):
                book_proto = response_proto.books.add()
                book_proto.bookId = f"Cohere-{idx}"
                book_proto.title = line[:50]  # Truncate if too long
                book_proto.author = "Cohere AI"

            log_tools.debug(f"[Suggestions Service] Returning {len(response_proto.books)} suggestions.")
            return response_proto

        except Exception as e:
            log_tools.error(f"[Suggestions Service] Cohere API error: {e}")
            return sug_pb2.SuggestionsResponse()
                
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    sug_pb2_grpc.add_SuggestionsServiceServicer_to_server(
        SuggestionsServiceServicer(), server
    )

    port = "50053"
    server.add_insecure_port(f"[::]:" + port)
    server.start()
    log_tools.info(f"[Suggestions Service] Listening on port {port}...")
    server.wait_for_termination()

if __name__ == '__main__':
    log_tools.info("[Suggestions Service] Starting...")
    serve()
    log_tools.info("[Suggestions Service] Stopped.")
