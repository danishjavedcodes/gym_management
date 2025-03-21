@app.route('/sales', methods=['GET'])
@login_required
def sales():
    try:
        # Get inventory items
        inventory = Inventory.query.filter_by(is_active=True).all()
        
        # Get custom products
        custom_products = CustomProduct.query.filter_by(is_active=True).all()
        
        # Get sales history
        sales = db.session.query(
            Sale.id,
            Sale.date,
            Sale.total_amount,
            Sale.payment_method,
            Sale.items_details,
            User.name.label('staff_name')
        ).join(User, Sale.staff_username == User.username)\
         .order_by(Sale.date.desc()).all()

        return render_template('sales.html', 
                             inventory=inventory,
                             custom_products=custom_products,
                             sales=sales,
                             current_user=current_user)
    except Exception as e:
        db.session.rollback()
        flash('Error loading sales data: ' + str(e), 'error')
        return redirect(url_for('admin_dashboard'))