import grpc

import sys
import os
import threading
import uuid


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

microservice_path = os.path.abspath(os.path.join(FILE, '../../../utils/microservice'))
sys.path.insert(0, microservice_path)
from microservice import MicroService

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
def call_initialize_fraud(order_id, order_data):
    with grpc.insecure_channel('fraud_detection:50051') as channel:
        stub = fraud_detection_grpc.FraudDetectionServiceStub(channel)

        # Prepare the request
        request_proto = fraud_detection.InitOrderRequest(
            order_id=order_id,
            order_data=fraud_detection.OrderData(
                items=[
                    fraud_detection.Item(name=i["name"], quantity=i["quantity"]) 
                    for i in order_data.get('items', [])
                ]
            )
        )

        response = stub.InitOrder(request_proto)

    log_tools.debug(f"[Orchestrator] Fraud detection response: isCreated={response.isCreated}")

@log_tools.log_decorator("Orchestrator")
def call_initialize_tx(order_id, order_data):
    with grpc.insecure_channel('transaction_verification:50052') as channel:
        stub = transaction_verification_grpc.TransactionVerificationServiceStub(channel)

        request_proto = transaction_verification.InitOrderRequest(
            order_id=order_id,
            order_data=transaction_verification.OrderData(
                items=[
                    transaction_verification.Item(name=item["name"], quantity=item["quantity"]) 
                    for item in order_data.get('items', [])
                ],
                creditCardNumber=order_data.get('creditCard', {}).get('number', ""),
                expirationDate=order_data.get('creditCard', {}).get('expirationDate', ""),
                cvv=order_data.get('creditCard', {}).get('cvv', "")
            )
        )

        response = stub.InitOrder(request_proto)

    log_tools.debug(f"[Orchestrator] Transaction verification response: isCreated={response.isCreated}")

@log_tools.log_decorator("Orchestrator")
def call_initialize_suggestions(order_id, order_data):
    with grpc.insecure_channel('suggestions:50053') as channel:
        stub = suggestions_grpc.SuggestionsServiceStub(channel)

        request_proto = suggestions.InitOrderRequest(
            order_id=order_id,
            order_data=suggestions.OrderData(
                items=[
                    suggestions.Item(name=item["name"], quantity=item["quantity"]) 
                    for item in order_data.get('items', [])
                ]
            )
        )

        response = stub.InitOrder(request_proto)

    log_tools.debug(f"[Orchestrator] Suggestions response: isCreated={response.isCreated}")

@log_tools.log_decorator("Orchestrator")
def call_fraud_detection(order_id: str, incoming_vc: list[int], result_dict: dict):
    with grpc.insecure_channel('fraud_detection:50051') as channel:
        stub = fraud_detection_grpc.FraudDetectionServiceStub(channel)

        # Prepare the request
        request_proto = fraud_detection.CheckOrderRequest(
            order_id=order_id,
            vc=incoming_vc
        )

        response = stub.CheckOrder(request_proto)

    log_tools.debug(f"[Orchestrator] Fraud detection response: isFraud={response.isFraud}, reason={response.reason}")
    result_dict['isFraud'] = response.isFraud
    result_dict['fraudReason'] = response.reason
    result_dict['fraud_vc'] = response.vc

@log_tools.log_decorator("Orchestrator")
def call_verify_cart(order_id: str, incoming_vc: list[int], result_dict: dict):
    """
    Calls the Transaction Verification microservice and updates result_dict.
    """
    with grpc.insecure_channel('transaction_verification:50052') as channel:
        stub = transaction_verification_grpc.TransactionVerificationServiceStub(channel)

        request_proto = transaction_verification.TransactionRequest(
            order_id=order_id,
            vc=incoming_vc
        )

        response = stub.VerifyCart(request_proto)

    log_tools.debug(f"[Orchestrator] Transaction verification response: valid={response.valid}, reason={response.reason}")
    result_dict['cart_ok'] = response.valid
    result_dict['cart_reason'] = response.reason
    result_dict['cart_vc'] = response.vc

