# Documentation

This repository is a **distributed systems** practice project, demonstrating a **client-server** architecture with **multiple microservices**. The system simulates an **online bookstore** checkout flow, including **fraud detection**, **transaction verification**, and **book suggestions**. It uses **Flask** for the orchestrator (REST), **gRPC** for inter-service communication, **Docker** for containerization, and **Docker Compose** for orchestration.

---

## Overview

**ds-practice-2025** showcases:

- **Frontend:** A simple HTML/JS page to submit orders.
- **Orchestrator:** A Flask service that receives orders, generates a unique OrderID, and orchestrates parallel gRPC calls to backend services.
- **Fraud Detection:** Uses an ML model (or dummy logic) to evaluate if an order is suspicious. (Port 50051)
- **Transaction Verification:** Checks order data including items, user and billing info, and credit card details using vector clocks. (Port 50052)
- **Suggestions:** Generates book recommendations via an AI service (e.g., Cohere). (Port 50053)
- **Order Queue:** Maintains a priority queue of orders; orders are enqueued and later dequeued for processing. (Port 50055)
- **Order Executor:** Replicated service that uses leader election (Bully algorithm) to ensure only the designated leader dequeues and executes orders. (Port 50056)

---


## Key Features in This Checkpoint

- **Event Ordering:**  
  Services update a vector clock as events occur (e.g., transaction checks, fraud detection, suggestions), ensuring a coherent order of operations.

- **Leader Election:**  
  The Order Executor uses a Bully-style algorithm for leader election. Each executor (replica) has a unique `REPLICA_ID`, and the leader (if not already set) is determined among the replicas. The leader is responsible for dequeuing orders from the Order Queue.

- **Priority Order Queue:**  
  Orders are enqueued with a priority value (implemented with Python’s `PriorityQueue`), so that orders can be dequeued based on their priority.

- **Automatic Polling:**  
  The Order Executor automatically polls the Order Queue every 10 seconds to check for new orders. If the queue is empty, it logs the lack of available orders.

---

## Services

1. **Frontend**  
   - Simple HTML/JS page in `frontend/src/index.html`.  
   - Displays items, user form, and sends `POST /checkout` to the orchestrator on port **8081**.

2. **Orchestrator**  
   - A Flask-based REST service (`/checkout`) listening on port **5000** internally (exposed as **8081** on the host).  
   - Spawns threads to call the three microservices in parallel.

3. **Fraud Detection**  
   - A gRPC service on port **50051**.  
   - Loads an AI/ML model (Logistic Regression) to decide if an order is suspicious.  
   - Uses synthetic training data (`fraud_detection/ml_model.py`) or a dummy logic if not trained.

4. **Transaction Verification**  
   - A gRPC service on port **50052**.  
   - Checks credit card info, item count, and other basic “valid transaction” rules (e.g. `quantity > 0`).

5. **Suggestions**  
   - A gRPC service on port **50053**.  
   - Returns response from AI service (like Cohere/OpenAI) to generate book recommendations.

---

## Architecture

- **Frontend** runs on **port 8080**.  
- **Orchestrator** listens on **port 8081**.  
- **Fraud Detection**: port 50051, **Transaction**: 50052, **Suggestions**: 50053.  
- The Orchestrator calls each microservice via **gRPC**.

---

## Cohere API Key (for Suggestions)

1. **Sign up** for a free account (or log in) at [cohere.com](https://cohere.com/).
2. **Retrieve** your API key from the [Cohere Dashboard](https://dashboard.cohere.ai/).  
   - Look under **API Keys** or **Settings**.
3. **Set** the API key in your environment. For example, in `docker-compose.yaml` under the `suggestions` service:
   ```yaml
   services:
     suggestions:
       environment:
         - COHERE_API_KEY=your-secret-key-here
       ...

## System Flow

1. **User** fills the checkout form in **Frontend** (`localhost:8080`) and clicks **Submit**.
2. **Frontend** sends `POST /checkout` to **Orchestrator** (`localhost:8081`) with order data (items, credit card, etc.).
3. **Orchestrator** spawns **3 threads**:
   - Fraud detection (gRPC on port 50051).  
   - Transaction verification (gRPC on port 50052).  
   - Suggestions (gRPC on port 50053).  
4. Each microservice returns a result:
   - **Fraud**: `isFraud=True/False`, `reason=...`.
   - **Transaction**: `valid=True/False`, `reason=...`.
   - **Suggestions**: a list of recommended books.
5. **Orchestrator** aggregates:
   - If `isFraud=True` or `transaction_ok=False`, **reject**.  
   - Else, **approve** + attach suggestions.
6. **Orchestrator** returns final JSON to **Frontend** → user sees “Order Approved/Rejected” plus any suggestions.

---

## Setup and Run

### Prerequisites

- **Docker**  
- **Docker Compose**
- **Git**

### Steps

1. **Clone** the repo:
   ```bash
   git clone https://github.com/FooKaDoO/ds-practice-2025
   cd ds-practice-2025

   docker-compose build
   docker-compose up