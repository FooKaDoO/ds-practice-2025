import os
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

def generate_data(n_samples=1000, random_seed=42):
    """
    Generates synthetic data that correlates large amounts, higher item counts, 
    and past fraudulent orders with a greater chance of fraud—without hardcoding 
    any specific threshold in the inference code.
    
    Features:
      - amount (float): 1..600
      - num_items (int): 1..20
      - past_fraudulent_orders (int): 0..4
    is_fraud is assigned by a probability function that 
    increases with amount, num_items, and past_fraudulent_orders.
    """
    np.random.seed(random_seed)

    amounts = np.random.uniform(1, 600, n_samples)             # 1..600
    num_items = np.random.randint(1, 20, n_samples)            # 1..20
    past_fraud = np.random.randint(0, 5, n_samples)            # 0..4

    is_fraud = []
    for i in range(n_samples):
        # Base probability of fraud
        base_prob = 0.05  

        # More items => higher chance
        prob_from_items = 0.01 * (num_items[i] - 1)  # +1% per item over 1

        # Larger amount => higher chance
        prob_from_amount = 0.0008 * amounts[i]       # ~ +0.08% per 100 amount

        # Past fraud => higher chance
        prob_from_past = 0.07 * past_fraud[i]        # +7% per past fraud count

        # Combine probabilities (simple additive approach)
        total_prob = base_prob + prob_from_items + prob_from_amount + prob_from_past
        # Bound it [0,1]
        total_prob = min(1.0, max(0.0, total_prob))

        # Draw from distribution
        label = 1 if np.random.rand() < total_prob else 0
        is_fraud.append(label)

    data = {
        "amount": amounts,
        "num_items": num_items,
        "past_fraudulent_orders": past_fraud,
        "is_fraud": is_fraud
    }
    return pd.DataFrame(data)

def train_model():
    df = generate_data(n_samples=1500)  # You can tweak sample size

    # Features & Labels
    X = df[["amount", "num_items", "past_fraudulent_orders"]]
    y = df["is_fraud"]

    # Train/Test split
    X_train, X_test, y_train, y_test = train_test_split(X, y, 
                                                        test_size=0.2, 
                                                        random_state=42)

    # Standardize features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Train logistic regression
    model = LogisticRegression()
    model.fit(X_train_scaled, y_train)

    # Ensure the model directory exists
    model_dir = "/app/fraud_detection/model"
    os.makedirs(model_dir, exist_ok=True)

    # Save model & scaler
    joblib.dump(model, f"{model_dir}/fraud_model.pkl")
    joblib.dump(scaler, f"{model_dir}/scaler.pkl")

    print("Fraud detection model trained and saved!")
    print(f"Dataset shape: {df.shape}, Frauds: {df['is_fraud'].sum()}")

if __name__ == "__main__":
    train_model()
