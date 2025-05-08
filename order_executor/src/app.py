import os
import sys
import grpc
import time
import threading
from concurrent import futures
import re
import json


# --- Set Up Paths and Import Stubs ---
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
order_executor_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/order_executor'))
sys.path.insert(0, order_executor_grpc_path)
from order_executor_pb2 import (
    DequeueResponse, ElectionRequest, ElectionResponse,
    CoordinatorRequest, CoordinatorResponse,
    GetLeaderRequest, GetLeaderResponse
)
from order_executor_pb2_grpc import (
    add_OrderExecutorServiceServicer_to_server, OrderExecutorServiceServicer, OrderExecutorServiceStub
)

# Import Order Queue stubs
order_queue_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/order_queue'))
sys.path.insert(0, order_queue_grpc_path)
import order_queue_pb2 as oq_pb2
import order_queue_pb2_grpc as oq_pb2_grpc

# Import logging
log_tools_path = os.path.abspath(os.path.join(FILE, '../../../utils/log_tools'))
sys.path.insert(0, log_tools_path)
import log_tools

# Import the generated gRPC stubs for Books Database
books_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/books'))
sys.path.insert(0, books_grpc_path)
import books_pb2
import books_pb2_grpc
from books_pb2 import DecrementRequest as DbDecReq, CommitRequest as DbCommitReq


# PaymentService stubs
payment_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/payments'))
sys.path.insert(0, payment_grpc_path)
import payment_pb2, payment_pb2_grpc
from payment_pb2 import PrepareRequest as PayPrepReq, CommitRequest as PayCommitReq, AbortRequest as PayAbortReq


# --- Environment Variables ---
REPLICA_ID = int(os.getenv("REPLICA_ID", "0"))
KNOWN_EXECUTORS = os.getenv("KNOWN_EXECUTORS", "")
KNOWN_EXECUTORS = [addr.strip() for addr in KNOWN_EXECUTORS.split(",") if addr.strip()]
KNOWN_EXECUTORS = [addr for addr in KNOWN_EXECUTORS if f"_{REPLICA_ID}:" not in addr]

# Global state
current_leader = None
election_in_progress = False
leader_lock = threading.RLock()

BOOKS_PRIMARY   = os.getenv("BOOKS_DB_PRIMARY", "books_db_0:50070")
PAYMENT_SERVICE = os.getenv("PAYMENT_SERVICE", "payments:50075")


# gRPC stub to BooksDB primary

_db_channel = grpc.insecure_channel(BOOKS_PRIMARY)
_db_stub    = books_pb2_grpc.BooksDatabaseStub(_db_channel)

def get_pay_stub():
    channel = grpc.insecure_channel(PAYMENT_SERVICE)
    try:
        grpc.channel_ready_future(channel).result(timeout=3)
    except grpc.FutureTimeoutError:
        raise grpc.RpcError("Channel to payment service not ready")
    return payment_pb2_grpc.PaymentServiceStub(channel)

def update_stock(title: str, qty: int):
    resp = _db_stub.DecrementStock(
        books_pb2.DecrementRequest(title=title, amount=qty)
    )
    if not resp.success:
        raise RuntimeError(f"Failed to decrement stock for '{title}' (insufficient or conflict)")


# right after your imports

# ─── In‐Memory Price Catalog ────────────────────────────
PRICE_LIST = {
    "Harry Potter":         10,
    "Twilight":             8,
    "Lord of the Rings":    12,
    "Clean Code":           30,
}

def price_lookup(title):
    return PRICE_LIST.get(title, 0)



def two_phase_commit(order_id, items, amount_cents):
    # Phase 1: Prepare
    # If breaks here, loop the same request until it works, since this is local.
    print("[Executor] Preparing...")
    _pay_stub = get_pay_stub()
    p_resp = _pay_stub.Prepare(PayPrepReq(order_id=order_id, amount_cents=amount_cents))
    if not p_resp.ready:
        _pay_stub.Abort(PayAbortReq(order_id=order_id))
        return False
    # Prepare each book
    for item in items:
        db_resp = _db_stub.PrepareDecrement(DbDecReq(title=item['name'], amount=item['quantity']))
        if not db_resp.success:
            # abort payment and staged books
            _pay_stub.Abort(PayAbortReq(order_id=order_id))
            for prev in items:
                _db_stub.AbortDecrement(DbCommitReq(title=prev['name']))
            return False
    # Phase 2: Commit
    # If breaks in commit.
    if not retry_commit_payment(order_id):
        log_tools.error(f"[2PC] Payment commit ultimately failed, potential inconsistency.")
        return False
    for item in items:
        _db_stub.CommitDecrement(DbCommitReq(title=item['name']))
    return True

