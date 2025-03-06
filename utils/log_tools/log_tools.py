import os
import sys
import grpc

FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
logger_grpc_path = os.path.abspath(os.path.join(FILE, '../../pb/logger'))
sys.path.insert(0, logger_grpc_path)

import logger_pb2 as logger
import logger_pb2_grpc as logger_grpc

def info(message):
    with grpc.insecure_channel('logger:50054') as channel:
        stub = logger_grpc.LoggerServiceStub(channel)
        request = logger.LogRequest(message=message)
        stub.LogInfo(request)

def debug(message):
    with grpc.insecure_channel('logger:50054') as channel:
        stub = logger_grpc.LoggerServiceStub(channel)
        request = logger.LogRequest(message=message)
        stub.LogDebug(request)

def warn(message):
    with grpc.insecure_channel('logger:50054') as channel:
        stub = logger_grpc.LoggerServiceStub(channel)
        request = logger.LogRequest(message=message)
        stub.LogWarn(request)

def error(message):
    with grpc.insecure_channel('logger:50054') as channel:
        stub = logger_grpc.LoggerServiceStub(channel)
        request = logger.LogRequest(message=message)
        stub.LogError(request)

# https://stackoverflow.com/a/25206079
def log_decorator(service_name):
    def inner_decorator(func):
        def wrapper(*func_args, **func_kwargs):
            arg_names = func.__code__.co_varnames[:func.__code__.co_argcount]
            args = func_args[:len(arg_names)]
            defaults = func.__defaults__ or ()
            args = args + defaults[len(defaults) - (func.__code__.co_argcount - len(args)):]
            params = list(zip(arg_names, args))
            args = func_args[len(arg_names):]
            if args: params.append(('args', args))
            if func_kwargs: params.append(('kwargs', func_kwargs))
            details = f"{func.__name__}({', '.join('%s = %r' % p for p in params)})"
            debug(f"[{service_name}] Called function: {details}")
            output = func(*func_args, **func_kwargs)
            debug(f"[{service_name}] Function {details} returned with value {output}")
            return output
        return wrapper
    return inner_decorator