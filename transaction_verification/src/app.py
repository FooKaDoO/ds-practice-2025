import sys
import os
import grpc
import json
import re
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
        Uses cached order data instead of request.items.
        """
        order_id = request.orderId
        # Use the incoming vector clock if present; otherwise start with [0,0,0]
        incoming_clock = list(request.vectorClock) if hasattr(request, 'vectorClock') and request.vectorClock else [0, 0, 0]
        local_clock = vector_clocks.get(order_id, [0, 0, 0])
        merged_clock = [max(incoming_clock[i], local_clock[i]) for i in range(3)]
        # Increment the Transaction Verification slot (index 0)
        merged_clock[0] += 1
        vector_clocks[order_id] = merged_clock
        log_tools.debug(f"[Transaction Verification] VerifyItems for order {order_id}: updated vector clock: {merged_clock}")

        # Instead of checking request.items, retrieve order data from cached_orders.
        order_data_json = cached_orders.get(order_id)
        if not order_data_json:
            success = False
            reason = "No order data found in cache."
        else:
            try:
                order_data = json.loads(order_data_json)
                items = order_data.get("items", [])
                if not items or len(items) == 0:
                    success = False
                    reason = "Order items list is empty."
                else:
                    success = True
                    reason = "Order items verified."
            except Exception as e:
                success = False
                reason = f"Error parsing order data: {e}"
        
        response = tx_pb2.VerifyItemsResponse(success=success, reason=reason)
        response.updatedClock.extend(merged_clock)
        return response


    @log_tools.log_decorator("Transaction Verification")
    def VerifyUserData(self, request, context):
        """
        Event (b): Verify that all mandatory user data (name, contact, and billing address fields) is filled in.
        """
        order_id = request.orderId
        incoming_clock = list(request.vectorClock) if request.vectorClock else [0, 0, 0]
        local_clock = vector_clocks.get(order_id, [0, 0, 0])
        merged_clock = [max(incoming_clock[i], local_clock[i]) for i in range(3)]
        merged_clock[0] += 1  # Increment Transaction Verification slot (index 0)
        vector_clocks[order_id] = merged_clock
        log_tools.debug(f"[Transaction Verification] VerifyUserData for order {order_id}: updated vector clock: {merged_clock}")

        # Retrieve cached order data (JSON) to check user and billing information.
        order_data_json = cached_orders.get(order_id)
        if not order_data_json:
            success = False
            reason = "Order data not found in cache."
        else:
            try:
                order_data = json.loads(order_data_json)
                user = order_data.get("user", {})
                billing = order_data.get("billingAddress", {})
                # Mandatory user fields
                mandatory_user_fields = ["name", "contact"]
                # Mandatory billing fields
                mandatory_billing_fields = ["street", "city", "state", "zip", "country"]
                missing_fields = [field for field in mandatory_user_fields if not user.get(field)]
                missing_billing = [field for field in mandatory_billing_fields if not billing.get(field)]
                if missing_fields or missing_billing:
                    success = False
                    reason = "Missing mandatory data: " + ", ".join(missing_fields + missing_billing)
                else:
                    success = True
                    reason = "Mandatory user and billing data verified."
            except Exception as e:
                success = False
                reason = f"Error parsing order data: {e}"

        response = tx_pb2.VerifyUserDataResponse(success=success, reason=reason)
        response.updatedClock.extend(merged_clock)
        return response

    @log_tools.log_decorator("Transaction Verification")
    def VerifyCardInfo(self, request, context):
        """
        Event (c): Verify that the credit card information is in the correct format.
        This version uses simple if/else checks instead of regular expressions.
        """
        order_id = request.orderId
        incoming_clock = list(request.vectorClock) if hasattr(request, 'vectorClock') and request.vectorClock else [0, 0, 0]
        local_clock = vector_clocks.get(order_id, [0, 0, 0])
        # Merge the incoming and local vector clocks element-wise.
        merged_clock = [max(incoming_clock[i], local_clock[i]) for i in range(3)]
        # Increment the Transaction Verification slot (index 0)
        merged_clock[0] += 1
        vector_clocks[order_id] = merged_clock
        log_tools.debug(f"[Transaction Verification] VerifyCardInfo for order {order_id}: updated vector clock: {merged_clock}")

        # Retrieve the credit card information from the cached order data.
        order_data_json = cached_orders.get(order_id)
        if not order_data_json:
            success = False
            reason = "Order data not found in cache."
            log_tools.error(f"[Transaction Verification] VerifyCardInfo failed for order {order_id}: {reason}")
        else:
            try:
                order_data = json.loads(order_data_json)
                credit_card = order_data.get("creditCard", {})
                card_number = credit_card.get("number", "").strip()
                expiration = credit_card.get("expirationDate", "").strip()
                cvv = credit_card.get("cvv", "").strip()

                # Validate card number: only digits, length 13 to 19.
                if not card_number.isdigit() or not (13 <= len(card_number) <= 19):
                    success = False
                    reason = "Invalid credit card number format."
                else:
                    # Validate expiration date: should be in "MM/YY" or "MM/YYYY" format.
                    parts = expiration.split("/")
                    if len(parts) != 2:
                        success = False
                        reason = "Expiration date must be in MM/YY or MM/YYYY format."
                    else:
                        month_str, year_str = parts[0].strip(), parts[1].strip()
                        if not month_str.isdigit():
                            success = False
                            reason = "Expiration month is not numeric."
                        else:
                            month = int(month_str)
                            if month < 1 or month > 12:
                                success = False
                                reason = "Expiration month is out of range (1-12)."
                            else:
                                if not year_str.isdigit():
                                    success = False
                                    reason = "Expiration year is not numeric."
                                elif len(year_str) not in [2, 4]:
                                    success = False
                                    reason = "Expiration year must be 2 or 4 digits."
                                else:
                                    # Validate CVV: only digits, length 3 or 4.
                                    if not cvv.isdigit() or len(cvv) not in [3, 4]:
                                        success = False
                                        reason = "Invalid CVV format."
                                    else:
                                        success = True
                                        reason = "Credit card information verified."
            except Exception as e:
                success = False
                reason = f"Error parsing credit card data: {e}"

            print(success, reason)

        # Log error if verification failed.

        if not success:
            log_tools.error(f"[Transaction Verification] VerifyCardInfo for order {order_id} failed: {reason}")
        else:
            log_tools.info(f"[Transaction Verification] VerifyCardInfo for order {order_id} succeeded.")

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
