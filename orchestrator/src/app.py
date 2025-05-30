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

# Import the generated gRPC stubs for Order Queue
order_queue_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/order_queue'))
sys.path.insert(0, order_queue_grpc_path)
import order_queue_pb2 as oq_pb2
import order_queue_pb2_grpc as oq_pb2_grpc

# Import the logging utility
log_tools_path = os.path.abspath(os.path.join(FILE, '../../../utils/log_tools'))
sys.path.insert(0, log_tools_path)
import log_tools

app = Flask(__name__)
CORS(app, resources={r'/*': {'origins': '*'}})

# Import the generated gRPC stubs for Books Database
books_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/books'))
sys.path.insert(0, books_grpc_path)
import books_pb2
import books_pb2_grpc

# and create the channel & stub using the same env var you already set
_db_channel = grpc.insecure_channel(
    os.getenv('BOOKS_DB_PRIMARY', 'books_0:50070')
)
_db_stub = books_pb2_grpc.BooksDatabaseStub(_db_channel)


# Grafana
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

# Service name is required for most backends
resource = Resource.create(attributes={
    SERVICE_NAME: "orchestrator"
})

tracerProvider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="http://observability:4318/v1/traces"))
tracerProvider.add_span_processor(processor)
trace.set_tracer_provider(tracerProvider)

reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint="http://observability:4318/v1/metrics")
)
meterProvider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(meterProvider)

# --------------------------
# RPC Helper Functions
# --------------------------

# orchestrator/src/app.py
@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200

@log_tools.log_decorator("Orchestrator")
def call_verify_items(order_id, current_clock, order_data, result_dict):
    """
    Event (a): Verify that the order items list is not empty.
    Uses cached order data instead of request.items.
    """
    with grpc.insecure_channel('transaction_verification:50052') as channel:
        stub = transaction_verification_grpc.TransactionVerificationServiceStub(channel)
        request_proto = transaction_verification.VerifyItemsRequest(
            orderId=order_id,
            vectorClock=current_clock
        )
        response = stub.VerifyItems(request_proto)
    log_tools.debug(f"[Orchestrator] VerifyItems updated clock: {response.updatedClock} | Success: {response.success} | Reason: {response.reason}")
    result_dict['verify_items'] = list(response.updatedClock)
    result_dict['verify_items_success'] = response.success
    result_dict['verify_items_reason'] = response.reason

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
    log_tools.debug(f"[Orchestrator] VerifyUserData updated clock: {response.updatedClock} | Success: {response.success} | Reason: {response.reason}")
    result_dict['verify_user'] = list(response.updatedClock)
    result_dict['verify_user_success'] = response.success
    result_dict['verify_user_reason'] = response.reason

@log_tools.log_decorator("Orchestrator")
def call_verify_card_info(order_id, current_clock, order_data, result_dict):
    """
    Event (c): Verify that the credit card information is in the correct format.
    Connects to the Transaction Verification service and stores both the updated vector clock,
    the success flag, and the error reason (if any).
    """
    with grpc.insecure_channel('transaction_verification:50052') as channel:
        stub = transaction_verification_grpc.TransactionVerificationServiceStub(channel)
        request_proto = transaction_verification.VerifyCardInfoRequest(
            orderId=order_id,
            vectorClock=current_clock
        )
        response = stub.VerifyCardInfo(request_proto)
    log_tools.debug(f"[Orchestrator] VerifyCardInfo updated clock: {response.updatedClock} | Success: {response.success} | Reason: {response.reason}")
    result_dict['verify_card'] = list(response.updatedClock)
    result_dict['verify_card_success'] = response.success
    result_dict['verify_card_reason'] = response.reason

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
            orderDataJson=json.dumps(order_data)
        )
        response = stub.CheckUserFraud(request_proto)
    log_tools.debug(f"[Orchestrator] CheckUserFraud updated clock: {response.updatedClock} | Success: {response.success} | Reason: {response.reason}")
    result_dict['check_user_fraud'] = list(response.updatedClock)
    result_dict['check_user_fraud_success'] = response.success
    result_dict['check_user_fraud_reason'] = response.reason

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
    log_tools.debug(f"[Orchestrator] CheckCardFraud updated clock: {response.updatedClock} | Success: {response.success} | Reason: {response.reason}")
    result_dict['check_card_fraud'] = list(response.updatedClock)
    result_dict['check_card_fraud_success'] = response.success
    result_dict['check_card_fraud_reason'] = response.reason

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
    log_tools.debug(f"[Orchestrator] GenerateSuggestions updated clock: {response.updatedClock} | Success: {response.success} | Reason: {getattr(response, 'reason', 'No reason provided')}")
    result_dict['generate_suggestions'] = {
        'clock': list(response.updatedClock),
        'books': [
            {"bookId": book.bookId, "title": book.title, "author": book.author}
            for book in response.books
        ]
    }
    result_dict['generate_suggestions_success'] = response.success
    result_dict['generate_suggestions_reason'] = getattr(response, 'reason', '')

