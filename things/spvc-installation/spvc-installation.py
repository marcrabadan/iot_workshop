import asyncio
import os
import time
import json
import random
import threading

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import redis
from prometheus_client import start_http_server, Gauge

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = 6379


grid = Gauge('grid', 'Grid (W)', ['device'])
battery = Gauge('battery', 'Battery (W)', ['device'])
panels = Gauge('panels', 'Solar Panels (W)', ['device'])
home = Gauge('home', 'Home Consumption (W)', ['device'])
wind_rpm = Gauge('wind_rpm', 'Wind (RPM)', ['device'])

INVERTER_TOPIC = "telemetry_inverter"

async def aio_produce_inverter():
    try:
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
        await producer.start()
        try:
            while True:
                telemetry = {
                    "device": os.getenv("NODE_NAME"),
                    "type": "inverter",
                    "grid": round(random.uniform(0, 100), 2), 
                    "home": round(random.uniform(0, 20), 2), 
                    "battery": round(random.uniform(0.1, 10), 2), 
                    "panels": random.uniform(0, 8), 
                    "wind_rpm": random.uniform(0, 8) * 10, 
                }
                await producer.send_and_wait(INVERTER_TOPIC, telemetry)
                print("Produced inverter telemetry:", telemetry)
                await asyncio.sleep(1)
        finally:
            await producer.stop()
    except Exception as e:
        print(f"Error: {e}")
        os._exit(1)
    
async def aio_consume_inverter():
    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        consumer = AIOKafkaConsumer(
            INVERTER_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            auto_offset_reset="earliest",
            group_id="group_inverter",
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        await consumer.start()
        try:
            async for message in consumer:
                telemetry = message.value
                print("Consumed inverter telemetry:", telemetry)
                r.hset("inverter:" + telemetry["device"], mapping=telemetry)
                grid.labels(device=telemetry["device"]).set(telemetry["grid"])
                battery.labels(device=telemetry["device"]).set(telemetry["battery"])
                home.labels(device=telemetry["device"]).set(telemetry["home"])
                panels.labels(device=telemetry["device"]).set(telemetry["panels"])
                wind_rpm.labels(device=telemetry["device"]).set(telemetry["wind_rpm"])
        finally:
            await consumer.stop()
    except Exception as e:
        print(f"Error: {e}")
        os._exit(1)

def consume_inverter():
    asyncio.run(aio_consume_inverter())

def produce_inverter():
    asyncio.run(aio_produce_inverter())

def start_prometheus():
    start_http_server(8000)
    print("Prometheus metrics available on port 8000")

if __name__ == "__main__":
    stop_event = threading.Event()
    threading.Thread(target=start_prometheus, daemon=True).start()
    threading.Thread(target=produce_inverter, daemon=True).start()
    threading.Thread(target=consume_inverter, daemon=True).start()
    stop_event.wait()