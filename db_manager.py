#!/usr/bin/env python3
"""
Database Manager for Meal Management System
Handles development and production database operations
"""

import os
import sys
import shutil
import sqlite3
from datetime import datetime
from database_config import setup_database, get_db_session, Base

def print_banner():
    """Print a nice banner for the database manager"""
    print("=" * 60)
    print("           MEAL MANAGEMENT DATABASE MANAGER")
    print("=" * 60)

def list_databases():
    """List all available databases"""
    print("\n📁 Available Databases:")
    print("-" * 40)
    
    data_dir = 'data'
    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            if file.endswith('.db'):
                file_path = os.path.join(data_dir, file)
                size = os.path.getsize(file_path)
                modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                print(f"  📄 {file}")
                print(f"     Size: {size:,} bytes")
                print(f"     Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}")
                print()
    else:
        print("  No data directory found.")

def create_production_database():
    """Create a new production database"""
    print("\n🔧 Creating Production Database...")
    
    try:
        # Setup production database
        engine, SessionLocal = setup_database('production')
        
        if engine and SessionLocal:
            print("✅ Production database created successfully!")
            print(f"   Location: data/meal_management_production.db")
        else:
            print("❌ Failed to create production database")
            return False
            
    except Exception as e:
        print(f"❌ Error creating production database: {e}")
        return False
    
    return True

def copy_development_to_production():
    """Copy development database to production"""
    print("\n📋 Copying Development Database to Production...")
    
    dev_db = 'data/meal_management.db'
    prod_db = 'data/meal_management_production.db'
    
    if not os.path.exists(dev_db):
        print("❌ Development database not found!")
        return False
    
    try:
        # Copy the database file
        shutil.copy2(dev_db, prod_db)
        print("✅ Development database copied to production successfully!")
        print(f"   Source: {dev_db}")
        print(f"   Destination: {prod_db}")
        
        # Verify the copy
        if os.path.exists(prod_db):
            dev_size = os.path.getsize(dev_db)
            prod_size = os.path.getsize(prod_db)
            print(f"   Development DB size: {dev_size:,} bytes")
            print(f"   Production DB size: {prod_size:,} bytes")
            
            if dev_size == prod_size:
                print("✅ Database copy verified successfully!")
            else:
                print("⚠️  Warning: Database sizes don't match!")
                
    except Exception as e:
        print(f"❌ Error copying database: {e}")
        return False
    
    return True

def backup_database(environment='development'):
    """Create a backup of the specified database"""
    print(f"\n💾 Creating Backup of {environment.title()} Database...")
    
    if environment == 'production':
        source_db = 'data/meal_management_production.db'
        backup_name = f'meal_management_production_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    else:
        source_db = 'data/meal_management.db'
        backup_name = f'meal_management_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    
    backup_path = os.path.join('data', backup_name)
    
    if not os.path.exists(source_db):
        print(f"❌ {environment.title()} database not found!")
        return False
    
    try:
        shutil.copy2(source_db, backup_path)
        print(f"✅ Backup created successfully!")
        print(f"   Source: {source_db}")
        print(f"   Backup: {backup_path}")
        
    except Exception as e:
        print(f"❌ Error creating backup: {e}")
        return False
    
    return True

def test_database_connection(environment='development'):
    """Test database connection and basic operations"""
    print(f"\n🔍 Testing {environment.title()} Database Connection...")
    
    try:
        session = get_db_session(environment)
        if session:
            # Test basic query
            result = session.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            table_count = result.scalar()
            
            print(f"✅ Database connection successful!")
            print(f"   Tables found: {table_count}")
            
            # Test specific tables
            tables_to_check = ['employees', 'meal_selections', 'meal_reminders', 'meal_options']
            for table in tables_to_check:
                try:
                    result = session.execute(f"SELECT COUNT(*) FROM {table}")
                    count = result.scalar()
                    print(f"   {table}: {count} records")
                except Exception as e:
                    print(f"   {table}: ❌ Error - {e}")
            
            session.close()
            return True
        else:
            print("❌ Failed to get database session")
            return False
            
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        return False

def show_database_info(environment='development'):
    """Show detailed information about the database"""
    print(f"\n📊 {environment.title()} Database Information:")
    print("-" * 50)
    
    if environment == 'production':
        db_path = 'data/meal_management_production.db'
    else:
        db_path = 'data/meal_management.db'
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return
    
    try:
        # File information
        size = os.path.getsize(db_path)
        modified = datetime.fromtimestamp(os.path.getmtime(db_path))
        
        print(f"📁 File: {db_path}")
        print(f"📏 Size: {size:,} bytes ({size/1024/1024:.2f} MB)")
        print(f"🕒 Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Database information
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get table information
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"\n📋 Tables ({len(tables)}):")
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"   • {table_name}: {count} records")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error reading database info: {e}")

def main():
    """Main function for the database manager"""
    print_banner()
    
    while True:
        print("\n🔧 Database Management Options:")
        print("1. List all databases")
        print("2. Create production database")
        print("3. Copy development to production")
        print("4. Backup development database")
        print("5. Backup production database")
        print("6. Test development database")
        print("7. Test production database")
        print("8. Show development database info")
        print("9. Show production database info")
        print("0. Exit")
        
        choice = input("\nEnter your choice (0-9): ").strip()
        
        if choice == '1':
            list_databases()
        elif choice == '2':
            create_production_database()
        elif choice == '3':
            copy_development_to_production()
        elif choice == '4':
            backup_database('development')
        elif choice == '5':
            backup_database('production')
        elif choice == '6':
            test_database_connection('development')
        elif choice == '7':
            test_database_connection('production')
        elif choice == '8':
            show_database_info('development')
        elif choice == '9':
            show_database_info('production')
        elif choice == '0':
            print("\n👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please try again.")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main() 