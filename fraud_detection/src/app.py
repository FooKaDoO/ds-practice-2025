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

microservice_path = os.path.abspath(os.path.join(FILE, '../../../utils/microservice'))
sys.path.insert(0, microservice_path)
from microservice import MicroService

import pandas as pd
import grpc
from concurrent import futures

# Load model & scaler
model_path = "/app/fraud_detection/model/fraud_model.pkl"
scaler_path = "/app/fraud_detection/model/scaler.pkl"



if os.path.exists(model_path) and os.path.exists(scaler_path):
    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    log_tools.info("[Fraud Service] AI-based fraud detection model loaded successfully!")
    
else:
    # Log to console for debugging
    log_tools.warn("[Fraud Service] Model not found! Train the model first.")
    model, scaler = None, None


class FraudDetectionServiceServicer(fraud_detection_grpc.FraudDetectionServiceServicer, MicroService):

    @log_tools.log_decorator("Fraud Service")
    def InitOrder(self, request, context):
        response = fraud_detection.InitOrderConfirmationResponse()
        
        self.init_order(request.order_id, request.order_data)

        response.isCreated = True
        return response     


    """
    Implements the FraudDetectionService from our .proto.
    """
    @log_tools.log_decorator("Fraud Service")
    def CheckOrder(self, request, context):
        """
        Decide whether an order is fraudulent based on:
        1. totalAmount (float)
        2. number of items (derived from repeated Item)
        3. past_fraudulent_orders (dummy set to 0 here)
        """

        # 1️⃣ Prepare a response object
        response = fraud_detection.CheckOrderResponse()

        # 2️⃣ Extract fields from the request
        order_id = request.order_id

        entry = self.orders[order_id]
        
        total_amount = 0
        for item in entry["order_data"].items:
            total_amount += 10 * item.quantity

        # Sum up all quantities
        item_count = sum(item.quantity for item in entry["order_data"].items)

        # 3️⃣ Build a DataFrame with the columns your model was trained on
        #    - "amount"   => matches "amount" in your training code
        #    - "num_items" => matches "num_items" in training
        #    - "past_fraudulent_orders" => dummy = 0
        features = [[total_amount, item_count, 0]]
        features_df = pd.DataFrame(features, columns=["amount", "num_items", "past_fraudulent_orders"])

        # 4️⃣ Standardize + predict
        log_tools.debug("[Fraud Service] Checking, if order is fraudulent.")
        features_scaled = scaler.transform(features_df)
        prediction = model.predict(features_scaled)[0]
        is_fraud = bool(prediction)

        # 5️⃣ Set response fields
        response.isFraud = is_fraud

        response.reason = "Suspicious transaction" if is_fraud else "Looks OK"

        # 6️⃣ Debug logs (optional)
        log_tools.debug(f"[Fraud Service] CheckOrder => totalAmount={total_amount}, itemCount={item_count}")
        log_tools.debug(f"[Fraud Service] Fraud result => isFraud={is_fraud}, reason={response.reason}")

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
