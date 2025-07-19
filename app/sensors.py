from websockets.sync.client import connect
import json
import time

keys = [
    "sensor:1:device:1:position",
    "sensor:2:device:1:speed",
    "sensor:3:device:1:acceleration",
    "sensor:4:device:1:load",
    "sensor:7:device:2:grip_force",
    "sensor:8:device:2:distance"
]

def hello():
    uri = "ws://localhost:8000/ws"
    with connect(uri) as websocket:
        data = {
    	    "sensor_type": "distance",
            "sensor_id": 8,
            "device_id": 2,
            "timestamp": int(time.time()),
            "data": {"distance": 15.5},
            "status": "active"
	    }

        websocket.send(json.dumps(data))
        print(f">>> {data}")

        greeting = websocket.recv()
        print(f"<<< {greeting}")


if __name__ == "__main__":
    hello()
