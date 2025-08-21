#!/usr/bin/env python3
"""
Startup script for the AI Agent FastAPI application
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    print("🔍 Checking dependencies...")
    
    required_packages = [
        'fastapi',
        'uvicorn',
        'pydantic',
        'langchain',
        'langgraph'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} - missing")
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Please install missing packages with: pip install -r requirements.txt")
        return False
    
    print("✅ All dependencies are installed")
    return True

def check_environment():
    """Check environment configuration"""
    print("\n🔍 Checking environment configuration...")
    
    # Check if .env file exists
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️  .env file not found. Creating from template...")
        create_env_template()
    else:
        print("✅ .env file found")
    
    # Check required environment variables
    required_vars = [
        'CHATBOT_API_KEY',
        'TAVILY_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these variables in your .env file")
        return False
    
    print("✅ Environment configuration looks good")
    return True

def create_env_template():
    """Create a template .env file"""
    template = """# AI Agent API Configuration

# API Configuration
CHATBOT_MODEL=openai:gpt-4
CHATBOT_API_KEY=your_openai_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here

# TTS Configuration
TTS_VOICE=af_heart
TTS_LANG_CODE=b

# Email Configuration (optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your_email@gmail.com
SENDER_PASSWORD=your_app_password

# Environment
ENV=development
DEBUG=true
"""
    
    with open(".env", "w") as f:
        f.write(template)
    
    print("✅ Created .env template. Please edit it with your API keys.")

def create_directories():
    """Create necessary directories"""
    print("\n🔍 Creating directories...")
    
    directories = [
        "audio_output",
        "data", 
        "logs"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Created {directory}/")

def start_server():
    """Start the FastAPI server"""
    print("\n🚀 Starting AI Agent API...")
    print("=" * 50)
    
    try:
        # Start uvicorn server
        cmd = [
            sys.executable, "-m", "uvicorn",
            "main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload"
        ]
        
        print("Starting server with command:")
        print(" ".join(cmd))
        print("\n📝 API Documentation will be available at:")
        print("   http://localhost:8000/docs")
        print("   http://localhost:8000/redoc")
        print("\n🔗 API endpoints:")
        print("   http://localhost:8000/api/v1/health")
        print("   http://localhost:8000/info")
        print("\n" + "=" * 50)
        
        subprocess.run(cmd)
        
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        return False
    
    return True

def main():
    """Main startup function"""
    print("🤖 AI Agent API Startup")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        return False
    
    # Check environment
    if not check_environment():
        print("\n⚠️  Please configure your environment variables and try again.")
        return False
    
    # Create directories
    create_directories()
    
    # Start server
    return start_server()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 