def retry_commit_payment(order_id, retries=100, delay=2):
    print("[Executor] Commiting...")
    for attempt in range(retries):
        try:
            _pay_stub = get_pay_stub()
            resp = _pay_stub.Commit(PayCommitReq(order_id=order_id))
            if resp.success:
                print(f"[Executor] Payment commit {order_id} successful")
                return True
        except grpc.RpcError as e:
            log_tools.warn(f"[2PC] Payment commit failed (attempt {attempt+1}): {e}")
        time.sleep(delay)
        print("[Executor] Retrying...")
    return False

# --- Helper ---
def parse_replica_id(addr):
    try:
        match = re.search(r"_(\d+):", addr)
        if match:
            return int(match.group(1))
        else:
            raise ValueError("No numeric ID found in address")
    except Exception as e:
        log_tools.error(f"[Election] Could not parse replica ID from {addr}: {e}")
        return -1

# Track whether this node is in an election to avoid repeated triggers
in_election = False
election_lock = threading.Lock()

def send_election_message(target_addr: str) -> bool:
    """
    Sends an Election RPC to target_addr. Returns True if the target (a higher ID) acknowledges.
    """
    try:
        with grpc.insecure_channel(target_addr) as channel:
            stub = OrderExecutorServiceStub(channel)
            response = stub.Election(ElectionRequest(senderId=REPLICA_ID))
            log_tools.debug(f"[Election] Response from {target_addr}: {response.acknowledged}")
            return response.acknowledged
    except Exception as e:
        log_tools.error(f"[Election] Failed to contact {target_addr}: {e}")
        return False

def broadcast_coordinator(new_leader: int):
    """
    Sends Coordinator RPC to all known executors to inform them of the new leader.
    """
    for addr in KNOWN_EXECUTORS:
        if addr:
            try:
                channel = grpc.insecure_channel(addr)
                stub = OrderExecutorServiceStub(channel)
                stub.Coordinator(CoordinatorRequest(leaderId=new_leader))
                log_tools.info(f"[Election] Notified {addr} that leader is {new_leader}")
            except Exception as e:
                log_tools.error(f"[Election] Failed to notify {addr}: {e}")

def start_election():
    global current_leader, election_in_progress

    with leader_lock:
        if election_in_progress:
            return None
        election_in_progress = True

    log_tools.info(f"[Election] Replica {REPLICA_ID} starting election...")
    ack_received = False

    for addr in KNOWN_EXECUTORS:
        target_id = parse_replica_id(addr)
        if target_id > REPLICA_ID:
            if send_election_message(addr):
                ack_received = True
                log_tools.info(f"[Election] Replica {target_id} acknowledged our election.")

    time.sleep(5)  # Don't block lock here

    with leader_lock:
        if current_leader is None and not ack_received:
            current_leader = REPLICA_ID
            log_tools.info(f"[Election] Replica {REPLICA_ID} becomes leader.")
            broadcast_coordinator(current_leader)
        else:
            log_tools.debug(f"[Election] Leader already set to {current_leader}, skipping broadcast.")

        election_in_progress = False

# --- Election Monitor ---
def election_monitor():
    """
    Checks if we have a leader; if not, triggers start_election().
    """
    global current_leader
    while True:
        time.sleep(10)
        with leader_lock:
            if current_leader is None:
                start_election()

