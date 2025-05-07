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

class BooksDatabaseServicer(books_pb2_grpc.BooksDatabaseServicer):
    def Read(self, request, context):
        with _store_lock:
            stock = _store.get(request.title, 0)
        return books_pb2.ReadResponse(stock=stock)

    def Write(self, request, context):
        with _store_lock:
            _store[request.title] = request.new_stock
        return books_pb2.WriteResponse(success=True)

class PrimaryReplica(BooksDatabaseServicer):
    def __init__(self, backup_stubs):
        super().__init__()
        self.backups = backup_stubs
        self._tentative  = {}

    @log_tools.log_decorator("BooksDB:Primary")
    def Write(self, request, context):
        # apply locally
        with _store_lock:
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

        if acks < required_acks:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details("Could not replicate to all backups")
            return books_pb2.WriteResponse(success=False)

        return books_pb2.WriteResponse(success=True)

    @log_tools.log_decorator("BooksDB:Primary")
    def DecrementStock(self, request, context):
        # atomic check-and-decrement
        with _store_lock:
            curr = _store.get(request.title, 0)
            if curr < request.amount:
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

        if acks < required_acks:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details("Could not replicate decrement to all backups")
            return books_pb2.WriteResponse(success=False)

        return books_pb2.WriteResponse(success=True)
    
    @log_tools.log_decorator("BooksDB:Primary")
    def PrepareDecrement(self, request, context):
        with _store_lock:
            curr = _store.get(request.title, 0)
            if curr < request.amount:
                return books_pb2.WriteResponse(success=False)
            # stage the tentative new stock, but don’t apply it yet
            self._tentative[request.title] = curr - request.amount
        return books_pb2.WriteResponse(success=True)

    # 2PC Phase-2a: commit
    @log_tools.log_decorator("BooksDB:Primary")
    def CommitDecrement(self, request, context):
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
        return books_pb2.WriteResponse(success=True)

    # 2PC Phase-2b: abort
    @log_tools.log_decorator("BooksDB:Primary")
    def AbortDecrement(self, request, context):
        # drop any staged change
        self._tentative.pop(request.title, None)
        return books_pb2.WriteResponse(success=True)
    

class BackupReplica(BooksDatabaseServicer):
    @log_tools.log_decorator("BooksDB:Backup")
    def Write(self, request, context):
        with _store_lock:
            _store[request.title] = request.new_stock
        return books_pb2.WriteResponse(success=True)
    
    def CommitDecrement(self, request, context):
        # On a commit we just mirror the primary’s Write
        # (request.new_stock isn’t actually here—so primary pushes via Write)
        return books_pb2.WriteResponse(success=True)
    
    def AbortDecrement(self, request, context):
        # nothing staged on backups, so nothing to undo
        return books_pb2.WriteResponse(success=True)

def load_initial_stock():
    fn = os.getenv("INITIAL_STOCK_FILE", "initial_stock.json")
    path = os.path.join(os.path.dirname(__file__), fn)
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
