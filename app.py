from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import pandas as pd
from datetime import datetime, timedelta
import os
import logging
import calendar
import json  # Add this import

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
    
    # Allow both admin and staff with member_attendance privilege
    if session['user_type'] != 'admin' and 'member_attendance' not in session.get('privileges', []):
        flash('Access denied')
        return redirect(url_for('staff_dashboard'))
    
    try:
        members_df = pd.read_excel('data/members.xlsx')
        attendance_df = pd.read_excel('data/attendance.xlsx')
        
        today = datetime.now().strftime('%Y-%m-%d')
        today_attendance = attendance_df[attendance_df['date'] == today]
        
        # Get member IDs who have checked in today
        checked_in_members = today_attendance['member_id'].tolist()
        
        return render_template('attendance.html',
                             members=members_df.to_dict('records'),
                             checked_in_members=checked_in_members,
                             today=today)
    except Exception as e:
        app.logger.error(f"Error loading member attendance: {e}")
        flash('Error loading member data')
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
        staff_attendance_df = pd.read_excel('data/trainer_attendance.xlsx')
        staff_df = pd.read_excel('data/receptionists.xlsx')
        
        # Ensure check_out column exists
        if 'check_out' not in staff_attendance_df.columns:
            staff_attendance_df['check_out'] = None
        
        staff_id = request.form.get('staff_id')
        action = request.form.get('staff_attendance_action')
        staff_query = staff_df[staff_df['username'] == staff_id]
        
        if staff_query.empty:
            flash('Staff member not found')
            return redirect(url_for('staff_attendance'))
        
        staff = staff_query.iloc[0]
        today = datetime.now().strftime('%Y-%m-%d')
        current_time = datetime.now().strftime('%H:%M:%S')
        
        # Check if staff has already checked in today
        today_attendance = staff_attendance_df[
            (staff_attendance_df['date'] == today) & 
            (staff_attendance_df['trainer_id'] == staff_id)
        ]
        
        if action == 'check_in':
            if today_attendance.empty:
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
            else:
                flash('Staff member already checked in for today')
        
        elif action == 'check_out':
            if not today_attendance.empty and pd.isna(today_attendance.iloc[0]['check_out']):
                staff_attendance_df.loc[
                    (staff_attendance_df['date'] == today) & 
                    (staff_attendance_df['trainer_id'] == staff_id),
                    'check_out'
                ] = current_time
                flash('Staff check-out recorded successfully')
            else:
                flash('No check-in record found for today or already checked out')
        
        staff_attendance_df.to_excel('data/trainer_attendance.xlsx', index=False)
        
    except Exception as e:
        app.logger.error(f"Error marking staff attendance: {e}")
        flash('Error marking staff attendance')
    
    return redirect(url_for('staff_attendance'))

@app.route('/attendance/mark', methods=['POST'])
def mark_attendance():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        attendance_df = pd.read_excel('data/attendance.xlsx')
        members_df = pd.read_excel('data/members.xlsx')
        
        # Ensure check_out column exists
        if 'check_out' not in attendance_df.columns:
            attendance_df['check_out'] = None
        
        member_id = request.form.get('member_id')
        member_query = members_df[members_df['id'].astype(str) == str(member_id)]
        
        if member_query.empty:
            flash('Member not found')
            return redirect(url_for('attendance'))
        
        member = member_query.iloc[0]
        today = datetime.now().strftime('%Y-%m-%d')
        current_time = datetime.now().strftime('%H:%M:%S')
        
        # Check if member has already checked in today
        today_attendance = attendance_df[
            (attendance_df['date'] == today) & 
            (attendance_df['member_id'].astype(str) == str(member_id))
        ]
        
        if today_attendance.empty:
            # Check in
            new_attendance = {
                'date': today,
                'member_id': str(member_id),
                'member_name': member['name'],
                'check_in': current_time,
                'check_out': None
            }
            attendance_df = pd.concat([attendance_df, pd.DataFrame([new_attendance])], ignore_index=True)
            flash('Check-in recorded successfully')
        else:
            # Check out
            if pd.isna(today_attendance.iloc[0]['check_out']):
                attendance_df.loc[
                    (attendance_df['date'] == today) & 
                    (attendance_df['member_id'].astype(str) == str(member_id)),
                    'check_out'
                ] = current_time
                flash('Check-out recorded successfully')
            else:
                flash('Member has already completed attendance for today')
        
        attendance_df.to_excel('data/attendance.xlsx', index=False)
    except Exception as e:
        app.logger.error(f"Error marking attendance: {e}")
        flash('Error marking attendance')
    
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
    
    # Allow both admin and staff with staff management privilege
    if session['user_type'] != 'admin' and 'staff' not in session.get('privileges', []):
        flash('Access denied')
        return redirect(url_for('staff_dashboard'))
    
    try:
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
                             is_admin=session['user_type'] == 'admin')
    except Exception as e:
        app.logger.error(f"Error loading staff data: {e}")
        flash('Error loading staff data')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/staff/add', methods=['POST'])
