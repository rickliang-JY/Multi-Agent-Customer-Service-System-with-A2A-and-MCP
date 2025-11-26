"""
Quick Database Initialization Script
Automatically sets up support.db without interactive prompts
"""

import sqlite3
import sys
import os

def quick_setup():
    """Initialize database quickly without prompts"""
    
    db_path = "support.db"
    
    # Remove old database if exists
    if os.path.exists(db_path):
        print(f"Removing existing {db_path}...")
        os.remove(db_path)
    
    # Import and use the official DatabaseSetup class
    try:
        from database_setup import DatabaseSetup
        
        print("Creating database...")
        db = DatabaseSetup(db_path)
        
        try:
            # Connect
            db.connect()
            
            # Create tables
            db.create_tables()
            
            # Create triggers
            db.create_triggers()
            
            # Insert sample data
            db.insert_sample_data()
            
            print("\n" + "="*60)
            print("DATABASE SETUP COMPLETE!")
            print("="*60)
            print(f"Database: {db_path}")
            print("Ready to run: python test_scenarios.py")
            print("="*60 + "\n")
            
        except Exception as e:
            print(f"Error during setup: {e}")
            sys.exit(1)
        finally:
            db.close()
            
    except ImportError:
        print("Error: Cannot import database_setup.py")
        print("Make sure database_setup.py is in the same directory.")
        sys.exit(1)

if __name__ == "__main__":
    quick_setup()