@log_tools.log_decorator("Orchestrator")
def call_initialize_fraud(order_id, order_data, result_dict):
    with grpc.insecure_channel('fraud_detection:50051') as channel:
        stub = fraud_detection_grpc.FraudDetectionServiceStub(channel)
        init_request = fraud_detection.InitializeOrderRequest(
            orderId=order_id,
            orderDataJson=json.dumps(order_data)
        )
        response = stub.InitializeOrder(init_request)
    log_tools.debug(f"[Orchestrator] Fraud Init: {response.message}")
    result_dict['fraud_init'] = response.success

@log_tools.log_decorator("Orchestrator")
def call_initialize_tx(order_id, order_data, result_dict):
    with grpc.insecure_channel('transaction_verification:50052') as channel:
        stub = transaction_verification_grpc.TransactionVerificationServiceStub(channel)
        init_request = transaction_verification.InitializeOrderRequest(
            orderId=order_id,
            orderDataJson=json.dumps(order_data)
        )
        response = stub.InitializeOrder(init_request)
    log_tools.debug(f"[Orchestrator] Transaction Verification Init: {response.message}")
    result_dict['tx_init'] = response.success

@log_tools.log_decorator("Orchestrator")
def call_initialize_suggestions(order_id, order_data, result_dict):
    with grpc.insecure_channel('suggestions:50053') as channel:
        stub = suggestions_grpc.SuggestionsServiceStub(channel)
        init_request = suggestions.InitializeOrderRequest(
            orderId=order_id,
            orderDataJson=json.dumps(order_data)
        )
        response = stub.InitializeOrder(init_request)
    log_tools.debug(f"[Orchestrator] Suggestions Init: {response.message}")
    result_dict['suggestions_init'] = response.success

@log_tools.log_decorator("Orchestrator")
def call_enqueue_order(order_id, order_data, result_dict):
    """
    Calls the Enqueue RPC on the order queue service.
    """
    with grpc.insecure_channel('order_queue:50055') as channel:
        stub = oq_pb2_grpc.OrderQueueServiceStub(channel)
        req = oq_pb2.EnqueueRequest(
            orderId=order_id,
            orderData=json.dumps(order_data)
        )
        response = stub.Enqueue(req)
        log_tools.debug(f"[Orchestrator] Enqueue result: {response.message}")
        result_dict['enqueue'] = response.success
        result_dict['enqueue_msg'] = response.message

# --------------------------
# /checkout Route Implementation
# --------------------------

KNOWN_TITLES = [
    "Harry Potter",
    "Twilight",
    "Lord of the Rings",
    "Clean Code"
]

@app.route('/api/books', methods=['GET'])
def list_books():
    catalog = []
    for title in KNOWN_TITLES:
        try:
            resp = _db_stub.Read(books_pb2.ReadRequest(title=title))
            catalog.append({"title": title, "stock": resp.stock})
        except Exception as e:
            # if the DB is unavailable, just show stock=0
            catalog.append({"title": title, "stock": 0})
    return jsonify(catalog)

