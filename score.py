# score.py
import os
import json
import joblib
import numpy as np
import pandas as pd
import logging 

model = None
scaler = None
scaled_feature_names = None

def init():
    global model, scaler, scaled_feature_names
    try:
        model_path = os.path.join(os.getenv("AZUREML_MODEL_DIR"), "anomaly_model.pkl")
        scaler_path = os.path.join(os.getenv("AZUREML_MODEL_DIR"), "scaler.pkl")
        scaled_feature_names_path = os.path.join(os.getenv("AZUREML_MODEL_DIR"), "scaled_feature_names.json")

        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path)

        with open(scaled_feature_names_path, 'r') as f:
            scaled_feature_names = json.load(f)

        logging.info("Model, scaler, and feature names loaded successfully for inference.")
    except Exception as e:
        logging.error(f"Error loading model artifacts: {e}")
        raise

def run(raw_data):
    try:
        data_dict = json.loads(raw_data)

        input_df = pd.DataFrame([data_dict]) 

        input_features = input_df[scaled_feature_names]

        scaled_input = scaler.transform(input_features)

        anomaly_score = model.decision_function(scaled_input)[0] 

        prediction = model.predict(scaled_input)[0]
        is_anomaly = True if prediction == -1 else False

        result = {
            "is_anomaly": is_anomaly,
            "anomaly_score": float(anomaly_score) 
        }
        logging.info(f"Prediction: {result}") 
        return json.dumps(result)

    except Exception as e:
        error_message = f"Error processing request: {e}"
        logging.error(error_message) 
        return json.dumps({"error": error_message})