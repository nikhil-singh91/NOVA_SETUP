"""Standalone launcher for NOVA UI backend gateway and local server."""

from __future__ import annotations

import sys
import time
from core.logger import get_logger, setup_logging
from ui.backend.command_gateway import command_gateway
from ui.backend.server import ui_server

logger = get_logger(__name__)


def run_ui_backend() -> int:
    """Launch the NOVA backend UI gateway server."""
    setup_logging()
    logger.info("Initializing NOVA UI Backend Gateway...")

    try:
        import threading
        from main import NovaApplication
        app = NovaApplication()
        command_gateway.bind_app(app)
        app_thread = threading.Thread(target=app.run, daemon=True, name="nova-backend-app")
        app_thread.start()
    except Exception as exc:
        logger.warning("Could not initialize full NovaApplication (%s); running in standalone UI mode.", exc)

    ui_server.start_background()
    print("==================================================")
    print("✨ NOVA UI V1 Backend Gateway Active")
    print(f"📡 WebSocket Stream: ws://127.0.0.1:{ui_server.port}/events")
    print(f"🌐 HTTP REST API:   http://127.0.0.1:{ui_server.port}/health")
    print("==================================================")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping NOVA UI Backend...")
        ui_server.stop()
        return 0


if __name__ == "__main__":
    sys.exit(run_ui_backend())