def add_staff():
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        receptionists_df = pd.read_excel('data/receptionists.xlsx')
        
        # Updated permissions list with separated attendance types
        permissions = []
        if request.form.get('perm_members'): permissions.append('members')
        if request.form.get('perm_member_attendance'): permissions.append('member_attendance')
        if request.form.get('perm_staff_attendance'): permissions.append('staff_attendance')
        if request.form.get('perm_payments'): permissions.append('payments')
        if request.form.get('perm_reports'): permissions.append('reports')
        
        new_staff = {
            'username': request.form.get('username'),
            'password': request.form.get('password'),
            'name': request.form.get('name'),
            'phone': request.form.get('phone'),
            'address': request.form.get('address'),
            'dob': request.form.get('dob'),
            'age': request.form.get('age'),
            'gender': request.form.get('gender'),
            'salary': request.form.get('salary'),
            'next_of_kin_name': request.form.get('next_of_kin_name'),
            'next_of_kin_phone': request.form.get('next_of_kin_phone'),
            'privileges': ','.join(permissions),
            'staff_type': request.form.get('staff_type')
        }
        
        if new_staff['username'] in receptionists_df['username'].values:
            flash('Username already exists')
        else:
            receptionists_df = pd.concat([receptionists_df, pd.DataFrame([new_staff])], 
                                       ignore_index=True)
            receptionists_df.to_excel('data/receptionists.xlsx', index=False)
            flash('Staff member added successfully')
    except Exception as e:
        app.logger.error(f"Error adding staff member: {e}")
        flash('Error adding staff member')
    
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
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        receptionists_df = pd.read_excel('data/receptionists.xlsx')
        receptionists_df = receptionists_df[receptionists_df['username'] != username]
        receptionists_df.to_excel('data/receptionists.xlsx', index=False)
        flash('Receptionist deleted successfully')
    except Exception as e:
        app.logger.error(f"Error deleting receptionist: {e}")
        flash('Error deleting receptionist')
    
    return redirect(url_for('manage_receptionists'))

# Reports routes
@app.route('/reports')
def reports():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        members_df = pd.read_excel('data/members.xlsx')
        payments_df = pd.read_excel('data/payments.xlsx')
        attendance_df = pd.read_excel('data/attendance.xlsx')
        
        # Current month revenue
        current_month = datetime.now().strftime('%Y-%m')
        monthly_revenue = float(payments_df[
            payments_df['date'].astype(str).str.startswith(current_month)
        ]['amount'].sum())
        
        # Past 6 months revenue
        past_6_months = []
        revenue_data = []
        current_date = datetime.now()
        
        for i in range(6):
            month_date = current_date - timedelta(days=30*i)
            month_str = month_date.strftime('%Y-%m')
            past_6_months.append(month_date.strftime('%B %Y'))
            month_revenue = float(payments_df[
                payments_df['date'].astype(str).str.startswith(month_str)
            ]['amount'].sum())
            revenue_data.append(month_revenue)
        
        past_6_months.reverse()
        revenue_data.reverse()
        
        # Members by package - Convert to regular Python dict with int values
        package_distribution = {
            k: int(v) for k, v in members_df['package'].value_counts().to_dict().items()
        }
        
        # Today's attendance
        today = datetime.now().strftime('%Y-%m-%d')
        today_attendance = int(len(attendance_df[attendance_df['date'] == today]))
        
        # Monthly attendance calendar
        current_month_attendance = attendance_df[
            attendance_df['date'].astype(str).str.startswith(current_month)
        ]
        attendance_by_date = {
            k: int(v) for k, v in current_month_attendance.groupby('date').size().to_dict().items()
        }
        
        # Get all dates of current month
        year = datetime.now().year
        month = datetime.now().month
        num_days = calendar.monthrange(year, month)[1]
        calendar_data = []
        
        for day in range(1, num_days + 1):
            date_str = f"{year}-{month:02d}-{day:02d}"
            calendar_data.append({
                'date': date_str,
                'count': attendance_by_date.get(date_str, 0)
            })
        
        return render_template('reports.html',
                             monthly_revenue=monthly_revenue,
                             past_6_months=past_6_months,
                             revenue_data=revenue_data,
                             total_members=int(len(members_df)),
                             package_distribution=package_distribution,
                             today_attendance=today_attendance,
                             calendar_data=calendar_data,
                             current_month=datetime.now().strftime('%B %Y'))
    except Exception as e:
        app.logger.error(f"Error generating reports: {e}")
        flash('Error generating reports')
        return redirect(url_for('login'))
        
        # Monthly attendance with check-in/out times
        current_month_attendance = attendance_df[
            attendance_df['date'].astype(str).str.startswith(current_month)
        ].sort_values('date', ascending=False)
        
        attendance_records = current_month_attendance.to_dict('records')
        
        return render_template('reports.html',
                             monthly_revenue=monthly_revenue,
                             past_6_months=past_6_months,
                             revenue_data=revenue_data,
                             total_members=int(len(members_df)),
                             package_distribution=package_distribution,
                             today_attendance=today_attendance,
                             calendar_data=calendar_data,
                             current_month=datetime.now().strftime('%B %Y'))
    except Exception as e:
        app.logger.error(f"Error generating reports: {e}")
        flash('Error generating reports')
        return redirect(url_for('login'))

# Inventory management routes
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
        total_amount = float(request.form.get('total_amount').replace('₹', ''))
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
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
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
