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

cached_orders = {}      # e.g., { orderId: orderDataJson }
vector_clocks = {}      # e.g., { orderId: [0, 0, 0] }  (for 3 microservices)


class TransactionVerificationServiceServicer(tx_pb2_grpc.TransactionVerificationServiceServicer):
    """
    Implements the TransactionVerificationService gRPC methods.
    """
    @log_tools.log_decorator("Transaction Verification")
    def InitializeOrder(self, request, context):
        """
        Caches the order data and initializes a vector clock for this order.
        """
        order_id = request.orderId
        order_data = request.orderDataJson

        # Cache the order data (you might parse it later as needed)
        cached_orders[order_id] = order_data
        
        # Initialize the vector clock for this order.
        # Here we use 3 slots (one for each microservice: Transaction, Fraud, Suggestions)
        vector_clocks[order_id] = [0, 0, 0]
        
        log_tools.debug(f"[Transaction Verification] InitializeOrder: orderId={order_id}, vectorClock={vector_clocks[order_id]}")
        
        response = tx_pb2.InitializeOrderResponse(success=True, message=f"Order {order_id} initialized.")
        return response

    @log_tools.log_decorator("Transaction Verification")
    def VerifyItems(self, request, context):
        """
        Event (a): Verify that the order items list is not empty.
        """
        order_id = request.orderId
        incoming_clock = list(request.vectorClock) if request.vectorClock else [0, 0, 0]
        local_clock = vector_clocks.get(order_id, [0, 0, 0])
        # Merge incoming clock with local (element-wise max)
        merged_clock = [max(incoming_clock[i], local_clock[i]) for i in range(3)]
        # Increment Transaction Verification's slot (index 0)
        merged_clock[0] += 1
        vector_clocks[order_id] = merged_clock
        log_tools.debug(f"[Transaction Verification] VerifyItems for order {order_id}: updated vector clock: {merged_clock}")
        
        # Dummy logic: if there are no items, return failure.
        # (In a real scenario, you'd check the cached order data.)
        if not cached_orders.get(order_id):  # or check actual items if passed in request
            success = False
            reason = "No order data found."
        else:
            success = True
            reason = "Order items verified."
        
        response = tx_pb2.VerifyItemsResponse(success=success, reason=reason)
        response.updatedClock.extend(merged_clock)
        return response

    @log_tools.log_decorator("Transaction Verification")
    def VerifyUserData(self, request, context):
        """
        Event (b): Verify that all mandatory user data (name, contact, address, etc.) is filled in.
        """
        order_id = request.orderId
        incoming_clock = list(request.vectorClock) if request.vectorClock else [0, 0, 0]
        local_clock = vector_clocks.get(order_id, [0, 0, 0])
        merged_clock = [max(incoming_clock[i], local_clock[i]) for i in range(3)]
        # Increment Tx's slot (index 0)
        merged_clock[0] += 1
        vector_clocks[order_id] = merged_clock
        log_tools.debug(f"[Transaction Verification] VerifyUserData for order {order_id}: updated vector clock: {merged_clock}")
        
        # Dummy logic: assume user data is always filled for demonstration.
        success = True
        reason = "Mandatory user data verified."
        
        response = tx_pb2.VerifyUserDataResponse(success=success, reason=reason)
        response.updatedClock.extend(merged_clock)
        return response

    @log_tools.log_decorator("Transaction Verification")
    def VerifyCardInfo(self, request, context):
        """
        Event (c): Verify that the credit card information is in the correct format.
        """
        order_id = request.orderId
        incoming_clock = list(request.vectorClock) if request.vectorClock else [0, 0, 0]
        local_clock = vector_clocks.get(order_id, [0, 0, 0])
        merged_clock = [max(incoming_clock[i], local_clock[i]) for i in range(3)]
        # Increment Tx's slot (index 0)
        merged_clock[0] += 1
        vector_clocks[order_id] = merged_clock
        log_tools.debug(f"[Transaction Verification] VerifyCardInfo for order {order_id}: updated vector clock: {merged_clock}")
        
        # Dummy logic: check that credit card info is not empty (simple check)
        # In a real scenario, you might use regex or a Luhn algorithm.
        # Here we assume the order data is cached and contains credit card info,
        # but for demonstration we'll simply mark it as valid.
        success = True
        reason = "Credit card info verified."
        
        response = tx_pb2.VerifyCardInfoResponse(success=success, reason=reason)
        response.updatedClock.extend(merged_clock)
        return response
    
    @log_tools.log_decorator("Transaction Verification")
    def VerifyTransaction(self, request, context):
        """
        Validate the transaction based on simple logic.
        - If creditCardNumber is empty, invalid transaction.
        - If there are no items in the order, invalid transaction.
        """

        response = tx_pb2.TransactionResponse()

        card_number = request.creditCardNumber or ""

        if len(request.items) == 0:
            response.valid = False
            response.reason = "Empty cart"
            return response

        for item in request.items:
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
