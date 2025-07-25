import pandas as pd
import time
import json
import os
from azure.eventhub import EventHubProducerClient, EventData
from dotenv import load_dotenv # To load environment variables from .env file

# --- Load Environment Variables ---
# This line looks for a .env file in the same directory and loads its contents
# as environment variables.
load_dotenv() 

# --- Configuration ---
# These variables are loaded from your .env file
EVENT_HUB_CONNECTION_STR = os.getenv("EVENT_HUB_CONNECTION_STR")
EVENT_HUB_NAME = os.getenv("EVENT_HUB_NAME")

# --- Path to your downloaded NASA Turbofan dataset ---
# Adjust this path if your 'CMaps' folder or 'train_FD001.txt' file
# is located differently relative to your script.
DATASET_PATH = 'CMaps/train_FD001.txt' 

# --- Define column names for the NASA Turbofan FD001 dataset ---
# There are 26 columns in train_FD001.txt.
# The RUL (Remaining Useful Life) is typically in a separate file (RUL_FD001.txt)
# and is a target for prediction, not a sensor measurement to stream.
# So, we define the 26 actual columns from the data file.
cols = ['unit_number', 'time_in_cycles', 'setting_1', 'setting_2', 'setting_3'] + \
       [f'sensor_{i}' for i in range(1, 22)] # This list now has exactly 26 names

# --- Simulation Parameters ---
# Adjust these to control the streaming rate and total messages for testing
MESSAGES_PER_SECOND = 10  # How many sensor readings to send per second
SEND_LIMIT = 5000         # Max messages to send for this demo (set to None for infinite stream)

# --- Load Data ---
try:
    # NASA Turbofan data is space-separated and has no header by default
    # sep='\s+' handles one or more whitespace characters as delimiters.
    # header=None indicates no header row in the file.
    # names=cols assigns our predefined column names.
    df = pd.read_csv(DATASET_PATH, sep='\s+', header=None, names=cols)
    
    # Optional: For initial testing, you might want to stream data from
    # a smaller subset of units to see faster cycles or specific behavior.
    # For example, streaming data for the first 5 unique engine units:
    df_to_stream = df[df['unit_number'] <= 5].copy() 
    print(f"Loaded {len(df)} rows from '{DATASET_PATH}'.")
    print(f"Streaming data for {df_to_stream['unit_number'].nunique()} units, total {len(df_to_stream)} rows for this demo.")
    
except FileNotFoundError:
    print(f"Error: Dataset not found at {DATASET_PATH}. Please ensure the 'CMaps' folder and 'train_FD001.txt' file are in the correct location relative to your script.")
    exit()
except Exception as e:
    print(f"Error loading or processing dataset: {e}")
    exit()

# --- Initialize Event Hubs Producer Client ---
# This client is responsible for sending events to your Event Hub.
producer = None
try:
    producer = EventHubProducerClient.from_connection_string(
        conn_str=EVENT_HUB_CONNECTION_STR,
        eventhub_name=EVENT_HUB_NAME
    )
    print("Event Hubs Producer Client initialized successfully.")
except Exception as e:
    print(f"Error initializing Event Hubs Producer: {e}")
    print("Please ensure EVENT_HUB_CONNECTION_STR and EVENT_HUB_NAME are correctly set as environment variables (e.g., in a .env file).")
    exit()

# --- Simulate Streaming of Sensor Data ---
print(f"Starting simulation. Sending up to {SEND_LIMIT if SEND_LIMIT else 'all available'} messages at {MESSAGES_PER_SECOND} messages/second...")
messages_sent = 0
start_time = time.time()

try:
    with producer: # 'with' statement ensures the client is properly closed
        # Iterate through the DataFrame (simulating incoming sensor readings)
        for index, row in df_to_stream.iterrows():
            if SEND_LIMIT is not None and messages_sent >= SEND_LIMIT:
                print(f"Send limit of {SEND_LIMIT} messages reached. Stopping simulation.")
                break

            # Create a JSON payload for the sensor reading.
            # Convert the entire Pandas Series (row) to a dictionary.
            # This will include unit_number, time_in_cycles, settings, and all 21 sensors.
            sensor_data = row.to_dict() 
            
            # Add unique message ID and current timestamp for real-time context.
            # Use .get() with a default to avoid KeyError if a field is unexpectedly missing
            sensor_data['message_id'] = f"msg_{messages_sent}_{sensor_data.get('unit_number', 'N/A')}_{sensor_data.get('time_in_cycles', 'N/A')}"
            sensor_data['event_timestamp'] = pd.Timestamp.now().isoformat() # ISO 8601 format

            # Create an EventData object from the JSON string.
            event_data = EventData(json.dumps(sensor_data))
            
            # Create a batch and add the event. Sending in batches is more efficient.
            event_data_batch = producer.create_batch()
            event_data_batch.add(event_data)

            # Send the batch of events to the Event Hub.
            producer.send_batch(event_data_batch)
            messages_sent += 1

            # Print status updates periodically
            if messages_sent % (MESSAGES_PER_SECOND * 5) == 0: # Update every 5 seconds of simulation
                print(f"Sent {messages_sent} messages. Last Unit: {sensor_data.get('unit_number')}, Cycle: {sensor_data.get('time_in_cycles')}")

            # Pause to simulate real-time intervals
            time.sleep(1 / MESSAGES_PER_SECOND) 

finally:
    end_time = time.time()
    duration = end_time - start_time
    print(f"\n--- Simulation Summary ---")
    print(f"Total messages sent: {messages_sent}")
    print(f"Simulation duration: {duration:.2f} seconds")
    print(f"Average messages/second: {messages_sent / duration:.2f}")
    if producer:
        producer.close()
        print("Event Hubs Producer Client closed.")