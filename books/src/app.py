import os
import sys
import threading
import grpc
import json
from concurrent import futures

# load generated code from utils/pb/books
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
PROTO_ROOT = os.path.abspath(os.path.join(FILE, '../../../utils/pb/books'))
sys.path.insert(0, PROTO_ROOT)
import books_pb2
import books_pb2_grpc

# load logging utils
tools_root = os.path.abspath(os.path.join(FILE, '../../../utils/log_tools'))
sys.path.insert(0, tools_root)
import log_tools

# replica identity + backup addresses
REPLICA_ID   = int(os.getenv('REPLICA_ID', '0'))
BACKUP_ADDRS = os.getenv('BACKUP_ADDRS', '')
BACKUPS      = [addr.strip() for addr in BACKUP_ADDRS.split(',') if addr.strip()]

# in-memory store
_store      = {}
_store_lock = threading.Lock()

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
    SERVICE_NAME: f"books_{REPLICA_ID}"
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

tracer = trace.get_tracer(f"books_{REPLICA_ID}")
meter = metrics.get_meter(f"books_{REPLICA_ID}")

stock_counters = {}

def set_stock_meter(name, value):
    name = name.lower().replace(" ", "_")
    _stock_counter = stock_counters.get(name)
    if _stock_counter is None:
        _stock_counter = meter.create_up_down_counter(f"stock.{name}", unit="1", description=f"Stock for {name}")
        stock_counters[name] = _stock_counter
    _stock_counter.add(value, {"stock.title": name})

class BooksDatabaseServicer(books_pb2_grpc.BooksDatabaseServicer):
    @tracer.start_as_current_span("BooksDB:Read")
    def Read(self, request, context):
        with _store_lock:
            stock = _store.get(request.title, 0)
        set_stock_meter(request.title, 0)
        return books_pb2.ReadResponse(stock=stock)

    @tracer.start_as_current_span("BooksDB:Write")
    def Write(self, request, context):
        with _store_lock:
            old_stock = _store.get(request.title, 0)
            _store[request.title] = request.new_stock
            set_stock_meter(request.title, old_stock - request.new_stock)
        return books_pb2.WriteResponse(success=True)

class PrimaryReplica(BooksDatabaseServicer):
    def __init__(self, backup_stubs):
        super().__init__()
        self.backups = backup_stubs
        self._tentative  = {}

    @tracer.start_as_current_span("BooksDB:Primary:Read")
    @log_tools.log_decorator("BooksDB:Primary")
    def Write(self, request, context):
        # apply locally
        with _store_lock:
            old_stock = _store.get(request.title, 0)
            _store[request.title] = request.new_stock

        # replicate with acknowledgments and retries
        required_acks = len(self.backups)
        acks = 0
        for stub in self.backups:
            for attempt in range(3):  # retry up to 3 times
                try:
                    resp = stub.Write(request)
                    if resp.success:
                        acks += 1
                        break
                except grpc.RpcError as e:
                    log_tools.error(f"BooksDB: replication error to backup: {e} (attempt {attempt+1})")
            else:
                log_tools.error("BooksDB: failed to replicate to a backup after 3 attempts")

        final_result = True
        if acks < required_acks:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details("Could not replicate to all backups")
            with _store_lock:
                _store[request.title] = old_stock
            final_result = False
        
        with _store_lock:
            set_stock_meter(request.title, old_stock - _store.get(request.title, 0))
        
        return books_pb2.WriteResponse(success=final_result)

    @tracer.start_as_current_span("BooksDB:Primary:Write")
    @log_tools.log_decorator("BooksDB:Primary")
    def DecrementStock(self, request, context):
        # atomic check-and-decrement
        with _store_lock:
            curr = _store.get(request.title, 0)
            if curr < request.amount:
                set_stock_meter(request.title, 0)
                return books_pb2.WriteResponse(success=False)
            new = curr - request.amount
            _store[request.title] = new

        # replicate new value
        write_req = books_pb2.WriteRequest(title=request.title, new_stock=new)
        required_acks = len(self.backups)
        acks = 0
        for stub in self.backups:
            for attempt in range(3):
                try:
                    resp = stub.Write(write_req)
                    if resp.success:
                        acks += 1
                        break
                except grpc.RpcError as e:
                    log_tools.error(f"BooksDB: replication error to backup: {e} (attempt {attempt+1})")
            else:
                log_tools.error("BooksDB: failed to replicate decrement to a backup after 3 attempts")

        final_result = True
        if acks < required_acks:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details("Could not replicate decrement to all backups")
            final_result = False
        
        with _store_lock:
            set_stock_meter(request.title, curr - _store.get(request.title, 0))

        return books_pb2.WriteResponse(success=final_result)
    
    @tracer.start_as_current_span("BooksDB:Primary:PrepareDecrement")
    @log_tools.log_decorator("BooksDB:Primary")
    def PrepareDecrement(self, request, context):
        with _store_lock:
            curr = _store.get(request.title, 0)
            if curr < request.amount:
                set_stock_meter(request.title, 0)
                return books_pb2.WriteResponse(success=False)
            # stage the tentative new stock, but don’t apply it yet
            self._tentative[request.title] = curr - request.amount
        return books_pb2.WriteResponse(success=True)

    # 2PC Phase-2a: commit
    @tracer.start_as_current_span("BooksDB:Primary:CommitDecrement")
    @log_tools.log_decorator("BooksDB:Primary")
    def CommitDecrement(self, request, context):
        old = _store.get(request.title, 0)
        new = self._tentative.pop(request.title, None)
        if new is None:
            return books_pb2.WriteResponse(success=False)
        # now apply it for real
        with _store_lock:
            _store[request.title] = new
        # replicate the final Write to backups
        wr = books_pb2.WriteRequest(title=request.title, new_stock=new)
        for stub in self.backups:
            stub.Write(wr)
        with _store_lock:
            set_stock_meter(request.title, old - _store.get(request.title, 0))
        return books_pb2.WriteResponse(success=True)

    # 2PC Phase-2b: abort
    @tracer.start_as_current_span("BooksDB:Primary:AbortDecrement")
    @log_tools.log_decorator("BooksDB:Primary")
    def AbortDecrement(self, request, context):
        # drop any staged change
        self._tentative.pop(request.title, None)
        return books_pb2.WriteResponse(success=True)
    

