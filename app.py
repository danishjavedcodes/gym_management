from flask import Flask, render_template, request, redirect, url_for, flash, session
import pandas as pd
from datetime import datetime, timedelta
import os
import logging
import calendar

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Changed secret key
app.permanent_session_lifetime = timedelta(minutes=30)

logging.basicConfig(level=logging.DEBUG)

# Create data directory and initialize Excel files
if not os.path.exists('data'):
    os.makedirs('data')

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
            'username': [], 'password': [], 'name': []
        },
        'attendance.xlsx': {
            'date': [], 'member_id': [], 'member_name': [], 
            'check_in': [], 'check_out': []  # Added check_out
        }
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
    
    receptionists = pd.read_excel('data/receptionists.xlsx')
    receptionist = receptionists[
        (receptionists['username'] == username) & 
        (receptionists['password'] == password)
    ]
    
    if not receptionist.empty:
        session.permanent = True
        session['user_type'] = 'receptionist'
        session['username'] = username
        return redirect(url_for('receptionist_dashboard'))
    
    flash('Invalid credentials')
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
            members_df.loc[members_df['id'] == member_id, 'name'] = request.form.get('name')
            members_df.loc[members_df['id'] == member_id, 'address'] = request.form.get('address')
            members_df.loc[members_df['id'] == member_id, 'package'] = request.form.get('package')
            members_df.loc[members_df['id'] == member_id, 'weight'] = float(request.form.get('weight'))
            members_df.loc[members_df['id'] == member_id, 'height'] = float(request.form.get('height'))
            
            members_df.to_excel('data/members.xlsx', index=False)
            flash('Member updated successfully')
            return redirect(url_for('view_members'))
        
        member = members_df[members_df['id'] == member_id].iloc[0]
        return render_template('edit_member.html', 
                             member=member.to_dict(),
                             packages=packages_df.to_dict('records'))
    except Exception as e:
        app.logger.error(f"Error editing member: {e}")
        flash('Error updating member')
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
        receptionists_df = pd.read_excel('data/receptionists.xlsx')
        return render_template('admin/receptionists.html',
                             receptionists=receptionists_df.to_dict('records'))
    except Exception as e:
        app.logger.error(f"Error loading receptionists: {e}")
        flash('Error loading receptionists')
        return redirect(url_for('admin_dashboard'))

@app.route('/admin/receptionists/add', methods=['POST'])
def add_receptionist():
    if 'user_type' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        receptionists_df = pd.read_excel('data/receptionists.xlsx')
        new_receptionist = {
            'username': request.form.get('username'),
            'password': request.form.get('password'),
            'name': request.form.get('name')
        }
        
        if new_receptionist['username'] in receptionists_df['username'].values:
            flash('Username already exists')
        else:
            receptionists_df = pd.concat([receptionists_df, pd.DataFrame([new_receptionist])], 
                                       ignore_index=True)
            receptionists_df.to_excel('data/receptionists.xlsx', index=False)
            flash('Receptionist added successfully')
    except Exception as e:
        app.logger.error(f"Error adding receptionist: {e}")
        flash('Error adding receptionist')
    
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

if __name__ == '__main__':
    app.run(debug=True)