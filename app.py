from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import pandas as pd
from datetime import datetime, timedelta
import os
from threading import Thread
import time
import logging
import calendar
import json  # Add this import
from flask import send_file
import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
import io


app = Flask(__name__)
app.secret_key = os.urandom(24)  # Changed secret key
app.permanent_session_lifetime = timedelta(minutes=30)

logging.basicConfig(level=logging.DEBUG)

# Create data directory and initialize Excel files
if not os.path.exists('data'):
    os.makedirs('data')

# Add this to your init_excel_files function
def init_excel_files():
    excel_files = {
        # In the init_excel_files function, update the members.xlsx structure
        'members.xlsx': {
            'member_id': [], 
            'name': [], 
            'phone': [], 
            'address': [], 
            'dob': [], 
            'gender': [], 
            'next_of_kin_name': [], 
            'next_of_kin_phone': [],
            'package': [], 
            'join_date': [], 
            'expiry_date': [], 
            'status': [],
            'payment_status': [],
            'medical_conditions': [],
            'weight': [],
            'height': []
        },
        'packages.xlsx': {
            'name': [], 
            'price': [], 
            'duration': [],
            'trainers': [], 
            'cardio_access': [], 
            'sauna_access': [],  # New column
            'steam_room': [],    # New column
            'timings': []
        },
        'trainers.xlsx': {
            'id': [], 'name': [], 'specialization': [], 'schedule': []
        },
        'trainer_attendance.xlsx': {
            'date': [], 'trainer_id': [], 'trainer_name': [], 
            'check_in': [], 'check_out': []
        },
        'payments.xlsx': {
            'date': [], 'member_id': [], 'member_name': [], 
            'package': [], 'amount': [], 'status': []
        },
        'receptionists.xlsx': {
            'username': [], 'password': [], 'name': [], 'phone': [], 
            'address': [], 'dob': [], 'age': [], 'gender': [], 
            'salary': [], 'next_of_kin_name': [], 'next_of_kin_phone': [],
            'privileges': []
        },
        'attendance.xlsx': {
            'date': [], 'member_id': [], 'member_name': [], 
            'check_in': [], 'check_out': []  # Added check_out
        },
        'custom_products.xlsx': {
            'product_id': [],
            'product_name': [],
            'ingredients': [],
            'price': [],
            'created_by': [],
            'creation_date': [],
            'can_be_sold': [],
            'final_price': [],
            'inventory_status': []
        },
        'inventory.xlsx': {
            'id': [], 'stock_type': [], 'servings': [], 'cost_per_serving': [],
            'profit_per_serving': [], 'other_charges': [], 'date_added': []
        },
        'sales.xlsx': {
            'id': [], 'date': [], 'member_id': [], 'member_name': [], 'inventory_id': [], 
            'item_name': [], 'quantity': [], 'total_amount': [], 'payment_method': []
        },
        
    }
    
    for filename, columns in excel_files.items():
        filepath = f'data/{filename}'
        if not os.path.exists(filepath):
            pd.DataFrame(columns).to_excel(filepath, index=False)

init_excel_files()

