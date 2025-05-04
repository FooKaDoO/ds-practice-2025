import os, sys, threading, grpc
from concurrent import futures

# load generated code from utils/pb/books

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")

PROTO_ROOT = os.path.abspath(os.path.join(FILE, '../../../utils/pb/books'))
sys.path.insert(0, PROTO_ROOT)
import books_pb2 as books_pb2
import books_pb2_grpc as books_pb2_grpc

# load logging utils (optional)
LOG_ROOT = os.path.abspath(os.path.join(FILE, '../../../utils/log_tools'))
sys.path.insert(0, LOG_ROOT)
import log_tools

# replica identity + backup addresses
REPLICA_ID   = int(os.getenv('REPLICA_ID', '0'))
BACKUP_ADDRS = os.getenv('BACKUP_ADDRS', '')
BACKUPS      = [a.strip() for a in BACKUP_ADDRS.split(',') if a.strip()]

# in‑memory store
_store      = {}
_store_lock = threading.Lock()

class BooksDatabaseServicer(books_pb2_grpc.BooksDatabaseServicer):
    def Read(self, request, context):
        with _store_lock:
            stock = _store.get(request.title, 0)
        return books_pb2.ReadResponse(stock=stock)

    def Write(self, request, context):
        # overwritten in Primary, fallback here does local write only
        with _store_lock:
            _store[request.title] = request.new_stock
        return books_pb2.WriteResponse(success=True)

class PrimaryReplica(BooksDatabaseServicer):
    def __init__(self, backup_stubs):
        super().__init__()
        self.backups = backup_stubs

    @log_tools.log_decorator("BooksDB:Primary")
    def Write(self, request, context):
        # 1) apply locally
        with _store_lock:
            _store[request.title] = request.new_stock
        # 2) replicate to backups
        for stub in self.backups:
            try:
                stub.Write(request)
            except Exception as e:
                log_tools.error(f"BooksDB: failed to replicate to backup: {e}")
        return books_pb2.WriteResponse(success=True)

    def DecrementStock(self, req, ctx):
        with _store_lock:
            curr = _store.get(req.title, 0)
            if curr < req.amount:
                return books_pb2.WriteResponse(success=False)
            new = curr - req.amount
            _store[req.title] = new
        # replicate new value to backups…
        for stub in self.backups:
            stub.Write(books_pb2.WriteRequest(title=req.title, new_stock=new))
        return books_pb2.WriteResponse(success=True)

class BackupReplica(BooksDatabaseServicer):
    @log_tools.log_decorator("BooksDB:Backup")
    def Write(self, request, context):
        with _store_lock:
            _store[request.title] = request.new_stock
        return books_pb2.WriteResponse(success=True)


def serve():
    port = os.getenv('PORT', '50070')
    is_primary = (REPLICA_ID == 0)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    if is_primary:
        # build stubs for each backup
        backup_stubs = []
        for addr in BACKUPS:
            ch = grpc.insecure_channel(addr)
            backup_stubs.append(books_pb2_grpc.BooksDatabaseStub(ch))
        servicer = PrimaryReplica(backup_stubs)
    else:
        servicer = BackupReplica()

    books_pb2_grpc.add_BooksDatabaseServicer_to_server(servicer, server)
    server.add_insecure_port(f"[::]:{port}")
    log_tools.info(f"[BooksDB] Replica {REPLICA_ID} listening on {port} (primary={is_primary})")
    server.start()
    server.wait_for_termination()

import json, os

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

if __name__ == '__main__':
    load_initial_stock()
    serve()