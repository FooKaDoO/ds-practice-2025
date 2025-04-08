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

# Create a Cohere client (for GetBookSuggestions, if still needed)
co = cohere.Client(os.getenv("COHERE_API_KEY"))

log_tools_path = os.path.abspath(os.path.join(FILE, '../../../utils/log_tools'))
sys.path.insert(0, log_tools_path)
import log_tools

# Global caches for orders and vector clocks
cached_orders = {}  # { orderId: orderDataJson }
vector_clocks = {}  # { orderId: [0, 0, 0] } (for [Tx, Fraud, Suggestions])

class SuggestionsServiceServicer(sug_pb2_grpc.SuggestionsServiceServicer):
    """
    Implements the SuggestionsService gRPC methods.
    """
    @log_tools.log_decorator("Suggestions")
    def InitializeOrder(self, request, context):
        """
        Caches the order data and initializes a vector clock for this order.
        """
        order_id = request.orderId
        order_data = request.orderDataJson

        # Cache the order data
        cached_orders[order_id] = order_data

        # Initialize the vector clock: 3 slots for [Transaction, Fraud, Suggestions]
        vector_clocks[order_id] = [0, 0, 0]
        log_tools.debug(f"[Suggestions] InitializeOrder: orderId={order_id}, vectorClock={vector_clocks[order_id]}")

        response = sug_pb2.InitializeOrderResponse(success=True, message=f"Order {order_id} initialized.")
        return response

    @log_tools.log_decorator("Suggestions Service")
    def GetBookSuggestions(self, request, context):
        """
        Existing method for generating suggestions using Cohere.
        (May still be used for non-event-ordered flows.)
        """
        items_ordered = [f"{i.name} (x{i.quantity})" for i in request.items]
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
                model="command-r-plus-08-2024",
                prompt=prompt,
                max_tokens=100,
                temperature=1.0,
                k=0,
                p=0.75
            )

            suggestions_text = response.generations[0].text.strip()
            log_tools.debug(f"[Suggestions Service] Cohere suggestions:\n{suggestions_text}")

            lines = [line.strip() for line in suggestions_text.splitlines() if line.strip()]
            response_proto = sug_pb2.SuggestionsResponse()
            for idx, line in enumerate(lines[:3], start=1):
                book_proto = response_proto.books.add()
                book_proto.bookId = f"Cohere-{idx}"
                book_proto.title = line[:50]
                book_proto.author = "Cohere AI"
            
            log_tools.debug(f"[Suggestions Service] Returning {len(response_proto.books)} suggestions.")
            return response_proto

        except Exception as e:
            log_tools.error(f"[Suggestions Service] Cohere API error: {e}")
            return sug_pb2.SuggestionsResponse()


    @log_tools.log_decorator("Suggestions Service")
    def GenerateSuggestions(self, request, context):
        """
        Event (f): Generate book suggestions with vector clock updates.
        This method:
        - Receives the orderId and an incoming vector clock.
        - Merges the incoming clock with the locally stored vector clock for this order.
        - Increments the Suggestions slot (index 2).
        - Calls the Cohere API to generate book suggestions based on the order details.
        - Returns the updated vector clock along with the suggestions.
        """
        order_id = request.orderId
        incoming_clock = list(request.vectorClock) if request.vectorClock else [0, 0, 0]
        local_clock = vector_clocks.get(order_id, [0, 0, 0])
        
        # Merge the clocks (element-wise max)
        merged_clock = [max(incoming_clock[i], local_clock[i]) for i in range(3)]
        # Increment Suggestions' slot (index 2)
        merged_clock[2] += 1
        vector_clocks[order_id] = merged_clock  # update local vector clock
        
        log_tools.debug(f"[Suggestions Service] GenerateSuggestions for order {order_id}: updated vector clock: {merged_clock}")
        
        # Build a prompt using the cached order data (if available)
        # Here, we assume that during initialization, orderDataJson was stored.
        order_data = cached_orders.get(order_id, "")
        # For example, if order_data contains items, we can extract item names:
        try:
            order_json = json.loads(order_data)
            items_ordered = [f"{i['name']} (x{i['quantity']})" for i in order_json.get("items", [])]
        except Exception:
            items_ordered = []
        
        prompt = (
            f"User ordered these books: {', '.join(items_ordered)}.\n"
            "Suggest EXACTLY 3 new similar books, each on its own line."
        )
        
        try:
            # Call the Cohere API to generate suggestions
            co_response = co.generate(
                model='command-r-plus',  # Use a valid model accessible to you
                prompt=prompt,
                max_tokens=100,
                temperature=1.0,
                k=0,
                p=0.75
            )
            
            suggestions_text = co_response.generations[0].text.strip()
            log_tools.debug(f"[Suggestions Service] Cohere suggestions:\n{suggestions_text}")
            
            # Split by lines, ignoring empty ones
            lines = [line.strip() for line in suggestions_text.splitlines() if line.strip()]
            
            response_proto = sug_pb2.GenerateSuggestionsResponse()
            response_proto.success = True
            response_proto.reason = "Suggestions generated successfully."
            response_proto.updatedClock.extend(merged_clock)
            
            # Create a Book entry for each suggestion line (taking up to 3 suggestions)
            for idx, line in enumerate(lines[:3], start=1):
                book_proto = response_proto.books.add()
                book_proto.bookId = f"Cohere-{idx}"
                book_proto.title = line[:50]  # Ensure it's not too long
                book_proto.author = "Cohere AI"
            
            log_tools.debug(f"[Suggestions Service] Returning {len(response_proto.books)} suggestions for order {order_id}.")
            return response_proto

        except Exception as e:
            log_tools.error(f"[Suggestions Service] Cohere API error: {e}")
            # Return a failure response with the updated clock
            response_proto = sug_pb2.GenerateSuggestionsResponse()
            response_proto.success = False
            response_proto.reason = str(e)
            response_proto.updatedClock.extend(merged_clock)
            return response_proto

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    sug_pb2_grpc.add_SuggestionsServiceServicer_to_server(
        SuggestionsServiceServicer(), server
    )
    port = "50053"
    server.add_insecure_port(f"[::]:{port}")
    log_tools.info(f"[Suggestions Service] Listening on port {port}...")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    log_tools.info("[Suggestions Service] Starting...")
    serve()
    log_tools.info("[Suggestions Service] Stopped.")
