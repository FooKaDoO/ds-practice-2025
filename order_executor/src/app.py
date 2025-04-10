import os
import sys
import grpc
import time
import threading
from concurrent import futures
import re

# --- Set Up Paths and Import Stubs ---
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
order_executor_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/order_executor'))
sys.path.insert(0, order_executor_grpc_path)
from order_executor_pb2 import DequeueRequest, DequeueResponse, ElectionRequest, ElectionResponse, CoordinatorRequest, CoordinatorResponse, GetLeaderRequest, GetLeaderResponse
from order_executor_pb2_grpc import add_OrderExecutorServiceServicer_to_server, OrderExecutorServiceServicer, OrderExecutorServiceStub


# Import Order Queue stubs
order_queue_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/order_queue'))
sys.path.insert(0, order_queue_grpc_path)
import order_queue_pb2 as oq_pb2
import order_queue_pb2_grpc as oq_pb2_grpc


# Import logging utility
log_tools_path = os.path.abspath(os.path.join(FILE, '../../../utils/log_tools'))
sys.path.insert(0, log_tools_path)
import log_tools

# Globals
REPLICA_ID = int(os.getenv("REPLICA_ID", "1"))
KNOWN_EXECUTORS = os.getenv("KNOWN_EXECUTORS", "").split(",")  # e.g., ["executor_1:50056", "executor_2:50056"]
current_leader = None
election_in_progress = False
leader_lock = threading.RLock()

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

# --- Leader Election Methods ---
def send_election_message(target_addr):
    try:
        with grpc.insecure_channel(target_addr) as channel:
            stub = OrderExecutorServiceStub(channel)
            response = stub.Election(ElectionRequest(senderId=REPLICA_ID))
            log_tools.debug(f"[Election] Response from {target_addr}: {response.acknowledged}")
            return response.acknowledged
    except Exception as e:
        log_tools.error(f"[Election] Failed to contact {target_addr}: {e}")
        return False

def broadcast_coordinator(new_leader):
    for addr in KNOWN_EXECUTORS:
        try:
            with grpc.insecure_channel(addr) as channel:
                stub = OrderExecutorServiceStub(channel)
                stub.Coordinator(CoordinatorRequest(leaderId=new_leader))
                log_tools.info(f"[Election] Informed {addr} that leader is {new_leader}")
        except Exception as e:
            log_tools.error(f"[Election] Notification to {addr} failed: {e}")

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
    while True:
        with leader_lock:
            needs_election = (current_leader is None and not election_in_progress)

        if needs_election:
            threading.Thread(target=start_election, daemon=True).start()

        time.sleep(10)

# --- Leader Discovery on Startup ---
def try_discover_leader():
    global current_leader
    for addr in KNOWN_EXECUTORS:
        try:
            with grpc.insecure_channel(addr) as channel:
                stub = OrderExecutorServiceStub(channel)
                response = stub.GetLeader(GetLeaderRequest())
                if response.leaderId != -1:
                    with leader_lock:
                        current_leader = response.leaderId
                    log_tools.info(f"[Startup] Discovered current leader: {current_leader}")
                    return
        except Exception as e:
            log_tools.error(f"[Startup] Failed to query leader from {addr}: {e}")
    log_tools.info("[Startup] No leader found. Will trigger election.")

# --- Executor Logic ---
def _do_dequeue_logic():
    try:
        with grpc.insecure_channel('order_queue:50055') as channel:
            queue_stub = oq_pb2_grpc.OrderQueueServiceStub(channel)
            response = queue_stub.Dequeue(oq_pb2.DequeueRequest())
            if response.success:
                log_tools.info(f"[Executor] Order {response.orderId} is being executed by Leader {REPLICA_ID}")
                return DequeueResponse(success=True, message="Order executed", orderId=response.orderId, orderData=response.orderData)
            return DequeueResponse(success=False, message="No orders available")
    except Exception as e:
        log_tools.error(f"[Executor] Dequeue failed: {e}")
        return DequeueResponse(success=False, message=str(e))

def periodic_dequeue():
    while True:
        with leader_lock:
            is_leader = current_leader == REPLICA_ID
        
        if is_leader:
            log_tools.debug(f"[Executor] Attempting to dequeue as leader {REPLICA_ID}...")
            result = _do_dequeue_logic()
            if result.success:
                log_tools.info(f"[Executor] Dequeued and executed order {result.orderId}")
            else:
                log_tools.debug(f"[Executor] No orders to dequeue. Message: {result.message}")

        time.sleep(1)

# --- gRPC Service Definition ---
class OrderExecutorService(OrderExecutorServiceServicer):
    def DequeueAndExecute(self, request, context):
        return _do_dequeue_logic()

    def Election(self, request, context):
        sender_id = request.senderId
        log_tools.info(f"[Election] Replica {REPLICA_ID} received Election from {sender_id}")
        if REPLICA_ID > sender_id:
            log_tools.info(f"[Election] Replica {REPLICA_ID} acknowledges Election from {sender_id}")
            threading.Thread(target=start_election, daemon=True).start()
            return ElectionResponse(acknowledged=True)
        return ElectionResponse(acknowledged=False)

    def Coordinator(self, request, context):
        global current_leader
        with leader_lock:
            current_leader = request.leaderId
        log_tools.info(f"[Election] Replica {REPLICA_ID} sets leader to {current_leader}")
        return CoordinatorResponse(success=True)

    def GetLeader(self, request, context):
        with leader_lock:
            leader_id = current_leader if current_leader is not None else -1
        return GetLeaderResponse(leaderId=leader_id)

# --- Server Setup ---
def serve():
    delay = 5
    log_tools.info(f"[Startup] Delaying election by {delay} seconds...")
    time.sleep(delay)

    try_discover_leader()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_OrderExecutorServiceServicer_to_server(OrderExecutorService(), server)
    port = "50056"
    server.add_insecure_port(f"[::]:{port}")
    log_tools.info(f"[Order Executor] Replica {REPLICA_ID} listening on port {port}...")
    server.start()

    threading.Thread(target=election_monitor, daemon=True).start()
    threading.Thread(target=periodic_dequeue, daemon=True).start()

    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        log_tools.info("[Order Executor] Shutting down...")
        server.stop(0)

if __name__ == '__main__':
    serve()