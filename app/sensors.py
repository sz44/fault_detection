from typing import Dict, Literal
from websockets.sync.client import connect
import json
import time
import math
import datetime
import pydantic
import random
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK, WebSocketException
import logging

keys = [
    "sensor:1:device:1:position",
    "sensor:2:device:1:speed",
    "sensor:3:device:1:acceleration",
    "sensor:4:device:1:load",
    "sensor:5:device:2:grip_force",
    "sensor:6:device:2:distance",
]

TIMESTAMP_TYPE = "iso" # or "epoch"

def periodic_step_function():
    """
    Periodic function that behaves like a step function with smooth transitions.
    
    Cycle (12000ms total):
    - 0-5000ms: stays at 50
    - 5000-6000ms: transitions from 50 to 5
    - 6000-11000ms: stays at 5  
    - 11000-12000ms: transitions from 5 to 50
    
    Args:
        timestamp_ms: timestamp in milliseconds. If None, uses current time.
    
    Returns:
        float: value between 5 and 50
    """
    timestamp_ms = int(time.time() * 1000)
    
    # Total cycle duration in milliseconds
    cycle_duration = 30000  # 30 seconds
    
    # Get position within the cycle
    cycle_position = timestamp_ms % cycle_duration
    
    if cycle_position < 5000:
        # First plateau: stay at 50
        return 50.0
    elif cycle_position < 6000:
        # Transition from 50 to 5 over 1000ms
        transition_progress = (cycle_position - 5000) / 1000.0
        # Use smooth cosine interpolation for natural transition
        smooth_progress = (1 - math.cos(transition_progress * math.pi)) / 2
        return 50 - (45 * smooth_progress)
    elif cycle_position < 11000:
        # Second plateau: stay at 5
        return 5.0
    else:
        # Transition from 5 to 50 over 1000ms
        transition_progress = (cycle_position - 11000) / 1000.0
        # Use smooth cosine interpolation for natural transition
        smooth_progress = (1 - math.cos(transition_progress * math.pi)) / 2
        return 5 + (45 * smooth_progress)

data = {
    "sensor_type": "distance",
    "sensor_id": 6,
    "device_id": 2,
    "timestamp": int(time.time()),
    # "data": {"distance": 15.5},
    "data": 15.5,
    "status": "active",
}

class AxisData(pydantic.BaseModel):
    sensor_type: str = "distance"
    sensor_id: int  
    device_id: int  
    timestamp: str
    data: Dict[Literal["distance"], float]
    status: str = "active"

def main2():
    uri = "ws://localhost:8000/ws"
    with connect(uri) as websocket:
        while True:
            axisData = AxisData(
                sensor_id=6,
                device_id=2,
                timestamp=get_timestamp(),
                data={"distance":periodic_step_function()},
                status="active"
            )

            websocket.send(json.dumps(axisData.model_dump()))
            print(f">>> {data}")

            res = websocket.recv()
            print(f"<<< {res}")

            time.sleep(1)  # Adjust the sleep time as needed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_timestamp() -> str:
    """Get current timestamp in milliseconds."""
    if TIMESTAMP_TYPE == "iso":
        # Return ISO format timestamp
        return datetime.datetime.now(datetime.timezone.utc).isoformat()
    elif TIMESTAMP_TYPE == "epoch":
        # Return epoch timestamp in milliseconds
        # Note: time.time() returns seconds, so multiply by 1000 for milliseconds
        return str(int(time.time() * 1000))
    else:
        raise ValueError("Invalid timestamp type. Use 'iso' or 'epoch'.")

class WebSocketClient:
    def __init__(self, uri, max_retries=5, initial_backoff=1, max_backoff=60):
        self.uri = uri
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.retry_count = 0
    
    def get_backoff_time(self):
        """Calculate exponential backoff with jitter"""
        backoff = min(self.initial_backoff * (2 ** self.retry_count), self.max_backoff)
        # Add jitter to prevent thundering herd
        jitter = random.uniform(0.1, 0.5) * backoff
        return backoff + jitter
    
    def send_data_safely(self, websocket, data):
        """Send data with error handling"""
        try:
            websocket.send(json.dumps(data))
            logger.info(f">>> Sent: {data}")
            return True
        except (ConnectionClosedError, ConnectionClosedOK) as e:
            logger.warning(f"Connection closed while sending: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending data: {e}")
            return False
    
    def receive_data_safely(self, websocket, timeout=5):
        """Receive data with error handling and timeout"""
        try:
            # Note: sync websockets doesn't have built-in timeout
            # You might want to use asyncio version for timeout support
            res = websocket.recv()
            logger.info(f"<<< Received: {res}")
            return res
        except (ConnectionClosedError, ConnectionClosedOK) as e:
            logger.warning(f"Connection closed while receiving: {e}")
            return None
        except Exception as e:
            logger.error(f"Error receiving data: {e}")
            return None
    

    def run(self):
        while self.retry_count < self.max_retries:
            try:
                logger.info(f"Attempting connection... (attempt {self.retry_count + 1}/{self.max_retries})")
                
                with connect(self.uri) as websocket:
                    logger.info("Connected successfully!")
                    self.retry_count = 0  # Reset retry count on successful connection
                    
                    while True:
                        # Prepare your data
                        axisData = AxisData(
                            sensor_id=6,
                            device_id=2,
                            timestamp=get_timestamp(),
                            data={"distance": periodic_step_function()},
                            status="active"
                        )
                        
                        # Send data
                        if not self.send_data_safely(websocket, axisData.model_dump()):
                            break  # Connection issue, will reconnect
                        
                        # Receive response
                        response = self.receive_data_safely(websocket)
                        if response is None:
                            break  # Connection issue, will reconnect
                        
                        time.sleep(1)
            
            except (ConnectionClosedError, ConnectionClosedOK) as e:
                logger.warning(f"Connection error: {e}")
                
            except WebSocketException as e:
                logger.error(f"WebSocket error: {e}")
                
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
            
            # Increment retry count and wait
            self.retry_count += 1
            if self.retry_count < self.max_retries:
                backoff_time = self.get_backoff_time()
                logger.info(f"Retrying in {backoff_time:.2f} seconds...")
                time.sleep(backoff_time)
            else:
                logger.error("Max retries reached, giving up")
                break

def main():
    uri = "ws://localhost:8000/ws"
    client = WebSocketClient(uri)
    client.run()

if __name__ == "__main__":
    main()
