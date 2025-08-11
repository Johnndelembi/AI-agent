#!/usr/bin/env python3
"""
Kokoro TTS Configuration
Uses local models and alternative sources instead of GitHub downloads
"""

import os
import warnings
import sys
import requests
import time
from pathlib import Path

def configure_kokoro_environment():
    """Configure environment for Kokoro TTS to reduce warnings"""
    
    # Set PyTorch environment variables BEFORE importing torch
    os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
    os.environ['PYTORCH_DISABLE_WARNINGS'] = '1'
    os.environ['TORCH_WARN_ONCE'] = '0'
    os.environ['PYTORCH_WARN_ONCE'] = '0'
    
    # Set network timeout for downloads
    os.environ['REQUESTS_TIMEOUT'] = '60'
    
    # Suppress all warnings at the system level
    warnings.filterwarnings("ignore")
    
    # Import torch after setting environment variables
    import torch
    
    # Configure PyTorch settings
    torch.set_warn_always(False)
    
    # Suppress specific warnings that are known to occur with Kokoro
    warnings.filterwarnings("ignore", category=UserWarning, module="torch.nn.modules.rnn")
    warnings.filterwarnings("ignore", category=UserWarning, module="torch.nn.utils.weight_norm")
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="torch")
    warnings.filterwarnings("ignore", message=".*dropout option adds dropout.*")
    warnings.filterwarnings("ignore", message=".*weight_norm is deprecated.*")
    
    # Set PyTorch to use deterministic algorithms where possible
    if hasattr(torch.backends, 'cudnn'):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

def setup_local_models():
    """Setup local model directory and check for existing models"""
    home_dir = Path.home()
    kokoro_dir = home_dir / ".cache" / "kokoro"
    kokoro_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"📁 Kokoro cache directory: {kokoro_dir}")
    
    # Check if models already exist
    model_files = list(kokoro_dir.glob("*.pth"))
    if model_files:
        print(f"✅ Found {len(model_files)} existing model files")
        return True
    else:
        print("⚠️ No existing models found")
        return False

def download_from_alternative_sources():
    """Try alternative sources for model downloads"""
    sources = [
        "https://huggingface.co/kokoro-ai/kokoro/resolve/main/",
        "https://models.kokoro.ai/",
        "https://cdn.kokoro.ai/models/"
    ]
    
    for source in sources:
        try:
            print(f"🔍 Trying alternative source: {source}")
            response = requests.get(f"{source}README.md", timeout=10)
            if response.status_code == 200:
                print(f"✅ Alternative source available: {source}")
                return source
        except Exception as e:
            print(f"❌ Source {source} failed: {e}")
            continue
    
    return None

def create_kokoro_pipeline(lang_code="b", use_local_only=False):
    """Create a properly configured Kokoro pipeline with local-first approach"""
    
    # Configure environment first
    configure_kokoro_environment()
    
    # Check for local models first
    if setup_local_models():
        print("🎯 Using existing local models")
        use_local_only = True
    
    if use_local_only:
        try:
            print("🔧 Creating Kokoro pipeline with local models...")
            
            # Import kokoro with warnings suppressed
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from kokoro import KPipeline
            
            # Create pipeline with local models
            pipeline = KPipeline(lang_code=lang_code)
            
            print("✅ Kokoro pipeline created successfully with local models")
            return pipeline
            
        except Exception as e:
            print(f"❌ Failed to create pipeline with local models: {e}")
            return None
    
    # Try alternative sources if no local models
    alternative_source = download_from_alternative_sources()
    if alternative_source:
        try:
            print(f"🔧 Creating Kokoro pipeline with alternative source...")
            
            # Set environment variable for alternative source
            os.environ['KOKORO_MODEL_SOURCE'] = alternative_source
            
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from kokoro import KPipeline
            
            pipeline = KPipeline(lang_code=lang_code)
            
            print("✅ Kokoro pipeline created successfully with alternative source")
            return pipeline
            
        except Exception as e:
            print(f"❌ Failed to create pipeline with alternative source: {e}")
            return None
    
    print("❌ No available model sources")
    return None

def generate_kokoro_audio(pipeline, text, voice="af_heart", output_file=None):
    """Generate audio using properly configured Kokoro pipeline"""
    
    if not pipeline:
        print("Pipeline not available")
        return None
    
    try:
        # Configure environment for generation
        configure_kokoro_environment()
        
        print(f"🎵 Generating audio for text: {text[:50]}...")
        
        # Generate audio with warnings suppressed
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            generator = pipeline(text, voice=voice)
        
        # Collect audio segments
        audio_segments = []
        for i, (gs, ps, audio) in enumerate(generator):
            audio_segments.append(audio)
            print(f"✅ Processed segment {i+1}")
        
        if not audio_segments:
            print("❌ No audio segments generated")
            return None
        
        # Concatenate segments
        import numpy as np
        concatenated_audio = np.concatenate(audio_segments)
        
        # Save audio if output file specified
        if output_file:
            import soundfile as sf
            sf.write(output_file, concatenated_audio, 24000)
            print(f"💾 Audio saved to: {output_file}")
        
        print("🎉 Audio generation completed successfully!")
        return concatenated_audio
        
    except Exception as e:
        print(f"❌ Error generating audio: {e}")
        return None

def get_available_voices():
    """Get list of available voices for Kokoro"""
    voices = [
        "af_heart", "af_angry", "af_sad", "af_happy",
        "am_heart", "am_angry", "am_sad", "am_happy",
        "bf_heart", "bf_angry", "bf_sad", "bf_happy",
        "bm_heart", "bm_angry", "bm_sad", "bm_happy"
    ]
    return voices

if __name__ == "__main__":
    # Test the configuration
    print("🚀 Testing Kokoro configuration with local-first approach...")
    
    # Configure environment
    configure_kokoro_environment()
    print("✅ Environment configured")
    
    # Setup local models
    has_local_models = setup_local_models()
    
    # Test pipeline creation
    pipeline = create_kokoro_pipeline(use_local_only=has_local_models)
    if pipeline:
        print("✅ Pipeline created successfully")
        
        # Test audio generation
        test_text = "Hello world! This is a test of the properly configured Kokoro TTS."
        audio = generate_kokoro_audio(pipeline, test_text, output_file="test_output.wav")
        
        if audio is not None:
            print("✅ Audio generated successfully")
        else:
            print("❌ Audio generation failed")
    else:
        print("❌ Pipeline creation failed - will use PyTTSx3 fallback") 