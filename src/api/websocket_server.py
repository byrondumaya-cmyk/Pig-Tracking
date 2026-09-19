"""
src/api/websocket_server.py
Websocket Server for Mobile App (Hybrid AI Architecture)

Streams raw video frames and thermal grid data to connected clients.
"""

import asyncio
import base64
import json
import logging
from typing import Optional

import cv2
import numpy as np

try:
    import websockets
    _WEBSOCKETS_AVAILABLE = True
except ImportError:
    websockets = None  # type: ignore[assignment]
    _WEBSOCKETS_AVAILABLE = False

logger = logging.getLogger(__name__)

class SensorHubStreamer:
    """
    Maintains active websocket connections to mobile apps.
    Broadcasts synchronized (RGB frame, Thermal grid) payloads.
    """
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.loop = None
        self._server_task = None
        self._latest_frame: Optional[np.ndarray] = None
        self._latest_thermal: Optional[np.ndarray] = None
        self._running = False

    async def _handler(self, websocket):
        self.clients.add(websocket)
        logger.info(f"Mobile app connected: {websocket.remote_address}")
        try:
            async for message in websocket:
                # We don't expect messages from the client yet, 
                # but we keep the loop alive to detect disconnects
                pass
        except Exception:
            pass
        finally:
            self.clients.remove(websocket)
            logger.info(f"Mobile app disconnected: {websocket.remote_address}")

    async def _broadcast_loop(self):
        """Continuously pulls latest frames and broadcasts them at high speed."""
        while self._running:
            if not self.clients:
                await asyncio.sleep(0.1)
                continue
                
            if self._latest_frame is None:
                await asyncio.sleep(0.01)
                continue

            # Encode frame to JPEG
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]  # Lower quality for speed
            success, buffer = cv2.imencode('.jpg', self._latest_frame, encode_param)
            
            if success:
                jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                
                # Payload matching what the mobile app expects
                payload = json.dumps({
                    "type": "sync_frame",
                    "image": jpg_as_text,
                    "thermal_grid": self._latest_thermal.tolist() if self._latest_thermal is not None else []
                })
                
                # Broadcast to all connected phones
                disconnected = set()
                for client in self.clients:
                    try:
                        await client.send(payload)
                    except Exception:
                        disconnected.add(client)
                        
                for c in disconnected:
                    self.clients.remove(c)
            
            # Throttle to max 30 FPS broadcast
            await asyncio.sleep(1.0 / 30.0)

    async def _start_server(self):
        if not _WEBSOCKETS_AVAILABLE:
            logger.error(
                "WebSocket server cannot start: 'websockets' package is not installed. "
                "Run: pip install websockets"
            )
            return
        self._running = True
        logger.info(f"Starting Sensor Hub Websocket on ws://{self.host}:{self.port}")
        # Run the server and the broadcaster concurrently
        async with websockets.serve(self._handler, self.host, self.port):
            await self._broadcast_loop()

    def start_in_background(self):
        """Starts the asyncio event loop in a background thread."""
        import threading
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._start_server())
            
        t = threading.Thread(target=run_loop, daemon=True, name="WebsocketServer")
        t.start()

    def update_sensor_data(self, frame: np.ndarray, thermal_grid: np.ndarray):
        """Thread-safe update called by the main camera loop."""
        self._latest_frame = frame
        self._latest_thermal = thermal_grid