@app.route('/checkout', methods=['POST'])
def checkout():
    """
    Processes a checkout request:
      - Generates a unique OrderID.
      - Dispatches initialization calls to all backend services.
      - Executes events in partial order using vector clocks.
      - Aggregates responses and returns final status.
      - Always returns "suggestedBooks" and "message" fields.
    """
    # Parse the JSON order data from the request
    request_data = json.loads(request.data)
    log_tools.debug(f"[Orchestrator] Request Data: {json.dumps(request_data.get('items'), indent=2)}")
    
    # Generate a unique OrderID
    order_id = str(uuid.uuid4())
    log_tools.info(f"[Orchestrator] Generated OrderID: {order_id}")
    
    # ----- Step 1: Initialization -----
    init_result = {}
    threads_init = [
        threading.Thread(target=call_initialize_fraud, args=(order_id, request_data, init_result)),
        threading.Thread(target=call_initialize_tx, args=(order_id, request_data, init_result)),
        threading.Thread(target=call_initialize_suggestions, args=(order_id, request_data, init_result))
    ]
    log_tools.debug("[Orchestrator] Starting initialization threads.")
    for t in threads_init:
        t.start()
    for t in threads_init:
        t.join()
    log_tools.debug(f"[Orchestrator] Initialization results: {init_result}")
    
    # ----- Step 2: Execute Transaction Verification Events -----
    initial_clock = [0, 0, 0]
    tx_result = {}
    # (a) Verify Items and (b) Verify User Data in parallel:
    thread_a = threading.Thread(target=call_verify_items, args=(order_id, initial_clock, request_data, tx_result))
    thread_b = threading.Thread(target=call_verify_user_data, args=(order_id, initial_clock, request_data, tx_result))
    log_tools.debug("[Orchestrator] Starting Transaction events (a) and (b) in parallel.")
    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()
    
    # Error checking for Items and User Data
    if not tx_result.get('verify_items_success', True):
        final_status = "Order Rejected. " + tx_result.get('verify_items_reason', "Items verification failed.")
        return jsonify({
            "orderId": order_id,
            "status": final_status,
            "suggestedBooks": [],
            
            "error": {"message": final_status}   # Error object for frontend
        }), 400
    if not tx_result.get('verify_user_success', True):
        final_status = "Order Rejected. " + tx_result.get('verify_user_reason', "User data verification failed.")
        return jsonify({
            "orderId": order_id,
            "status": final_status,
            "suggestedBooks": [],
            
            "error": {"message": final_status}
        }), 400

    # Merge vector clocks from (a) and (b)
    merged_tx_clock = [max(tx_result['verify_items'][i], tx_result['verify_user'][i]) for i in range(3)]
    log_tools.debug(f"[Orchestrator] Merged clock after events (a) and (b): {merged_tx_clock}")
    
    # (c) Verify Card Info
    tx_result2 = {}
    call_verify_card_info(order_id, merged_tx_clock, request_data, tx_result2)
    if not tx_result2.get('verify_card_success', True):
        final_status = "Order Rejected. " + tx_result2.get('verify_card_reason', "Credit card verification failed.")
        return jsonify({
            "orderId": order_id,
            "status": final_status,
            "suggestedBooks": [],
            
            "error": {"message": final_status}
        }), 400
    updated_tx_clock = tx_result2['verify_card']
    log_tools.debug(f"[Orchestrator] Updated clock after event (c): {updated_tx_clock}")
    
    # ----- Step 3: Execute Fraud Detection Events -----
    fraud_result = {}
    call_check_user_fraud(order_id, updated_tx_clock, request_data, fraud_result)
    if not fraud_result.get('check_user_fraud_success', True):
        final_status = "Order Rejected. " + fraud_result.get('check_user_fraud_reason', "User fraud check failed.")
        return jsonify({
            "orderId": order_id,
            "status": final_status,
            "suggestedBooks": [],
            
            "error": {"message": final_status}
        }), 400
    clock_after_user_fraud = fraud_result['check_user_fraud']
    
    fraud_result2 = {}
    call_check_card_fraud(order_id, clock_after_user_fraud, request_data, fraud_result2)
    if not fraud_result2.get('check_card_fraud_success', True):
        final_status = "Order Rejected. " + fraud_result2.get('check_card_fraud_reason', "Credit card fraud check failed.")
        return jsonify({
            "orderId": order_id,
            "status": final_status,
            "suggestedBooks": [],
            
            "error": {"message": final_status}
        }), 400
    updated_fraud_clock = fraud_result2['check_card_fraud']
    log_tools.debug(f"[Orchestrator] Updated clock after Fraud events: {updated_fraud_clock}")
    
    # ----- Step 4: Execute Suggestions Event -----
    sug_result = {}
    call_generate_suggestions(order_id, updated_fraud_clock, request_data, sug_result)
    if not sug_result.get('generate_suggestions_success', True):
        final_status = "Order Rejected. " + sug_result.get('generate_suggestions_reason', "Suggestions generation failed.")
        return jsonify({
            "orderId": order_id,
            "status": final_status,
            "suggestedBooks": [],
            
            "error": {"message": final_status}
        }), 400
    final_suggestions = sug_result['generate_suggestions']['books']
    final_clock = sug_result['generate_suggestions']['clock']
    log_tools.debug(f"[Orchestrator] Final vector clock from Suggestions: {final_clock}")
    
    # ----- Step 5: Enqueue the Order -----
    final_status = "Order Placed Successfully."
    enqueue_result = {}
    enqueue_thread = threading.Thread(target=call_enqueue_order, args=(order_id, request_data, enqueue_result))
    log_tools.debug("[Orchestrator] Starting enqueue thread.")
    enqueue_thread.start()
    enqueue_thread.join()
    log_tools.debug(f"[Orchestrator] Enqueue result: {enqueue_result}")
    
    # ----- Step 7: Build the Final JSON Response -----
    response_json = {
        "orderId": order_id,
        "status": final_status,
        "suggestedBooks": final_suggestions,  # Always return an array
        "finalVectorClock": final_clock,
        "enqueueSuccess": enqueue_result.get('enqueue', None),
        "enqueueMessage": enqueue_result.get('enqueue_msg', "")
    }
    return jsonify(response_json)

if __name__ == '__main__':
    log_tools.info("[Orchestrator] Starting...")
    app.run(host='0.0.0.0')
    log_tools.info("[Orchestrator] Stopped.")