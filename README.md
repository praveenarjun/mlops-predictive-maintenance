# Real-time IoT Anomaly Detection for Predictive Maintenance

## Project Overview
This project implements an end-to-end MLOps pipeline for real-time anomaly detection in IoT sensor data, designed to support predictive maintenance strategies in industrial settings. It demonstrates capabilities in data streaming, machine learning, model serving, and cloud integration.

## Business Problem
Unforeseen equipment failures in manufacturing or industrial settings lead to costly downtime, production losses, and increased maintenance expenses. Traditional reactive maintenance is inefficient. This project aims to provide an early warning system by identifying anomalous sensor readings, enabling proactive interventions.

## Architecture
(Draw or describe your architecture clearly here. You can use simple text, or draw a diagram and upload it to your repo, then link it.
Example text description of your architecture:
- **Data Source Simulation:** `stream_data.py` simulates IoT sensor data streams (from NASA Turbofan engines).
- **Real-time Ingestion:** Data is ingested into **Azure Event Hubs**, a high-throughput messaging service.
- **Real-time Processing & ML Inference:** A Python consumer script (`event_consumer.py`) continuously reads from Event Hubs. It sends incoming sensor data to a local **FastAPI Model API** for real-time anomaly prediction and persists enriched data to **Azure Cosmos DB**.
- **Model Serving:** The FastAPI API (`model_api.py`) loads a pre-trained Isolation Forest model and serves predictions via a REST endpoint.
- **Data Persistence:** **Azure Cosmos DB** stores all processed sensor readings, including anomaly flags and scores, for historical analysis and downstream applications.
- **Monitoring (Direct API Integration):** Both the `model_api.py` and `event_consumer.py` send custom application metrics directly to **Datadog's API** for real-time observability.
)

## Technologies Used
* **Python:** Core programming language.
* **Machine Learning:** `scikit-learn` (Isolation Forest for anomaly detection).
* **Data Processing:** `Pandas`, `NumPy`.
* **Real-time Stream Ingestion:** Azure Event Hubs.
* **NoSQL Database:** Azure Cosmos DB (for processed data persistence).
* **API Framework:** `FastAPI` (for model serving).
* **Asynchronous I/O:** `uvicorn`, `aiohttp`.
* **Monitoring:** `Datadog` (direct API integration for custom metrics).
* **Version Control:** Git & GitHub.
* **Environment Management:** Conda/Micromamba.
* **(Optional for Docker):** Docker, Docker Compose (if you successfully ran this locally and want to mention the attempt/plan).

## Setup and Running the Project
**(Provide clear, concise instructions for someone to get your project running. Adjust based on what you want to enable/disable for a quick demo.)**

1.  **Prerequisites:**
    * Python 3.11 (via Conda/Micromamba recommended).
    * Azure Account (Azure for Students).
    * Datadog Account (GitHub Student Pack benefits).
    * (Optional if you use Docker Compose locally for a full demo, if it worked for you): Docker Desktop installed and running.

2.  **Azure Resource Setup:**
    * Create a Resource Group (e.g., `iot-anomaly-rg`).
    * Create an Azure Event Hubs Namespace and Event Hub instance (e.g., `iot-sensor-data-stream`).
    * Create an Azure Cosmos DB account (NoSQL API, Serverless), database (e.g., `iot-sensor-db`), and container (e.g., `anomalies` with `/unit_number` as partition key).
    * **Crucial:** Add a composite index on `unit_number` and `time_in_cycles` in Cosmos DB for efficient querying.
    <img width="2868" height="1444" alt="Screenshot 2025-07-23 at 4 28 21 PM" src="https://github.com/user-attachments/assets/6bf10ce0-598d-40e5-8301-3280e5f716fd" />