class BackupReplica(BooksDatabaseServicer):
    @tracer.start_as_current_span("BooksDB:Backup:Write")
    @log_tools.log_decorator("BooksDB:Backup")
    def Write(self, request, context):
        with _store_lock:
            old_stock = _store.get(request.title, 0)
            _store[request.title] = request.new_stock
            set_stock_meter(request.title, old_stock - _store.get(request.title, 0))
        return books_pb2.WriteResponse(success=True)
    
    @tracer.start_as_current_span("BooksDB:Backup:CommitDecrement")
    def CommitDecrement(self, request, context):
        # On a commit we just mirror the primary’s Write
        # (request.new_stock isn’t actually here—so primary pushes via Write)
        return books_pb2.WriteResponse(success=True)
    
    @tracer.start_as_current_span("BooksDB:Backup:AbortDecrement")
    def AbortDecrement(self, request, context):
        # nothing staged on backups, so nothing to undo
        return books_pb2.WriteResponse(success=True)

def load_initial_stock():
    fn = os.getenv("INITIAL_STOCK_FILE", "initial_stock.json")
    path = os.path.join(os.path.dirname(__file__), fn)
    with _store_lock:
        # only seed once
        if _store:
            log_tools.info("[BooksDB] Store already initialized, skipping seeding.")
            return

    try:
        with open(path) as f:
            data = json.load(f)
        with _store_lock:
            _store.update(data)
        log_tools.info(f"[BooksDB] Seeded initial stock: {data}")
    except FileNotFoundError:
        log_tools.info(f"[BooksDB] No initial stock file at {path}; starting empty")

def serve():
    port = os.getenv('PORT', '50070')
    is_primary = (REPLICA_ID == 0)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    if is_primary:
        backup_stubs = []
        for addr in BACKUPS:
            ch = grpc.insecure_channel(addr)
            backup_stubs.append(books_pb2_grpc.BooksDatabaseStub(ch))
        servicer = PrimaryReplica(backup_stubs)
    else:
        servicer = BackupReplica()

    books_pb2_grpc.add_BooksDatabaseServicer_to_server(servicer, server)
    server.add_insecure_port(f"[::]:{port}")
    log_tools.info(f"[BooksDB] Replica {REPLICA_ID} listening on port {port} (primary={is_primary})")
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    load_initial_stock()
    serve()
