import sys
import os
import grpc
from concurrent import futures

# Import the generated gRPC stubs
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
transaction_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/transaction_verification'))
sys.path.insert(0, transaction_grpc_path)

import transaction_verification_pb2 as tx_pb2
import transaction_verification_pb2_grpc as tx_pb2_grpc

log_tools_path = os.path.abspath(os.path.join(FILE, '../../../utils/log_tools'))
sys.path.insert(0, log_tools_path)
import log_tools

microservice_path = os.path.abspath(os.path.join(FILE, '../../../utils/microservice'))
sys.path.insert(0, microservice_path)
from microservice import MicroService

class TransactionVerificationServiceServicer(tx_pb2_grpc.TransactionVerificationServiceServicer, MicroService):

    @log_tools.log_decorator("Transaction Verification")
    def InitOrder(self, request, context):
        response = tx_pb2.InitOrderConfirmationResponse()

        self.init_order(request.order_id, request.order_data)

        response.isCreated = True
        return response
    

    """
    Implements the TransactionVerificationService gRPC methods.
    """
    @log_tools.log_decorator("Transaction Verification")
    def VerifyTransaction(self, request, context):
        """
        Validate the transaction based on simple logic.
        - If creditCardNumber is empty, invalid transaction.
        - If there are no items in the order, invalid transaction.
        """

        response = tx_pb2.TransactionResponse()

        order_id = request.order_id

        entry = self.orders[order_id]

        card_number = entry["order_data"].creditCardNumber or ""

        if len(entry["order_data"].items) == 0:
            response.valid = False
            response.reason = "Empty cart"
            return response

        for item in entry["order_data"].items:
            if item.quantity <= 0:
                response.valid = False
                response.reason = f"Invalid item quantity: {item.quantity} for {item.name}"
                return response

        if not card_number or len(card_number) < 13:
            response.valid = False
            response.reason = "Invalid credit card number"
            log_tools.debug(f"[Transaction Verification] VerifyTransaction called. valid={response.valid}, reason={response.reason}")
            return response
        

        # If all checks pass
        response.valid = True
        response.reason = "Transaction is valid."
        log_tools.debug(f"[Transaction Verification] VerifyTransaction called. valid={response.valid}, reason={response.reason}")
        return response

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    tx_pb2_grpc.add_TransactionVerificationServiceServicer_to_server(
        TransactionVerificationServiceServicer(), server
    )

    port = "50052"
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    log_tools.info(f"[Transaction Verification] Listening on port {port}...")
    server.wait_for_termination()

if __name__ == '__main__':
    log_tools.info("[Transaction Verification] Starting...")
    serve()
    log_tools.info("[Transaction Verification] Stopped.")
