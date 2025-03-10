import asyncio
import os
import json
import random
import threading
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import redis
from prometheus_client import start_http_server, Gauge

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = 6379
DEVICE_ID=os.getenv("NODE_NAME")
  
rooms = ["living", "dining", "patio", "guest_bedroom", "guest_bath", "hall", "wine_cellar", "kitchen", "gym", "garage", "bath", "terrace", "laundry"]

SMARTHOME_TOPIC = "telemetry_smarthome"

light_telemetry = Gauge("smart_home_light", "Light", ["device", "room"])
temperature_telemetry = Gauge("smart_home_temperature", "Smart Home Temperature (°C)", ["device", "room"])
humidity_telemetry = Gauge("smart_home_humidity", "Smart Home Humidity (%)", ["device", "room"])
energy_telemetry = Gauge("smart_home_energy", "Smart Home Energy Consumption (kWh)", ["device", "room"])

async def publish_lights_telemetry(producer: AIOKafkaProducer, redis: redis.Redis):
    for room in rooms:
        light = redis.get(f"device:{DEVICE_ID}:lights:{room}")
        if light is not None:
            light_telemetry.labels(device=DEVICE_ID, room=room).set(1)
            await producer.send_and_wait(SMARTHOME_TOPIC, {
                    "device": DEVICE_ID,
                    "room": room,
                    "type": "smarthome",
                    "sensor": "light",
                    "value": 1
                })
        else:
            light_telemetry.labels(device=DEVICE_ID, room=room).set(0)
            await producer.send_and_wait(SMARTHOME_TOPIC, {
                    "device": DEVICE_ID,
                    "room": room,
                    "type": "smarthome",
                    "sensor": "light",
                    "value": 0
                })


async def publish_sensors_telemetry(producer: AIOKafkaProducer):
    for room in rooms:
        temperature_value = round(random.uniform(18, 30), 2)
        temperature_telemetry.labels(device=DEVICE_ID, room=room).set(temperature_value)
        await producer.send_and_wait(SMARTHOME_TOPIC, {
                "device": DEVICE_ID,
                "room": room,
                "type": "smarthome",
                "sensor": "temperature",
                "value": temperature_value
            })
        humidity_value = round(random.uniform(30, 70), 2)
        humidity_telemetry.labels(device=DEVICE_ID, room=room).set(humidity_value)
        await producer.send_and_wait(SMARTHOME_TOPIC, {
                "device": DEVICE_ID,
                "room": room,
                "type": "smarthome",
                "sensor": "humidity",
                "value": humidity_value
            })
        energy_value = round(random.uniform(0, 10), 2)
        energy_telemetry.labels(device=DEVICE_ID, room=room).set(energy_value)
        await producer.send_and_wait(SMARTHOME_TOPIC, {
                "device": DEVICE_ID,
                "room": room,
                "type": "smarthome",
                "sensor": "energy",
                "value": energy_value
            })

async def aio_produce_smarthome():
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await producer.start()
        try:
            while True:
                await publish_lights_telemetry(producer, r)
                await publish_sensors_telemetry(producer)
                await asyncio.sleep(5)
        finally:
            await producer.stop()
    except Exception as e:
        print(f"Error: {e}")
        raise e

async def aio_consume_smarthome():
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

        consumer = AIOKafkaConsumer(
            SMARTHOME_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            auto_offset_reset="earliest",
            group_id="group_smarthome",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        await consumer.start()
        try:
            async for message in consumer:
                telemetry = message.value
                if "light" == telemetry.get("sensor"):
                    key = f"device:{telemetry.get("device")}:lights:{telemetry.get("room")}"
                    r.set(key, telemetry.get("value"))
        finally:
            await consumer.stop()
    except Exception as e:
        print(f"Error: {e}")
        raise e

def consume_smarthome():
    asyncio.run(aio_consume_smarthome())

def produce_smarthome():
    asyncio.run(aio_produce_smarthome())

def start_prometheus():
    start_http_server(8000)

if __name__ == "__main__":
    try:
        stop_event = threading.Event()
        threading.Thread(target=start_prometheus, daemon=True).start()
        threading.Thread(target=produce_smarthome, daemon=True).start()
        threading.Thread(target=consume_smarthome, daemon=True).start()
        stop_event.wait()
    except Exception as e:
        print(e)
        raise e