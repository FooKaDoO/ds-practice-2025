import sys
import os
import grpc
from concurrent import futures
import cohere


# Import the generated gRPC stubs
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
suggestions_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/suggestions'))
sys.path.insert(0, suggestions_grpc_path)

import suggestions_pb2 as sug_pb2
import suggestions_pb2_grpc as sug_pb2_grpc

co = cohere.Client(os.getenv("COHERE_API_KEY"))

log_tools_path = os.path.abspath(os.path.join(FILE, '../../../utils/log_tools'))
sys.path.insert(0, log_tools_path)
import log_tools

class SuggestionsServiceServicer(sug_pb2_grpc.SuggestionsServiceServicer):
    """
    Implements the SuggestionsService gRPC methods.
    """

    @log_tools.log_decorator("Suggestions Service")
    def GetBookSuggestions(self, request, context):
        items_ordered = [f"{i.name} (x{i.quantity})" for i in request.items]
        prompt = f"User ordered these books: {', '.join(items_ordered)}. Suggest 3 new similar books in separate lines."

        
        log_tools.debug("[Suggestions Service] Generating suggestions using Cohere.")
        try:
            response = co.generate(
                model='command-r-plus',
                prompt=prompt,
                max_tokens=100,
                temperature=1.0,
                k=0,
                p=0.75
            )

            # The returned text
            suggestions_text = response.generations[0].text.strip()
            log_tools.debug(f"[Suggestions Service] Cohere suggestions: {suggestions_text}")

            # Convert the text to a structured list of Book objects
            # For a quick hack, we'll just split lines
            lines = suggestions_text.split('\n')
            response_proto = sug_pb2.SuggestionsResponse()
            for idx, line in enumerate(lines[:3], start=1):
                if line.strip():
                    book_proto = response_proto.books.add()
                    book_proto.bookId = f"Cohere-{idx}"
                    book_proto.title = line.strip()[:50]
                    book_proto.author = "Cohere AI"
            
            log_tools.debug(f"[Suggestions Service] Returning {len(response_proto.books)} suggestions.")
            return response_proto

        except Exception as e:
            log_tools.error(f"[Suggestions Service] Cohore error API error: {e}")
            return sug_pb2.SuggestionsResponse()
                
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
