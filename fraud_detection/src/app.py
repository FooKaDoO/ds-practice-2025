import sys
import os

# This set of lines are needed to import the gRPC stubs.
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
fraud_detection_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/fraud_detection'))
sys.path.insert(0, fraud_detection_grpc_path)

import fraud_detection_pb2 as fraud_detection
import fraud_detection_pb2_grpc as fraud_detection_grpc

log_tools_path = os.path.abspath(os.path.join(FILE, '../../../utils/log_tools'))
sys.path.insert(0, log_tools_path)
import log_tools

import grpc
from concurrent import futures

class FraudDetectionServiceServicer(fraud_detection_grpc.FraudDetectionServiceServicer):
    """
    Implements the FraudDetectionService from our .proto.
    """
    @log_tools.log_decorator("Fraud Service")
    def CheckOrder(self, request, context):
        """
        Decide whether an order is fraudulent based on the totalAmount field.
        For example, if totalAmount > 1000, mark it as fraud.
        """

        response = fraud_detection.CheckOrderResponse()

        log_tools.debug("[Fraud Service] Checking if total amount is above 1000.")
        if request.totalAmount > 1000:
            response.isFraud = True
            response.reason = "Amount too large"
        else:
            response.isFraud = False
            response.reason = "Looks ok"
        log_tools.debug(f"[Fraud Service] Response info: isFraud={response.isFraud} reason=\"{response.reason}\".")

        return response

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    fraud_detection_grpc.add_FraudDetectionServiceServicer_to_server(
        FraudDetectionServiceServicer(),
        server
    )

    port = "50051"
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    log_tools.info(f"[Fraud Service] Listening on port {port}...")
    server.wait_for_termination()

if __name__ == '__main__':
    log_tools.info("[Fraud Service] Starting...")
    serve()
    log_tools.info("[Fraud Service] Stopped.")
