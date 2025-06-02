import asyncio
import time
from src.tws_config import TWSConfig
from src.tws_connection import TWSConnection
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_connection():
    """Test connection with unique client ID."""
    config = TWSConfig(
        host='127.0.0.1', 
        port=7497, 
        client_id=999,  # Completely unique ID
        connection_timeout=10.0
    )
    
    conn = TWSConnection(config)
    
    try:
        logger.info("🔌 Testing connection with client ID 999...")
        result = await conn.connect()
        logger.info(f"Connection result: {result}")
        
        if result:
            logger.info("✅ SUCCESS! No competing session error")
            
            # Test getting a simple price
            logger.info("Testing basic functionality...")
            await asyncio.sleep(2)
            
            return True
        else:
            logger.error("❌ Connection failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Exception: {e}")
        return False
    finally:
        if conn.is_connected():
            logger.info("Disconnecting...")
            conn.disconnect()
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(test_connection()) 