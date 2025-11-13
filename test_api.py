"""Test script for FastAPI endpoints."""
import asyncio
import sys
from src.services.chat_service import ChatService


async def test_chat_service():
    """Test the chat service."""
    print("\n🧪 Testing Chat Service...")
    
    try:
        service = ChatService()
        
        # Test sending a message
        print("  → Sending test message...")
        response = await service.send_message(
            message="Hello! Say 'Hi' back.",
            thread_id="test-thread"
        )
        
        if response and len(response) > 0:
            print(f"  ✓ Chat service working! Response: {response[:100]}...")
        else:
            print("  ✗ Chat service returned empty response")
            return False
        
        # Test health check
        print("  → Checking service health...")
        is_healthy = await service.is_healthy()
        
        if is_healthy:
            print("  ✓ Chat service is healthy")
        else:
            print("  ✗ Chat service health check failed")
            return False
        
        # Cleanup
        await service.shutdown()
        print("  ✓ Chat service test completed successfully")
        return True
        
    except Exception as e:
        print(f"  ✗ Chat service test failed: {e}")
        return False


async def test_app_startup():
    """Test app startup and structure."""
    print("\n🧪 Testing App Structure...")
    
    try:
        from src.main import app
        
        # Check app metadata
        print(f"  ✓ App title: {app.title}")
        print(f"  ✓ App version: {app.version}")
        print(f"  ✓ App description: {app.description}")
        
        # Check routes are registered
        routes = [route.path for route in app.routes]
        expected_routes = ["/", "/chat/message"]
        
        for route in expected_routes:
            if any(r for r in routes if route in r):
                print(f"  ✓ Route registered: {route}")
            else:
                print(f"  ✗ Route missing: {route}")
                return False
        
        print("  ✓ App structure test completed successfully")
        return True
        
    except Exception as e:
        print(f"  ✗ App structure test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("🚀 AI Agent FastAPI - Test Suite")
    print("=" * 60)
    
    results = []
    
    # Test app structure
    results.append(await test_app_startup())
    
    # Test chat service
    results.append(await test_chat_service())
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed!")
        return 0
    else:
        print(f"✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

