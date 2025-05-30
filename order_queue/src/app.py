import sys
import os
import threading
import grpc
from concurrent import futures
from queue import PriorityQueue  # Using PriorityQueue for ordering

# Import generated stubs
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
order_queue_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/order_queue'))
sys.path.insert(0, order_queue_grpc_path)

import order_queue_pb2 as oq_pb2
import order_queue_pb2_grpc as oq_pb2_grpc

# Logging
log_tools_path = os.path.abspath(os.path.join(FILE, '../../../utils/log_tools'))
sys.path.insert(0, log_tools_path)
import log_tools

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
    SERVICE_NAME: "order_queue"
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

class OrderQueueServiceServicer(oq_pb2_grpc.OrderQueueServiceServicer):
    def __init__(self):
        # Use a lock for thread-safety and a PriorityQueue to store orders.
        self._lock = threading.RLock()
        self._pq = PriorityQueue()  # Orders stored as tuples (-priority, orderId, orderData)

    @log_tools.log_decorator("OrderQueue")
    def Enqueue(self, request, context):
        with self._lock:
            # Here, higher numbers indicate higher priority. We store the negative.
            priority = request.priority
            self._pq.put((-priority, request.orderId, request.orderData))
            msg = f"Order {request.orderId} enqueued with priority {priority}."
            log_tools.debug("[OrderQueue] " + msg)
        return oq_pb2.EnqueueResponse(success=True, message=msg)

    @log_tools.log_decorator("OrderQueue")
    def Dequeue(self, request, context):
        with self._lock:
            if not self._pq.empty():
                neg_priority, order_id, order_data = self._pq.get()
                msg = f"Order {order_id} dequeued."
                log_tools.debug("[OrderQueue] " + msg)
                return oq_pb2.DequeueResponse(success=True, message=msg, orderId=order_id, orderData=order_data)
            else:
                msg = "Queue is empty."
                log_tools.debug("[OrderQueue] " + msg)
                return oq_pb2.DequeueResponse(success=False, message=msg, orderId="", orderData="")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    oq_pb2_grpc.add_OrderQueueServiceServicer_to_server(OrderQueueServiceServicer(), server)
    port = "50055"
    server.add_insecure_port(f"[::]:{port}")
    log_tools.info(f"[OrderQueue] Listening on port {port}...")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    log_tools.info("[OrderQueue] Starting...")
    serve()
    log_tools.info("[OrderQueue] Stopped.")