@log_tools.log_decorator("Orchestrator")
def call_verify_item_quantities(order_id: str, incoming_vc: list[int], result_dict: dict):
    """
    Calls the Transaction Verification microservice and updates result_dict.
    """
    with grpc.insecure_channel('transaction_verification:50052') as channel:
        stub = transaction_verification_grpc.TransactionVerificationServiceStub(channel)

        request_proto = transaction_verification.TransactionRequest(
            order_id=order_id,
            vc=incoming_vc
        )

        response = stub.VerifyItemQuantities(request_proto)

    log_tools.debug(f"[Orchestrator] Transaction verification response: valid={response.valid}, reason={response.reason}")
    result_dict['item_quantities_ok'] = response.valid
    result_dict['item_quantities_reason'] = response.reason
    result_dict['item_quantities_vc'] = response.vc

@log_tools.log_decorator("Orchestrator")
def call_verify_item_names(order_id: str, incoming_vc: list[int], result_dict: dict):
    """
    Calls the Transaction Verification microservice and updates result_dict.
    """
    with grpc.insecure_channel('transaction_verification:50052') as channel:
        stub = transaction_verification_grpc.TransactionVerificationServiceStub(channel)

        request_proto = transaction_verification.TransactionRequest(
            order_id=order_id,
            vc=incoming_vc
        )

        response = stub.VerifyItemNames(request_proto)

    log_tools.debug(f"[Orchestrator] Transaction verification response: valid={response.valid}, reason={response.reason}")
    result_dict['item_names_ok'] = response.valid
    result_dict['item_names_reason'] = response.reason
    result_dict['item_names_vc'] = response.vc

@log_tools.log_decorator("Orchestrator")
def call_verify_user_data(order_id: str, incoming_vc: list[int], result_dict: dict):
    """
    Calls the Transaction Verification microservice and updates result_dict.
    """
    with grpc.insecure_channel('transaction_verification:50052') as channel:
        stub = transaction_verification_grpc.TransactionVerificationServiceStub(channel)

        request_proto = transaction_verification.TransactionRequest(
            order_id=order_id,
            vc=incoming_vc
        )

        response = stub.VerifyUserData(request_proto)

    log_tools.debug(f"[Orchestrator] Transaction verification response: valid={response.valid}, reason={response.reason}")
    result_dict['user_data_ok'] = response.valid
    result_dict['user_data_reason'] = response.reason
    result_dict['user_data_vc'] = response.vc

@log_tools.log_decorator("Orchestrator")
def call_suggestions(order_id: str, incoming_vc: list[int], result_dict: dict):
    """
    Calls the Suggestions microservice and updates result_dict.
    """
    with grpc.insecure_channel('suggestions:50053') as channel:
        stub = suggestions_grpc.SuggestionsServiceStub(channel)

        request_proto = suggestions.SuggestionsRequest(
            order_id=order_id,
            vc=incoming_vc
        )

        response = stub.GetBookSuggestions(request_proto)

    log_tools.debug(f"[Orchestrator] Suggestions received: {len(response.books)} books.")
    result_dict['suggested_books'] = [
        {"bookId": book.bookId, "title": book.title, "author": book.author} for book in response.books
    ]
    result_dict['suggestions_vc'] = response.vc