# Authentication routes
@app.route('/')
def login():
    if 'user_type' in session:
        if session['user_type'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('receptionist_dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_post():
    username = request.form.get('username')
    password = request.form.get('password')
    
    try:
        # Check admin login
        admin_df = pd.read_excel('data/admin.xlsx')
        admin = admin_df[
            (admin_df['username'].astype(str).str.lower() == str(username).lower()) & 
            (admin_df['password'].astype(str) == str(password))
        ]
        
        if not admin.empty:
            session.permanent = True
            session['user_type'] = 'admin'
            session['username'] = username
            return redirect(url_for('admin_dashboard'))
        
        # Check staff login
        receptionists = pd.read_excel('data/receptionists.xlsx')
        receptionist = receptionists[
            (receptionists['username'].astype(str) == str(username)) & 
            (receptionists['password'].astype(str) == str(password))
        ]
        
        if not receptionist.empty:
            session.permanent = True
            session['user_type'] = 'staff'
            session['username'] = username
            privileges_str = receptionist.iloc[0]['privileges']
            if pd.isna(privileges_str):
                session['privileges'] = []
            else:
                session['privileges'] = [p.strip() for p in privileges_str.split(',') if p.strip()]
            return redirect(url_for('staff_dashboard'))
        
        flash('Invalid credentials')
    except Exception as e:
        app.logger.error(f"Login error: {e}")
        flash('Error during login')
    
    return redirect(url_for('login'))

@app.route('/staff/dashboard')
@app.route('/staff_dashboard')
def staff_dashboard():
    if 'user_type' not in session or session['user_type'] != 'staff':
        return redirect(url_for('login'))
    
    try:
        # Get staff details including privileges
        staff_df = pd.read_excel('data/receptionists.xlsx')
        staff = staff_df[staff_df['username'] == session['username']].iloc[0]
        
        # Convert privileges string to list properly
        privileges = []
        if not pd.isna(staff['privileges']) and staff['privileges']:
            privileges = [priv.strip() for priv in staff['privileges'].split(',')]
        
        # Store privileges in session
        session['privileges'] = privileges
        
        return render_template('staff/dashboard.html',
                             staff=staff.to_dict(),
                             privileges=privileges)
                             
    except Exception as e:
        app.logger.error(f"Error loading staff dashboard: {e}")
        flash('Error loading dashboard')
        return redirect(url_for('login'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# This duplicate route and keep only one instance
@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        members_df = pd.read_excel('data/members.xlsx')
        packages_df = pd.read_excel('data/packages.xlsx')
        payments_df = pd.read_excel('data/payments.xlsx')
        receptionists_df = pd.read_excel('data/receptionists.xlsx')
        
        # Calculate statistics
        stats = {
            'total_members': len(members_df),
            'monthly_revenue': payments_df[
                payments_df['date'].astype(str).str.startswith(datetime.now().strftime('%Y-%m'))
            ]['amount'].sum(),
            'total_packages': len(packages_df),
            'total_receptionists': len(receptionists_df)
        }
        
        # Revenue by package
        revenue_by_package = payments_df.groupby('package')['amount'].sum().to_dict()
        package_names = list(packages_df['name'])
        revenue_data = [revenue_by_package.get(pkg, 0) for pkg in package_names]
        
        # Members by package
        members_by_package = members_df['package'].value_counts().to_dict()
        members_data = [members_by_package.get(pkg, 0) for pkg in package_names]
        
        return render_template('admin/dashboard.html',
                             stats=stats,
                             package_names=package_names,
                             revenue_data=revenue_data,
                             members_data=members_data)
    except Exception as e:
        app.logger.error(f"Error loading admin dashboard: {e}")
        flash('Error loading dashboard data')
        return redirect(url_for('login'))

@app.route('/receptionist/dashboard')
def receptionist_dashboard():
    if 'user_type' not in session or session['user_type'] != 'receptionist':
        return redirect(url_for('login'))
    return render_template('receptionist/dashboard.html')

@app.route('/view_members')
def view_members():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    if session['user_type'] != 'admin' and 'members' not in session.get('privileges', []):
        flash('You do not have permission to view members')
        return redirect(url_for('staff_dashboard'))
    
    try:
        members_df = pd.read_excel('data/members.xlsx')
        packages_df = pd.read_excel('data/packages.xlsx')
        
        # Ensure member_id is included in the display
        if 'member_id' not in members_df.columns:
            members_df['member_id'] = range(1001, 1001 + len(members_df))
            members_df.to_excel('data/members.xlsx', index=False)
        
        # Convert members DataFrame to list of dictionaries for template
        members = members_df.to_dict('records')
        packages = packages_df['name'].tolist()
        
        return render_template('members.html',
                             members=members,
                             packages=packages,
                             active_page='members')
    except Exception as e:
        app.logger.error(f"Error loading members: {e}")
        flash('Error loading members data')
        return redirect(url_for('staff_dashboard'))

@app.route('/members/edit/<member_id>', methods=['GET', 'POST'])
def edit_member(member_id):
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        members_df = pd.read_excel('data/members.xlsx')
        packages_df = pd.read_excel('data/packages.xlsx')
        
        # Convert member_id column to string and clean any NaN values
        members_df['member_id'] = members_df['member_id'].fillna('').astype(str)
        member_data = members_df[members_df['member_id'] == str(member_id)]
        
        if member_data.empty:
            flash('Member not found')
            return redirect(url_for('view_members'))
        
        if request.method == 'POST':
            # Create a mask for the specific member
            mask = members_df['member_id'] == str(member_id)
            
            # Update member information using the mask
            update_fields = {
                'name': request.form.get('name'),
                'phone': request.form.get('phone'),
                'gender': request.form.get('gender'),
                'dob': request.form.get('dob'),
                'address': request.form.get('address'),
                'medical_conditions': request.form.get('medical_conditions'),
                'package': request.form.get('package'),
                'weight': request.form.get('weight'),
                'height': request.form.get('height'),
                'next_of_kin_name': request.form.get('next_of_kin_name'),
                'next_of_kin_phone': request.form.get('next_of_kin_phone')
            }
            
            # Update all fields at once
            for field, value in update_fields.items():
                members_df.loc[mask, field] = value
            
            members_df.to_excel('data/members.xlsx', index=False)
            flash('Member updated successfully')
            return redirect(url_for('view_members'))
        
        # GET request - display edit form
        member = member_data.iloc[0].to_dict()
        return render_template('edit_member.html', 
                             member=member,
                             packages=packages_df.to_dict('records'))
                             
    except Exception as e:
        app.logger.error(f"Error editing member: {e}")
        flash('Error updating member')
        return redirect(url_for('view_members'))


@app.route('/members/delete/<member_id>')
def delete_member(member_id):
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        members_df = pd.read_excel('data/members.xlsx')
        
        # Convert member_id column to string and clean any NaN values
        members_df['member_id'] = members_df['member_id'].fillna('').astype(str)
        
        # Find the member to delete
        member_mask = members_df['member_id'] == str(member_id)
        
        if any(member_mask):
            # Delete the member
            members_df = members_df[~member_mask]
            members_df.to_excel('data/members.xlsx', index=False)
            flash('Member deleted successfully')
        else:
            flash('Member not found')
            
    except Exception as e:
        app.logger.error(f"Error deleting member: {e}")
        flash('Error deleting member')
    
    return redirect(url_for('view_members'))

# Attendance routes
@app.route('/attendance')
def attendance():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        # Load members and attendance data
        members_df = pd.read_excel('data/members.xlsx')
        attendance_df = pd.read_excel('data/attendance.xlsx') if os.path.exists('data/attendance.xlsx') else pd.DataFrame()
        
        # Get today's date
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Filter today's attendance
        today_attendance = attendance_df[attendance_df['date'] == today] if not attendance_df.empty else pd.DataFrame()
        
        return render_template('attendance.html',
                             members=members_df.to_dict('records'),
                             attendance=today_attendance.to_dict('records'),  # Changed from today_attendance to attendance
                             current_date=today)
    except Exception as e:
        app.logger.error(f"Error loading attendance page: {e}")
        flash('Error loading attendance data')
        return redirect(url_for('staff_dashboard'))

@app.route('/staff_attendance')
def staff_attendance():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    # Check for both admin and staff with staff_attendance privilege
    if session['user_type'] != 'admin' and 'staff_attendance' not in session.get('privileges', []):
        flash('Access denied')
        return redirect(url_for('staff_dashboard'))
    
    try:
        staff_df = pd.read_excel('data/receptionists.xlsx')
        staff_attendance_df = pd.read_excel('data/trainer_attendance.xlsx')
        
        today = datetime.now().strftime('%Y-%m-%d')
        today_staff_attendance = staff_attendance_df[staff_attendance_df['date'] == today]
        
        return render_template('staff_attendance.html',
                             staff=staff_df.to_dict('records'),
                             staff_attendance=today_staff_attendance.to_dict('records'))
    except Exception as e:
        app.logger.error(f"Error loading staff attendance: {e}")
        flash('Error loading staff attendance data')
        return redirect(url_for('staff_dashboard'))




@app.route('/mark_staff_attendance', methods=['POST'])
def mark_staff_attendance():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        if not os.path.exists('data/trainer_attendance.xlsx'):
            pd.DataFrame(columns=[
                'date', 'trainer_id', 'trainer_name', 'staff_type', 'check_in', 'check_out'
            ]).to_excel('data/trainer_attendance.xlsx', index=False)
            
        staff_attendance_df = pd.read_excel('data/trainer_attendance.xlsx')
        staff_df = pd.read_excel('data/receptionists.xlsx')
        
        staff_id = request.form.get('staff_id')
        action = request.form.get('staff_attendance_action')
        
        if not staff_id:
            flash('Staff ID is required')
            return redirect(url_for('staff_attendance'))
            
        staff_query = staff_df[staff_df['username'] == staff_id]
        
        if staff_query.empty:
            flash('Staff member not found')
            return redirect(url_for('staff_attendance'))
        
        staff = staff_query.iloc[0]
        today = datetime.now().strftime('%Y-%m-%d')
        current_time = datetime.now().strftime('%H:%M:%S')
        
        # Convert date column to datetime if it exists
        if 'date' in staff_attendance_df.columns:
            staff_attendance_df['date'] = pd.to_datetime(staff_attendance_df['date']).dt.strftime('%Y-%m-%d')
        
        # Check today's attendance for this staff member
        today_attendance = staff_attendance_df[
            (staff_attendance_df['date'] == today) & 
            (staff_attendance_df['trainer_id'] == staff_id)
        ]
        
        if action == 'check_in':
            if not today_attendance.empty:
                if pd.isna(today_attendance.iloc[0]['check_out']):
                    flash('You have already checked in and not checked out yet')
                else:
                    flash('You have already completed your attendance for today')
                return redirect(url_for('staff_attendance'))
                
            new_attendance = {
                'date': today,
                'trainer_id': staff_id,
                'trainer_name': staff['name'],
                'staff_type': staff['staff_type'],
                'check_in': current_time,
                'check_out': None
            }
            staff_attendance_df = pd.concat([staff_attendance_df, pd.DataFrame([new_attendance])], ignore_index=True)
            flash('Staff check-in recorded successfully')
            
        elif action == 'check_out':
            if today_attendance.empty:
                flash('You need to check in first')
            elif pd.notna(today_attendance.iloc[0]['check_out']):
                flash('You have already checked out for today')
            else:
                staff_attendance_df.loc[
                    (staff_attendance_df['date'] == today) & 
                    (staff_attendance_df['trainer_id'] == staff_id),
                    'check_out'
                ] = current_time
                flash('Staff check-out recorded successfully')
        
        staff_attendance_df.to_excel('data/trainer_attendance.xlsx', index=False)
        
    except Exception as e:
        app.logger.error(f"Error marking staff attendance: {str(e)}")
        flash('Error marking staff attendance')
    
    return redirect(url_for('staff_attendance'))

@app.route('/attendance/mark', methods=['POST'])
def mark_attendance():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        if not os.path.exists('data/attendance.xlsx'):
            pd.DataFrame(columns=[
                'date', 'member_id', 'member_name', 'check_in', 'check_out'
            ]).to_excel('data/attendance.xlsx', index=False)
        
        attendance_df = pd.read_excel('data/attendance.xlsx')
        members_df = pd.read_excel('data/members.xlsx')
        
        # Convert date column to datetime if it exists
        if 'date' in attendance_df.columns:
            attendance_df['date'] = pd.to_datetime(attendance_df['date']).dt.strftime('%Y-%m-%d')
        
        member_id = request.form.get('member_id')
        action = request.form.get('action')
        current_date = datetime.now().strftime('%Y-%m-%d')
        current_time = datetime.now().strftime('%H:%M:%S')
        
        # Convert member_id to string for comparison
        member_id_str = str(member_id)
        members_df['member_id'] = members_df['member_id'].astype(str)
        
        # Find member
        member = members_df[members_df['member_id'] == member_id_str].iloc[0]
        
        # Check today's attendance for this member
        today_attendance = attendance_df[
            (attendance_df['member_id'].astype(str) == member_id_str) & 
            (attendance_df['date'] == current_date)
        ]
        
        if action == 'check_in':
            if not today_attendance.empty:
                flash(f'Member {member["name"]} has already checked in today')
                return redirect(url_for('attendance'))
            
            # Mark check-in
            new_attendance = {
                'date': current_date,
                'member_id': member_id_str,
                'member_name': member['name'],
                'check_in': current_time,
                'check_out': None
            }
            attendance_df = pd.concat([attendance_df, pd.DataFrame([new_attendance])], ignore_index=True)
            flash(f'Attendance marked for {member["name"]}')
            
        elif action == 'check_out':
            if today_attendance.empty:
                flash(f'Member {member["name"]} has not checked in today')
                return redirect(url_for('attendance'))
            
            if pd.notna(today_attendance.iloc[0]['check_out']):
                flash(f'Member {member["name"]} has already checked out today')
                return redirect(url_for('attendance'))
            
            # Mark check-out
            mask = (attendance_df['member_id'].astype(str) == member_id_str) & (attendance_df['date'] == current_date)
            attendance_df.loc[mask, 'check_out'] = current_time
            flash(f'Check-out marked for {member["name"]}')
        
        attendance_df.to_excel('data/attendance.xlsx', index=False)
        
    except Exception as e:
        app.logger.error(f"Error marking attendance: {str(e)}")
        flash(f'Error marking attendance: {str(e)}')
    
    return redirect(url_for('attendance'))

# Package management routes
@app.route('/packages')
def packages():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    if session['user_type'] != 'admin' and 'packages' not in session.get('privileges', []):
        flash('Access denied')
        return redirect(url_for('staff_dashboard'))
    
    try:
        packages_df = pd.read_excel('data/packages.xlsx')
        return render_template('packages.html', 
                             packages=packages_df.to_dict('records'),
                             is_admin=session['user_type'] == 'admin')
    except Exception as e:
        app.logger.error(f"Error reading packages file: {e}")
        flash('Error loading packages data')
        return redirect(url_for('staff_dashboard'))

@app.route('/packages/add', methods=['POST'])
def add_package():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    # Allow both admin and staff with packages privilege
    if session['user_type'] != 'admin' and 'packages' not in session.get('privileges', []):
        flash('Access denied')
        return redirect(url_for('staff_dashboard'))
    
    try:
        packages_df = pd.read_excel('data/packages.xlsx')
        new_package = {
            'name': request.form.get('name'),
            'price': float(request.form.get('price')),
            'duration': request.form.get('duration'),
            'trainers': request.form.get('trainers'),
            'cardio_access': request.form.get('cardio_access'),
            'sauna_access': request.form.get('sauna_access'),
            'steam_room': request.form.get('steam_room'),
            'timings': request.form.get('timings')
        }
        
        packages_df = pd.concat([packages_df, pd.DataFrame([new_package])], ignore_index=True)
        packages_df.to_excel('data/packages.xlsx', index=False)
        flash('Package added successfully')
    except Exception as e:
        app.logger.error(f"Error adding package: {e}")
        flash('Error adding package')
    
    return redirect(url_for('packages'))

@app.route('/packages/delete/<name>')
def delete_package(name):
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    # Allow both admin and staff with packages privilege
    if session['user_type'] != 'admin' and 'packages' not in session.get('privileges', []):
        flash('Access denied')
        return redirect(url_for('staff_dashboard'))
    
    try:
        packages_df = pd.read_excel('data/packages.xlsx')
        packages_df = packages_df[packages_df['name'] != name]
        packages_df.to_excel('data/packages.xlsx', index=False)
        flash('Package deleted successfully')
    except Exception as e:
        app.logger.error(f"Error deleting package: {e}")
        flash('Error deleting package')
    
    return redirect(url_for('packages'))

@app.route('/packages/edit/<name>', methods=['GET', 'POST'])
def edit_package(name):
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    # Allow both admin and staff with packages privilege
    if session['user_type'] != 'admin' and 'packages' not in session.get('privileges', []):
        flash('Access denied')
        return redirect(url_for('staff_dashboard'))
    
    try:
        packages_df = pd.read_excel('data/packages.xlsx')
        package_row = packages_df[packages_df['name'] == name]
        
        if package_row.empty:
            flash('Package not found')
            return redirect(url_for('packages'))
            
        if request.method == 'POST':
            packages_df.loc[packages_df['name'] == name, 'price'] = float(request.form.get('price'))
            packages_df.loc[packages_df['name'] == name, 'duration'] = int(request.form.get('duration'))
            packages_df.loc[packages_df['name'] == name, 'trainers'] = request.form.get('trainers')
            packages_df.loc[packages_df['name'] == name, 'cardio_access'] = request.form.get('cardio_access')
            packages_df.loc[packages_df['name'] == name, 'sauna_access'] = request.form.get('sauna_access')
            packages_df.loc[packages_df['name'] == name, 'steam_room'] = request.form.get('steam_room')
            packages_df.loc[packages_df['name'] == name, 'timings'] = request.form.get('timings')
            
            packages_df.to_excel('data/packages.xlsx', index=False)
            flash('Package updated successfully')
            return redirect(url_for('packages'))
        
        package = package_row.iloc[0].to_dict()
        return render_template('edit_package.html', package=package)
        
    except Exception as e:
        app.logger.error(f"Error editing package: {e}")
        flash('Error updating package')
        return redirect(url_for('packages'))



@app.route('/payments')
def payments():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    # Check for both admin and staff with payments privilege
    if session['user_type'] != 'admin' and 'payments' not in session.get('privileges', []):
        flash('Access denied')
        return redirect(url_for('staff_dashboard'))
    
    try:
        payments_df = pd.read_excel('data/payments.xlsx')
        members_df = pd.read_excel('data/members.xlsx')
        packages_df = pd.read_excel('data/packages.xlsx')
        
        packages = dict(zip(packages_df['name'], packages_df['price']))
        
        return render_template('payments.html',
                             payments=payments_df.to_dict('records'),
                             members=members_df.to_dict('records'),
                             packages=packages)
    except Exception as e:
        app.logger.error(f"Error loading payments: {e}")
        flash('Error loading payments')
        return redirect(url_for('staff_dashboard'))

@app.route('/members/add', methods=['GET'])
def add_member_page():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        packages_df = pd.read_excel('data/packages.xlsx')
        return render_template('add_member.html', 
                             packages=packages_df.to_dict('records'),
                             datetime=datetime)  # Pass datetime to the template
    except Exception as e:
        app.logger.error(f"Error loading add member page: {e}")
        flash('Error loading packages data')
        return redirect(url_for('view_members'))

@app.route('/members/add', methods=['POST'])
def add_member():
    try:
        members_df = pd.read_excel('data/members.xlsx')
        
        # Generate unique member ID
        if members_df.empty or 'member_id' not in members_df.columns:
            next_id = 1001
        else:
            # Convert member_id to numeric, handling any non-numeric values
            valid_ids = pd.to_numeric(members_df['member_id'], errors='coerce')
            next_id = int(valid_ids.max() + 1) if not valid_ids.empty else 1001
        
        new_member = {
            'member_id': next_id,  # Ensure member_id is included
            'name': request.form.get('name'),
            'phone': request.form.get('phone'),
            'gender': request.form.get('gender'),
            'dob': request.form.get('dob'),
            'address': request.form.get('address'),
            'package': request.form.get('package'),
            'join_date': datetime.now().strftime('%Y-%m-%d'),
            'next_of_kin_name': request.form.get('kin_name'),
            'next_of_kin_phone': request.form.get('kin_phone'),
            'medical_conditions': request.form.get('medical_conditions'),
            'weight': request.form.get('weight'),
            'height': request.form.get('height'),
            'status': 'Active',
            'payment_status': 'Pending'  # Added payment status
        }
        
        # Create DataFrame with single row and concat
        new_member_df = pd.DataFrame([new_member])
        members_df = pd.concat([members_df, new_member_df], ignore_index=True)
        members_df.to_excel('data/members.xlsx', index=False)
        flash('Member added successfully')
        
    except Exception as e:
        app.logger.error(f"Error adding member: {e}")
        flash('Error adding member')
    
    return redirect(url_for('view_members'))



# @app.route('/payments/add', methods=['POST'])
# def add_payment():
#     if 'user_type' not in session:
#         return redirect(url_for('login'))
    
#     try:
#         payments_df = pd.read_excel('data/payments.xlsx')
#         members_df = pd.read_excel('data/members.xlsx')
        
#         member_id = request.form.get('member_id')
#         member = members_df[members_df['id'].astype(str) == str(member_id)].iloc[0]
        
#         new_payment = {
#             'date': datetime.now().strftime('%Y-%m-%d'),
#             'member_id': member_id,
#             'member_name': member['name'],
#             'package': member['package'],
#             'amount': float(request.form.get('amount')),
#             'status': 'Paid'
#         }
        
#         payments_df = pd.concat([payments_df, pd.DataFrame([new_payment])], ignore_index=True)
#         payments_df.to_excel('data/payments.xlsx', index=False)
        
#         # Update member payment status
#         members_df.loc[members_df['id'].astype(str) == str(member_id), 'payment_status'] = 'Paid'
#         members_df.to_excel('data/members.xlsx', index=False)
        
#         flash('Payment recorded successfully')
#     except Exception as e:
#         app.logger.error(f"Error recording payment: {e}")
#         flash('Error recording payment')
    
#     return redirect(url_for('payments'))





@app.route('/custom_product', methods=['GET'])
def custom_product_page():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        inventory_df = pd.read_excel('data/inventory.xlsx')
        return render_template('custom_product.html', 
                             inventory=inventory_df.to_dict('records'),
                             staff_name=session.get('username'))
    except Exception as e:
        app.logger.error(f"Error loading custom product page: {e}")
        flash('Error loading inventory data')
        return redirect(url_for('sales'))

@app.route('/add_custom_product', methods=['POST'])
def add_custom_product():
    try:
        # Get form data with correct field names
        product_name = str(request.form.get('product_name', '')).strip()
        ingredients_json = request.form.get('ingredients_json', '[]')
        final_price = int(float(request.form.get('final_price', '0')))
        
        if not product_name:
            flash('Product name is required')
            return redirect(url_for('custom_product_page'))

        # Parse ingredients JSON
        try:
            ingredients = json.loads(ingredients_json)
        except json.JSONDecodeError:
            ingredients = []

        # Calculate total cost from ingredients
        total_cost = sum(float(item['price']) * float(item['quantity']) for item in ingredients)
        profit = final_price - total_cost

        # Create or load custom_products.xlsx
        file_path = 'data/custom_products.xlsx'
        os.makedirs('data', exist_ok=True)
        
        try:
            custom_products_df = pd.read_excel(file_path)
        except FileNotFoundError:
            custom_products_df = pd.DataFrame(columns=[
                'product_id', 'product_name', 'ingredients', 
                'total_cost', 'final_price', 'profit',
                'created_by', 'creation_date'
            ])

        # Generate unique product ID
        next_id = 1001 if custom_products_df.empty else int(custom_products_df['product_id'].max()) + 1

        # Create new product entry
        new_product = {
            'product_id': next_id,
            'product_name': product_name,
            'ingredients': ingredients_json,  # Store the original JSON string
            'total_cost': total_cost,
            'final_price': final_price,
            'profit': profit,
            'created_by': session.get('username', 'admin'),
            'creation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        # Add to DataFrame and save
        custom_products_df = pd.concat([custom_products_df, pd.DataFrame([new_product])], ignore_index=True)
        custom_products_df.to_excel(file_path, index=False)
        
        flash('Custom product added successfully')
        return redirect(url_for('custom_product_page'))

    except Exception as e:
        app.logger.error(f"Error in add_custom_product: {str(e)}")
        flash(f'Error adding custom product: {str(e)}')
        return redirect(url_for('custom_product_page'))








@app.route('/payments/mark_as_paid', methods=['POST'])
def mark_payment_as_paid():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        # Initialize DataFrames
        if not os.path.exists('data/payments.xlsx'):
            pd.DataFrame(columns=['date', 'member_id', 'member_name', 'package', 'amount', 'status']).to_excel('data/payments.xlsx', index=False)
        
        payments_df = pd.read_excel('data/payments.xlsx')
        members_df = pd.read_excel('data/members.xlsx')
        packages_df = pd.read_excel('data/packages.xlsx')
        
        # Get member_id from form and log it for debugging
        member_id = request.form.get('member_id')
        app.logger.info(f"Received member_id from form: {member_id}")
        
        if not member_id:
            app.logger.error("No member_id received from form")
            flash("Member ID is required")
            return redirect(url_for('payments'))
        
        # Convert member_id to string for comparison
        member_id_str = str(member_id)
        
        # Debug: Print all member IDs in the dataframe
        app.logger.info(f"All member IDs in database: {members_df['member_id'].tolist()}")
        
        # Convert all member_id values to string for comparison
        members_df['member_id'] = members_df['member_id'].astype(str)
        
        # Find the member
        member_rows = members_df[members_df['member_id'] == member_id_str]
        
        if member_rows.empty:
            app.logger.error(f"Member with ID {member_id} not found in database")
            flash(f"Member with ID {member_id} not found")
            return redirect(url_for('payments'))
            
        member = member_rows.iloc[0]
        package_name = member['package']
        
        # Get package price
        package_row = packages_df[packages_df['name'] == package_name]
        if package_row.empty:
            app.logger.error(f"Package {package_name} not found")
            flash(f"Package {package_name} not found")
            return redirect(url_for('payments'))
            
        package_price = package_row['price'].iloc[0]
        
        # Create new payment record
        payment_date = datetime.now().strftime('%Y-%m-%d')
        new_payment = {
            'date': payment_date,
            'member_id': member_id_str,
            'member_name': member['name'],
            'package': package_name,
            'amount': float(package_price),
            'status': 'Paid'
        }
        
        # Add to payments dataframe
        payments_df = pd.concat([payments_df, pd.DataFrame([new_payment])], ignore_index=True)
        payments_df.to_excel('data/payments.xlsx', index=False)
        
        # Update member payment status
        members_df.loc[members_df['member_id'] == member_id_str, 'payment_status'] = 'Paid'
        members_df.to_excel('data/members.xlsx', index=False)
        
        app.logger.info(f"Payment recorded successfully for member {member_id_str}")
        flash('Payment recorded successfully')
        
    except Exception as e:
        app.logger.error(f"Error recording payment: {str(e)}")
        flash(f'Error recording payment: {str(e)}')
    
    return redirect(url_for('payments'))





# Receptionist management routes
@app.route('/admin/receptionists')
def manage_receptionists():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        # Get and process privileges
        privileges = session.get('privileges', '')
        if isinstance(privileges, str):
            privileges = [p.strip() for p in privileges.split(',') if p.strip()]
        
        # Check access rights
        if session['user_type'] != 'admin' and 'staff' not in privileges:
            flash('Access denied')
            return redirect(url_for('staff_dashboard'))
        
        # Create file if it doesn't exist
        if not os.path.exists('data/receptionists.xlsx'):
            df = pd.DataFrame(columns=[
                'username', 'password', 'name', 'phone', 'address', 
                'dob', 'age', 'gender', 'salary', 'next_of_kin_name',
                'next_of_kin_phone', 'privileges', 'staff_type'
            ])
            df.to_excel('data/receptionists.xlsx', index=False)
        
        staff_df = pd.read_excel('data/receptionists.xlsx')
        return render_template('admin/staff.html', 
                             staff=staff_df.to_dict('records'),
                             is_admin=session['user_type'] == 'admin',
                             user_privileges=privileges)
    except Exception as e:
        app.logger.error(f"Error loading staff data: {e}")
        flash('Error loading staff data')
        return redirect(url_for('staff_dashboard'))

@app.route('/admin/staff/add', methods=['POST'])
def add_staff():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        # Get and process privileges
        privileges = session.get('privileges', '')
        if isinstance(privileges, str):
            privileges = [p.strip() for p in privileges.split(',') if p.strip()]
        
        # Check access rights
        if session['user_type'] != 'admin' and 'staff' not in privileges:
            flash('Access denied')
            return redirect(url_for('staff_dashboard'))
            
        # Create file if it doesn't exist
        if not os.path.exists('data/receptionists.xlsx'):
            initial_df = pd.DataFrame(columns=[
                'username', 'password', 'name', 'phone', 'address', 
                'dob', 'age', 'gender', 'salary', 'next_of_kin_name',
                'next_of_kin_phone', 'privileges', 'staff_type'
            ])
            initial_df.to_excel('data/receptionists.xlsx', index=False)
        
        receptionists_df = pd.read_excel('data/receptionists.xlsx')
        
        # Get form data
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        name = request.form.get('name', '').strip()
        
        # Validate required fields
        if not username or not password or not name:
            flash('Username, password, and name are required')
            return redirect(url_for('manage_receptionists'))
        
        # Check for duplicate username
        if username in receptionists_df['username'].values:
            flash('Username already exists')
            return redirect(url_for('manage_receptionists'))
        
        # Get permissions
        permissions = []
        for perm in ['members', 'member_attendance', 'staff_attendance', 
                    'payments', 'reports', 'staff', 'sales', 
                    'inventory', 'packages']:
            if request.form.get(f'perm_{perm}'):
                permissions.append(perm)
        
        # Create new staff record
        new_staff = {
            'username': username,
            'password': password,
            'name': name,
            'phone': request.form.get('phone', ''),
            'address': request.form.get('address', ''),
            'dob': request.form.get('dob', ''),
            'age': request.form.get('age', 0),
            'gender': request.form.get('gender', ''),
            'salary': request.form.get('salary', 0),
            'next_of_kin_name': request.form.get('next_of_kin_name', ''),
            'next_of_kin_phone': request.form.get('next_of_kin_phone', ''),
            'privileges': ','.join(permissions),
            'staff_type': request.form.get('staff_type', 'staff')
        }
        
        # Add new staff member
        receptionists_df = pd.concat([receptionists_df, pd.DataFrame([new_staff])], 
                                   ignore_index=True)
        receptionists_df.to_excel('data/receptionists.xlsx', index=False)
        flash('Staff member added successfully')
        
    except Exception as e:
        app.logger.error(f"Error adding staff member: {str(e)}")
        flash(f'Error adding staff member: {str(e)}')
    
    return redirect(url_for('manage_receptionists'))


@app.route('/admin/staff/edit/<username>', methods=['GET', 'POST'])
def edit_staff(username):
    # Allow both admin and staff with staff management privilege
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    if session['user_type'] != 'admin' and 'staff' not in session.get('privileges', []):
        flash('Access denied')
        return redirect(url_for('staff_dashboard'))
    
    try:
        receptionists_df = pd.read_excel('data/receptionists.xlsx')
        staff_data = receptionists_df[receptionists_df['username'] == username]
        
        if staff_data.empty:
            flash('Staff member not found')
            return redirect(url_for('manage_receptionists'))
            
        if request.method == 'GET':
            staff = staff_data.iloc[0].to_dict()
            # Convert privileges string to list, handling empty or None values
            if pd.isna(staff['privileges']) or staff['privileges'] == '':
                staff['privileges'] = []
            else:
                staff['privileges'] = staff['privileges'].split(',')
            return render_template('admin/edit_staff.html', staff=staff)
        
        # Handle POST request - Updated permissions list
        permissions = []
        permission_fields = [
            'perm_members', 'perm_member_attendance', 'perm_staff_attendance',
            'perm_payments', 'perm_reports', 'perm_staff', 'perm_sales', 
            'perm_inventory', 'perm_packages'
        ]
        
        for perm in permission_fields:
            if request.form.get(perm):
                permissions.append(perm.replace('perm_', ''))
        
        # Update staff information
        mask = receptionists_df['username'] == username
        update_fields = {
            'name': request.form.get('name'),
            'phone': request.form.get('phone'),
            'address': request.form.get('address'),
            'dob': request.form.get('dob'),
            'age': request.form.get('age'),
            'gender': request.form.get('gender'),
            'salary': request.form.get('salary'),
            'next_of_kin_name': request.form.get('next_of_kin_name'),
            'next_of_kin_phone': request.form.get('next_of_kin_phone'),
            'staff_type': request.form.get('staff_type'),
            'privileges': ','.join(permissions)
        }
        
        for field, value in update_fields.items():
            receptionists_df.loc[mask, field] = value
        
        receptionists_df.to_excel('data/receptionists.xlsx', index=False)
        flash('Staff member updated successfully')
        return redirect(url_for('manage_receptionists'))
        
    except Exception as e:
        app.logger.error(f"Error updating staff member: {str(e)}")
        flash(f'Error updating staff member: {str(e)}')
        return redirect(url_for('manage_receptionists'))


@app.route('/admin/receptionists/delete/<username>')
def delete_receptionist(username):
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        if not os.path.exists('data/receptionists.xlsx'):
            flash('No staff records found')
            return redirect(url_for('manage_receptionists'))
        
        receptionists_df = pd.read_excel('data/receptionists.xlsx')
        
        # Check if staff member exists
        if username not in receptionists_df['username'].values:
            flash('Staff member not found')
            return redirect(url_for('manage_receptionists'))
        
        # Delete staff member
        receptionists_df = receptionists_df[receptionists_df['username'] != username]
        receptionists_df.to_excel('data/receptionists.xlsx', index=False)
        flash('Staff member deleted successfully')
        
    except Exception as e:
        app.logger.error(f"Error deleting staff member: {str(e)}")
        flash('Error deleting staff member')
    
    return redirect(url_for('manage_receptionists'))

# Reports routes
@app.route('/reports')
def reports():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        selected_date = request.args.get('selected_date', datetime.now().strftime('%Y-%m'))
        year, month = map(int, selected_date.split('-'))
        
        # Read from backup file
        backup_file = os.path.join('data', 'gym_data_backup.xlsx')
        if not os.path.exists(backup_file):
            flash('No backup data available')
            return redirect(url_for('staff_dashboard'))
            
        # Staff Attendance from backup
        staff_attendance_details = []
        with pd.ExcelFile(backup_file) as xls:
            attendance_df = pd.read_excel(xls, 'Staff Attendance')
            staff_df = pd.read_excel(xls, 'Staff')
            
            # Convert date column to datetime
            attendance_df['date'] = pd.to_datetime(attendance_df['date'])
            
            # Filter for selected month
            month_mask = (
                (attendance_df['date'].dt.year == year) & 
                (attendance_df['date'].dt.month == month)
            )
            filtered_attendance = attendance_df[month_mask].copy()
            
            if not filtered_attendance.empty:
                # Format date to string
                filtered_attendance['date'] = filtered_attendance['date'].dt.strftime('%Y-%m-%d')
                
                # Create staff name mapping
                staff_names = dict(zip(staff_df['username'], staff_df['name']))
                
                # Apply staff names mapping
                filtered_attendance['staff_name'] = filtered_attendance['trainer_id'].map(
                    lambda x: staff_names.get(x, x) if pd.notna(x) else 'Unknown'
                )
                
                # Select and order columns
                staff_attendance_details = filtered_attendance[[
                    'date', 'staff_name', 'check_in', 'check_out'
                ]].to_dict('records')
                
                # Sort by date and check_in time
                staff_attendance_details = sorted(
                    staff_attendance_details,
                    key=lambda x: (x['date'], x['check_in'] if pd.notna(x['check_in']) else '')
                )

        # Revenue calculations from backup
        monthly_revenue = 0
        monthly_sales_revenue = 0
        
        with pd.ExcelFile(backup_file) as xls:
            # Package payments
            payments_df = pd.read_excel(xls, 'Payments')
            payments_df['date'] = pd.to_datetime(payments_df['date'])
            month_mask = (
                (payments_df['date'].dt.year == year) & 
                (payments_df['date'].dt.month == month)
            )
            monthly_payments = payments_df[month_mask]
            monthly_revenue = float(monthly_payments['amount'].sum()) if not monthly_payments.empty else 0

            # Sales revenue
            sales_df = pd.read_excel(xls, 'Sales')
            sales_df['date'] = pd.to_datetime(sales_df['date'])
            month_mask = (
                (sales_df['date'].dt.year == year) & 
                (sales_df['date'].dt.month == month)
            )
            monthly_sales = sales_df[month_mask]
            monthly_sales_revenue = float(monthly_sales['total_amount'].sum()) if not monthly_sales.empty else 0

        total_revenue = monthly_revenue + monthly_sales_revenue

        # Member Attendance from backup
        with pd.ExcelFile(backup_file) as xls:
            member_df = pd.read_excel(xls, 'Member Attendance')
            member_df['date'] = pd.to_datetime(member_df['date'])
            month_mask = (
                (member_df['date'].dt.year == year) & 
                (member_df['date'].dt.month == month)
            )
            member_attendance_details = member_df[month_mask].to_dict('records')

        # Sales Details from backup
        sales_details = []
        with pd.ExcelFile(backup_file) as xls:
            sales_df = pd.read_excel(xls, 'Sales')
            sales_df['date'] = pd.to_datetime(sales_df['date'])
            month_mask = (
                (sales_df['date'].dt.year == year) & 
                (sales_df['date'].dt.month == month)
            )
            monthly_sales = sales_df[month_mask]
            
            for _, row in monthly_sales.iterrows():
                sale_record = row.to_dict()
                try:
                    if pd.notna(sale_record.get('items_details')):
                        items_data = json.loads(sale_record['items_details'])
                        formatted_items = []
                        for item in items_data:
                            if isinstance(item, dict):
                                formatted_items.append(f"• {item['name']} (x{item['quantity']})")
                        sale_record['items_display'] = '\n'.join(formatted_items) if formatted_items else 'No items'
                    else:
                        sale_record['items_display'] = 'No items'
                except Exception as e:
                    app.logger.error(f"Error processing items for sale {sale_record.get('id', 'unknown')}: {e}")
                    sale_record['items_display'] = 'Error processing items'
                
                sales_details.append(sale_record)

        return render_template('reports.html',
                             selected_date=selected_date,
                             current_month_year=datetime.now().strftime('%Y-%m'),
                             monthly_revenue=monthly_revenue,
                             monthly_sales_revenue=monthly_sales_revenue,
                             total_revenue=total_revenue,
                             staff_attendance_details=staff_attendance_details,
                             member_attendance_details=member_attendance_details,
                             sales_details=sales_details)

    except Exception as e:
        app.logger.error(f"Error in reports: {str(e)}")
        flash('Error loading reports')
        return redirect(url_for('staff_dashboard'))


@app.route('/inventory')
def inventory():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        inventory_df = pd.read_excel('data/inventory.xlsx')
        custom_products_df = pd.read_excel('data/custom_products.xlsx')
        return render_template('inventory.html', 
                             inventory=inventory_df.to_dict('records'),
                             custom_products=custom_products_df.to_dict('records'))
    except Exception as e:
        app.logger.error(f"Error reading inventory file: {e}")
        flash('Error loading inventory data')
        return redirect(url_for('login'))

@app.route('/inventory/add', methods=['POST'])
def add_inventory():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        inventory_df = pd.read_excel('data/inventory.xlsx')
        new_item = {
            'id': str(len(inventory_df) + 1),
            'stock_type': request.form.get('stock_type'),
            'servings': int(request.form.get('servings')),
            'cost_per_serving': float(request.form.get('cost_per_serving')),
            'profit_per_serving': float(request.form.get('profit_per_serving')),
            'other_charges': float(request.form.get('other_charges')),
            'date_added': datetime.now().strftime('%Y-%m-%d')
        }
        
        inventory_df = pd.concat([inventory_df, pd.DataFrame([new_item])], ignore_index=True)
        inventory_df.to_excel('data/inventory.xlsx', index=False)
        flash('Inventory item added successfully')
    except Exception as e:
        app.logger.error(f"Error adding inventory item: {e}")
        flash('Error adding inventory item')
    
    return redirect(url_for('inventory'))

@app.route('/inventory/edit/<item_id>', methods=['GET', 'POST'])
def edit_inventory(item_id):
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        inventory_df = pd.read_excel('data/inventory.xlsx')
        
        if request.method == 'POST':
            inventory_df.loc[inventory_df['id'].astype(str) == str(item_id), 'stock_type'] = request.form.get('stock_type')
            inventory_df.loc[inventory_df['id'].astype(str) == str(item_id), 'servings'] = int(request.form.get('servings'))
            inventory_df.loc[inventory_df['id'].astype(str) == str(item_id), 'cost_per_serving'] = float(request.form.get('cost_per_serving'))
            inventory_df.loc[inventory_df['id'].astype(str) == str(item_id), 'profit_per_serving'] = float(request.form.get('profit_per_serving'))
            inventory_df.loc[inventory_df['id'].astype(str) == str(item_id), 'other_charges'] = float(request.form.get('other_charges'))
            
            inventory_df.to_excel('data/inventory.xlsx', index=False)
            flash('Inventory item updated successfully')
            return redirect(url_for('inventory'))
        
        item = inventory_df[inventory_df['id'].astype(str) == str(item_id)].iloc[0]
        return render_template('edit_inventory.html', item=item.to_dict())
    except Exception as e:
        app.logger.error(f"Error editing inventory item: {e}")
        flash('Error updating inventory item')
        return redirect(url_for('inventory'))

@app.route('/inventory/delete/<item_id>')
def delete_inventory(item_id):
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        inventory_df = pd.read_excel('data/inventory.xlsx')
        inventory_df = inventory_df[inventory_df['id'].astype(str) != str(item_id)]
        inventory_df.to_excel('data/inventory.xlsx', index=False)
        flash('Inventory item deleted successfully')
    except Exception as e:
        app.logger.error(f"Error deleting inventory item: {e}")
        flash('Error deleting inventory item')
    
    return redirect(url_for('inventory'))




@app.route('/sales', methods=['GET', 'POST'])
def sales():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        # Initialize or get item count from session
        if request.method == 'POST' and 'add_more_items' in request.form:
            session['item_count'] = session.get('item_count', 1) + 1
        elif request.method == 'GET':
            session['item_count'] = 1

        # Load data
        inventory_df = pd.read_excel('data/inventory.xlsx')
        sales_df = pd.read_excel('data/sales.xlsx')
        
        # Load custom products with explicit error handling
        custom_products = []
        try:
            custom_products_df = pd.read_excel('data/custom_products.xlsx')
            # Convert DataFrame to records and ensure all products are included
            custom_products = custom_products_df.fillna('').to_dict('records')
            print(f"Loaded {len(custom_products)} custom products")  # Debug print
            
        except Exception as e:
            app.logger.error(f"Error loading custom products: {str(e)}")
            flash('Warning: Could not load custom products')

        return render_template('sales.html',
                             inventory=inventory_df.to_dict('records'),
                             custom_products=custom_products,
                             recent_sales=sales_df.tail(10).to_dict('records'),
                             item_count=session.get('item_count', 1))

    except Exception as e:
        app.logger.error(f"Error in sales: {str(e)}")
        flash('Error loading sales data')
        return redirect(url_for('staff_dashboard'))


@app.template_filter('from_json')
def from_json(value):
    return json.loads(value)


@app.route('/sales/add', methods=['POST'])
def add_sale():
    try:
        # Load necessary data
        sales_df = pd.read_excel('data/sales.xlsx') if os.path.exists('data/sales.xlsx') else pd.DataFrame()
        inventory_df = pd.read_excel('data/inventory.xlsx')
        custom_products_df = pd.read_excel('data/custom_products.xlsx')
        
        # Generate new sale ID
        new_id = 1 if len(sales_df) == 0 else int(sales_df['id'].max()) + 1
        
        # Get form data
        payment_method = request.form.get('payment_method')
        total_amount = float(request.form.get('total_amount').replace('Rs. ', ''))
        items_data = json.loads(request.form.get('items'))
        
        # Process each item and update inventory
        for item_id, item_details in items_data:
            quantity = int(item_details['quantity'])
            
            if item_id.startswith('R_'):  # Regular inventory item
                inventory_id = int(item_id.split('_')[1])
                # Update inventory servings
                mask = inventory_df['id'].astype(str) == str(inventory_id)
                if not mask.any():
                    raise Exception(f"Inventory item {inventory_id} not found")
                
                current_servings = inventory_df.loc[mask, 'servings'].iloc[0]
                if current_servings < quantity:
                    raise Exception(f"Insufficient stock for {item_details['name']}")
                
                inventory_df.loc[mask, 'servings'] = current_servings - quantity
                
            elif item_id.startswith('C_'):  # Custom product
                product_id = int(item_id.split('_')[1])
                custom_product = custom_products_df[custom_products_df['product_id'] == product_id].iloc[0]
                ingredients = json.loads(custom_product['ingredients'])
                
                # Update inventory for each ingredient
                for ingredient in ingredients:
                    inv_id = ingredient['id']
                    ing_quantity = float(ingredient['quantity']) * quantity
                    
                    mask = inventory_df['id'].astype(str) == str(inv_id)
                    if not mask.any():
                        raise Exception(f"Ingredient {inv_id} not found")
                    
                    current_servings = inventory_df.loc[mask, 'servings'].iloc[0]
                    if current_servings < ing_quantity:
                        raise Exception(f"Insufficient stock for ingredient in {item_details['name']}")
                    
                    inventory_df.loc[mask, 'servings'] = current_servings - ing_quantity
        
        # Save updated inventory
        inventory_df.to_excel('data/inventory.xlsx', index=False)
        
        # Create sale record
        new_sale = {
            'id': new_id,
            'date': datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S'),
            'staff_name': session.get('username'),
            'total_amount': total_amount,
            'payment_method': payment_method,
            'items_details': json.dumps([{
                'name': item[1]['name'],
                'quantity': item[1]['quantity'],
                'price': item[1]['price'],
                'total': item[1]['subtotal']
            } for item in items_data])
        }
        
        # Save sale record
        if len(sales_df) == 0:
            sales_df = pd.DataFrame(columns=['id', 'date', 'staff_name', 'total_amount', 'payment_method', 'items_details'])
        sales_df = pd.concat([sales_df, pd.DataFrame([new_sale])], ignore_index=True)
        sales_df.to_excel('data/sales.xlsx', index=False)
        
        return jsonify({
            'success': True,
            'redirect': url_for('sales')
        })
        
    except Exception as e:
        app.logger.error(f"Error in add_sale: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/sales/report')
def sales_report():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        sales_df = pd.read_excel('data/sales.xlsx')
        
        # Get date range from query parameters or use current date
        start_date = request.args.get('start_date', datetime.now().strftime('%Y-%m-%d'))
        end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
        
        # Filter sales by date range
        filtered_sales = sales_df[
            (sales_df['date'].astype(str) >= start_date) & 
            (sales_df['date'].astype(str) <= end_date)
        ]
        
        # Process sales data for report
        report_data = []
        total_amount = 0
        
        for _, sale in filtered_sales.iterrows():
            if sale['items_details']:
                items = json.loads(sale['items_details'])
                for item in items:
                    report_data.append({
                        'date': sale['date'],
                        'product': item['name'],
                        'quantity': item['quantity'],
                        'price': item['price'],
                        'total': item['total']
                    })
                    total_amount += item['total']
        
        return render_template('sales_report.html',
                             report_data=report_data,
                             total_amount=total_amount,
                             start_date=start_date,
                             end_date=end_date)
    except Exception as e:
        app.logger.error(f"Error generating sales report: {e}")
        flash('Error generating sales report')
        return redirect(url_for('sales'))


@app.route('/receipt/download', methods=['POST'])
def download_receipt():
    receipt_id = request.form.get('receipt_id')
    # Generate PDF receipt
    # Return the file for download
    return send_file(
        'path_to_generated_receipt.pdf',
        as_attachment=True,
        download_name=f'receipt_{receipt_id}.pdf'
    )

@app.route('/receipt/print', methods=['POST'])
def print_receipt():
    receipt_id = request.form.get('receipt_id')
    # Generate printable HTML receipt
    return render_template('print_receipt.html', receipt=receipt_data)


@app.route('/receipt/<int:sale_id>')
def view_receipt(sale_id):
    try:
        # Load sales data
        sales_df = pd.read_excel('data/sales.xlsx')
        sale = sales_df[sales_df['id'] == sale_id].iloc[0]
        
        # Parse items from JSON string
        items = json.loads(sale['items_details'])
        
        return render_template('receipt.html', 
                             sale=sale.to_dict(),
                             items=items)
    except Exception as e:
        app.logger.error(f"Error viewing receipt: {str(e)}")
        flash('Error viewing receipt')
        return redirect(url_for('sales'))

        
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if new_password != confirm_password:
                flash('New passwords do not match')
                return redirect(url_for('change_password'))
            
            # Load appropriate Excel file based on user type
            file_path = 'data/admin.xlsx' if session['user_type'] == 'admin' else 'data/receptionists.xlsx'
            df = pd.read_excel(file_path)
            
            # Verify current password
            user_row = df[df['username'] == session['username']]
            if user_row.empty or user_row.iloc[0]['password'] != current_password:
                flash('Current password is incorrect')
                return redirect(url_for('change_password'))
            
            # Update password
            df.loc[df['username'] == session['username'], 'password'] = new_password
            df.to_excel(file_path, index=False)
            
            flash('Password changed successfully')
            return redirect(url_for('admin_dashboard' if session['user_type'] == 'admin' else 'staff_dashboard'))
            
        except Exception as e:
            flash('Error changing password')
            return redirect(url_for('change_password'))
    
    return render_template('change_password.html')


# #backup
# def create_daily_backup():
#     try:
#         data_path = 'data'
#         backup_file = os.path.join(data_path, 'gym_data_backup.xlsx')
        
#         # First load existing backup if it exists
#         backup_data = {}
#         if os.path.exists(backup_file):
#             with pd.ExcelFile(backup_file) as xls:
#                 for sheet_name in xls.sheet_names:
#                     backup_data[sheet_name] = pd.read_excel(xls, sheet_name)

#         with pd.ExcelWriter(backup_file, engine='openpyxl') as writer:
#             # Members - Merge with existing backup
#             current_members = pd.read_excel(os.path.join(data_path, 'members.xlsx'))
#             if 'Members' in backup_data:
#                 all_members = pd.concat([backup_data['Members'], current_members]).drop_duplicates(subset=['member_id'], keep='last')
#             else:
#                 all_members = current_members
#             all_members.to_excel(writer, sheet_name='Members', index=False)

#             # Staff - Merge with existing backup
#             current_staff = pd.read_excel(os.path.join(data_path, 'receptionists.xlsx'))
#             if 'Staff' in backup_data:
#                 all_staff = pd.concat([backup_data['Staff'], current_staff]).drop_duplicates(subset=['username'], keep='last')
#             else:
#                 all_staff = current_staff
#             all_staff.to_excel(writer, sheet_name='Staff', index=False)

#             # Attendance - Append new records
#             current_attendance = pd.read_excel(os.path.join(data_path, 'attendance.xlsx'))
#             if 'Member Attendance' in backup_data:
#                 all_attendance = pd.concat([backup_data['Member Attendance'], current_attendance]).drop_duplicates()
#             else:
#                 all_attendance = current_attendance
#             all_attendance.to_excel(writer, sheet_name='Member Attendance', index=False)

#             # Staff Attendance - Append new records
#             current_staff_attendance = pd.read_excel(os.path.join(data_path, 'trainer_attendance.xlsx'))
#             if 'Staff Attendance' in backup_data:
#                 all_staff_attendance = pd.concat([backup_data['Staff Attendance'], current_staff_attendance]).drop_duplicates()
#             else:
#                 all_staff_attendance = current_staff_attendance
#             all_staff_attendance.to_excel(writer, sheet_name='Staff Attendance', index=False)

#             # Payments - Append new records
#             current_payments = pd.read_excel(os.path.join(data_path, 'payments.xlsx'))
#             if 'Payments' in backup_data:
#                 all_payments = pd.concat([backup_data['Payments'], current_payments]).drop_duplicates()
#             else:
#                 all_payments = current_payments
#             all_payments.to_excel(writer, sheet_name='Payments', index=False)

#             # Inventory - Keep all items
#             current_inventory = pd.read_excel(os.path.join(data_path, 'inventory.xlsx'))
#             if 'Inventory' in backup_data:
#                 all_inventory = pd.concat([backup_data['Inventory'], current_inventory]).drop_duplicates(subset=['id'], keep='last')
#             else:
#                 all_inventory = current_inventory
#             all_inventory.to_excel(writer, sheet_name='Inventory', index=False)

#             # Custom Products - Keep all products
#             current_products = pd.read_excel(os.path.join(data_path, 'custom_products.xlsx'))
#             if 'Custom Products' in backup_data:
#                 all_products = pd.concat([backup_data['Custom Products'], current_products]).drop_duplicates(subset=['product_id'], keep='last')
#             else:
#                 all_products = current_products
#             all_products.to_excel(writer, sheet_name='Custom Products', index=False)

#             # Sales - Append new records
#             current_sales = pd.read_excel(os.path.join(data_path, 'sales.xlsx'))
#             if 'Sales' in backup_data:
#                 all_sales = pd.concat([backup_data['Sales'], current_sales]).drop_duplicates()
#             else:
#                 all_sales = current_sales
#             all_sales.to_excel(writer, sheet_name='Sales', index=False)

#             # Packages - Keep all packages
#             current_packages = pd.read_excel(os.path.join(data_path, 'packages.xlsx'))
#             if 'Packages' in backup_data:
#                 all_packages = pd.concat([backup_data['Packages'], current_packages]).drop_duplicates(subset=['name'], keep='last')
#             else:
#                 all_packages = current_packages
#             all_packages.to_excel(writer, sheet_name='Packages', index=False)

#         app.logger.info(f"Daily backup created successfully at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
#     except Exception as e:
#         app.logger.error(f"Error creating daily backup: {str(e)}")

# # Schedule the backup to run at midnight every day
# def schedule_backup():
#     while True:
#         now = datetime.now()
#         # Calculate time until next midnight
#         next_run = (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
#         delay = (next_run - now).total_seconds()
#         time.sleep(delay)
#         create_daily_backup()


# Thread(target=schedule_backup, daemon=True).start()



# Remove the scheduling code and modify backup handling
# Add this near the top of the file, after other imports
from datetime import datetime, timedelta
import pytz

# Define timezone
IST = pytz.timezone('Asia/Kolkata')  # UTC+05:30

# Update the create_backup function
def create_backup():
    try:
        data_path = 'data'
        backup_file = os.path.join(data_path, 'gym_data_backup.xlsx')
        
        # First load existing backup if it exists
        backup_data = {}
        if os.path.exists(backup_file):
            with pd.ExcelFile(backup_file) as xls:
                for sheet_name in xls.sheet_names:
                    backup_data[sheet_name] = pd.read_excel(xls, sheet_name)

        with pd.ExcelWriter(backup_file, engine='openpyxl', mode='w') as writer:
            # Members - Merge with existing backup
            current_members = pd.read_excel(os.path.join(data_path, 'members.xlsx'))
            current_members.to_excel(writer, sheet_name='Members', index=False)

            # Staff - Merge with existing backup
            current_staff = pd.read_excel(os.path.join(data_path, 'receptionists.xlsx'))
            current_staff.to_excel(writer, sheet_name='Staff', index=False)

            # Attendance - Append new records
            current_attendance = pd.read_excel(os.path.join(data_path, 'attendance.xlsx'))
            current_attendance.to_excel(writer, sheet_name='Member Attendance', index=False)

            # Staff Attendance - Append new records
            current_staff_attendance = pd.read_excel(os.path.join(data_path, 'trainer_attendance.xlsx'))
            current_staff_attendance.to_excel(writer, sheet_name='Staff Attendance', index=False)

            # Payments - Append new records
            current_payments = pd.read_excel(os.path.join(data_path, 'payments.xlsx'))
            current_payments.to_excel(writer, sheet_name='Payments', index=False)

            # Inventory - Keep all items
            current_inventory = pd.read_excel(os.path.join(data_path, 'inventory.xlsx'))
            current_inventory.to_excel(writer, sheet_name='Inventory', index=False)

            # Custom Products - Keep all products
            current_products = pd.read_excel(os.path.join(data_path, 'custom_products.xlsx'))
            current_products.to_excel(writer, sheet_name='Custom Products', index=False)

            # Sales - Append new records
            current_sales = pd.read_excel(os.path.join(data_path, 'sales.xlsx'))
            current_sales.to_excel(writer, sheet_name='Sales', index=False)

            # Packages - Keep all packages
            current_packages = pd.read_excel(os.path.join(data_path, 'packages.xlsx'))
            current_packages.to_excel(writer, sheet_name='Packages', index=False)

        # Update timestamp with timezone
        current_time = datetime.now(IST).strftime('%Y-%m-%d %H:%M:%S %Z')
        app.logger.info(f"Backup created successfully at {current_time}")
        
    except Exception as e:
        app.logger.error(f"Error creating backup: {str(e)}")

# Create backup immediately when server starts
create_backup()


@app.route('/download_report/<type>/<date>')
def download_report(type, date):
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        # Load data from backup file
        backup_file = os.path.join('data', 'gym_data_backup.xlsx')
        if not os.path.exists(backup_file):
            flash('No backup data available')
            return redirect(url_for('reports'))

        # Create Excel file in memory
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            with pd.ExcelFile(backup_file) as xls:
                # Process each sheet from backup
                for sheet_name in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name)
                    
                    # Filter by date if the sheet has a date column
                    if 'date' in df.columns:
                        df['date'] = pd.to_datetime(df['date'])
                        month_mask = df['date'].dt.strftime('%Y-%m') == date
                        df = df[month_mask]
                    
                    # Write to new Excel file
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'gym_report_{date}.xlsx'
        )
            
    except Exception as e:
        app.logger.error(f"Error generating report: {str(e)}")
        flash('Error generating report')
        return redirect(url_for('reports'))



if __name__ == '__main__':
    app.run(debug=True)


# Move the API endpoint before the if __name__ == '__main__' line
@app.route('/api/inventory')
def api_inventory():
    try:
        inventory_df = pd.read_excel('data/inventory.xlsx')
        inventory_data = inventory_df.to_dict('records')
        return json.dumps(inventory_data)
    except Exception as e:
        app.logger.error(f"Error fetching inventory data: {e}")
        return json.dumps([])