3.  **Local Environment Setup:**
    * Clone this repository: `git clone https://github.com/your-username/your-repo-name.git`
    * Navigate into the project directory: `cd your-repo-name`
    * Create and activate a Conda environment: `conda create -n iot_ad_env python=3.11 && conda activate iot_ad_env`
    * Install Python dependencies: `pip install pandas numpy scikit-learn fastapi uvicorn pydantic aiohttp azure-eventhub azure-cosmos python-dotenv joblib`
    * Set up your `.env` file with Azure Event Hubs, Cosmos DB, and Datadog API credentials (refer to `.env.example` if you create one, but don't commit your actual `.env` file).

4.  **Generate Model Artifacts:**
    * Run the Jupyter Notebook: `/path/to/your/jupyter/lab anomaly_model_training.ipynb`
    * Execute Cells 1-7 to train the anomaly detection model and save `anomaly_model.pkl`, `scaler.pkl`, `scaled_feature_names.json` into the `models/` directory.

5.  **Run the Pipeline (Manual Local Orchestration):**
    * **Terminal 1 (Model API):** `uvicorn model_api:app --host 0.0.0.0 --port 8000`
    <img width="1818" height="448" alt="Screenshot 2025-07-23 at 4 26 57 PM" src="https://github.com/user-attachments/assets/49368253-1e64-44f0-b25b-7b376f2ac711" />
    * **Terminal 2 (Event Consumer):** `/path/to/your/python event_consumer.py`
     <img width="1832" height="506" alt="Screenshot 2025-07-23 at 4 26 50 PM" src="https://github.com/user-attachments/assets/ecd1a734-7383-4855-bb8c-2340cb11c804" />
    * **Terminal 3 (Data Streamer):** `/path/to/your/python stream_data.py`
      <img width="1304" height="970" alt="Screenshot 2025-07-23 at 4 27 09 PM" src="https://github.com/user-attachments/assets/144b1b19-11fb-412b-91fc-36e54d5f4db1" />


6.  **Verify Results:**
    * Observe logs in terminals for processing and API calls.
    * Check Azure Cosmos DB Data Explorer for new items with anomaly predictions.
    * Check Datadog Metrics Explorer for custom metric graphs (e.g., `iot.anomaly.predictions.total`).


## Results and Findings
(Summarize what the pipeline achieves and the insights it provides, as discussed previously)
This project successfully demonstrates a real-time, end-to-end MLOps pipeline capable of processing streaming IoT sensor data, performing machine learning inference for anomaly detection, and persisting actionable results. The system effectively identifies deviations from normal operating conditions, providing early warning capabilities crucial for predictive maintenance. Custom application metrics are actively streamed to Datadog for observability.
<img width="2856" height="1526" alt="Screenshot 2025-07-23 at 4 30 39 PM" src="https://github.com/user-attachments/assets/63f6a2a9-cebc-495e-9a09-2867ce2eb67e" />
<img width="2878" height="676" alt="Screenshot 2025-07-23 at 4 28 38 PM" src="https://github.com/user-attachments/assets/aa4af380-0343-4dad-bc01-a79bbd72ac4a" />
<img width="2536" height="1358" alt="Screenshot 2025-07-23 at 1 38 23 PM" src="https://github.com/user-attachments/assets/fda8bc17-fef4-4e20-84fc-a3a9935a29d0" />

## Challenges Faced & Solutions
**(THIS SECTION IS KEY FOR INTERVIEWS. Be honest, detailed, and focus on your problem-solving process.)**
* **Persistent `NaN`s in Ingested Data:** Initially, a portion of streamed sensor data arrived with missing values in Cosmos DB due to subtle issues in JSON object construction and merging within the processing layer.
    * **Solution:** Conducted rigorous multi-stage debugging, utilizing `logging.debug` and manual Cosmos DB item inspection, leading to a robust `record_to_save = sensor_data.copy()` approach in `event_consumer.py` that guarantees all incoming data is preserved and correctly structured.
* **Azure ML SDK & Docker Deployment Blockers:** Encountered `ModuleNotFoundError` (`resolution-too-deep` from `pip`) for `azureml-sdk` in the local Conda environment, followed by `docker compose` failing to build images reliably (connection errors, no active builds in GUI).
    * **Strategic Pivot:** Rather than spending days on intractable local environment/tooling issues, strategically decided to **pivot away from Azure ML cloud deployment and Docker Compose orchestration** for the immediate project delivery.
    * **Alternative Solution:** Implemented **local ML model serving using FastAPI/Uvicorn** and **manual orchestration of local Python scripts**. This demonstrated core MLOps principles (model serving, real-time inference) while ensuring project completion. This showcased adaptability, pragmatic decision-making under pressure, and understanding of diverse deployment patterns.
* **Datadog Agent Installation Failures & Metric Ingestion Delays:** Faced persistent `404 Not Found` errors for `curl` install scripts and `brew install` quirks for the Datadog Agent, preventing local agent setup. Additionally, initial custom metrics sent via API were slow to appear in the Datadog UI.
    * **Solution:** Pivoted to **direct Datadog API integration** from `model_api.py` and `event_consumer.py`, bypassing the local agent. Utilized `asyncio.create_task` and `aiohttp` for non-blocking metric submission. Addressed UI delay by demonstrating successful log output and explaining the concept of backend indexing. This highlighted creativity and ability to achieve monitoring goals despite tooling roadblocks.

## Future Work
* **Full Cloud Deployment:** Migrate the `model_api.py` and `event_consumer.py` to Azure Container Apps or Azure Kubernetes Service for scalable, cloud-native deployment.
* **Model Retraining Pipeline:** Implement an automated retraining pipeline (e.g., using Azure Data Factory, Azure ML Pipelines) that periodically trains the model on new data from Cosmos DB.
* **User Interface/Dashboard:** Develop a real-time dashboard (e.g., using Streamlit, Power BI, Grafana) to visualize anomalies, historical trends, and system health metrics.
* **More Advanced Models:** Experiment with deep learning models (e.g., LSTMs, Transformers) for time-series anomaly detection.
* **Data Quality Monitoring:** Add explicit data quality checks in the `event_consumer.py` (e.g., validate sensor ranges, detect missing fields) and send alerts for quality issues.

---
**Contact:** [praveenchalla] | [www.linkedin.com/in/praveen-challa-6043a3276]
