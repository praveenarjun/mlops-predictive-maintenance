# test_dotenv_loading.py
import os
from dotenv import load_dotenv

print("--- Attempting to load .env file ---")
# load_dotenv() returns True if it successfully loads, False otherwise
# Set override=True to force loading even if already loaded or env var exists
load_success = load_dotenv(override=True) 
print(f"load_dotenv() returned: {load_success}")

print("\n--- Checking loaded environment variables ---")
eh_conn_str = os.getenv("EVENT_HUB_CONNECTION_STR")
eh_name = os.getenv("EVENT_HUB_NAME")
cosmos_uri = os.getenv("COSMOS_DB_URI")
cosmos_key = os.getenv("COSMOS_DB_KEY")

print(f"EVENT_HUB_CONNECTION_STR is {'Loaded' if eh_conn_str else 'NOT LOADED'}")
print(f"EVENT_HUB_NAME is {'Loaded' if eh_name else 'NOT LOADED'}")
print(f"COSMOS_DB_URI is {'Loaded' if cosmos_uri else 'NOT LOADED'}")
print(f"COSMOS_DB_KEY is {'Loaded' if cosmos_key else 'NOT LOADED'}")

if cosmos_uri:
    print(f"COSMOS_DB_URI value (first 10 chars): {cosmos_uri[:10]}")
if cosmos_key:
    print(f"COSMOS_DB_KEY value (first 10 chars): {cosmos_key[:10]}")
    print(f"COSMOS_DB_KEY value (last 10 chars): {cosmos_key[-10:]}")

print("\n--- Diagnostic Complete ---")