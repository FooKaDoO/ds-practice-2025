import os
import sys
import threading
import grpc
import json
from concurrent import futures

# load generated code from utils/pb/books
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
sys.path.insert(0, os.path.join(os.path.dirname(FILE), '../../utils/pb/payments'))
import payment_pb2, payment_pb2_grpc

STATE_FILE = os.path.join(os.path.dirname(FILE), '../../utils/data/mnt/payments_state.json')
SIMULATE_CRASH = False

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
    SERVICE_NAME: "payments"
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

class PaymentService(payment_pb2_grpc.PaymentServiceServicer):
    def __init__(self):
        self.lock = threading.Lock()
        self.prepared = self.load_state()

    def load_state(self):
        with self.lock:
            with open(STATE_FILE, 'r') as f:
                try:
                    return set(json.load(f))
                except:
                    return set()
        return set()

    def save_state(self):
        with self.lock:
            with open(STATE_FILE, 'w') as f:
                json.dump(list(self.prepared), f)

    def Prepare(self, request, context):
        self.prepared.add(request.order_id)
        self.save_state()
        print(f"[Payment] PREPARED {request.order_id}")
        return payment_pb2.PrepareResponse(ready=True)

    def Commit(self, request, context):
        if SIMULATE_CRASH:
            import time
            print("[Payment] Commit called, simulating crash...")
            time.sleep(2)
            os._exit(1)
        if request.order_id in self.prepared:
            print(f"[Payment] Committed {request.order_id}")
            self.prepared.remove(request.order_id)
            self.save_state()
            return payment_pb2.CommitResponse(success=True)
        return payment_pb2.CommitResponse(success=False)

    def Abort(self, request, context):
        if request.order_id in self.prepared:
            print(f"[Payment] Aborted {request.order_id}")
            self.prepared.remove(request.order_id)
            self.save_state()
        return payment_pb2.AbortResponse(aborted=True)

def serve():
    port = os.getenv("PORT","50075")
    server = grpc.server(futures.ThreadPoolExecutor(4))
    payment_pb2_grpc.add_PaymentServiceServicer_to_server(PaymentService(), server)
    server.add_insecure_port(f"[::]:{port}")
    print(f"[Payment] Listening on {port}")
    server.start()
    server.wait_for_termination()

if __name__=='__main__':
    serve()
