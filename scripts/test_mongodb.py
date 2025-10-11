#!/usr/bin/env python3
"""
Test MongoDB connection and operations.
Comprehensive test suite for the MongoDB migration.
"""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_header(title):
    """Print a formatted header."""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)


def test_connection():
    """Test MongoDB connection."""
    print("\n🔍 Testing MongoDB connection...")
    
    try:
        from app.services.database_service import connect_db, is_connected
        from app.config import settings
        
        # Check if MONGO_URI is set
        if not settings.MONGO_URI:
            print("❌ MONGO_URI not set in environment variables")
            print("   Please set MONGO_URI in your .env file")
            return False
        
        print(f"   MongoDB URI: {settings.MONGO_URI[:30]}...")
        print(f"   Database Name: {settings.DATABASE_NAME}")
        
        # Attempt connection
        connect_db()
        
        if is_connected():
            print("✅ MongoDB connected successfully!")
            return True
        else:
            print("❌ MongoDB connection failed")
            return False
            
    except Exception as e:
        print(f"❌ Connection test failed with error: {e}")
        return False


def test_models():
    """Test model operations."""
    print("\n🔍 Testing model operations...")
    
    try:
        from app.models.database import Employee
        from app.services.meal_service import add_employee_with_password
        
        # Generate unique email
        test_email = f"test_{int(time.time())}@example.com"
        
        # Test creating an employee
        print(f"   Creating test employee: {test_email}")
        result = add_employee_with_password(
            name="Test User",
            email=test_email,
            password="test123",
            department="Engineering"
        )
        
        if result["success"]:
            print(f"✅ Employee created successfully!")
            print(f"   ID: {result['employee_id']}")
            
            # Test reading the employee
            employee = Employee.objects(email=test_email).first()
            if employee:
                print(f"✅ Employee retrieved: {employee.name}")
                
                # Test updating
                employee.department = "Testing"
                employee.save()
                print(f"✅ Employee updated: department = {employee.department}")
                
                # Clean up - delete test employee
                employee.delete()
                print(f"✅ Employee deleted (cleanup)")
                
                return True
            else:
                print("❌ Could not retrieve created employee")
                return False
        else:
            print(f"❌ Employee creation failed: {result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ Model test failed with error: {e}")
        return False


def test_queries():
    """Test database queries."""
    print("\n🔍 Testing database queries...")
    
    try:
        from app.services.meal_service import get_employees, get_all_employees_admin
        from app.models.database import Employee
        
        # Test getting active employees
        employees = get_employees()
        print(f"✅ Active employees query: {len(employees)} employees")
        
        # Test admin query (all employees)
        all_employees = get_all_employees_admin()
        print(f"✅ All employees query: {len(all_employees)} employees")
        
        # Display first 3 employees
        if employees:
            print("\n   Sample employees:")
            for emp in employees[:3]:
                print(f"      - {emp['name']} ({emp['email']})")
        
        # Test filtering
        active_count = Employee.objects(is_active=True).count()
        total_count = Employee.objects().count()
        print(f"✅ Filter query: {active_count} active / {total_count} total")
        
        return True
        
    except Exception as e:
        print(f"❌ Query test failed with error: {e}")
        return False


def test_authentication():
    """Test authentication functions."""
    print("\n🔍 Testing authentication...")
    
    try:
        from app.services.meal_service import (
            add_employee_with_password,
            authenticate_employee
        )
        
        # Create test user
        test_email = f"auth_test_{int(time.time())}@example.com"
        test_password = "secure_password_123"
        
        result = add_employee_with_password(
            name="Auth Test User",
            email=test_email,
            password=test_password,
            department="Testing"
        )
        
        if not result["success"]:
            print(f"❌ Could not create test user: {result['error']}")
            return False
        
        print("✅ Test user created")
        
        # Test successful authentication
        auth_result = authenticate_employee("Auth Test User", test_password)
        
        if auth_result["success"]:
            print("✅ Authentication successful")
            print(f"   User: {auth_result['employee']['name']}")
            print(f"   Role: {auth_result['employee']['role']}")
        else:
            print(f"❌ Authentication failed: {auth_result['error']}")
            return False
        
        # Test failed authentication (wrong password)
        auth_result = authenticate_employee("Auth Test User", "wrong_password")
        
        if not auth_result["success"]:
            print("✅ Invalid password correctly rejected")
        else:
            print("❌ Invalid password incorrectly accepted")
            return False
        
        # Clean up
        from app.models.database import Employee
        test_user = Employee.objects(email=test_email).first()
        if test_user:
            test_user.delete()
            print("✅ Test user deleted (cleanup)")
        
        return True
        
    except Exception as e:
        print(f"❌ Authentication test failed with error: {e}")
        return False


