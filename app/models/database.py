"""
Database models for the Meal Management System.
Contains MongoEngine Document models for employees, meal selections, reminders, and options.
"""

from mongoengine import (
    Document, 
    StringField, 
    EmailField, 
    BooleanField, 
    DateTimeField,
    ReferenceField,
    IntField,
    PULL
)
from datetime import datetime


class Employee(Document):
    """Employee model for storing user information."""
    meta = {
        'collection': 'employees',
        'indexes': [
            'email',  # Index for faster email lookups
            'is_active',
            ('email', 'is_active')  # Compound index
        ]
    }
    
    name = StringField(required=True, max_length=100)
    email = EmailField(required=True, unique=True)
    department = StringField(max_length=50)
    password_hash = StringField(required=True, max_length=255)  # Store hashed passwords
    role = StringField(max_length=20, default='client', choices=['admin', 'client'])
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    
    def save(self, *args, **kwargs):
        """Override save to update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()
        return super(Employee, self).save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} ({self.email})"


class MealSelection(Document):
    """Meal selection model for storing weekly meal choices."""
    meta = {
        'collection': 'meal_selections',
        'indexes': [
            'employee',
            'week_start_date',
            ('employee', 'week_start_date')  # Compound index for queries
        ]
    }
    
    employee = ReferenceField(Employee, required=True, reverse_delete_rule=PULL)
    week_start_date = DateTimeField(required=True)  # Monday of the week
    monday_meal = StringField()
    tuesday_meal = StringField()
    wednesday_meal = StringField()
    thursday_meal = StringField()
    friday_meal = StringField()
    special_dietary_requirements = StringField()
    submitted_at = DateTimeField(default=datetime.utcnow)
    is_submitted = BooleanField(default=False)
    
    def __str__(self):
        return f"Meal selection for {self.employee.name} - Week of {self.week_start_date.strftime('%Y-%m-%d')}"


class MealReminder(Document):
    """Meal reminder model for tracking sent reminders."""
    meta = {
        'collection': 'meal_reminders',
        'indexes': [
            'employee',
            'week_start_date',
            'reminder_sent_at'
        ]
    }
    
    employee = ReferenceField(Employee, required=True, reverse_delete_rule=PULL)
    week_start_date = DateTimeField(required=True)
    reminder_sent_at = DateTimeField(default=datetime.utcnow)
    reminder_type = StringField(max_length=20, default='weekly', choices=['weekly', 'reminder', 'final'])
    
    def __str__(self):
        return f"{self.reminder_type} reminder for {self.employee.name} - {self.week_start_date.strftime('%Y-%m-%d')}"


class MealOptions(Document):
    """Meal options model for storing available meal choices by day."""
    meta = {
        'collection': 'meal_options',
        'indexes': [
            'day',
            'is_active',
            ('name', 'day'),  # Compound unique index
            ('day', 'is_active')
        ]
    }
    
    name = StringField(required=True, max_length=100)
    day = StringField(
        required=True, 
        max_length=20,
        choices=['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
    )
    is_active = BooleanField(default=True)
    created_by = ReferenceField(Employee, required=True)
    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(default=datetime.utcnow)
    
    def save(self, *args, **kwargs):
        """Override save to update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()
        return super(MealOptions, self).save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} ({self.day})"
    
    @classmethod
    def ensure_unique_meal_per_day(cls, name, day, exclude_id=None):
        """Check if a meal with the same name already exists for the day."""
        query = cls.objects(name=name, day=day)
        if exclude_id:
            query = query.filter(id__ne=exclude_id)
        return query.first() is None

