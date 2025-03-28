import sys
import os
import grpc
import threading
import uuid  # Import UUID for generating unique OrderIDs
import json
from flask import Flask, request, jsonify
from flask_cors import CORS

# Import the generated gRPC stubs for Fraud Detection
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
fraud_detection_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/fraud_detection'))
sys.path.insert(0, fraud_detection_grpc_path)
import fraud_detection_pb2 as fraud_detection
import fraud_detection_pb2_grpc as fraud_detection_grpc

# Import the generated gRPC stubs for Transaction Verification
transaction_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/transaction_verification'))
sys.path.insert(0, transaction_grpc_path)
import transaction_verification_pb2 as transaction_verification
import transaction_verification_pb2_grpc as transaction_verification_grpc

# Import the generated gRPC stubs for Suggestions
suggestions_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/suggestions'))
sys.path.insert(0, suggestions_grpc_path)
import suggestions_pb2 as suggestions
import suggestions_pb2_grpc as suggestions_grpc

log_tools_path = os.path.abspath(os.path.join(FILE, '../../../utils/log_tools'))
sys.path.insert(0, log_tools_path)
import log_tools

app = Flask(__name__)
CORS(app, resources={r'/*': {'origins': '*'}})

# --- New: Functions for Transaction Verification Events ---

@log_tools.log_decorator("Orchestrator")
def call_verify_items(order_id, current_clock, order_data, result_dict):
    """
    Event (a): Verify that the order items list is not empty.
    """
    with grpc.insecure_channel('transaction_verification:50052') as channel:
        stub = transaction_verification_grpc.TransactionVerificationServiceStub(channel)
        request_proto = transaction_verification.VerifyItemsRequest(
            orderId=order_id,
            vectorClock=current_clock
        )
        response = stub.VerifyItems(request_proto)
    log_tools.debug(f"[Orchestrator] VerifyItems updated clock: {response.updatedClock}")
    result_dict['verify_items'] = response.updatedClock

@log_tools.log_decorator("Orchestrator")
def call_verify_user_data(order_id, current_clock, order_data, result_dict):
    """
    Event (b): Verify that all mandatory user data is filled in.
    """
    with grpc.insecure_channel('transaction_verification:50052') as channel:
        stub = transaction_verification_grpc.TransactionVerificationServiceStub(channel)
        request_proto = transaction_verification.VerifyUserDataRequest(
            orderId=order_id,
            vectorClock=current_clock
        )
        response = stub.VerifyUserData(request_proto)
    log_tools.debug(f"[Orchestrator] VerifyUserData updated clock: {response.updatedClock}")
    result_dict['verify_user'] = response.updatedClock

@log_tools.log_decorator("Orchestrator")
def call_verify_card_info(order_id, current_clock, order_data, result_dict):
    """
    Event (c): Verify that the credit card information is in the correct format.
    """
    with grpc.insecure_channel('transaction_verification:50052') as channel:
        stub = transaction_verification_grpc.TransactionVerificationServiceStub(channel)
        request_proto = transaction_verification.VerifyCardInfoRequest(
            orderId=order_id,
            vectorClock=current_clock
        )
        response = stub.VerifyCardInfo(request_proto)
    log_tools.debug(f"[Orchestrator] VerifyCardInfo updated clock: {response.updatedClock}")
    result_dict['verify_card'] = response.updatedClock

# --- New: Functions for Fraud Detection Events ---

@log_tools.log_decorator("Orchestrator")
def call_check_user_fraud(order_id, current_clock, order_data, result_dict):
    """
    Event (d): Fraud detection checks the user data for fraud.
    """
    with grpc.insecure_channel('fraud_detection:50051') as channel:
        stub = fraud_detection_grpc.FraudDetectionServiceStub(channel)
        request_proto = fraud_detection.CheckFraudRequest(
            orderId=order_id,
            vectorClock=current_clock,
            orderDataJson=json.dumps(order_data)  # if needed
        )
        response = stub.CheckUserFraud(request_proto)
    log_tools.debug(f"[Orchestrator] CheckUserFraud updated clock: {response.updatedClock}")
    result_dict['check_user_fraud'] = response.updatedClock

@log_tools.log_decorator("Orchestrator")
def call_check_card_fraud(order_id, current_clock, order_data, result_dict):
    """
    Event (e): Fraud detection checks the credit card data for fraud.
    """
    with grpc.insecure_channel('fraud_detection:50051') as channel:
        stub = fraud_detection_grpc.FraudDetectionServiceStub(channel)
        request_proto = fraud_detection.CheckFraudRequest(
            orderId=order_id,
            vectorClock=current_clock,
            orderDataJson=json.dumps(order_data)
        )
        response = stub.CheckCardFraud(request_proto)
    log_tools.debug(f"[Orchestrator] CheckCardFraud updated clock: {response.updatedClock}")
    result_dict['check_card_fraud'] = response.updatedClock

# --- New: Function for Suggestions Event ---

