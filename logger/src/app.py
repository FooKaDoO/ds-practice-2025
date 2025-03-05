import sys
import os
import logging

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
logger_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/logger'))
sys.path.insert(0, logger_grpc_path)

import logger_pb2 as logger
import logger_pb2_grpc as logger_grpc

import grpc
from concurrent import futures

log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)

_logger = logging.getLogger()
_logger.setLevel(logging.NOTSET)

info_handler = logging.FileHandler(os.path.join(log_dir, 'info.log'))
debug_handler = logging.FileHandler(os.path.join(log_dir, 'debug.log'))
warn_handler = logging.FileHandler(os.path.join(log_dir, 'warn.log'))
error_handler = logging.FileHandler(os.path.join(log_dir, 'error.log'))

info_handler.setLevel(logging.INFO)
debug_handler.setLevel(logging.DEBUG)
warn_handler.setLevel(logging.WARN)
error_handler.setLevel(logging.ERROR)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
info_handler.setFormatter(formatter)
debug_handler.setFormatter(formatter)
warn_handler.setFormatter(formatter)
error_handler.setFormatter(formatter)

_logger.addHandler(info_handler)
_logger.addHandler(debug_handler)
_logger.addHandler(warn_handler)
_logger.addHandler(error_handler)

class LoggerServiceServicer(logger_grpc.LoggerServiceServicer):
    """
    Implements the LoggerService from our .proto.
    """
    def _log(self, level, request, context):

        if not request:
            print(f"[Logger Service] Log failed. No request object.")
            return logger.LogResponse()
            
        if not request.message or len(request.message) == 0:
            print(f"[Logger Service] Log failed. No log message.")
            return logger.LogResponse()

        try:
            _logger.log(level=level, msg=request.message)
        except Exception as e:
            print(f"[Logger Service] Log failed. {e}")
        return logger.LogResponse()
    
    def LogInfo(self, request, context):
        return self._log(logging.INFO, request, context)
    
    def LogDebug(self, request, context):
        return self._log(logging.DEBUG, request, context)
    
    def LogError(self, request, context):
        return self._log(logging.ERROR, request, context)
    
    def LogWarn(self, request, context):
        return self._log(logging.WARN, request, context)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    logger_grpc.add_LoggerServiceServicer_to_server(
        LoggerServiceServicer(),
        server
    )

    port = "50054"
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    _logger.info(f"[Logger Service] Listening on port {port}...")
    server.wait_for_termination()

if __name__ == '__main__':
    _logger.info(f"[Logger Service] Starting...")
    serve()
    _logger.info(f"[Logger Service] Stopped.")
