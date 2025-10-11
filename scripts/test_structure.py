#!/usr/bin/env python3
"""
Test script to verify the FastAPI migration structure.
Checks imports, file structure, and configurations.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Test that all main modules can be imported."""
    print("🔍 Testing module imports...")
    
    tests = [
        ("Config module", "app.config"),
        ("Database models", "app.models.database"),
        ("Database service", "app.services.database_service"),
        ("Meal service", "app.services.meal_service"),
        ("TTS service", "app.services.tts_service"),
        ("Agent service (partial)", "app.services.agent_service"),
        ("Chat service", "app.services.chat_service"),
        ("Audio service", "app.services.audio_service"),
        ("Dependencies", "app.dependencies"),
        ("Utils", "app.utils"),
    ]
    
    passed = 0
    failed = 0
    
    for name, module_path in tests:
        try:
            __import__(module_path)
            print(f"  ✅ {name}: OK")
            passed += 1
        except Exception as e:
            print(f"  ❌ {name}: FAILED - {e}")
            failed += 1
    
    print(f"\n📊 Import Test Results: {passed} passed, {failed} failed")
    return failed == 0


def test_file_structure():
    """Test that all required files exist."""
    print("\n🔍 Testing file structure...")
    
    root = Path(__file__).parent.parent
    required_files = [
        "app/config.py",
        "app/models/database.py",
        "app/services/database_service.py",
        "app/services/meal_service.py",
        "app/services/tts_service.py",
        "app/services/agent_service.py",
        "app/services/chat_service.py",
        "app/services/audio_service.py",
        "app/dependencies.py",
        "app/main.py",
        "app/utils/__init__.py",
        "app/utils/kokoro.py",
        "scripts/db_manager.py",
        "scripts/download_models.py",
    ]
    
    passed = 0
    failed = 0
    
    for file_path in required_files:
        full_path = root / file_path
        if full_path.exists():
            print(f"  ✅ {file_path}: EXISTS")
            passed += 1
        else:
            print(f"  ❌ {file_path}: MISSING")
            failed += 1
    
    print(f"\n📊 File Structure Test Results: {passed} passed, {failed} failed")
    return failed == 0


def test_old_files_removed():
    """Test that old files have been removed."""
    print("\n🔍 Testing old files removed...")
    
    root = Path(__file__).parent.parent
    old_files = [
        "basic_chatbot.py",
        "database_config.py",
        "db_manager.py",
        "kokoro_config.py",
        "kokoro_local_config.py",
        "download_kokoro_models.py",
    ]
    
    passed = 0
    failed = 0
    
    for file_path in old_files:
        full_path = root / file_path
        if not full_path.exists():
            print(f"  ✅ {file_path}: REMOVED")
            passed += 1
        else:
            print(f"  ❌ {file_path}: STILL EXISTS")
            failed += 1
    
    print(f"\n📊 Old Files Test Results: {passed} passed, {failed} failed")
    return failed == 0


def test_config():
    """Test that config loads properly."""
    print("\n🔍 Testing configuration...")
    
    try:
        from app import config
        
        checks = [
            ("Environment", hasattr(config, 'ENVIRONMENT')),
            ("Database URL", hasattr(config, 'DATABASE_URL')),
            ("Model settings", hasattr(config, 'CHATBOT_MODEL')),
            ("TTS settings", hasattr(config, 'TTS_AVAILABLE')),
            ("App settings", hasattr(config, 'APP_TITLE')),
        ]
        
        passed = 0
        failed = 0
        
        for name, result in checks:
            if result:
                print(f"  ✅ {name}: OK")
                passed += 1
            else:
                print(f"  ❌ {name}: MISSING")
                failed += 1
        
        print(f"\n📊 Config Test Results: {passed} passed, {failed} failed")
        return failed == 0
        
    except Exception as e:
        print(f"  ❌ Config loading failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("     FASTAPI MIGRATION STRUCTURE TEST")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("File Structure", test_file_structure()))
    results.append(("Old Files Removed", test_old_files_removed()))
    results.append(("Configuration", test_config()))
    results.append(("Module Imports", test_imports()))
    
    # Summary
    print("\n" + "=" * 60)
    print("     TEST SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("     🎉 ALL TESTS PASSED!")
        print("     Migration to FastAPI structure complete!")
    else:
        print("     ⚠️  SOME TESTS FAILED")
        print("     Please review the errors above.")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

