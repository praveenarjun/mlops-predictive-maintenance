import logging
import json
import os
import azure.functions as func
from azure.cosmos import CosmosClient, exceptions

# --- Cosmos DB Configuration (Loaded from Application Settings in Azure) ---
COSMOS_DB_URI = os.getenv("CosmosDbUri")
COSMOS_DB_KEY = os.getenv("CosmosDbKey")
COSMOS_DB_DATABASE_ID = "iot-sensor-db"
COSMOS_DB_CONTAINER_ID = "anomalies"

# Initialize Cosmos DB client globally to reuse connection
cosmos_client = None
try:
    if COSMOS_DB_URI and COSMOS_DB_KEY:
        cosmos_client = CosmosClient(COSMOS_DB_URI, credential=COSMOS_DB_KEY)
        logging.info("Cosmos DB client initialized. Will get database/container client per batch.")
    else:
        logging.warning("Cosmos DB credentials not found. Cosmos DB writes will be skipped.")
except Exception as e:
    logging.error(f"Error initializing Cosmos DB client: {e}")
    cosmos_client = None

# Initialize the FunctionApp instance
app = func.FunctionApp()

# Define the Event Hub Trigger function using a decorator
@app.event_hub_message_trigger(arg_name="events",
                               event_hub_name="iot-sensor-data-stream",
                               connection="EventHubConnection", # This refers to an app setting
                               cardinality="many") # Process messages in batches
def ConsumeEventHubData(events: list[func.EventHubEvent]):
    logging.info(f'Python EventHub trigger function processed {len(events)} events.')

    processed_records = []
    current_container = None
    if cosmos_client:
        try:
            database = cosmos_client.get_database_client(COSMOS_DB_DATABASE_ID)
            current_container = database.get_container_client(COSMOS_DB_CONTAINER_ID)
        except exceptions.CosmosResourceNotFoundError:
            logging.error(f"Cosmos DB database '{COSMOS_DB_DATABASE_ID}' or container '{COSMOS_DB_CONTAINER_ID}' not found.")
            current_container = None
        except Exception as e:
            logging.error(f"Error getting Cosmos DB container client: {e}")
            current_container = None

    for event in events:
        try:
            # 1. Parse the incoming JSON message
            event_body = event.get_body().decode('utf-8')
            sensor_data = json.loads(event_body)

            # 2. Extract features (example: use sensor_2 value from NASA Turbofan)
            sensor_value_to_monitor = sensor_data.get('sensor_2')
            machine_id = sensor_data.get('unit_number')
            time_in_cycles = sensor_data.get('time_in_cycles')
            event_timestamp = sensor_data.get('event_timestamp') 

            # --- 3. Anomaly Detection Logic (Placeholder for now) ---
            is_anomaly = False
            anomaly_score = 0.0 

            # Example: A simple rule - if sensor_2 is very high, consider it an anomaly
            # Adjust threshold based on your data's sensor_2 range or observed anomalies
            if sensor_value_to_monitor is not None and isinstance(sensor_value_to_monitor, (int, float)) and sensor_value_to_monitor > 800: 
                is_anomaly = True
                anomaly_score = float(sensor_value_to_monitor) 

            # 4. Prepare record for Cosmos DB
            # Ensure 'id' field is unique and 'unit_number' matches your partition key
            record_to_save = {
                "id": f"{machine_id}-{time_in_cycles}-{event_timestamp}-{sensor_data.get('message_id')}", 
                "unit_number": machine_id,  # This is your partition key, MUST be present
                "time_in_cycles": time_in_cycles,
                "event_timestamp": event_timestamp,
                "sensor_2_value": sensor_value_to_monitor,
                "is_anomaly": is_anomaly,
                "anomaly_score": anomaly_score,
                "raw_message_id": sensor_data.get('message_id'),
                "raw_data_sample": {k: sensor_data[k] for k in list(sensor_data.keys())[:5] if k in sensor_data} # Save a small sample
            }
            processed_records.append(record_to_save)

            logging.info(f"Processed unit {machine_id}, cycle {time_in_cycles}. Sensor 2: {sensor_value_to_monitor}. Anomaly: {is_anomaly}")

        except Exception as e:
            logging.error(f"Error processing event: {e}. Event body: {event.get_body().decode('utf-8')[:200]}...")

    # 5. Write to Cosmos DB (if client and container are initialized)
    if current_container and processed_records:
        try:
            # Batch insert is more efficient for multiple items
            # Cosmos DB allows batching using bulk operations, but for simplicity here,
            # we'll use upsert_item in a loop.
            for record in processed_records:
                current_container.upsert_item(body=record) 
            logging.info(f"Successfully wrote {len(processed_records)} records to Cosmos DB.")
        except Exception as e:
            logging.error(f"Error writing to Cosmos DB: {e}")
    elif not current_container:
        logging.warning(f"Skipped writing {len(processed_records)} records to Cosmos DB because client or container was not initialized.")