@app.route('/checkout', methods=['POST'])
def checkout():
    """
    Responds with a JSON object containing the order ID, status, and suggested books.
    """
    # Get request object data to json
    request_data = json.loads(request.data)
    # Print request object data
    log_tools.debug(f"[Orchestrator] Request Data: {request_data.get('items')}")

    order_id = str(uuid.uuid4())

    log_tools.debug(f"[Orchestrator] Created Order, OrderID: {order_id}")
    # ----- Step 1: Initialization -----
    fraud_init_thread = threading.Thread(target=call_initialize_fraud, args=(order_id, request_data))
    tx_init_thread = threading.Thread(target=call_initialize_tx, args=(order_id, request_data))
    suggestions_init_thread = threading.Thread(target=call_initialize_suggestions, args=(order_id, request_data))

    log_tools.debug("[Orchestrator] Starting initialization threads.")
    fraud_init_thread.start()
    tx_init_thread.start()
    suggestions_init_thread.start()

    fraud_init_thread.join()
    tx_init_thread.join()
    suggestions_init_thread.join()
    log_tools.debug(f"[Orchestrator] Initialized order {order_id} in all services.")

    
    current_clock = MicroService._static_microservice_index * [0]

    # ----- Step 2: Execute Concurrent Events -----
    # Verify cart || verify user data

    # Verify cart < verify item quantities
    # Verify cart < verify item names

    # Verify item quantities || item names

    # Fraud detection > verify item quantities
    # Fraud detection > verify item names

    # Suggestions > verify item quantities
    # Suggestions > verify item names

    # Fraud detection || suggestions


    # We'll store partial results here
    result_dict = {}
    log_tools.debug("[Orchestrator] Creating threads.")
    cart_thread = threading.Thread(target=call_verify_cart, args=(order_id, current_clock[::], result_dict))
    user_data_thread = threading.Thread(target=call_verify_user_data, args=(order_id, current_clock[::], result_dict))

    log_tools.debug("[Orchestrator] Starting cart and user data verification threads.")
    cart_thread.start()
    user_data_thread.start()
    log_tools.debug("[Orchestrator] Threads started.")
    log_tools.debug("[Orchestrator] Waiting for cart and user data verification threads to complete.")

    cart_thread.join()
    user_data_thread.join()
    log_tools.debug("[Orchestrator] Cart and user data verification completed.")

    if not result_dict.get('cart_ok'):
        # Cart verification failed
        reason = result_dict.get('cart_reason', "Cart verification failed")
        return {
            'orderId': order_id,
            'status': f"Order Rejected. {reason}",
            'suggestedBooks': []
        }
    elif not result_dict.get('user_data_ok'):
        # User data verification failed
        reason = result_dict.get('user_data_reason', "User data verification failed")
        return {
            'orderId': order_id,
            'status': f"Order Rejected. {reason}",
            'suggestedBooks': []
        }

    for i, cur, cart, user in zip(range(MicroService._static_microservice_index), current_clock, result_dict.get('cart_vc'), result_dict.get('user_data_vc')):
        current_clock[i] = max(cur, cart, user)
    

    # Verify quantites and names
    quantity_thread = threading.Thread(target=call_verify_item_quantities, args=(order_id, current_clock[::], result_dict))
    name_thread = threading.Thread(target=call_verify_item_names, args=(order_id, current_clock[::], result_dict))
    
    log_tools.debug("[Orchestrator] Starting item quantities and item names verification threads.")
    quantity_thread.start()
    name_thread.start()

    log_tools.debug("[Orchestrator] Item quantities and item names verification threads started.")
    quantity_thread.join()
    name_thread.join()
    log_tools.debug("[Orchestator] Item quantities and item names verification completed.")

    if not result_dict.get('item_quantities_ok'):
        # Item quantities verification failed
        reason = result_dict.get('item_quantities_reason', "Item quantities verification failed")
        return {
            'orderId': order_id,
            'status': f"Order Rejected. {reason}",
            'suggestedBooks': []
        }
    elif not result_dict.get('item_names_ok'):
        # Item names verification failed
        reason = result_dict.get('item_names_reason', "Item names verification failed")
        return {
            'orderId': order_id,
            'status': f"Order Rejected. {reason}",
            'suggestedBooks': []
        }
    
    for i, cur, quantity, name in zip(range(MicroService._static_microservice_index), current_clock, result_dict.get('item_quantities_vc'), result_dict.get('item_names_vc')):
        current_clock[i] = max(cur, quantity, name)
    
    fraud_thread = threading.Thread(target=call_fraud_detection, args=(order_id, current_clock[::], result_dict))
    suggestions_thread = threading.Thread(target=call_suggestions, args=(order_id, current_clock[::], result_dict))

    log_tools.debug("[Orchestrator] Starting fraud detection and suggestions threads.")
    fraud_thread.start()
    suggestions_thread.start()
    log_tools.debug("[Orchestrator] Fraud detection and suggestions threads started.")

    log_tools.debug("[Orchestrator] Waiting for fraud detection and suggestions threads to complete.")
    fraud_thread.join()
    suggestions_thread.join()
    log_tools.debug("[Orchestrator] Fraud detection and suggestions threads completed.")

    if result_dict.get('isFraud'):
        # Fraud detection failed
        reason = result_dict.get('fraudReason', "Fraud detected")
        return {
            'orderId': order_id,
            'status': f"Order Rejected. {reason}",
            'suggestedBooks': []
        }
    
    final_status = 'Order Approved'
    suggested_books = result_dict.get('suggested_books', [])

    log_tools.debug(f"[Orchestrator] {final_status}")
    if suggested_books:
        log_tools.debug(f"[Orchestrator] Suggested books: {suggested_books}")


    # Build the final JSON response
    # matching bookstore.yaml -> OrderStatusResponse
    order_status_response = {
        'orderId': order_id,
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