import grpc

import sys
import os
import threading


FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
fraud_detection_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/fraud_detection'))

sys.path.insert(0, fraud_detection_grpc_path)

import fraud_detection_pb2 as fraud_detection
import fraud_detection_pb2_grpc as fraud_detection_grpc


transaction_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/transaction_verification'))
sys.path.insert(0, transaction_grpc_path)
import transaction_verification_pb2 as transaction_verification
import transaction_verification_pb2_grpc as transaction_verification_grpc


suggestions_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/suggestions'))
sys.path.insert(0, suggestions_grpc_path)

import suggestions_pb2 as suggestions
import suggestions_pb2_grpc as suggestions_grpc

log_tools_path = os.path.abspath(os.path.join(FILE, '../../../utils/log_tools'))
sys.path.insert(0, log_tools_path)
import log_tools

# Import Flask.
# Flask is a web framework for Python.
# It allows you to build a web application quickly.
# For more information, see https://flask.palletsprojects.com/en/latest/
from flask import Flask, request
from flask_cors import CORS
import json

# Create a simple Flask app.
app = Flask(__name__)
# Enable CORS for the app.
CORS(app, resources={r'/*': {'origins': '*'}})

# Define a GET endpoint.
@app.route('/', methods=['GET'])
def index():
    """
    Responds with 'Hello, [name]' when a GET request is made to '/' endpoint.
    """
    # Test the fraud-detection gRPC service.
    response = log_tools.info("yo")
    # Return the response.
    return response


@log_tools.log_decorator("Orchestrator")
def calculate_order_total(items):
    # For a real scenario, you'd sum up item.price * item.quantity or similar
    # Here, just do something dummy:
    total = 0
    for item in items:
        quantity = item.get('quantity', 1)
        total += 10 * quantity
    return total

@log_tools.log_decorator("Orchestrator")
def call_fraud_detection(order_data, result_dict):
    total_amount = calculate_order_total(order_data.get('items', []))

    with grpc.insecure_channel('fraud_detection:50051') as channel:
        stub = fraud_detection_grpc.FraudDetectionServiceStub(channel)

        # Prepare the request
        request_proto = fraud_detection.CheckOrderRequest(
            totalAmount=total_amount,
            items=[
                fraud_detection.Item(name=i["name"], quantity=i["quantity"]) 
                for i in order_data.get('items', [])
            ]
        )

        response = stub.CheckOrder(request_proto)

    log_tools.debug(f"[Orchestrator] Fraud detection response: isFraud={response.isFraud}, reason={response.reason}")
    result_dict['isFraud'] = response.isFraud
    result_dict['fraudReason'] = response.reason

@log_tools.log_decorator("Orchestrator")
def call_transaction_verification(order_data, result_dict):
    """
    Calls the Transaction Verification microservice and updates result_dict.
    """
    with grpc.insecure_channel('transaction_verification:50052') as channel:
        stub = transaction_verification_grpc.TransactionVerificationServiceStub(channel)

        request_proto = transaction_verification.TransactionRequest(
            creditCardNumber=order_data.get('creditCard', {}).get('number', ""),
            expirationDate=order_data.get('creditCard', {}).get('expirationDate', ""),
            cvv=order_data.get('creditCard', {}).get('cvv', ""),
            items=[transaction_verification.Item(name=item["name"], quantity=item["quantity"]) for item in order_data.get('items', [])]
        )

        response = stub.VerifyTransaction(request_proto)

    log_tools.debug(f"[Orchestrator] Transaction verification response: valid={response.valid}, reason={response.reason}")
    result_dict['transaction_ok'] = response.valid
    result_dict['transaction_reason'] = response.reason

@log_tools.log_decorator("Orchestrator")
def call_suggestions(order_data, result_dict):
    """
    Calls the Suggestions microservice and updates result_dict.
    """
    with grpc.insecure_channel('suggestions:50053') as channel:
        stub = suggestions_grpc.SuggestionsServiceStub(channel)

        request_proto = suggestions.SuggestionsRequest(
            items=[suggestions.Item(name=item["name"], quantity=item["quantity"]) for item in order_data.get('items', [])]
        )

        response = stub.GetBookSuggestions(request_proto)

    log_tools.debug(f"[Orchestrator] Suggestions received: {len(response.books)} books.")
    result_dict['suggested_books'] = [
        {"bookId": book.bookId, "title": book.title, "author": book.author} for book in response.books
    ]

@app.route('/checkout', methods=['POST'])
def checkout():
    """
    Responds with a JSON object containing the order ID, status, and suggested books.
    """
    # Get request object data to json
    request_data = json.loads(request.data)
    # Print request object data
    log_tools.debug(f"[Orchestrator] Request Data: {request_data.get('items')}")

    # We'll store partial results here
    result_dict = {}
    
    log_tools.debug("[Orchestrator] Creating threads.")
    fraud_thread = threading.Thread(target=call_fraud_detection, args=(request_data, result_dict))
    transaction_thread = threading.Thread(target=call_transaction_verification, args=(request_data, result_dict))
    suggestions_thread = threading.Thread(target=call_suggestions, args=(request_data, result_dict))


    log_tools.debug("[Orchestrator] Starting all threads.")
    fraud_thread.start()
    transaction_thread.start()
    suggestions_thread.start()
    log_tools.debug("[Orchestrator] All threads started.")

    log_tools.debug("[Orchestrator] Waiting for all threads to complete.")
    fraud_thread.join()
    transaction_thread.join()
    suggestions_thread.join()
    log_tools.debug("[Orchestrator] All threads completed.")

    log_tools.debug("[Orchestrator] Deciding if order is approved or not.")

    if not result_dict.get('transaction_ok'):
        # Transaction verification failed
        reason = result_dict.get('transaction_reason', "Transaction verification failed")
        final_status = f"Order Rejected. {reason}"
        suggested_books = []
    elif result_dict.get('isFraud'):
        # Fraud detection failed
        reason = result_dict.get('fraudReason', "Fraud detected")
        final_status = f"Order Rejected. {reason}"
        suggested_books = []
    else:
        # Both checks passed
        final_status = 'Order Approved'
        suggested_books = result_dict.get('suggested_books', [])

    log_tools.debug(f"[Orchestrator] {final_status}")
    if suggested_books:
        log_tools.debug(f"[Orchestrator] Suggested books: {suggested_books}")


    # Build the final JSON response
    # matching bookstore.yaml -> OrderStatusResponse
    order_status_response = {
        'orderId': '12345',
        'status': final_status,
        'suggestedBooks': suggested_books
    }

    return order_status_response


if __name__ == '__main__':
    # Run the app in debug mode to enable hot reloading.
    # This is useful for development.
    # The default port is 5000.
    log_tools.info("[Orchestrator] Starting...")
    app.run(host='0.0.0.0')
    log_tools.info("[Orchestrator] Stopped.")