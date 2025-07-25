import os
import asyncio
import json
import logging
import time # Needed for Datadog metric timestamps
from azure.eventhub.aio import EventHubConsumerClient
from azure.cosmos.aio import CosmosClient 
from azure.cosmos import exceptions
from dotenv import load_dotenv 
import aiohttp 

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger("azure").setLevel(logging.WARNING) 

# --- Global Clients and Config Variables (initialized to None) ---
eventhub_client = None
cosmos_client = None
cosmos_container = None 
http_session = None # Shared aiohttp client session for both model API and Datadog API calls

# --- Global Datadog API Config Variables ---
# These will be set inside initialize_clients() and then accessed globally.
GLOBAL_DD_API_METRICS_URL = None
GLOBAL_DD_API_KEY_HEADER = None

async def initialize_clients():
    """Initializes Event Hub, Cosmos DB, and HTTP clients."""
    global eventhub_client, cosmos_client, cosmos_container, http_session, GLOBAL_DD_API_METRICS_URL, GLOBAL_DD_API_KEY_HEADER

    # --- Configuration - Get env vars INSIDE this function ---
    # These are local variables within this function's scope
    eh_connection_str = os.getenv("EVENT_HUB_CONNECTION_STR")
    eh_name = os.getenv("EVENT_HUB_NAME")
    eh_consumer_group = os.getenv("EVENT_HUB_CONSUMER_GROUP", "$Default") 
    
    cosmos_uri = os.getenv("COSMOS_DB_URI")
    cosmos_key = os.getenv("COSMOS_DB_KEY")
    cosmos_db_database_id = "iot-sensor-db"
    cosmos_db_container_id = "anomalies"

    ml_endpoint_url_check = os.getenv("ML_ENDPOINT_URL")

    # --- Assign Datadog env vars to GLOBAL variables ---
    GLOBAL_DD_API_METRICS_URL = os.getenv("DD_API_METRICS_URL")
    GLOBAL_DD_API_KEY_HEADER = os.getenv("DD_API_KEY_HEADER")

    # --- Debugging: Check if ALL env vars are loaded ---
    if not all([eh_connection_str, eh_name, cosmos_uri, cosmos_key, ml_endpoint_url_check, GLOBAL_DD_API_METRICS_URL, GLOBAL_DD_API_KEY_HEADER]):
        missing_vars = [v for v, val in {
            "EVENT_HUB_CONNECTION_STR": eh_connection_str, 
            "EVENT_HUB_NAME": eh_name, 
            "COSMOS_DB_URI": cosmos_uri, 
            "COSMOS_DB_KEY": cosmos_key,
            "ML_ENDPOINT_URL": ml_endpoint_url_check,
            "DD_API_METRICS_URL": GLOBAL_DD_API_METRICS_URL,
            "DD_API_KEY_HEADER": GLOBAL_DD_API_KEY_HEADER
        }.items() if not val]
        logging.critical(f"ERROR: Missing environment variables: {', '.join(missing_vars)}. Check .env file.")
        return False
    
    logging.info("Attempting to initialize Event Hub Consumer Client...")
    try:
        eventhub_client = EventHubConsumerClient.from_connection_string(
            conn_str=eh_connection_str, # Use local variable
            consumer_group=eh_consumer_group, # Use local variable
            eventhub_name=eh_name # Use local variable
        )
        logging.info("Event Hub Consumer Client initialized.")
    except Exception as e:
        logging.critical(f"CRITICAL ERROR: Failed to initialize Event Hub Consumer Client: {e}")
        eventhub_client = None
        return False

    logging.info("Attempting to initialize Cosmos DB Client...")
    try:
        cosmos_client = CosmosClient(cosmos_uri, credential=cosmos_key) # Use local variables
        database_proxy = cosmos_client.get_database_client(cosmos_db_database_id) # Use local variable
        cosmos_container = database_proxy.get_container_client(cosmos_db_container_id) # Use local variable
        logging.info(f"Cosmos DB client initialized for {cosmos_db_database_id}/{cosmos_db_container_id}") # Use local variables
    except exceptions.CosmosResourceNotFoundError as e:
        logging.critical(f"CRITICAL ERROR: Cosmos DB resource not found: {e}. Please ensure database and container exist and names are correct.")
        cosmos_client = None
        cosmos_container = None
        return False
    except Exception as e:
        logging.critical(f"CRITICAL ERROR: Failed to initialize Cosmos DB client: {e}")
        cosmos_client = None
        cosmos_container = None
        return False
    
    # --- Initialize aiohttp client session (shared for ML API and Datadog API) ---
    logging.info("Attempting to initialize aiohttp ClientSession...")
    try:
        http_session = aiohttp.ClientSession() 
        logging.info("aiohttp ClientSession initialized.")
    except Exception as e:
        logging.critical(f"CRITICAL ERROR: Failed to initialize aiohttp session: {e}")
        http_session = None
        return False

    return True # All clients initialized successfully

