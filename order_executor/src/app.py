import os
import sys
import grpc
import time
import threading
from concurrent import futures

# --- Set Up Paths and Import Stubs ---
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
order_executor_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/order_executor'))
sys.path.insert(0, order_executor_grpc_path)
from order_executor_pb2 import (
    DequeueResponse, ElectionRequest, ElectionResponse,
    CoordinatorRequest, CoordinatorResponse
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

# --- Environment Variables ---
REPLICA_ID = int(os.getenv("REPLICA_ID", "0"))
KNOWN_EXECUTORS = os.getenv("KNOWN_EXECUTORS", "")
KNOWN_EXECUTORS = [addr.strip() for addr in KNOWN_EXECUTORS.split(",") if addr.strip()]

# Global state
current_leader = None
leader_lock = threading.Lock()

# Track whether this node is in an election to avoid repeated triggers
in_election = False
election_lock = threading.Lock()

def send_election_message(target_addr: str) -> bool:
    """
    Sends an Election RPC to target_addr. Returns True if the target (a higher ID) acknowledges.
    """
    try:
        channel = grpc.insecure_channel(target_addr)
        stub = OrderExecutorServiceStub(channel)
        response = stub.Election(ElectionRequest(senderId=REPLICA_ID))
        log_tools.debug(f"[Election] Received response from {target_addr}: {response.acknowledged}")
        return response.acknowledged
    except Exception as e:
        log_tools.error(f"[Election] Error contacting {target_addr}: {e}")
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
    global current_leader, in_election
    with election_lock:
        if in_election:
            # Already in election, skip
            return
        in_election = True

    log_tools.info(f"[Election] Replica {REPLICA_ID} starting election...")

    # Step 1: Send Election messages to all higher-ID replicas
    higher_exists = False
    for addr in KNOWN_EXECUTORS:
        try:
            target_id = int(addr.split("_")[2].split(":")[0])
            if target_id > REPLICA_ID:
                higher_exists = True
                acknowledged = send_election_message(addr)
                if acknowledged:
                    log_tools.info(f"[Election] Higher ID {target_id} acknowledged our election request.")
        except Exception as e:
            log_tools.error(f"[Election] Error parsing address {addr}: {e}")

    # Step 2: If no higher ID exists, become leader immediately
    if not higher_exists:
        with leader_lock:
            current_leader = REPLICA_ID
        broadcast_coordinator(current_leader)
        log_tools.info(f"[Election] Replica {REPLICA_ID} is the highest ID => leader immediately.")
        with election_lock:
            in_election = False
        return

    # Step 3: If a higher ID exists, wait some time for a Coordinator
    time.sleep(5)

    # If we still don't have a leader, assume leadership
    with leader_lock:
        if current_leader is None:
            current_leader = REPLICA_ID
            broadcast_coordinator(current_leader)
            log_tools.info(f"[Election] Timeout => Replica {REPLICA_ID} elects itself leader.")
    with election_lock:
        in_election = False

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
    def process_order(self):
        """
        Called automatically by polling loop. Only the leader can execute an order.
        """
        log_tools.info(f"[Order Executor] process_order invoked (Replica {REPLICA_ID}).")
        global current_leader
        with leader_lock:
            effective_leader = current_leader if current_leader is not None else REPLICA_ID
            if effective_leader != REPLICA_ID:
                log_tools.debug(f"[Order Executor] Not leader => skip. Leader is {effective_leader}")
                return
        # We are the leader => Dequeue
        try:
            with grpc.insecure_channel('order_queue:50055') as channel:
                stub = oq_pb2_grpc.OrderQueueServiceStub(channel)
                log_tools.info("[Order Executor] Leader polling => Dequeue call")
                dq_response = stub.Dequeue(oq_pb2.DequeueRequest(), timeout=5)
                log_tools.info(f"[Order Executor] Dequeue returned: {dq_response}")
                if dq_response.success:
                    log_tools.info(f"[Order Executor] Leader {REPLICA_ID} executing order {dq_response.orderId}.")
                else:
                    log_tools.debug("[Order Executor] No orders available.")
        except Exception as e:
            log_tools.error(f"[Order Executor] Exception polling queue: {e}")

    def DequeueAndExecute(self, request, context):
        """
        RPC: Force an immediate attempt to dequeue an order. Only the leader can do so.
        """
        log_tools.info(f"[Order Executor] DequeueAndExecute called on replica {REPLICA_ID}.")
        global current_leader
        with leader_lock:
            effective_leader = current_leader if current_leader is not None else REPLICA_ID
            if effective_leader != REPLICA_ID:
                return DequeueResponse(success=False, message="Not leader, standing by.")

        # We are the leader => attempt Dequeue
        try:
            with grpc.insecure_channel('order_queue:50055') as channel:
                stub = oq_pb2_grpc.OrderQueueServiceStub(channel)
                dq_response = stub.Dequeue(oq_pb2.DequeueRequest(), timeout=5)
                log_tools.info(f"[Order Executor] DequeueAndExecute => {dq_response}")
                if dq_response.success:
                    log_tools.info(f"[Order Executor] Leader {REPLICA_ID} executing order {dq_response.orderId}.")
                    return DequeueResponse(
                        success=True,
                        message="Order executed",
                        orderId=dq_response.orderId,
                        orderData=dq_response.orderData
                    )
                else:
                    return DequeueResponse(success=False, message="No orders available")
        except Exception as e:
            log_tools.error(f"[Order Executor] Exception => {e}")
            return DequeueResponse(success=False, message=str(e))

    def Election(self, request, context):
        """
        Called by lower ID replicas. If this replica is higher, it acknowledges => triggers own election => can become leader.
        """
        sender_id = request.senderId
        log_tools.info(f"[Election] Replica {REPLICA_ID} received Election from {sender_id}.")
        if REPLICA_ID > sender_id:
            log_tools.info(f"[Election] Replica {REPLICA_ID} acknowledges => will start own election.")
            # Start election in background, so we don't block this RPC
            threading.Thread(target=start_election, daemon=True).start()
            return ElectionResponse(acknowledged=True)
        else:
            log_tools.info(f"[Election] Replica {REPLICA_ID} does not acknowledge => lower ID or same.")
            return ElectionResponse(acknowledged=False)

    def Coordinator(self, request, context):
        """
        Called when a node declares itself leader => updates current_leader here.
        """
        new_leader = request.leaderId
        log_tools.info(f"[Election] Received Coordinator => new leader is {new_leader}.")
        global current_leader
        with leader_lock:
            current_leader = new_leader
        return CoordinatorResponse(success=True)

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
