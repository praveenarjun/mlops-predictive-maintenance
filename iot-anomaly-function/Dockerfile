# In iot-anomaly-function/Dockerfile
FROM mcr.microsoft.com/azure-functions/python:4-python3.11-slim
ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

COPY requirements.txt /temp/requirements.txt
RUN pip install -r /temp/requirements.txt && rm -rf /temp

COPY . /home/site/wwwroot