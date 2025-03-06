# Documentation

This repository is a **distributed systems** practice project, demonstrating a **client-server** architecture with **multiple microservices**. The system simulates an **online bookstore** checkout flow, including **fraud detection**, **transaction verification**, and **book suggestions**. It uses **Flask** for the orchestrator (REST), **gRPC** for inter-service communication, **Docker** for containerization, and **Docker Compose** for orchestration.

## Overview

**ds-practice-2025** showcases:

- **Frontend** (HTML + JavaScript) sending orders via REST to an **Orchestrator**.
- The **Orchestrator** spawns **threads** to call:
  - **Fraud Detection** microservice (AI-based).
  - **Transaction Verification** microservice (basic transaction checks).
  - **Suggestions** microservice (static or AI-based book suggestions).
- The microservices communicate with the orchestrator via **gRPC**.
- The final result (approved/rejected) plus any suggestions is returned to the user.

---

## Services

1. **Frontend**  
   - Simple HTML/JS page in `frontend/src/index.html`.  
   - Displays items, user form, and sends `POST /checkout` to the orchestrator on port **8081** (mapped from 5000).

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
   - Either returns static suggestions or calls an AI service (like Cohere/OpenAI) to generate book recommendations.

---

## Architecture

- **Frontend** runs on **port 8080**.  
- **Orchestrator** listens on **port 8081** externally (5000 internally).  
- **Fraud Detection**: port 50051, **Transaction**: 50052, **Suggestions**: 50053.  
- The Orchestrator calls each microservice via **gRPC**.

---

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