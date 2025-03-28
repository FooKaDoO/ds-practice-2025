import sys
import os
import joblib

# This set of lines are needed to import the gRPC stubs.
FILE = __file__ if '__file__' in globals() else os.getenv("PYTHONFILE", "")
fraud_detection_grpc_path = os.path.abspath(os.path.join(FILE, '../../../utils/pb/fraud_detection'))
sys.path.insert(0, fraud_detection_grpc_path)

import fraud_detection_pb2 as fraud_detection
import fraud_detection_pb2_grpc as fraud_detection_grpc

log_tools_path = os.path.abspath(os.path.join(FILE, '../../../utils/log_tools'))
sys.path.insert(0, log_tools_path)
import log_tools

import pandas as pd
import grpc
from concurrent import futures

# Load model & scaler
model_path = "/app/fraud_detection/model/fraud_model.pkl"
scaler_path = "/app/fraud_detection/model/scaler.pkl"

cached_orders = {}      # e.g. { orderId: "some data" }
vector_clocks = {}      # e.g. { orderId: [0,0,0] } if you have 3 microservices


if os.path.exists(model_path) and os.path.exists(scaler_path):
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    log_tools.info("[Fraud Service] AI-based fraud detection model loaded successfully!")
    
else:
    # Log to console for debugging
    log_tools.warn("[Fraud Service] Model not found! Train the model first.")
    model, scaler = None, None


class FraudDetectionServiceServicer(fraud_detection_grpc.FraudDetectionServiceServicer):
    """
    Implements the FraudDetectionService from our .proto.
    """

    @log_tools.log_decorator("Fraud Service")
    def InitializeOrder(self, request, context):
        """
        Cache the order data and initialize a vector clock for the given orderId.
        """
        order_id = request.orderId
        order_data_json = request.orderDataJson  # or parse it if you want

        # Store/cache the data
        cached_orders[order_id] = order_data_json

        # Initialize the vector clock for this order, e.g. [0,0,0] if you have 3 microservices
        # If you have just 2 microservices, do [0,0], etc.
        if order_id not in vector_clocks:
            vector_clocks[order_id] = [0,0,0]  # or however many entries you need

        # Log or debug
        log_tools.debug(f"[Fraud Service] InitializeOrder: Stored data for orderId={order_id}, vectorClock={vector_clocks[order_id]}")

        # Return a success response
        response = fraud_detection.InitializeOrderResponse(
            success=True,
            message=f"Initialized order {order_id}"
        )
        return response

    @log_tools.log_decorator("Fraud Service")
    def CheckOrder(self, request, context):
        """
        Decide whether an order is fraudulent based on:
        1. totalAmount (float)
        2. number of items (derived from repeated Item)
        3. past_fraudulent_orders (dummy set to 0 here)
        """

        # 1Prepare a response object
        response = fraud_detection.CheckOrderResponse()

        # Extract fields from the request
        total_amount = request.totalAmount
        # Sum up all quantities
        item_count = sum(item.quantity for item in request.items)

        # Build a DataFrame with the columns your model was trained on
        #    - "amount"   => matches "amount" in your training code
        #    - "num_items" => matches "num_items" in training
        #    - "past_fraudulent_orders" => dummy = 0
        features = [[total_amount, item_count, 0]]
        features_df = pd.DataFrame(features, columns=["amount", "num_items", "past_fraudulent_orders"])

        # Standardize + predict
        log_tools.debug("[Fraud Service] Checking, if order is fraudulent.")
        features_scaled = scaler.transform(features_df)
        prediction = model.predict(features_scaled)[0]
        is_fraud = bool(prediction)

        # Set response fields
        response.isFraud = is_fraud

        response.reason = "Suspicious transaction" if is_fraud else "Looks OK"

        # Debug logs
        log_tools.debug(f"[Fraud Service] CheckOrder => totalAmount={total_amount}, itemCount={item_count}")
        log_tools.debug(f"[Fraud Service] Fraud result => isFraud={is_fraud}, reason={response.reason}")

        return response
    
    @log_tools.log_decorator("Fraud Service")
    def CheckUserFraud(self, request, context):
        """
        Event (d): Check user data for fraud.
        Merges the incoming vector clock and increments Fraud's slot (index 1).
        """
        order_id = request.orderId
        incoming_clock = list(request.vectorClock) if request.vectorClock else [0, 0, 0]
        # Merge with local clock for this order if exists; for simplicity, we assume local clock is the one from initialization.
        local_clock = vector_clocks.get(order_id, [0, 0, 0])
        # For demonstration, take element-wise maximum.
        merged_clock = [max(incoming_clock[i], local_clock[i]) for i in range(3)]
        # Increment Fraud's slot (index 1)
        merged_clock[1] += 1
        
        # Update local clock
        vector_clocks[order_id] = merged_clock
        
        log_tools.debug(f"[Fraud Service] CheckUserFraud for order {order_id}: updated vector clock: {merged_clock}")
        response = fraud_detection.CheckFraudResponse()
        response.success = True
        response.reason = "User data appears normal"
        response.updatedClock.extend(merged_clock)
        return response

    @log_tools.log_decorator("Fraud Service")
    def CheckCardFraud(self, request, context):
        """
        Event (e): Check credit card data for fraud.
        Merges the incoming vector clock and increments Fraud's slot (index 1) again.
        """
        order_id = request.orderId
        incoming_clock = list(request.vectorClock) if request.vectorClock else [0, 0, 0]
        local_clock = vector_clocks.get(order_id, [0, 0, 0])
        merged_clock = [max(incoming_clock[i], local_clock[i]) for i in range(3)]
        # Increment Fraud's slot (index 1)
        merged_clock[1] += 1
        
        # Update local clock
        vector_clocks[order_id] = merged_clock
        
        log_tools.debug(f"[Fraud Service] CheckCardFraud for order {order_id}: updated vector clock: {merged_clock}")
        response = fraud_detection.CheckFraudResponse()
        response.success = True
        response.reason = "Credit card data appears normal"
        response.updatedClock.extend(merged_clock)
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
