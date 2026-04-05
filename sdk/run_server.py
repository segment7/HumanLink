#!/usr/bin/env python
"""
HumanLink SDK Server Startup Script

Starts the HumanLink SDK API server on localhost:8765
"""
import sys
import logging
from pathlib import Path

# Add the SDK directory to the Python path
sdk_dir = Path(__file__).parent
sys.path.insert(0, str(sdk_dir))

# Now import and run the server
if __name__ == "__main__":
    import uvicorn
    from api.server import app

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    logger.info("Starting HumanLink SDK API server...")
    logger.info("Server will be available at http://localhost:8765")
    logger.info("API documentation at http://localhost:8765/docs")

    try:
        uvicorn.run(
            "api.server:app",
            host="127.0.0.1",
            port=8765,
            reload=False,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server failed to start: {e}")
        sys.exit(1)