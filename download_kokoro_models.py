#!/usr/bin/env python3
"""
Script to pre-download Kokoro TTS models during Docker build process
"""

import os
import warnings
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_kokoro_models():
    """Download Kokoro models during Docker build"""
    try:
        # Set environment variables to specify repo and suppress warnings
        os.environ['KOKORO_REPO_ID'] = 'hexgrad/Kokoro-82M'
        
        # Suppress warnings
        warnings.filterwarnings("ignore")
        
        logger.info("🔧 Initializing Kokoro model download...")
        
        # Import kokoro with warnings suppressed
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from kokoro import KPipeline
            
            # Create pipeline to trigger model download
            # This will download models to the cache directory
            logger.info("📥 Downloading Kokoro models...")
            pipeline = KPipeline(lang_code="b")
            logger.info("✅ Kokoro models downloaded successfully")
            
            # Clean up
            del pipeline
            
    except Exception as e:
        logger.error(f"❌ Failed to download Kokoro models: {e}")
        raise

if __name__ == "__main__":
    download_kokoro_models()