def test_meal_operations():
    """Test meal selection operations."""
    print("\n🔍 Testing meal operations...")
    
    try:
        from app.services.meal_service import (
            add_employee_with_password,
            submit_meal_selection,
            get_meal_selection,
            get_current_week_start
        )
        from app.models.database import Employee, MealSelection
        
        # Create test employee
        test_email = f"meal_test_{int(time.time())}@example.com"
        result = add_employee_with_password(
            name="Meal Test User",
            email=test_email,
            password="test123",
            department="Testing"
        )
        
        if not result["success"]:
            print(f"❌ Could not create test employee")
            return False
        
        print("✅ Test employee created")
        
        # Submit meal selection
        week_start = get_current_week_start()
        meal_result = submit_meal_selection(
            employee_email=test_email,
            week_start_date=week_start,
            monday_meal="Vegetarian",
            tuesday_meal="Non-Vegetarian",
            wednesday_meal="Vegan",
            thursday_meal="Gluten-Free",
            friday_meal="Vegetarian",
            special_requirements="No nuts"
        )
        
        if meal_result["success"]:
            print("✅ Meal selection submitted")
        else:
            print(f"❌ Meal submission failed: {meal_result['error']}")
            return False
        
        # Retrieve meal selection
        get_result = get_meal_selection(test_email, week_start)
        
        if get_result["success"] and get_result["data"]:
            print("✅ Meal selection retrieved")
            data = get_result["data"]
            print(f"   Monday: {data['monday_meal']}")
            print(f"   Special requirements: {data['special_requirements']}")
        else:
            print("❌ Could not retrieve meal selection")
            return False
        
        # Clean up
        test_user = Employee.objects(email=test_email).first()
        if test_user:
            # Delete meal selections
            MealSelection.objects(employee=test_user).delete()
            test_user.delete()
            print("✅ Test data deleted (cleanup)")
        
        return True
        
    except Exception as e:
        print(f"❌ Meal operations test failed with error: {e}")
        return False


def test_indexes():
    """Test that indexes are created."""
    print("\n🔍 Testing database indexes...")
    
    try:
        from app.models.database import Employee, MealSelection, MealOptions, MealReminder
        
        models = [
            ("Employee", Employee),
            ("MealSelection", MealSelection),
            ("MealOptions", MealOptions),
            ("MealReminder", MealReminder)
        ]
        
        for name, model in models:
            # This will ensure indexes exist
            model.ensure_indexes()
            print(f"✅ {name} indexes ensured")
        
        return True
        
    except Exception as e:
        print(f"❌ Index test failed with error: {e}")
        return False


def main():
    """Run all tests."""
    print_header("MongoDB Migration Test Suite")
    print("\nThis script will test the MongoDB migration")
    print("Make sure MONGO_URI is set in your .env file")
    
    tests = [
        ("Connection", test_connection),
        ("Models", test_models),
        ("Queries", test_queries),
        ("Authentication", test_authentication),
        ("Meal Operations", test_meal_operations),
        ("Indexes", test_indexes),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
            
            if not result:
                print(f"\n⚠️  {name} test failed, continuing with other tests...")
                
        except Exception as e:
            print(f"\n❌ {name} test failed with exception: {e}")
            results.append((name, False))
    
    # Print summary
    print_header("Test Summary")
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name:.<30} {status}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! MongoDB migration successful!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

