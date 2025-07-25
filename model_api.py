# model_api.py
import os
import json
import joblib
import pandas as pd
import numpy as np
import logging
import time # For getting current timestamp for Datadog metrics
import asyncio # For running async tasks (sending metrics)

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import aiohttp # For making async HTTP requests to Datadog API
from dotenv import load_dotenv # Ensure this import is at the top

# Configure logging for the API. This will print messages to the terminal.
logging.basicConfig(level=logging.INFO, 
                            format='%(asctime)s - %(levelname)s - %(message)s')

# Define the directory where model artifacts are located.
MODEL_DIR = "models" 

# Global variables for model, scaler, and feature names.
model = None
scaler = None
scaled_feature_names = None
dd_http_session = None # Global aiohttp client session for Datadog API calls

# --- Datadog API Configuration (Declared globally, assigned in startup) ---
# These will be assigned their values from os.getenv inside the startup event
GLOBAL_DD_API_METRICS_URL = None
GLOBAL_DD_API_KEY_HEADER = None

# --- FastAPI Application Setup ---
app = FastAPI(title="IoT Anomaly Detection API",
              description="Real-time anomaly detection for IoT turbofan engine sensor data.")

# --- Pydantic Model for Input Data ---
class SensorDataInput(BaseModel):
    unit_number: float
    time_in_cycles: float
    setting_1: float
    setting_2: float
    setting_3: float
    sensor_1: float
    sensor_2: float
    sensor_3: float
    sensor_4: float
    sensor_5: float
    sensor_6: float
    sensor_7: float
    sensor_8: float
    sensor_9: float
    sensor_10: float
    sensor_11: float
    sensor_12: float
    sensor_13: float
    sensor_14: float
    sensor_15: float
    sensor_16: float
    sensor_17: float
    sensor_18: float
    sensor_19: float
    sensor_20: float
    sensor_21: float
    
    message_id: str = None
    event_timestamp: str = None

    class Config:
        extra = "allow" 

# --- API Startup Event ---
@app.on_event("startup")
async def load_artifacts_and_init_clients():
    """
    Load the pre-trained model, scaler, feature names, and initialize Datadog HTTP client.
    """
    global model, scaler, scaled_feature_names, dd_http_session, GLOBAL_DD_API_METRICS_URL, GLOBAL_DD_API_KEY_HEADER
    try:
        # --- Load environment variables explicitly here ---
        load_dotenv() 
        logging.info(".env file loaded during API startup.")

        # --- Assign global Datadog API credentials after dotenv is loaded ---
        GLOBAL_DD_API_METRICS_URL = os.getenv("DD_API_METRICS_URL")
        GLOBAL_DD_API_KEY_HEADER = os.getenv("DD_API_KEY_HEADER")

        if not all([GLOBAL_DD_API_METRICS_URL, GLOBAL_DD_API_KEY_HEADER]):
            logging.warning("Datadog API credentials (URL or Key) not found in .env. Metrics sending will be skipped.")
        else:
            logging.info("Datadog API credentials loaded successfully.")

        logging.info("Attempting to load model artifacts...")
        model_path = os.path.join(MODEL_DIR, "anomaly_model.pkl")
        scaler_path = os.path.join(MODEL_DIR, "scaler.pkl")
        scaled_feature_names_path = os.path.join(MODEL_DIR, "scaled_feature_names.json")

        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)
        with open(scaled_feature_names_path, 'r') as f:
            scaled_feature_names = json.load(f)
        
        logging.info("Model, scaler, and feature names loaded successfully.")

        # Initialize aiohttp ClientSession for Datadog API calls
        dd_http_session = aiohttp.ClientSession() 
        logging.info("aiohttp ClientSession for Datadog API initialized.")

    except Exception as e:
        logging.error(f"API startup failed: Could not load model artifacts or init clients. Error: {e}")
        raise RuntimeError(f"API startup failed: {e}")

