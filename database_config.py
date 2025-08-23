import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

# Configure logging
logger = logging.getLogger(__name__)

# Create base class for models
Base = declarative_base()

class Employee(Base):
    __tablename__ = 'employees'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    department = Column(String(50))
    password_hash = Column(String(255), nullable=False)  # Store hashed passwords
    role = Column(String(20), default='client')  # 'admin' or 'client'
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationship
    meal_selections = relationship("MealSelection", back_populates="employee")

class MealSelection(Base):
    __tablename__ = 'meal_selections'
    
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    week_start_date = Column(DateTime, nullable=False)  # Monday of the week
    monday_meal = Column(Text)
    tuesday_meal = Column(Text)
    wednesday_meal = Column(Text)
    thursday_meal = Column(Text)
    friday_meal = Column(Text)
    special_dietary_requirements = Column(Text)
    submitted_at = Column(DateTime, default=func.now())
    is_submitted = Column(Boolean, default=False)
    
    # Relationship
    employee = relationship("Employee", back_populates="meal_selections")

class MealReminder(Base):
    __tablename__ = 'meal_reminders'
    
    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    week_start_date = Column(DateTime, nullable=False)
    reminder_sent_at = Column(DateTime, default=func.now())
    reminder_type = Column(String(20), default='weekly')  # weekly, reminder, final
    
    # Relationship
    employee = relationship("Employee")

class MealOptions(Base):
    __tablename__ = 'meal_options'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    day = Column(String(20), nullable=False)  # monday, tuesday, wednesday, thursday, friday
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey('employees.id'), nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationship
    creator = relationship("Employee")
    
    # Unique constraint to prevent duplicate meal names for the same day
    __table_args__ = (UniqueConstraint('name', 'day', name='unique_meal_per_day'),)

def setup_database(environment='development'):
    """
    Setup the database and create tables
    
    Args:
        environment (str): 'development' or 'production'
    """
    try:
        # Create data directory if it doesn't exist
        data_dir = 'data'
        os.makedirs(data_dir, exist_ok=True)
        
        # Determine database path based on environment
        if environment == 'production':
            db_filename = 'meal_management_production.db'
        else:
            db_filename = 'meal_management.db'
        
        # Create SQLite database
        db_path = os.path.join(data_dir, db_filename)
        engine = create_engine(f'sqlite:///{db_path}')
        
        # Create tables
        Base.metadata.create_all(engine)
        
        # Create session factory
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        logger.info(f"Database setup successfully at {db_path} (Environment: {environment})")
        return engine, SessionLocal
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        return None, None

def get_db_session(environment='development'):
    """
    Get database session for the specified environment
    
    Args:
        environment (str): 'development' or 'production'
    """
    engine, SessionLocal = setup_database(environment)
    if SessionLocal:
        return SessionLocal()
    return None

# Environment-based database setup
def get_environment():
    """Get current environment from environment variable"""
    return os.getenv('ENVIRONMENT', 'development')

def setup_environment_database():
    """Setup database based on current environment"""
    environment = get_environment()
    return setup_database(environment)

def get_environment_db_session():
    """Get database session based on current environment"""
    environment = get_environment()
    return get_db_session(environment)

# Initialize database based on environment
db_engine, SessionLocal = setup_environment_database() 