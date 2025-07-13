const ws = new WebSocket("ws://localhost:8000/ws");

const send = document.getElementById("send");
send.addEventListener("click", sendMessage);

function sendMessage(event) {
	let data = {
		component_id: "component_1",
		component_name: "gripper_tool_x",
        timestamp: new Date().toISOString(),
		status: "idle",
		position: 100,
		speed: 50,
		acceleration: 5,
		load: 75,
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