# --- API Shutdown Event ---
@app.on_event("shutdown")
async def close_dd_session():
    """
    Close the Datadog aiohttp client session when the API shuts down.
    """
    global dd_http_session
    if dd_http_session:
        await dd_http_session.close()
        logging.info("aiohttp ClientSession for Datadog API closed.")

# --- Health Check Endpoint ---
@app.get("/health")
async def health_check():
    if model is not None and scaler is not None and scaled_feature_names is not None and dd_http_session is not None:
        return {"status": "healthy", "model_loaded": True, "message": "API is running and model artifacts are loaded."}
    else:
        raise HTTPException(status_code=500, detail="API is unhealthy: Model artifacts or clients not loaded.")

# --- Prediction Endpoint ---
@app.post("/predict")
async def predict_anomaly(data: SensorDataInput):
    try:
        logging.info(f"Received prediction request for unit {data.unit_number}, cycle {data.time_in_cycles}.")

        input_dict = data.dict()
        input_df = pd.DataFrame([input_dict])[scaled_feature_names] 

        scaled_input = scaler.transform(input_df)

        anomaly_score = float(model.decision_function(scaled_input)[0])
        prediction_value = model.predict(scaled_input)[0]
        is_anomaly = True if prediction_value == -1 else False

        response_data = {
            "is_anomaly": is_anomaly,
            "anomaly_score": anomaly_score,
            "unit_number": data.unit_number,
            "time_in_cycles": data.time_in_cycles,
            "event_timestamp": data.event_timestamp,
            "message_id": data.message_id 
        }
        
        logging.info(f"Prediction result: Unit {data.unit_number}, Cycle {data.time_in_cycles}, Anomaly: {is_anomaly}, Score: {anomaly_score:.4f}")

        # --- Send custom metrics directly to Datadog API ---
        # Use the GLOBAL variables for Datadog API credentials directly here
        # This bypasses any potential timing issues with the 'if' condition on globals
        metrics_payload = {
            "series": [
                {
                    "metric": "iot.anomaly.predictions.debug_total", 
                    "points": [[int(time.time()), 1]], 
                    "type": "count",
                    "tags": ["service:model_api", "env:local", "unit_number:{}".format(data.unit_number)]
                },
                {
                    "metric": "iot.anomaly.predictions.debug_anomaly", 
                    "points": [[int(time.time()), 1 if is_anomaly else 0]],
                    "type": "count", 
                    "tags": ["service:model_api", "env:local", "is_anomaly:{}".format(is_anomaly), "unit_number:{}".format(data.unit_number)]
                },
                {
                    "metric": "iot.anomaly.debug_score_distribution", 
                    "points": [[int(time.time()), anomaly_score]],
                    "type": "gauge", 
                    "tags": ["service:model_api", "env:local", "unit_number:{}".format(data.unit_number)]
                }
            ]
        }
        headers = { # Re-define headers here so GLOBAL_DD_API_KEY_HEADER is used directly
            "Content-Type": "application/json",
            "DD-API-KEY": GLOBAL_DD_API_KEY_HEADER # Use GLOBAL variable here
        }
        try:
            # Fire and forget: send the request in a background task
            # Check if dd_http_session is not None before using it
            if dd_http_session and GLOBAL_DD_API_METRICS_URL: # Only attempt if session and URL are truly available
                 asyncio.create_task(dd_http_session.post(GLOBAL_DD_API_METRICS_URL, headers=headers, json=metrics_payload, timeout=aiohttp.ClientTimeout(total=5)))
                 logging.info("Custom metrics sent to Datadog API.")
            else:
                 logging.warning("Datadog API credentials or session not properly initialized. Skipping metrics send.")

        except Exception as dd_e:
            logging.error(f"Failed to send metrics to Datadog API: {dd_e}")
            
        return response_data

    except Exception as e:
        error_message = f"Prediction failed for unit {data.unit_number}, cycle {data.time_in_cycles}: {e}"
        logging.error(error_message)
        raise HTTPException(status_code=500, detail=error_message)