async def process_event_batch(partition_context, events):
    """Processes a batch of events from Event Hubs."""
    logging.info(f"Received batch of {len(events)} events from partition {partition_context.partition_id}.")
    
    processed_records = []
    if not cosmos_container:
        logging.warning("Cosmos DB container not available. Skipping record persistence for this batch.")
        return 

    ML_ENDPOINT_URL = os.getenv("ML_ENDPOINT_URL") # This needs to be fetched here or passed as param
    
    headers = {"Content-Type": "application/json"}
    # If your local API had authentication, add headers here:
    # ML_ENDPOINT_KEY = os.getenv("ML_ENDPOINT_KEY")
    # if ML_ENDPOINT_KEY and ML_ENDPOINT_KEY != "N/A":
    #    headers["Authorization"] = f"Bearer {ML_ENDPOINT_KEY}" 

    if not ML_ENDPOINT_URL or not http_session:
        logging.critical("ML Endpoint URL or HTTP session not available. Cannot perform anomaly prediction via API.")
        return 

    for event in events:
        try:
            event_body = event.body_as_str()
            sensor_data = json.loads(event_body)

            # --- Debugging: Inspect incoming data (can be removed after verification) ---
            # logging.debug(f"DEBUG: Incoming sensor_data keys: {list(sensor_data.keys())}") 
            # logging.debug(f"DEBUG: Sample sensor_data content (first 500 chars): {json.dumps(sensor_data, indent=2)[:500]}...") 
            # --- End Debugging ---

            is_anomaly = False 
            anomaly_score = 0.0 

            # Prepare data for API call (matches SensorDataInput Pydantic model in model_api.py)
            api_input_data = sensor_data.copy()
            if 'raw_message_id' in api_input_data: del api_input_data['raw_message_id']
            if 'raw_data_sample' in api_input_data: del api_input_data['raw_data_sample']
            if 'sensor_2_value' in api_input_data: del api_input_data['sensor_2_value'] 

            try:
                async with http_session.post(ML_ENDPOINT_URL, headers=headers, json=api_input_data, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    response.raise_for_status() 
                    api_response = await response.json()
                    
                    is_anomaly = api_response.get("is_anomaly", False)
                    anomaly_score = api_response.get("anomaly_score", 0.0)
                    
                    logging.info(f"API Prediction for unit {sensor_data.get('unit_number')}, cycle {sensor_data.get('time_in_cycles')}: Anomaly: {is_anomaly}, Score: {anomaly_score:.4f}")

            except aiohttp.ClientError as api_e:
                logging.error(f"API call to ML endpoint failed for unit {sensor_data.get('unit_number')}, cycle {sensor_data.get('time_in_cycles')}: {api_e}")
                is_anomaly = False 
                anomaly_score = -999.0 
                logging.warning("Falling back to default anomaly status due to API failure.")
            except Exception as e_api:
                logging.error(f"Unexpected error during API call for unit {sensor_data.get('unit_number')}, cycle {sensor_data.get('time_in_cycles')}: {e_api}")
                is_anomaly = False
                anomaly_score = -999.0 
            
            # --- Construct the record to save to Cosmos DB ---
            record_to_save = sensor_data.copy()
            
            record_to_save["id"] = f"{sensor_data.get('unit_number')}-{sensor_data.get('time_in_cycles')}-{sensor_data.get('event_timestamp')}-{sensor_data.get('message_id')}"
            record_to_save["is_anomaly"] = is_anomaly 
            record_to_save["anomaly_score"] = anomaly_score 
            
            record_to_save["unit_number"] = sensor_data.get('unit_number')

            if "raw_message_id" in record_to_save: del record_to_save["raw_message_id"]
            if "raw_data_sample" in record_to_save: del record_to_save["raw_data_sample"]
            if "sensor_2_value" in record_to_save: del record_to_save["sensor_2_value"] 
            
            processed_records.append(record_to_save)

            logging.info(f"Processed unit {sensor_data.get('unit_number')}, cycle {sensor_data.get('time_in_cycles')}. Anomaly from API: {is_anomaly}, Score: {anomaly_score:.4f}")

            # --- Send Custom Metrics to Datadog API (from consumer) ---
            if GLOBAL_DD_API_METRICS_URL and GLOBAL_DD_API_KEY_HEADER and http_session: # Use GLOBAL vars
                metrics_payload = {
                    "series": [
                        {
                            "metric": "iot.consumer.events_processed",
                            "points": [[int(time.time()), 1]], 
                            "type": "count",
                            "tags": ["service:event_consumer", "env:local", "unit_number:{}".format(sensor_data.get('unit_number'))]
                        },
                        {
                            "metric": "iot.consumer.writes_to_cosmos_db",
                            "points": [[int(time.time()), 1]], 
                            "type": "count",
                            "tags": ["service:event_consumer", "env:local", "unit_number:{}".format(sensor_data.get('unit_number'))]
                        }
                    ]
                }
                headers_dd = { 
                    "Content-Type": "application/json",
                    "DD-API-KEY": GLOBAL_DD_API_KEY_HEADER # Use GLOBAL var
                }
                try:
                    asyncio.create_task(http_session.post(GLOBAL_DD_API_METRICS_URL, headers=headers_dd, json=metrics_payload, timeout=aiohttp.ClientTimeout(total=5)))
                    logging.info("Custom consumer metrics sent to Datadog API.")
                except Exception as dd_e:
                    logging.error(f"Failed to send consumer metrics to Datadog API: {dd_e}")
            else:
                logging.warning("Datadog API credentials or session not available for consumer. Skipping metrics send.")

        except Exception as e:
            logging.error(f"Error processing event: {e}. Event body: {event_body[:200]}...")
    
    # --- Write processed records to Cosmos DB ---
    if cosmos_container and processed_records: 
        try:
            for record in processed_records:
                await cosmos_container.upsert_item(body=record) 
            logging.info(f"Successfully wrote {len(processed_records)} records to Cosmos DB.")
        except Exception as e:
            logging.error(f"Error writing to Cosmos DB: {e}")
    else:
        logging.warning(f"Skipped writing {len(processed_records)} records to Cosmos DB because client or container was not initialized.")
    
    # --- Checkpointing: Update Event Hubs offset ---
    if events: 
        await partition_context.update_checkpoint(events[-1]) 

async def main():
    """Main function to run the Event Hubs consumer."""
    load_dotenv()

    local_event_hub_name = os.getenv("EVENT_HUB_NAME")
    local_consumer_group = os.getenv("EVENT_HUB_CONSUMER_GROUP", "$Default")

    local_ml_endpoint_url = os.getenv("ML_ENDPOINT_URL")

    if not await initialize_clients():
        logging.critical("Client initialization failed. Exiting main.")
        return

    if not eventhub_client:
        logging.critical("Event Hub client not available after initialization. Exiting.")
        return

    async with eventhub_client:
        logging.info(f"Starting to receive events from Event Hub '{local_event_hub_name}' consumer group '$Default'...") # Use $Default as defined
        if local_ml_endpoint_url: 
            logging.info(f"Anomaly predictions will be obtained from ML Endpoint: {local_ml_endpoint_url}")
        else:
            logging.warning("ML_ENDPOINT_URL not set in .env. Anomaly prediction via API will be skipped.")

        try:
            await eventhub_client.receive_batch(
                on_event_batch=process_event_batch,
                max_batch_size=100, 
                max_wait_time=5,    
                starting_position="-1", 
            )
        except Exception as e:
            logging.critical(f"CRITICAL ERROR during event reception: {e}")

# --- Entry Point for Script Execution ---
if __name__ == "__main__":
    try:
        logging.info("Starting consumer script...")
        asyncio.run(main()) 
    except KeyboardInterrupt:
        logging.info("Consumer stopped by user (KeyboardInterrupt).")
    except Exception as e:
        logging.critical(f"Unhandled exception in main execution: {e}")
    finally:
        logging.info("Shutting down clients.")
        async def close_clients_async():
            if eventhub_client:
                logging.info("Closing Event Hub Consumer Client...")
                await eventhub_client.close()
            if cosmos_client:
                logging.info("Closing Cosmos DB Client...")
                await cosmos_client.close()
            if http_session: 
                logging.info("Closing aiohttp ClientSession...")
                await http_session.close()
        asyncio.run(close_clients_async())