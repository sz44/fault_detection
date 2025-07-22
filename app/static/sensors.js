const ws = new WebSocket("ws://localhost:8000/ws");

const sendDistanceBtn = document.getElementById("sendDistanceBtn");
sendDistanceBtn.addEventListener("click", sendDistance);

let keys = [
    "sensor:1:device:1:position",
    "sensor:2:device:1:speed",
    "sensor:3:device:1:acceleration",
    "sensor:4:device:1:load",
    "sensor:5:device:2:grip_force",
    "sensor:6:device:2:distance"
]

function sendDistance(event) {
	let data = {
    	sensor_type: "distance",
    	sensor_id: 6,
    	device_id: 2,
        timestamp: new Date().toISOString(),
    	data: {"distance": 15.5},
    	status: "active"
	};
    ws.send(JSON.stringify(data));
    console.log("Sent:", data);
    event.preventDefault();
}


ws.onmessage = function (event) {
	var messages = document.getElementById("messages");
	var message = document.createElement("li");
	var content = document.createTextNode(event.data);
	message.appendChild(content);
	messages.appendChild(message);
};