@log_tools.log_decorator("Orchestrator")
def call_generate_suggestions(order_id, current_clock, order_data, result_dict):
    """
    Event (f): Generate book suggestions.
    """
    with grpc.insecure_channel('suggestions:50053') as channel:
        stub = suggestions_grpc.SuggestionsServiceStub(channel)
        request_proto = suggestions.GenerateSuggestionsRequest(
            orderId=order_id,
            vectorClock=current_clock
        )
        response = stub.GenerateSuggestions(request_proto)
    log_tools.debug(f"[Orchestrator] GenerateSuggestions updated clock: {response.updatedClock}")
    result_dict['generate_suggestions'] = {
        'clock': list(response.updatedClock),
        'books': [
            {"bookId": book.bookId, "title": book.title, "author": book.author}
            for book in response.books
        ]
    }

# --- Updated /checkout route to orchestrate the event flow ---
@app.route('/checkout', methods=['POST'])
def checkout():
    """
    Processes a checkout request:
      - Generates a unique OrderID.
      - Dispatches initialization calls to all backend services.
      - Executes events in partial order using vector clocks.
      - Aggregates responses and returns final status.
    """
    # Parse the JSON order data from the request
    request_data = json.loads(request.data)
    log_tools.debug(f"[Orchestrator] Request Data: {request_data.get('items')}")

    # Generate a unique OrderID
    order_id = str(uuid.uuid4())
    log_tools.info(f"[Orchestrator] Generated OrderID: {order_id}")

    # ----- Step 1: Initialization (already implemented) -----
    init_result = {}
    fraud_init_thread = threading.Thread(target=call_initialize_fraud, args=(order_id, request_data, init_result))
    tx_init_thread = threading.Thread(target=call_initialize_tx, args=(order_id, request_data, init_result))
    suggestions_init_thread = threading.Thread(target=call_initialize_suggestions, args=(order_id, request_data, init_result))
    log_tools.debug("[Orchestrator] Starting initialization threads.")
    fraud_init_thread.start()
    tx_init_thread.start()
    suggestions_init_thread.start()
    fraud_init_thread.join()
    tx_init_thread.join()
    suggestions_init_thread.join()
    log_tools.debug(f"[Orchestrator] Initialization results: {init_result}")

    # ----- Step 2: Execute Transaction Verification Events -----
    # Assume initial vector clock for events is the one from initialization: [0,0,0]
    initial_clock = [0, 0, 0]
    tx_result = {}
    # (a) Verify Items and (b) Verify User Data run in parallel:
    thread_a = threading.Thread(target=call_verify_items, args=(order_id, initial_clock, request_data, tx_result))
    thread_b = threading.Thread(target=call_verify_user_data, args=(order_id, initial_clock, request_data, tx_result))
    log_tools.debug("[Orchestrator] Starting Transaction events (a) and (b) in parallel.")
    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()
    # Merge the vector clocks from events (a) and (b) by taking element-wise max:
    merged_tx_clock = [max(tx_result['verify_items'][i], tx_result['verify_user'][i]) for i in range(3)]
    log_tools.debug(f"[Orchestrator] Merged clock after events (a) and (b): {merged_tx_clock}")
    # (c) Verify Card Info (depends on (a))
    tx_result2 = {}
    call_verify_card_info(order_id, merged_tx_clock, request_data, tx_result2)
    updated_tx_clock = tx_result2['verify_card']
    log_tools.debug(f"[Orchestrator] Updated clock after event (c): {updated_tx_clock}")

    # ----- Step 3: Execute Fraud Detection Events -----
    # Use the updated clock from Transaction events for Fraud events
    fraud_result = {}
    call_check_user_fraud(order_id, updated_tx_clock, request_data, fraud_result)
    clock_after_user_fraud = fraud_result['check_user_fraud']
    fraud_result2 = {}
    call_check_card_fraud(order_id, clock_after_user_fraud, request_data, fraud_result2)
    updated_fraud_clock = fraud_result2['check_card_fraud']
    log_tools.debug(f"[Orchestrator] Updated clock after Fraud events: {updated_fraud_clock}")

    # ----- Step 4: Execute Suggestions Event -----
    sug_result = {}
    call_generate_suggestions(order_id, updated_fraud_clock, request_data, sug_result)
    final_suggestions = sug_result['generate_suggestions']['books']
    final_clock = sug_result['generate_suggestions']['clock']
    log_tools.debug(f"[Orchestrator] Final vector clock from Suggestions: {final_clock}")

    # ----- Step 5: Decide Final Order Status -----
    # For simplicity, if all events complete, we approve the order.
    final_status = "Order Approved"

    response_json = {
        "orderId": order_id,
        "status": final_status,
        "suggestedBooks": final_suggestions,
        "finalVectorClock": final_clock
    }
    return jsonify(response_json)

if __name__ == '__main__':
    log_tools.info("[Orchestrator] Starting...")
    app.run(host='0.0.0.0')
    log_tools.info("[Orchestrator] Stopped.")
