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

class PaymentService(payment_pb2_grpc.PaymentServiceServicer):
    def __init__(self):
        self.prepared = set()

    def Prepare(self, request, context):
        self.prepared.add(request.order_id)
        return payment_pb2.PrepareResponse(ready=True)

    def Commit(self, request, context):
        if request.order_id in self.prepared:
            print(f"[Payment] Committed {request.order_id}")
            self.prepared.remove(request.order_id)
            return payment_pb2.CommitResponse(success=True)
        return payment_pb2.CommitResponse(success=False)

    def Abort(self, request, context):
        if request.order_id in self.prepared:
            print(f"[Payment] Aborted {request.order_id}")
            self.prepared.remove(request.order_id)
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
