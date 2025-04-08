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
from order_executor_pb2 import DequeueRequest, DequeueResponse, ElectionRequest, ElectionResponse, CoordinatorRequest, CoordinatorResponse
from order_executor_pb2_grpc import add_OrderExecutorServiceServicer_to_server, OrderExecutorServiceServicer, OrderExecutorServiceStub

# Import logging utility
log_tools_path = os.path.abspath(os.path.join(FILE, '../../../utils/log_tools'))
sys.path.insert(0, log_tools_path)
import log_tools

# --- Environment Variables and Globals ---
# Each replica must have a unique REPLICA_ID.
REPLICA_ID = int(os.getenv("REPLICA_ID", "0"))
# KNOWN_EXECUTORS should be a comma-separated list of executor addresses (e.g., "executor_0:50056,executor_1:50056")
KNOWN_EXECUTORS = os.getenv("KNOWN_EXECUTORS", "")
KNOWN_EXECUTORS = [addr.strip() for addr in KNOWN_EXECUTORS.split(",") if addr.strip()]

# Global variable to hold the current leader's ID (protected by a lock)
current_leader = None
leader_lock = threading.Lock()

# --- Leader Election Methods ---

def send_election_message(target_addr):
    """
    Sends an Election RPC to the target executor.
    Returns True if the target acknowledges (i.e., has a higher ID).
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

def broadcast_coordinator(new_leader):
    """
    Sends a Coordinator RPC to all known executor replicas.
    """
    from order_executor_pb2 import CoordinatorRequest
    for addr in KNOWN_EXECUTORS:
        if addr:  # ensure not empty
            try:
                channel = grpc.insecure_channel(addr)
                stub = OrderExecutorServiceStub(channel)
                stub.Coordinator(CoordinatorRequest(leaderId=new_leader))
                log_tools.info(f"[Election] Notified {addr} that leader is {new_leader}")
            except Exception as e:
                log_tools.error(f"[Election] Failed to notify {addr}: {e}")

def start_election():
    """
    Implements a simple Bully algorithm:
      - Send Election RPCs to all replicas with higher IDs.
      - If no higher-ID replica acknowledges, declare self as leader.
      - Otherwise, wait for a Coordinator broadcast.
    """
    global current_leader
    log_tools.info(f"[Election] Replica {REPLICA_ID} starting election...")
    ack_received = False
    for addr in KNOWN_EXECUTORS:
        try:
            # Assume address format "executor_<id>:port"
            target_id = int(addr.split("_")[1].split(":")[0])
            if target_id > REPLICA_ID:
                if send_election_message(addr):
                    ack_received = True
                    log_tools.info(f"[Election] Replica {target_id} acknowledged our election.")
        except Exception as e:
            log_tools.error(f"[Election] Error parsing address {addr}: {e}")
    with leader_lock:
        if not ack_received:
            current_leader = REPLICA_ID
            broadcast_coordinator(current_leader)
            log_tools.info(f"[Election] Replica {REPLICA_ID} becomes leader (no higher replica acknowledged).")
        else:
            # Wait for some time to receive a Coordinator message
            time.sleep(5)
            if current_leader is None:
                current_leader = REPLICA_ID
                broadcast_coordinator(current_leader)
                log_tools.info(f"[Election] Timeout reached. Replica {REPLICA_ID} elects itself as leader.")

def election_monitor():
    """
    Periodically check if a leader is assigned; if not, start election.
    """
    global current_leader
    while True:
        with leader_lock:
            if current_leader is None:
                start_election()
        time.sleep(10)

# --- Order Executor Service Implementation ---
class OrderExecutorService(OrderExecutorServiceServicer):
    @log_tools.log_decorator("Order Executor")
    def DequeueAndExecute(self, request, context):
        global current_leader
        with leader_lock:
            if current_leader != REPLICA_ID:
                log_tools.debug(f"[Order Executor] Replica {REPLICA_ID} is not the leader (current leader: {current_leader}).")
                return DequeueResponse(success=False, message="Not leader, standing by.")
        try:
            with grpc.insecure_channel('order_queue:50060') as channel:
                from order_queue_pb2 import DequeueRequest
                from order_queue_pb2_grpc import OrderQueueServiceStub
                queue_stub = OrderQueueServiceStub(channel)
                dq_response = queue_stub.Dequeue(DequeueRequest())
                if dq_response.success:
                    log_tools.info(f"[Order Executor] Leader {REPLICA_ID} executing order {dq_response.orderId}.")
                    return DequeueResponse(success=True, message="Order executed", orderId=dq_response.orderId, orderData=dq_response.orderData)
                else:
                    log_tools.debug(f"[Order Executor] Leader {REPLICA_ID}: No orders available.")
                    return DequeueResponse(success=False, message="No orders available")
        except Exception as e:
            log_tools.error(f"[Order Executor] Leader {REPLICA_ID}: Exception during dequeue: {e}")
            return DequeueResponse(success=False, message=str(e))

    @log_tools.log_decorator("Election")
    def Election(self, request, context):
        sender_id = request.senderId
        log_tools.info(f"[Election] Replica {REPLICA_ID} received Election from {sender_id}.")
        # Acknowledge if our ID is greater.
        if REPLICA_ID > sender_id:
            log_tools.info(f"[Election] Replica {REPLICA_ID} acknowledges Election from {sender_id}.")
            return ElectionResponse(acknowledged=True)
        else:
            log_tools.info(f"[Election] Replica {REPLICA_ID} does not acknowledge Election from {sender_id}.")
            return ElectionResponse(acknowledged=False)

    @log_tools.log_decorator("Election")
    def Coordinator(self, request, context):
        new_leader = request.leaderId
        with leader_lock:
            global current_leader
            current_leader = new_leader
        log_tools.info(f"[Election] Replica {REPLICA_ID} sets leader to {new_leader} upon receiving Coordinator.")
        return CoordinatorResponse(success=True)

# --- Server Setup ---
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    # Add the combined service (order execution and election)
    add_OrderExecutorServiceServicer_to_server(OrderExecutorService(), server)
    port = "50056"  # Port for the Order Executor service
    server.add_insecure_port(f"[::]:{port}")
    log_tools.info(f"[Order Executor] Replica {REPLICA_ID} is listening on port {port}...")
    server.start()
    # Start the election monitor on a background thread.
    threading.Thread(target=election_monitor, daemon=True).start()
    while True:
        time.sleep(10)

if __name__ == '__main__':
    serve()
