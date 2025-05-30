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

tracer = trace.get_tracer("orchestrator")
meter = metrics.get_meter("orchestrator")

# Create a histogram to track service call frequency
service_call_histogram = meter.create_histogram(
    name="orchestrator.service_calls",
    description="Counts how many times each service is called",
    unit="1"
)

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
    with tracer.start_as_current_span("Parse Request & Generate Order ID") as span:
        request_data = json.loads(request.data)
        order_id = str(uuid.uuid4())
        span.set_attribute("order.id", order_id)
        span.set_attribute("component", "request.parser")
        span.set_attribute("item.count", len(request_data.get('items', [])))
        log_tools.debug(f"[Orchestrator] Request Data: {json.dumps(request_data.get('items'), indent=2)}")
        log_tools.info(f"[Orchestrator] Generated OrderID: {order_id}")

    with tracer.start_as_current_span("Initialization Phase") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("component", "init.services")

        init_result = {}

        # Record each initialization call
        service_call_histogram.record(1, attributes={"service": "initialize_fraud"})
        service_call_histogram.record(1, attributes={"service": "initialize_tx"})
        service_call_histogram.record(1, attributes={"service": "initialize_suggestions"})

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

    initial_clock = [0, 0, 0]
    tx_result = {}

    with tracer.start_as_current_span("Verify Items & User Data") as span:
        span.set_attribute("order.id", order_id)
        span.set_attribute("component", "tx.verify")

        # Record each verification call
        service_call_histogram.record(1, attributes={"service": "verify_items"})
        service_call_histogram.record(1, attributes={"service": "verify_user_data"})

        thread_a = threading.Thread(target=call_verify_items, args=(order_id, initial_clock, request_data, tx_result))
        thread_b = threading.Thread(target=call_verify_user_data, args=(order_id, initial_clock, request_data, tx_result))
        log_tools.debug("[Orchestrator] Starting Transaction events (a) and (b) in parallel.")
        thread_a.start()
        thread_b.start()
        thread_a.join()
        thread_b.join()

        span.set_attribute("verify_items.success", tx_result.get('verify_items_success', False))
        span.set_attribute("verify_user.success", tx_result.get('verify_user_success', False))

        if not tx_result.get('verify_items_success', True):
            reason = tx_result.get('verify_items_reason', "Items verification failed.")
            span.set_attribute("verify_items.reason", reason)
            return jsonify({
                "orderId": order_id,
                "status": "Order Rejected. " + reason,
                "suggestedBooks": [],
                "error": {"message": reason}
            }), 400

        if not tx_result.get('verify_user_success', True):
            reason = tx_result.get('verify_user_reason', "User data verification failed.")
            span.set_attribute("verify_user.reason", reason)
            return jsonify({
                "orderId": order_id,
                "status": "Order Rejected. " + reason,
                "suggestedBooks": [],
                "error": {"message": reason}
            }), 400

    with tracer.start_as_current_span("Merge Vector Clocks") as span:
        merged_tx_clock = [max(tx_result['verify_items'][i], tx_result['verify_user'][i]) for i in range(3)]
        span.set_attribute("merged.clock", str(merged_tx_clock))
        log_tools.debug(f"[Orchestrator] Merged clock after events (a) and (b): {merged_tx_clock}")

    with tracer.start_as_current_span("Verify Card Info") as span:
        tx_result2 = {}

        # Record verification call
        service_call_histogram.record(1, attributes={"service": "verify_card_info"})

        call_verify_card_info(order_id, merged_tx_clock, request_data, tx_result2)
        span.set_attribute("order.id", order_id)
        span.set_attribute("verify_card.success", tx_result2.get('verify_card_success', False))
        if not tx_result2.get('verify_card_success', True):
            reason = tx_result2.get('verify_card_reason', "Credit card verification failed.")
            span.set_attribute("verify_card.reason", reason)
            return jsonify({
                "orderId": order_id,
                "status": "Order Rejected. " + reason,
                "suggestedBooks": [],
                "error": {"message": reason}
            }), 400
        updated_tx_clock = tx_result2['verify_card']
        span.set_attribute("updated.clock", str(updated_tx_clock))
        log_tools.debug(f"[Orchestrator] Updated clock after event (c): {updated_tx_clock}")

    with tracer.start_as_current_span("Fraud Check - User") as span:
        fraud_result = {}

        service_call_histogram.record(1, attributes={"service": "check_user_fraud"})

        call_check_user_fraud(order_id, updated_tx_clock, request_data, fraud_result)
        span.set_attribute("check_user_fraud.success", fraud_result.get('check_user_fraud_success', False))
        if not fraud_result.get('check_user_fraud_success', True):
            reason = fraud_result.get('check_user_fraud_reason', "User fraud check failed.")
            span.set_attribute("check_user_fraud.reason", reason)
            return jsonify({
                "orderId": order_id,
                "status": "Order Rejected. " + reason,
                "suggestedBooks": [],
                "error": {"message": reason}
            }), 400
        clock_after_user_fraud = fraud_result['check_user_fraud']

    with tracer.start_as_current_span("Fraud Check - Card") as span:
        fraud_result2 = {}

        service_call_histogram.record(1, attributes={"service": "check_card_fraud"})

        call_check_card_fraud(order_id, clock_after_user_fraud, request_data, fraud_result2)
        span.set_attribute("check_card_fraud.success", fraud_result2.get('check_card_fraud_success', False))
        if not fraud_result2.get('check_card_fraud_success', True):
            reason = fraud_result2.get('check_card_fraud_reason', "Credit card fraud check failed.")
            span.set_attribute("check_card_fraud.reason", reason)
            return jsonify({
                "orderId": order_id,
                "status": "Order Rejected. " + reason,
                "suggestedBooks": [],
                "error": {"message": reason}
            }), 400
        updated_fraud_clock = fraud_result2['check_card_fraud']
        span.set_attribute("updated.clock", str(updated_fraud_clock))
        log_tools.debug(f"[Orchestrator] Updated clock after Fraud events: {updated_fraud_clock}")

    with tracer.start_as_current_span("Generate Suggestions") as span:
        sug_result = {}

        service_call_histogram.record(1, attributes={"service": "generate_suggestions"})

        call_generate_suggestions(order_id, updated_fraud_clock, request_data, sug_result)
        span.set_attribute("generate_suggestions.success", sug_result.get('generate_suggestions_success', False))
        if not sug_result.get('generate_suggestions_success', True):
            reason = sug_result.get('generate_suggestions_reason', "Suggestions generation failed.")
            span.set_attribute("generate_suggestions.reason", reason)
            return jsonify({
                "orderId": order_id,
                "status": "Order Rejected. " + reason,
                "suggestedBooks": [],
                "error": {"message": reason}
            }), 400
        final_suggestions = sug_result['generate_suggestions']['books']
        final_clock = sug_result['generate_suggestions']['clock']
        span.set_attribute("suggested_books.count", len(final_suggestions))
        span.set_attribute("final.clock", str(final_clock))
        log_tools.debug(f"[Orchestrator] Final vector clock from Suggestions: {final_clock}")

    with tracer.start_as_current_span("Enqueue Order") as span:
        enqueue_result = {}

        service_call_histogram.record(1, attributes={"service": "enqueue_order"})

        enqueue_thread = threading.Thread(target=call_enqueue_order, args=(order_id, request_data, enqueue_result))
        span.set_attribute("order.id", order_id)
        log_tools.debug("[Orchestrator] Starting enqueue thread.")
        enqueue_thread.start()
        enqueue_thread.join()
        span.set_attribute("enqueue.success", enqueue_result.get('enqueue', False))
        log_tools.debug(f"[Orchestrator] Enqueue result: {enqueue_result}")

    with tracer.start_as_current_span("Build Response") as span:
        span.set_attribute("order.id", order_id)
        response_json = {
            "orderId": order_id,
            "status": "Order Placed Successfully.",
            "suggestedBooks": final_suggestions,
            "finalVectorClock": final_clock,
            "enqueueSuccess": enqueue_result.get('enqueue', None),
            "enqueueMessage": enqueue_result.get('enqueue_msg', "")
        }
        span.set_attribute("response.status", "Order Placed Successfully.")
        return jsonify(response_json)

if __name__ == '__main__':
    log_tools.info("[Orchestrator] Starting...")
    app.run(host='0.0.0.0')
    log_tools.info("[Orchestrator] Stopped.")