# --- Order Executor Service ---
class OrderExecutorService(OrderExecutorServiceServicer):
    def Election(self, request, context):
        """
        RPC from a lower‐ID asking “should I be leader?”
        If we have a higher ID, we acknowledge and kick off our own election.
        """
        sender_id = request.senderId
        log_tools.info(f"[Election] Replica {REPLICA_ID} received Election from {sender_id}")
        if REPLICA_ID > sender_id:
            log_tools.info(f"[Election] Replica {REPLICA_ID} acknowledges and will start its own election")
            threading.Thread(target=start_election, daemon=True).start()
            return ElectionResponse(acknowledged=True)
        else:
            return ElectionResponse(acknowledged=False)

    def Coordinator(self, request, context):
        """
        RPC from the newly elected leader announcing “I’m leader now.”
        We just record it locally.
        """
        new_leader = request.leaderId
        log_tools.info(f"[Election] Received Coordinator → new leader is {new_leader}")
        global current_leader
        with leader_lock:
            current_leader = new_leader
        return CoordinatorResponse(success=True)

    def GetLeader(self, request, context):
        """
        RPC to ask “who’s the leader?”
        """
        return GetLeaderResponse(leaderId=current_leader if current_leader is not None else -1)

    def process_order(self):
        log_tools.info(f"[Executor] process_order (Replica {REPLICA_ID})")
        # only leader runs
        with leader_lock:
            leader = current_leader if current_leader is not None else REPLICA_ID
        if leader != REPLICA_ID:
            return
        

        stub = oq_pb2_grpc.OrderQueueServiceStub(
            grpc.insecure_channel('order_queue:50055')
        )
        dq = stub.Dequeue(oq_pb2.DequeueRequest(), timeout=5)
        log_tools.info(f"[Executor] Dequeue → {dq}")
        if not dq.success:
            return

        order = json.loads(dq.orderData)

        USE_2PC = True

        if USE_2PC:
            # ─── Your existing two_phase_commit logic ─────────────────────────
            total_cents = sum(item['quantity'] * price_lookup(item['name']) * 100
                            for item in order['items'])
            if two_phase_commit(dq.orderId, order['items'], total_cents):
                log_tools.info(f"[Executor] Order {dq.orderId} COMMITTED via 2PC")
            else:
                log_tools.error(f"[Executor] Order {dq.orderId} ABORTED via 2PC")        
        else:
        # ─── Simple “decrement‐stock” fallback ─────────────────────────────
            committed = True
            for item in order['items']:
                try:
                    update_stock(item['name'], item['quantity'])
                    log_tools.info(f"[Executor] Decremented {item['quantity']} of '{item['name']}'")
                except Exception as e:
                    log_tools.error(f"[Executor] Fallback update_stock failed for '{item['name']}': {e}")
                    committed = False
                    break
                
            if committed:
                log_tools.info(f"[Executor] Order {dq.orderId} successfully executed (stock updated).")
            else:
                log_tools.error(f"[Executor] Order {dq.orderId} execution aborted (no stock change).")

    def DequeueAndExecute(self, request, context):
        """
        RPC entrypoint — just alias to process_order() and return status.
        """
        log_tools.info(f"[Executor] DequeueAndExecute called on Replica {REPLICA_ID}")
        # only leader will actually dequeue/commit
        with leader_lock:
            leader = current_leader if current_leader is not None else REPLICA_ID
        if leader != REPLICA_ID:
            return DequeueResponse(success=False, message="Not leader")

        # invoke the same logic
        self.process_order()
        return DequeueResponse(success=True, message="Triggered execution")


# Server Setup
def serve():
    exec_service = OrderExecutorService()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_OrderExecutorServiceServicer_to_server(exec_service, server)
    port = "50056"
    server.add_insecure_port(f"[::]:{port}")
    log_tools.info(f"[Order Executor] Replica {REPLICA_ID} => listening on {port}")
    server.start()

    # Election monitor => ensures we have a leader eventually
    threading.Thread(target=election_monitor, daemon=True).start()

    # Polling loop => tries to process orders every 10s
    def polling_loop():
        log_tools.info("[Order Executor] Starting polling loop.")
        while True:
            time.sleep(10)
            exec_service.process_order()

    threading.Thread(target=polling_loop, daemon=True).start()

    while True:
        time.sleep(999999)

if __name__ == '__main__':
    serve()