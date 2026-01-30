import json
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# -------------------------------
# Socket.IO ASGI server
# -------------------------------
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*"
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

socket_app = socketio.ASGIApp(sio, app)

# -------------------------------
# Load static disaster map
# -------------------------------
with open("disaster_map.json") as f:
    DISASTER_MAP = json.load(f)

# -------------------------------
# REST endpoint
# -------------------------------
@app.get("/map")
async def get_map():
    return DISASTER_MAP

# -------------------------------
# Socket.IO events
# -------------------------------
@sio.event
async def connect(sid, environ):
    print("Client connected:", sid)
    await sio.emit("map_data", DISASTER_MAP, to=sid)

@sio.event
async def disconnect(sid):
    print("Client disconnected:", sid)

@sio.event
async def drone_update(sid, data):
    await sio.emit("drone_update", data)

@sio.event
async def human_detected(sid, data):
    await sio.emit("alert", {
        "type": "SURVIVOR_DETECTED",
        "payload": data
    })
