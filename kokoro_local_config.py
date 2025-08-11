#!/usr/bin/env python3
"""
Kokoro TTS Local Configuration
Works with local models without GitHub dependencies
"""

import os
import warnings
import time
from pathlib import Path

def configure_kokoro_environment():
    """Configure environment for Kokoro TTS to reduce warnings and improve performance"""
    
    # Set PyTorch environment variables BEFORE importing torch
    os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
    os.environ['PYTORCH_DISABLE_WARNINGS'] = '1'
    os.environ['TORCH_WARN_ONCE'] = '0'
    os.environ['PYTORCH_WARN_ONCE'] = '0'
    
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
        print("⚠️ No existing models found - will download on first use")
        return False

def create_kokoro_pipeline(lang_code="b", use_local_only=True):
    """Create a properly configured Kokoro pipeline with local-first approach"""
    
    # Configure environment first
    configure_kokoro_environment()
    
    # Check for local models
    has_local_models = setup_local_models()
    
    try:
        print("🔧 Creating Kokoro pipeline...")
        
        # Import kokoro with warnings suppressed
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from kokoro import KPipeline
        
        # Create pipeline
        pipeline = KPipeline(lang_code=lang_code)
        
        print("✅ Kokoro pipeline created successfully")
        return pipeline
        
    except Exception as e:
        print(f"❌ Failed to create Kokoro pipeline: {e}")
        return None

def generate_kokoro_audio(pipeline, text, voice="af_heart", output_file=None):
    """Generate audio using properly configured Kokoro pipeline"""
    
    if not pipeline:
        print("Pipeline not available")
        return None
    
    try:
        # Configure environment for generation
        configure_kokoro_environment()
        
        print(f"🎵 Generating Kokoro audio for text: {text[:50]}...")
        
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

def test_kokoro_tts():
    """Test Kokoro TTS functionality"""
    print("🚀 Testing Kokoro TTS with local configuration...")
    
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
        audio = generate_kokoro_audio(pipeline, test_text, output_file="kokoro_test.wav")
        
        if audio is not None:
            print("✅ Audio generated successfully")
            return True
        else:
            print("❌ Audio generation failed")
            return False
    else:
        print("❌ Pipeline creation failed")
        return False

if __name__ == "__main__":
    test_kokoro_tts()