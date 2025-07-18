from websockets.sync.client import connect
# from fastapi import WebSocket
import json
from datetime import datetime


def hello():
    uri = "ws://localhost:8000/ws"
    with connect(uri) as websocket:
        data = {
            "component_id": "component_1",
            "component_name": "gripper_tool_x",
            "timestamp": datetime.utcnow().isoformat(),
            "status": "idle",
            "position": 100,
            "speed": 50,
            "acceleration": 5,
            "load": 75,
        }
        websocket.send(json.dumps(data))
        print(f">>> {data}")

        greeting = websocket.recv()
        print(f"<<< {greeting}")


if __name__ == "__main__":
    hello()
