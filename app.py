from flask import Flask, render_template, request, redirect, url_for, flash, session
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
        'members.xlsx': {
            'id': [], 'name': [], 'address': [], 'package': [],
            'weight': [], 'height': [], 'join_date': [], 'payment_status': []
        },
        'packages.xlsx': {
            'name': [], 'price': [], 'trainers': [], 
            'cardio_access': [], 'timings': [], 'duration': []  # Added duration field
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
        'inventory.xlsx': {
            'id': [], 'stock_type': [], 'servings': [], 'cost_per_serving': [],
            'profit_per_serving': [], 'other_charges': [], 'date_added': []
        },
        'sales.xlsx': {
            'date': [], 'member_id': [], 'member_name': [], 'inventory_id': [], 
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
    
    if username == 'admin' and password == 'admin':
        session.permanent = True
        session['user_type'] = 'admin'
        session['username'] = 'admin'
        return redirect(url_for('admin_dashboard'))
    
    try:
        receptionists = pd.read_excel('data/receptionists.xlsx')
        receptionist = receptionists[
            (receptionists['username'] == username) & 
            (receptionists['password'] == password)
        ]
        
        if not receptionist.empty:
            session.permanent = True
            session['user_type'] = 'staff'
            session['username'] = username
            # Safely handle privileges
            privileges_str = receptionist.iloc[0]['privileges']
            session['privileges'] = privileges_str.split(',') if isinstance(privileges_str, str) else []
            return redirect(url_for('staff_dashboard'))
        
        flash('Invalid credentials')
    except Exception as e:
        app.logger.error(f"Login error: {e}")
        flash('Error during login')
    
    return redirect(url_for('login'))

@app.route('/staff/dashboard')
def staff_dashboard():
    if 'user_type' not in session or session['user_type'] != 'staff':
        return redirect(url_for('login'))
    
    try:
        receptionists_df = pd.read_excel('data/receptionists.xlsx')
        staff = receptionists_df[receptionists_df['username'] == session['username']].iloc[0]
        privileges = session.get('privileges', [])
        return render_template('staff/dashboard.html', staff_name=staff['name'], privileges=privileges)
    except Exception as e:
        app.logger.error(f"Error loading staff dashboard: {e}")
        flash('Error loading dashboard')
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Remove this duplicate route and keep only one instance
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

# Member management routes
@app.route('/view_members')
def view_members():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        members_df = pd.read_excel('data/members.xlsx')
        packages_df = pd.read_excel('data/packages.xlsx')
        return render_template('members.html', 
                             members=members_df.to_dict('records'),
                             packages=packages_df.to_dict('records'))
    except Exception as e:
        app.logger.error(f"Error reading Excel files: {e}")
        flash('Error loading data')
        return redirect(url_for('login'))

@app.route('/members/add', methods=['POST'])
def add_member():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        members_df = pd.read_excel('data/members.xlsx')
        new_member = {
            'id': str(len(members_df) + 1),
            'name': request.form.get('name'),
            'address': request.form.get('address'),
            'package': request.form.get('package'),
            'weight': float(request.form.get('weight')),
            'height': float(request.form.get('height')),
            'join_date': datetime.now().strftime('%Y-%m-%d'),
            'payment_status': 'Pending'
        }
        
        members_df = pd.concat([members_df, pd.DataFrame([new_member])], ignore_index=True)
        members_df.to_excel('data/members.xlsx', index=False)
        flash('Member added successfully')
    except Exception as e:
        app.logger.error(f"Error adding member: {e}")
        flash('Error adding member')
    
    return redirect(url_for('view_members'))

@app.route('/members/edit/<member_id>', methods=['GET', 'POST'])
def edit_member(member_id):
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        members_df = pd.read_excel('data/members.xlsx')
        packages_df = pd.read_excel('data/packages.xlsx')
        
        if request.method == 'POST':
            members_df.loc[members_df['id'].astype(str) == str(member_id), 'name'] = request.form.get('name')
            members_df.loc[members_df['id'].astype(str) == str(member_id), 'address'] = request.form.get('address')
            members_df.loc[members_df['id'].astype(str) == str(member_id), 'package'] = request.form.get('package')
            members_df.loc[members_df['id'].astype(str) == str(member_id), 'weight'] = float(request.form.get('weight'))
            members_df.loc[members_df['id'].astype(str) == str(member_id), 'height'] = float(request.form.get('height'))
            
            members_df.to_excel('data/members.xlsx', index=False)
            flash('Member updated successfully')
            return redirect(url_for('view_members'))
        
        member = members_df[members_df['id'].astype(str) == str(member_id)].iloc[0]
        return render_template('edit_member.html', 
                             member=member.to_dict(),
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
        members_df = members_df[members_df['id'].astype(str) != str(member_id)]
        members_df.to_excel('data/members.xlsx', index=False)
        flash('Member deleted successfully')
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
        members_df = pd.read_excel('data/members.xlsx')
        attendance_df = pd.read_excel('data/attendance.xlsx')
        today = datetime.now().strftime('%Y-%m-%d')
        today_attendance = attendance_df[attendance_df['date'] == today]
        
        return render_template('attendance.html',
                             members=members_df.to_dict('records'),
                             attendance=today_attendance.to_dict('records'))
    except Exception as e:
        app.logger.error(f"Error reading Excel files: {e}")
        flash('Error loading attendance data')
        return redirect(url_for('login'))

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
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        packages_df = pd.read_excel('data/packages.xlsx')
        return render_template('packages.html', packages=packages_df.to_dict('records'))
    except Exception as e:
        app.logger.error(f"Error reading packages file: {e}")
        flash('Error loading packages data')
        return redirect(url_for('login'))

@app.route('/packages/add', methods=['POST'])
def add_package():
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        packages_df = pd.read_excel('data/packages.xlsx')
        new_package = {
            'name': request.form.get('name'),
            'price': float(request.form.get('price')),
            'trainers': request.form.get('trainers'),
            'cardio_access': request.form.get('cardio_access'),
            'timings': request.form.get('timings'),
            'duration': request.form.get('duration')  # Added duration field
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
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        packages_df = pd.read_excel('data/packages.xlsx')
        packages_df = packages_df[packages_df['name'] != name]
        packages_df.to_excel('data/packages.xlsx', index=False)
        flash('Package deleted successfully')
    except Exception as e:
        app.logger.error(f"Error deleting package: {e}")
        flash('Error deleting package')
    
    return redirect(url_for('packages'))

# Payment management routes
# Update the payments route to handle both GET and POST methods
@app.route('/payments', methods=['GET', 'POST'])
def payments():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        payments_df = pd.read_excel('data/payments.xlsx')
        members_df = pd.read_excel('data/members.xlsx')
        packages_df = pd.read_excel('data/packages.xlsx')
        
        # Create a dictionary of package prices
        packages = dict(zip(packages_df['name'], packages_df['price']))
        
        return render_template('payments.html',
                             payments=payments_df.to_dict('records'),
                             members=members_df.to_dict('records'),
                             packages=packages)
    except Exception as e:
        app.logger.error(f"Error loading payments: {e}")
        flash('Error loading payments')
        return redirect(url_for('login'))

@app.route('/payments/add', methods=['POST'])
def add_payment():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        payments_df = pd.read_excel('data/payments.xlsx')
        members_df = pd.read_excel('data/members.xlsx')
        
        member_id = request.form.get('member_id')
        member = members_df[members_df['id'].astype(str) == str(member_id)].iloc[0]
        
        new_payment = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'member_id': member_id,
            'member_name': member['name'],
            'package': member['package'],
            'amount': float(request.form.get('amount')),
            'status': 'Paid'
        }
        
        payments_df = pd.concat([payments_df, pd.DataFrame([new_payment])], ignore_index=True)
        payments_df.to_excel('data/payments.xlsx', index=False)
        
        # Update member payment status
        members_df.loc[members_df['id'].astype(str) == str(member_id), 'payment_status'] = 'Paid'
        members_df.to_excel('data/members.xlsx', index=False)
        
        flash('Payment recorded successfully')
    except Exception as e:
        app.logger.error(f"Error recording payment: {e}")
        flash('Error recording payment')
    
    return redirect(url_for('payments'))

# Receptionist management routes
@app.route('/admin/receptionists')
def manage_receptionists():
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    
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
        return render_template('admin/staff.html', staff=staff_df.to_dict('records'))
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
        
        # Get permissions as a list and join them
        permissions = []
        if request.form.get('perm_members'): permissions.append('members')
        if request.form.get('perm_attendance'): permissions.append('attendance')
        if request.form.get('perm_payments'): permissions.append('payments')
        if request.form.get('perm_packages'): permissions.append('packages')
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
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        receptionists_df = pd.read_excel('data/receptionists.xlsx')
        staff_data = receptionists_df[receptionists_df['username'] == username]
        
        if staff_data.empty:
            flash('Staff member not found')
            return redirect(url_for('manage_receptionists'))
            
        if request.method == 'GET':
            staff = staff_data.iloc[0].to_dict()
            # Convert privileges string to list
            staff['privileges'] = staff['privileges'].split(',') if isinstance(staff['privileges'], str) else []
            return render_template('admin/edit_staff.html', staff=staff)
        
        # Handle POST request
        permissions = []
        if request.form.get('perm_members'): permissions.append('members')
        if request.form.get('perm_attendance'): permissions.append('attendance')
        if request.form.get('perm_payments'): permissions.append('payments')
        if request.form.get('perm_packages'): permissions.append('packages')
        if request.form.get('perm_reports'): permissions.append('reports')
        
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
        app.logger.error(f"Error updating staff member: {e}")
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
        return render_template('inventory.html', inventory=inventory_df.to_dict('records'))
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

# Sales management routes
@app.route('/sales')
def sales():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        sales_df = pd.read_excel('data/sales.xlsx')
        # Sort sales by date in descending order
        sales_df = sales_df.sort_values(by='date', ascending=False)
        inventory_df = pd.read_excel('data/inventory.xlsx')
        
        # Get current user info
        current_user = {
            'username': session['username'],
            'name': 'Admin' if session['user_type'] == 'admin' else None
        }
        
        # If not admin, get receptionist name
        if session['user_type'] != 'admin':
            staff_df = pd.read_excel('data/receptionists.xlsx')
            staff = staff_df[staff_df['username'] == session['username']].iloc[0]
            current_user['name'] = staff['name']
        
        return render_template('sales.html',
                             sales=sales_df.to_dict('records'),
                             current_user=current_user,
                             inventory=inventory_df.to_dict('records'))
    except Exception as e:
        app.logger.error(f"Error loading sales data: {e}")
        flash('Error loading sales data')
        return redirect(url_for('login'))

@app.route('/sales/add', methods=['POST'])
def add_sale():
    if 'user_type' not in session:
        return redirect(url_for('login'))
    
    try:
        sales_df = pd.read_excel('data/sales.xlsx')
        inventory_df = pd.read_excel('data/inventory.xlsx')
        
        # Use logged-in user's information
        staff_username = session['username']
        staff_name = 'Admin' if session['user_type'] == 'admin' else None
        
        # Get receptionist name if not admin
        if session['user_type'] != 'admin':
            staff_df = pd.read_excel('data/receptionists.xlsx')
            staff = staff_df[staff_df['username'] == staff_username].iloc[0]
            staff_name = staff['name']
        
        payment_method = request.form.get('payment_method')
        total_amount = float(request.form.get('total_amount'))
        selected_items_json = request.form.get('selected_items')
        
        if not selected_items_json:
            flash('No items selected')
            return redirect(url_for('sales'))
            
        selected_items = json.loads(selected_items_json)
        
        # Prepare items description and detailed information
        items_description = []
        items_details = []
        
        # Process each selected item
        for selected_item in selected_items:
            item_id = selected_item['id']
            quantity = selected_item['quantity']
            
            # Get item details
            item_rows = inventory_df[inventory_df['id'].astype(str) == str(item_id)]
            if item_rows.empty:
                flash(f'Item with ID {item_id} not found')
                return redirect(url_for('sales'))
                
            item = item_rows.iloc[0]
            
            # Calculate item total
            item_price = float(item['cost_per_serving']) + float(item['profit_per_serving'])
            item_total = item_price * quantity
            
            # Add to items description
            items_description.append(f"{item['stock_type']} ({quantity})")
            
            # Add detailed item information
            items_details.append({
                'name': item['stock_type'],
                'quantity': quantity,
                'price': item_price,
                'total': item_total
            })
            
            # Update inventory (reduce servings)
            remaining_servings = int(item['servings']) - quantity
            if remaining_servings < 0:
                flash(f'Not enough servings available for {item["stock_type"]}')
                return redirect(url_for('sales'))
            
            inventory_df.loc[inventory_df['id'].astype(str) == str(item_id), 'servings'] = remaining_servings
        
        # Save updated inventory
        inventory_df.to_excel('data/inventory.xlsx', index=False)
        
        # Record the sale with detailed information
        new_sale = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'staff_username': staff_username,
            'staff_name': staff_name,
            'items': ', '.join(items_description),
            'items_details': json.dumps(items_details),  # Store detailed information as JSON
            'total_amount': total_amount,
            'payment_method': payment_method
        }
        
        sales_df = pd.concat([sales_df, pd.DataFrame([new_sale])], ignore_index=True)
        sales_df.to_excel('data/sales.xlsx', index=False)
        
        flash('Sale recorded successfully')
    except Exception as e:
        app.logger.error(f"Error recording sale: {e}")
        flash(f'Error recording sale: {str(e)}')
    
    return redirect(url_for('sales'))

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