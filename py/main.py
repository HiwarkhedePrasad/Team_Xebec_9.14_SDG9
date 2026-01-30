"""
Disaster Response Backend with LangGraph Drone Fleet Agent
Team Xebec 9.14 - SDG9

FastAPI + Socket.IO server with AI-powered drone coordination.
"""

import json
import asyncio
import logging
from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agents import run_agent_loop

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# -------------------------------
# Socket.IO ASGI server
# -------------------------------
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*"
)

# Agent task handle
agent_task = None


# -------------------------------
# Lifespan management (startup/shutdown)
# -------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events."""
    global agent_task
    
    # Startup: Start the agent loop
    logger.info("🚀 Starting Drone Fleet Agent...")
    agent_task = asyncio.create_task(
        run_agent_loop(
            emit_callback=emit_to_clients,
            tick_interval=0.1,  # Update every 0.1 seconds (10Hz)
        )
    )
    
    yield
    
    # Shutdown: Cancel the agent
    if agent_task:
        logger.info("Stopping Drone Fleet Agent...")
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Drone Fleet Coordinator API",
    description="AI-powered disaster response drone coordination",
    version="1.0.0",
    lifespan=lifespan
)

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
try:
    with open("disaster_map.json") as f:
        DISASTER_MAP = json.load(f)
except FileNotFoundError:
    logger.warning("disaster_map.json not found, using empty map")
    DISASTER_MAP = []


# -------------------------------
# Emit helper for agent
# -------------------------------
async def emit_to_clients(event: str, data: dict):
    """Emit Socket.IO events from the agent to all clients."""
    await sio.emit(event, data)
    logger.debug(f"Emitted '{event}': {data}")


# -------------------------------
# REST endpoints
# -------------------------------
@app.get("/")
async def root():
    return {"status": "online", "service": "Drone Fleet Coordinator"}


@app.get("/map")
async def get_map():
    """Get the static disaster map data."""
    return DISASTER_MAP


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent_running": agent_task is not None and not agent_task.done()
    }


# -------------------------------
# Socket.IO events  
# -------------------------------
@sio.event
async def connect(sid, environ):
    """Handle client connection - auto-reset simulation for fresh start."""
    global agent_task
    
    logger.info(f"Client connected: {sid}")
    
    # Cancel existing agent and restart with fresh state
    if agent_task and not agent_task.done():
        logger.info("🔄 Resetting simulation for new client...")
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
    
    # Start fresh agent loop
    agent_task = asyncio.create_task(
        run_agent_loop(
            emit_callback=emit_to_clients,
            tick_interval=0.1,
        )
    )
    logger.info("✅ Fresh simulation started")
    
    # Send initial map data
    await sio.emit("map_data", DISASTER_MAP, to=sid)
    
    # Send heat signatures (will be populated by agent loop on first tick)
    # Note: Agent runs immediately, so we can rely on subsequent "drone_update" to carry state?
    # Actually, we should ask the running agent for state or just wait for first tick.
    # To be safe, let's wait a tiny bit for agent to init structure
    await asyncio.sleep(0.5) 
    
    # Send welcome message
    await sio.emit("alert", {
        "type": "SYSTEM",
        "message": "🚀 Simulation started - 10 drones deployed from base",
        "payload": {"sid": sid, "reset": True}
    }, to=sid)


@sio.event
async def disconnect(sid):
    """Handle client disconnection."""
    logger.info(f"Client disconnected: {sid}")


@sio.event
async def reset_simulation(sid, data=None):
    """Manually reset the simulation to fresh state."""
    global agent_task
    
    logger.info(f"🔄 Manual reset requested by {sid}")
    
    # Cancel existing agent
    if agent_task and not agent_task.done():
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
    
    # Start fresh agent loop
    agent_task = asyncio.create_task(
        run_agent_loop(
            emit_callback=emit_to_clients,
            tick_interval=0.1,
        )
    )
    
    await sio.emit("alert", {
        "type": "SYSTEM",
        "message": "🔄 Simulation reset - fresh start!",
        "payload": {"reset": True}
    })


@sio.event
async def drone_update(sid, data):
    """Receive drone update from client (manual override)."""
    logger.info(f"Manual drone update from {sid}: {data}")
    await sio.emit("drone_update", data)


@sio.event
async def request_scan(sid, data):
    """Client requests a scan of a specific area."""
    logger.info(f"Scan requested by {sid}: {data}")
    await sio.emit("alert", {
        "type": "SCAN_REQUESTED",
        "message": f"Scan requested for area ({data.get('x', 0)}, {data.get('y', 0)})",
        "payload": data
    })


@sio.event
async def human_detected(sid, data):
    """Manual human detection report from frontend."""
    logger.info(f"Human detected report from {sid}: {data}")
    await sio.emit("alert", {
        "type": "SURVIVOR_DETECTED",
        "payload": data
    })


# -------------------------------
# Run with: uvicorn main:socket_app --reload
# -------------------------------
