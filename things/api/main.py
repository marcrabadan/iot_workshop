import json
import os
from typing import Generic, Optional, TypeVar, Any
from aiokafka import AIOKafkaProducer
from fastapi import FastAPI, status
from pydantic import BaseModel

app = FastAPI()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
SMARTHOME_TOPIC = "telemetry_smarthome"

class Telemetry(BaseModel):
    device_id: Optional[str]
    room_id: Optional[str]
    value: Optional[bool]

@app.post("/api/telemetry", status_code=status.HTTP_200_OK)
async def send_telemetry(telemetry: Telemetry):
    try:
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await producer.start()
        try:
            await producer.send_and_wait(SMARTHOME_TOPIC, {
                    "device": telemetry.device_id,
                    "room": telemetry.room_id,
                    "type": "smarthome",
                    "sensor": "light",
                    "value": 1 if telemetry.value else 0
                })
        finally:
            await producer.stop()
    except Exception as e:
        print(f"Error: {e}")
        raise e