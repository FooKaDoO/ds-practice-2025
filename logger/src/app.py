import sys
import os
import logging

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
logger_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/logger'))
sys.path.insert(0, logger_grpc_path)

# Ensure the logs directory exists
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)

# Log file path
log_file = os.path.join(log_dir, 'log.txt')

# Configure logging
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

import logger_pb2 as logger
import logger_pb2_grpc as logger_grpc

import grpc
from concurrent import futures

class LoggerServiceServicer(logger_grpc.LoggerServiceServicer):
    """
    Implements the LoggerService from our .proto.
    """

    def Log(self, request, context):

        response = logger.LogResponse()
        print(f"[Logger Service] Log called.")

        if not request:
            response.message = "Not logged. No request object."
            response.isLogged = False
            print(f"[Logger Service] Log failed.")
            return response
            
        if not request.message or len(request.message) == 0:
            response.message = "Not logged. No log message."
            response.isLogged = False
            print(f"[Logger Service] Log failed.")
            return response

        try:
            logging.info(msg=request.message)
            response.message = "Logged."
            response.isLogged = True
            print(f"[Logger Service] Log success.")
        except Exception as e:
            response.message = f"Not logged. {e}"
            response.isLogged = False
            print(f"[Logger Service] Log failed.")
        
        return response

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    logger_grpc.add_LoggerServiceServicer_to_server(
        LoggerServiceServicer(),
        server
    )

    port = "50054"
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"[Logger Service] Listening on port {port}...")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
