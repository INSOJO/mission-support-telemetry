import requests
import time

API_URL = "http://127.0.0.1:8000/telemetry/latest"

while True:
    response = requests.get(API_URL)
    data = response.json()

    print("Latest telemetry:")
    print(data)

    time.sleep(3)
