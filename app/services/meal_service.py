"""
Meal management service for handling employee authentication and meal selections.
Contains all business logic for the meal management system using MongoDB/MongoEngine.
"""

import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from mongoengine.errors import NotUniqueError, DoesNotExist, ValidationError

from app.config import logger
from app.models.database import Employee, MealSelection, MealReminder, MealOptions


# ============================================================================
# AUTHENTICATION FUNCTIONS
# ============================================================================

def hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return hash_password(password) == hashed_password


def authenticate_employee(name: str, password: str) -> Dict:
    """
    Authenticate an employee by name and password.
    
    Args:
        name: Employee's full name
        password: Employee's password
        
    Returns:
        Dictionary with success status and employee data or error message
    """
    try:
        # Find employee by name (case-insensitive) and active status
        employee = Employee.objects(name__iexact=name, is_active=True).first()
        
        if not employee:
            return {"success": False, "error": "Employee not found or inactive"}
        
        # Verify password
        if not verify_password(password, employee.password_hash):
            return {"success": False, "error": "Invalid password"}
        
        # Get available meal options
        meal_options = get_meal_options_by_day()
        
        logger.info(f"Employee authenticated: {employee.name}")
        return {
            "success": True,
            "message": f"Welcome back, {employee.name}!",
            "employee": {
                "id": str(employee.id),
                "name": employee.name,
                "email": employee.email,
                "department": employee.department,
                "role": employee.role
            },
            "meal_options": meal_options
        }
        
    except Exception as e:
        logger.error(f"Error authenticating employee: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# EMPLOYEE MANAGEMENT FUNCTIONS
# ============================================================================

def add_employee(name: str, email: str, department: str = "General") -> Dict:
    """Add a new employee to the meal management system."""
    try:
        # Check if employee already exists
        existing = Employee.objects(email=email).first()
        if existing:
            return {"success": False, "error": f"Employee with email {email} already exists"}
        
        # Create new employee with a default password (should be changed)
        new_employee = Employee(
            name=name,
            email=email,
            password_hash=hash_password("changeme123"),  # Default password
            department=department
        )
        new_employee.save()
        
        logger.info(f"Added employee: {name} ({email})")
        return {
            "success": True,
            "message": f"Employee {name} added successfully",
            "employee_id": str(new_employee.id)
        }
        
    except NotUniqueError:
        return {"success": False, "error": f"Employee with email {email} already exists"}
    except ValidationError as e:
        return {"success": False, "error": f"Validation error: {str(e)}"}
    except Exception as e:
        logger.error(f"Error adding employee: {e}")
        return {"success": False, "error": str(e)}


def add_employee_with_password(name: str, email: str, password: str, department: str = "General") -> Dict:
    """Add a new employee with password to the meal management system."""
    try:
        # Check if employee already exists
        existing = Employee.objects(email=email).first()
        if existing:
            return {"success": False, "error": f"Employee with email {email} already exists"}
        
        # Create new employee
        new_employee = Employee(
            name=name,
            email=email,
            password_hash=hash_password(password),
            department=department
        )
        new_employee.save()
        
        logger.info(f"Added employee with password: {name} ({email})")
        return {
            "success": True,
            "message": f"Employee {name} added successfully with password",
            "employee_id": str(new_employee.id)
        }
        
    except NotUniqueError:
        return {"success": False, "error": f"Employee with email {email} already exists"}
    except ValidationError as e:
        return {"success": False, "error": f"Validation error: {str(e)}"}
    except Exception as e:
        logger.error(f"Error adding employee with password: {e}")
        return {"success": False, "error": str(e)}


def get_employees() -> List[Dict]:
    """Get all active employees."""
    try:
        employees = Employee.objects(is_active=True)
        
        return [
            {
                "id": str(emp.id),
                "name": emp.name,
                "email": emp.email,
                "department": emp.department
            }
            for emp in employees
        ]
        
    except Exception as e:
        logger.error(f"Error getting employees: {e}")
        return []


# ============================================================================
# ADMIN FUNCTIONS
# ============================================================================

def create_admin_user(name: str, email: str, password: str, department: str = "Management") -> Dict:
    """Create an admin user with full system access."""
    try:
        # Check if employee already exists
        existing = Employee.objects(email=email).first()
        if existing:
            return {"success": False, "error": f"Employee with email {email} already exists"}
        
        # Create admin employee
        admin_employee = Employee(
            name=name,
            email=email,
            password_hash=hash_password(password),
            department=department,
            role='admin'
        )
        admin_employee.save()
        
        logger.info(f"Created admin user: {name} ({email})")
        return {
            "success": True,
            "message": f"Admin user {name} created successfully",
            "employee_id": str(admin_employee.id),
            "role": "admin"
        }
        
    except NotUniqueError:
        return {"success": False, "error": f"Employee with email {email} already exists"}
    except ValidationError as e:
        return {"success": False, "error": f"Validation error: {str(e)}"}
    except Exception as e:
        logger.error(f"Error creating admin user: {e}")
        return {"success": False, "error": str(e)}


def get_all_employees_admin() -> List[Dict]:
    """Get all employees (admin only)."""
    try:
        employees = Employee.objects()
        
        return [
            {
                "id": str(emp.id),
                "name": emp.name,
                "email": emp.email,
                "department": emp.department,
                "role": emp.role,
                "is_active": emp.is_active,
                "created_at": emp.created_at.isoformat() if emp.created_at else None
            }
            for emp in employees
        ]
        
    except Exception as e:
        logger.error(f"Error getting all employees: {e}")
        return []


def deactivate_employee(employee_email: str) -> Dict:
    """Deactivate an employee (admin only)."""
    try:
        # Find employee
        employee = Employee.objects(email=employee_email).first()
        if not employee:
            return {"success": False, "error": f"Employee with email {employee_email} not found"}
        
        # Check if trying to deactivate admin
        if employee.role == 'admin':
            return {"success": False, "error": "Cannot deactivate admin users"}
        
        # Deactivate employee
        employee.is_active = False
        employee.save()
        
        logger.info(f"Deactivated employee: {employee.name}")
        return {
            "success": True,
            "message": f"Employee {employee.name} deactivated successfully"
        }
        
    except Exception as e:
        logger.error(f"Error deactivating employee: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MEAL SELECTION FUNCTIONS
# ============================================================================

def get_current_week_start() -> str:
    """Get the current week's Monday date in YYYY-MM-DD format."""
    today = datetime.now()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:  # Today is Monday
        monday = today
    else:
        monday = today + timedelta(days=days_until_monday)
    return monday.strftime("%Y-%m-%d")


def submit_meal_selection(employee_email: str, week_start_date: str, 
                         monday_meal: str = "", tuesday_meal: str = "", 
                         wednesday_meal: str = "", thursday_meal: str = "", 
                         friday_meal: str = "", special_requirements: str = "") -> Dict:
    """Submit meal selection for an employee for a specific week."""
    try:
        # Find employee
        employee = Employee.objects(email=employee_email).first()
        if not employee:
            return {"success": False, "error": f"Employee with email {employee_email} not found"}
        
        # Parse week start date
        try:
            week_start = datetime.strptime(week_start_date, "%Y-%m-%d")
        except ValueError:
            return {"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}
        
        # Check if selection already exists for this week
        existing = MealSelection.objects(employee=employee, week_start_date=week_start).first()
        
        if existing:
            # Update existing selection
            existing.monday_meal = monday_meal
            existing.tuesday_meal = tuesday_meal
            existing.wednesday_meal = wednesday_meal
            existing.thursday_meal = thursday_meal
            existing.friday_meal = friday_meal
            existing.special_dietary_requirements = special_requirements
            existing.is_submitted = True
            existing.submitted_at = datetime.utcnow()
            existing.save()
        else:
            # Create new selection
            new_selection = MealSelection(
                employee=employee,
                week_start_date=week_start,
                monday_meal=monday_meal,
                tuesday_meal=tuesday_meal,
                wednesday_meal=wednesday_meal,
                thursday_meal=thursday_meal,
                friday_meal=friday_meal,
                special_dietary_requirements=special_requirements,
                is_submitted=True
            )
            new_selection.save()
        
        logger.info(f"Meal selection submitted for {employee.name} for week starting {week_start_date}")
        return {
            "success": True,
            "message": f"Meal selection submitted successfully for {employee.name}",
            "week_start": week_start_date
        }
        
    except ValidationError as e:
        return {"success": False, "error": f"Validation error: {str(e)}"}
    except Exception as e:
        logger.error(f"Error submitting meal selection: {e}")
        return {"success": False, "error": str(e)}


def get_meal_selection(employee_email: str, week_start_date: str) -> Dict:
    """Get meal selection for an employee for a specific week."""
    try:
        # Find employee
        employee = Employee.objects(email=employee_email).first()
        if not employee:
            return {"success": False, "error": f"Employee with email {employee_email} not found"}
        
        # Parse week start date
        try:
            week_start = datetime.strptime(week_start_date, "%Y-%m-%d")
        except ValueError:
            return {"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}
        
        # Get meal selection
        selection = MealSelection.objects(employee=employee, week_start_date=week_start).first()
        
        if not selection:
            return {
                "success": True,
                "message": "No meal selection found for this week",
                "data": None
            }
        
        return {
            "success": True,
            "message": "Meal selection retrieved successfully",
            "data": {
                "employee_name": employee.name,
                "employee_email": employee.email,
                "week_start": week_start_date,
                "monday_meal": selection.monday_meal,
                "tuesday_meal": selection.tuesday_meal,
                "wednesday_meal": selection.wednesday_meal,
                "thursday_meal": selection.thursday_meal,
                "friday_meal": selection.friday_meal,
                "special_requirements": selection.special_dietary_requirements,
                "submitted_at": selection.submitted_at.isoformat() if selection.submitted_at else None,
                "is_submitted": selection.is_submitted
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting meal selection: {e}")
        return {"success": False, "error": str(e)}


def get_meal_status_for_employee(employee_email: str, week_start_date: str = None) -> Dict:
    """Get meal selection status for an employee."""
    if not week_start_date:
        week_start_date = get_current_week_start()
    
    result = get_meal_selection(employee_email, week_start_date)
    
    if result["success"]:
        if result["data"] is None:
            # No selection exists - all days are empty
            return {
                "success": True,
                "week_start": week_start_date,
                "employee_email": employee_email,
                "status": "no_selection",
                "filled_days": [],
                "empty_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                "message": "No meal selection found for this week. All days need to be filled."
            }
        
        data = result["data"]
        filled_days = []
        empty_days = []
        
        # Check each day
        days = [
            ("Monday", data["monday_meal"]),
            ("Tuesday", data["tuesday_meal"]),
            ("Wednesday", data["wednesday_meal"]),
            ("Thursday", data["thursday_meal"]),
            ("Friday", data["friday_meal"])
        ]
        
        for day_name, meal in days:
            if meal and meal.strip():
                filled_days.append(day_name)
            else:
                empty_days.append(day_name)
        
        status = "complete" if len(empty_days) == 0 else "partial"
        
        return {
            "success": True,
            "week_start": week_start_date,
            "employee_email": employee_email,
            "employee_name": data["employee_name"],
            "status": status,
            "filled_days": filled_days,
            "empty_days": empty_days,
            "special_requirements": data["special_requirements"],
            "message": f"Selection status: {len(filled_days)} days filled, {len(empty_days)} days empty"
        }
    
    return result


def update_meal_for_day(employee_email: str, day: str, meal_choice: str, week_start_date: str = None) -> Dict:
    """Update meal selection for a specific day."""
    if not week_start_date:
        week_start_date = get_current_week_start()
    
    try:
        # Find employee
        employee = Employee.objects(email=employee_email).first()
        if not employee:
            return {"success": False, "error": f"Employee with email {employee_email} not found"}
        
        # Parse week start date
        try:
            week_start = datetime.strptime(week_start_date, "%Y-%m-%d")
        except ValueError:
            return {"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}
        
        # Get or create meal selection
        selection = MealSelection.objects(employee=employee, week_start_date=week_start).first()
        
        if not selection:
            # Create new selection
            selection = MealSelection(
                employee=employee,
                week_start_date=week_start
            )
        
        # Update the specific day
        day_mapping = {
            "monday": "monday_meal",
            "tuesday": "tuesday_meal", 
            "wednesday": "wednesday_meal",
            "thursday": "thursday_meal",
            "friday": "friday_meal"
        }
        
        day_lower = day.lower()
        if day_lower not in day_mapping:
            return {"success": False, "error": f"Invalid day: {day}. Use Monday, Tuesday, Wednesday, Thursday, or Friday"}
        
        setattr(selection, day_mapping[day_lower], meal_choice)
        selection.submitted_at = datetime.utcnow()
        
        # Check if all days are filled
        all_meals = [selection.monday_meal, selection.tuesday_meal, selection.wednesday_meal, 
                    selection.thursday_meal, selection.friday_meal]
        selection.is_submitted = all(all_meals) and all(meal.strip() if meal else False for meal in all_meals)
        
        selection.save()
        
        return {
            "success": True,
            "message": f"Meal for {day} updated successfully",
            "day": day,
            "meal": meal_choice,
            "is_complete": selection.is_submitted
        }
        
    except ValidationError as e:
        return {"success": False, "error": f"Validation error: {str(e)}"}
    except Exception as e:
        logger.error(f"Error updating meal for day: {e}")
        return {"success": False, "error": str(e)}


def get_weekly_meal_summary(week_start_date: str) -> Dict:
    """Get meal summary for all employees for a specific week."""
    try:
        # Parse week start date
        try:
            week_start = datetime.strptime(week_start_date, "%Y-%m-%d")
        except ValueError:
            return {"success": False, "error": "Invalid date format. Use YYYY-MM-DD"}
        
        # Get all meal selections for the week
        selections = MealSelection.objects(week_start_date=week_start)
        
        summary = {
            "week_start": week_start_date,
            "total_employees": selections.count(),
            "submitted_count": selections.filter(is_submitted=True).count(),
            "pending_count": selections.filter(is_submitted=False).count(),
            "employees": []
        }
        
        for selection in selections:
            employee = selection.employee
            summary["employees"].append({
                "name": employee.name,
                "email": employee.email,
                "department": employee.department,
                "is_submitted": selection.is_submitted,
                "submitted_at": selection.submitted_at.isoformat() if selection.submitted_at else None,
                "meals": {
                    "monday": selection.monday_meal,
                    "tuesday": selection.tuesday_meal,
                    "wednesday": selection.wednesday_meal,
                    "thursday": selection.thursday_meal,
                    "friday": selection.friday_meal
                },
                "special_requirements": selection.special_dietary_requirements
            })
        
        return {
            "success": True,
            "message": "Weekly meal summary retrieved successfully",
            "data": summary
        }
        
    except Exception as e:
        logger.error(f"Error getting weekly meal summary: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# MEAL OPTIONS MANAGEMENT
# ============================================================================

def get_meal_options(include_inactive: bool = False) -> List[Dict]:
    """Get all available meal options."""
    try:
        if include_inactive:
            options = MealOptions.objects()
        else:
            options = MealOptions.objects(is_active=True)
        
        return [
            {
                "id": str(opt.id),
                "name": opt.name,
                "day": opt.day,
                "is_active": opt.is_active,
                "created_at": opt.created_at.isoformat() if opt.created_at else None
            }
            for opt in options
        ]
        
    except Exception as e:
        logger.error(f"Error getting meal options: {e}")
        return []


def get_meal_options_by_day() -> Dict:
    """Get meal options organized by day."""
    options = get_meal_options()
    
    organized_by_day = {}
    for option in options:
        day = option['day']
        if day not in organized_by_day:
            organized_by_day[day] = []
        organized_by_day[day].append(option)
    
    return organized_by_day


def add_meal_option(admin_email: str, name: str, day: str) -> Dict:
    """Add a new meal option for a specific day (admin only)."""
    try:
        # Verify admin
        admin = Employee.objects(email=admin_email, role='admin', is_active=True).first()
        
        if not admin:
            return {"success": False, "error": "Only active admin users can add meal options"}
        
        # Validate day
        valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
        day_lower = day.lower()
        if day_lower not in valid_days:
            return {"success": False, "error": f"Invalid day: {day}. Use Monday, Tuesday, Wednesday, Thursday, or Friday"}
        
        # Check if meal option already exists for this day
        existing = MealOptions.objects(name=name, day=day_lower).first()
        if existing:
            return {"success": False, "error": f"Meal option '{name}' already exists for {day_lower.title()}"}
        
        # Create new meal option
        new_option = MealOptions(
            name=name,
            day=day_lower,
            created_by=admin
        )
        new_option.save()
        
        logger.info(f"Added meal option: {name} for {day_lower} by admin {admin.name}")
        return {
            "success": True,
            "message": f"Meal option '{name}' added successfully for {day_lower.title()}",
            "option_id": str(new_option.id)
        }
        
    except ValidationError as e:
        return {"success": False, "error": f"Validation error: {str(e)}"}
    except Exception as e:
        logger.error(f"Error adding meal option: {e}")
        return {"success": False, "error": str(e)}


def update_meal_option(admin_email: str, option_name: str, day: str, new_name: str = None, 
                      new_day: str = None, is_active: bool = None) -> Dict:
    """Update a meal option (admin only)."""
    try:
        # Verify admin
        admin = Employee.objects(email=admin_email, role='admin', is_active=True).first()
        
        if not admin:
            return {"success": False, "error": "Only active admin users can update meal options"}
        
        # Validate day
        valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
        day_lower = day.lower()
        if day_lower not in valid_days:
            return {"success": False, "error": f"Invalid day: {day}. Use Monday, Tuesday, Wednesday, Thursday, or Friday"}
        
        # Find meal option
        option = MealOptions.objects(name=option_name, day=day_lower).first()
        if not option:
            return {"success": False, "error": f"Meal option '{option_name}' not found for {day_lower.title()}"}
        
        # Update fields
        if new_name is not None:
            option.name = new_name
        
        if new_day is not None:
            new_day_lower = new_day.lower()
            if new_day_lower not in valid_days:
                return {"success": False, "error": f"Invalid new day: {new_day}"}
            option.day = new_day_lower
        
        if is_active is not None:
            option.is_active = is_active
        
        option.updated_at = datetime.utcnow()
        option.save()
        
        logger.info(f"Updated meal option: {option_name} for {day_lower} by admin {admin.name}")
        return {
            "success": True,
            "message": f"Meal option '{option_name}' updated successfully"
        }
        
    except ValidationError as e:
        return {"success": False, "error": f"Validation error: {str(e)}"}
    except Exception as e:
        logger.error(f"Error updating meal option: {e}")
        return {"success": False, "error": str(e)}


def delete_meal_option(admin_email: str, option_name: str, day: str) -> Dict:
    """Delete a meal option for a specific day (admin only)."""
    try:
        # Verify admin
        admin = Employee.objects(email=admin_email, role='admin', is_active=True).first()
        
        if not admin:
            return {"success": False, "error": "Only active admin users can delete meal options"}
        
        # Validate day
        valid_days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
        day_lower = day.lower()
        if day_lower not in valid_days:
            return {"success": False, "error": f"Invalid day: {day}"}
        
        # Find meal option
        option = MealOptions.objects(name=option_name, day=day_lower).first()
        if not option:
            return {"success": False, "error": f"Meal option '{option_name}' not found for {day_lower.title()}"}
        
        # Delete the option
        option.delete()
        
        logger.info(f"Deleted meal option: {option_name} for {day_lower} by admin {admin.name}")
        return {
            "success": True,
            "message": f"Meal option '{option_name}' deleted successfully for {day_lower.title()}"
        }
        
    except Exception as e:
        logger.error(f"Error deleting meal option: {e}")
        return {"success": False, "error": str(e)}
