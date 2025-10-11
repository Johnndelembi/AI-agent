"""
Kokoro TTS utility functions for model download and testing.
"""

import warnings
from app.config import logger, configure_kokoro_environment, TTS_AVAILABLE


def download_kokoro_models():
    """Download Kokoro models during initialization or Docker build."""
    if not TTS_AVAILABLE:
        logger.warning("Kokoro TTS not available, skipping model download")
        return False
    
    try:
        configure_kokoro_environment()
        logger.info("🔧 Initializing Kokoro model download...")
        
        # Import kokoro with warnings suppressed
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from kokoro import KPipeline
            
            # Create pipeline to trigger model download
            logger.info("📥 Downloading Kokoro models...")
            pipeline = KPipeline(lang_code="b")
            logger.info("✅ Kokoro models downloaded successfully")
            
            # Clean up
            del pipeline
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to download Kokoro models: {e}")
        return False


def test_kokoro_setup():
    """Test Kokoro TTS functionality."""
    if not TTS_AVAILABLE:
        logger.warning("Kokoro TTS not available")
        return False
    
    try:
        logger.info("🚀 Testing Kokoro TTS setup...")
        
        configure_kokoro_environment()
        logger.info("✅ Environment configured")
        
        # Test pipeline creation
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from kokoro import KPipeline
            pipeline = KPipeline(lang_code="b")
        
        if pipeline:
            logger.info("✅ Pipeline created successfully")
            
            # Test audio generation with a short test
            test_text = "Hello, this is a test."
            generator = pipeline(test_text, voice="af_heart")
            
            # Check if generator produces output
            segment_count = 0
            for _ in generator:
                segment_count += 1
                break  # Just test first segment
            
            if segment_count > 0:
                logger.info("✅ Audio generation test passed")
                return True
            else:
                logger.error("❌ Audio generation test failed")
                return False
        else:
            logger.error("❌ Pipeline creation failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Kokoro setup test failed: {e}")
        return False


if __name__ == "__main__":
    # Test when run directly
    test_kokoro_setup()

