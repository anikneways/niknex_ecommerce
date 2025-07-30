from flask import Flask, request, jsonify, render_template, session, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import pytz
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
from functools import wraps
from pytz import timezone
from datetime import timedelta
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = 'anikking'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///products.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Models
expected_delivery = datetime.utcnow() + timedelta(days=3)


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100), unique=True)
    address = db.Column(db.String(200))
    username = db.Column(db.String(50), unique=True)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Product(db.Model):
    __tablename__ = 'product'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_filename = db.Column(db.String(200))
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.Column(db.String(50), nullable=True)


class Order(db.Model):
    __tablename__ = 'order'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_id = db.Column(db.Integer, db.ForeignKey(
        'product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    customer_name = db.Column(db.String(100))
    customer_phone = db.Column(db.String(20))
    customer_address = db.Column(db.Text)
    payment_method = db.Column(db.String(50))
    bkash_number = db.Column(db.String(20))
    transaction_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    delivery_area = db.Column(db.String(50))
    courier_charge = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    delivery_status = db.Column(db.String(50), default='Order Placed')
    notified = db.Column(db.Boolean, default=False)
    color = db.Column(db.String(50), nullable=True)
    size = db.Column(db.String(50), nullable=True)
    selected_color = db.Column(db.String(50), nullable=True)
    expected_delivery = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref='orders')
    product = db.relationship('Product', backref='orders')


class SearchLog(db.Model):
    __tablename__ = 'search_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey(
        'user.id', name='fk_searchlog_user_id'), nullable=False)
    query = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


# Helpers


@app.context_processor
def inject_today_date():
    return {'today_date': datetime.today().strftime('%d.%m.%Y')}


def local_time(utc_dt):
    local_tz = timezone('Asia/Dhaka')
    utc = timezone('UTC')
    utc_dt = utc.localize(utc_dt)
    return utc_dt.replace(tzinfo=pytz.utc).astimezone(local_tz)


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("You need to be logged in.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin access required.")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return wrapper

# Routes


@app.route('/')
def home():
    products = Product.query.all()
    return render_template('index.html', products=products, username=session.get('username'))


@app.route('/upload', methods=['GET', 'POST'])
@login_required
@admin_required
def upload_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        image = request.files['image']
        image_filename = image.filename if image else None

        if image:
            image.save(os.path.join(
                app.config['UPLOAD_FOLDER'], image_filename))
        category = request.form['category']
        new_product = Product(name=name, description=description,
                              price=price, image_filename=image_filename)
        db.session.add(new_product)
        db.session.commit()
        flash("Product uploaded successfully!", "success")
    return render_template('upload_product.html')


@app.route('/product/<int:product_id>')
def product_view(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product_view.html', product=product)


@app.route('/api/favourite', methods=['POST'])
@login_required
def api_favourite():
    data = request.get_json()
    product_id = str(data.get("product_id"))
    if not product_id:
        return jsonify({"status": "error", "message": "No product_id provided"}), 400
    favourites = session.get("favourites", [])

    if product_id in favourites:
        favourites.remove(product_id)
        message = "Removed from favourites."
    else:
        favourites.append(product_id)
        message = "Added to favourites."

    session["favourites"] = favourites
    session.modified = True

    return jsonify({"status": "success", "message": message})


@app.route('/favourites')
@login_required
def view_favourites():
    favourite_ids = session.get("favourites", [])
    products = Product.query.filter(Product.id.in_(
        map(int, favourite_ids))).all() if favourite_ids else []
    return render_template("favourites.html", products=products)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = User(
            name=request.form['name'], phone=request.form['phone'],
            email=request.form['email'], address=request.form['address'],
            username=request.form['username']
        )
        user.set_password(request.form['password'])
        db.session.add(user)
        try:
            db.session.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))
        except:
            flash("Username or email already exists!", "danger")
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            flash("Login successful!", "success")
            return redirect(url_for('admin_dashboard' if user.is_admin else 'home'))
        flash("Invalid credentials!", "danger")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('login'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template("admin/dashboard.html")


@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.all()
    return render_template("admin/users.html", users=users)


@app.route('/admin/products')
@admin_required
def admin_products():
    products = Product.query.all()
    return render_template("admin/products.html", products=products)


@app.route('/admin/orders')
@admin_required
def admin_orders():
    new_orders = Order.query.filter_by(notified=False).all()
    for order in new_orders:
        order.notified = True
    db.session.commit()
    flash(f"You have {len(new_orders)} new order(s).",
          "info") if new_orders else None
    return render_template('admin/admin_orders.html', orders=Order.query.all())


@app.route('/admin/search-logs')
@admin_required
def admin_search_logs():
    logs = SearchLog.query.order_by(SearchLog.timestamp.desc()).all()
    return render_template('admin/search_logs.html', logs=logs)


@app.route('/buy/<int:product_id>', methods=['GET', 'POST'])
@login_required
def buy_product(product_id):
    product = Product.query.get_or_404(product_id)
    is_garment = product.category and product.category.lower() in [
        "tshirts", "garments"]

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        payment_method = request.form.get(
            'payment_method', 'Cash on Delivery').strip()
        selected_color = request.form.get('color', '').strip()

        selected_size = request.form.get(
            'size', '').strip() if is_garment else None
        delivery_area = address
        quantity = int(request.form.get('quantity', 1))
        is_garment = product.category and product.category.lower() in [
            "tshirt", "garments"]

        if not all([name, phone, address, payment_method]):
            flash("Please fill all required fields.", "danger")
            return render_template('buy_form.html', product=product)

        courier_charge = 100 if 'dhaka' in delivery_area.lower() else 200
        total_amount = (product.price * quantity) + courier_charge

        order = Order(
            user_id=session.get('user_id'),
            product_id=product.id,
            quantity=quantity,
            customer_name=name,
            customer_phone=phone,
            customer_address=address,
            payment_method=payment_method,
            delivery_area=delivery_area,
            courier_charge=courier_charge,
            total_amount=total_amount,
            selected_color=selected_color,
            size=selected_size
        )

        try:
            db.session.add(order)
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Failed to place order. Please try again.", "danger")
            return render_template('buy_form.html', product=product, is_garment=is_garment)

        flash(
            f"Order placed successfully! Total: ৳{total_amount:.2f}", "success")
        return redirect(url_for('order_status', order_id=order.id))

    return render_template('buy_form.html', product=product, is_garment=is_garment)


@app.route('/order/<int:order_id>')
@login_required
def order_status(order_id):
    order = Order.query.get_or_404(order_id)
    days = (datetime.utcnow() - order.created_at).days
    if days >= 2 and order.delivery_status != 'Delivered':
        order.delivery_status = 'Delivered'
        order.delivered_at = datetime.utcnow()
        db.session.commit()

    return render_template('order_status.html', order=order, datetime=datetime)


@app.route('/my_orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=session['user_id']).order_by(
        Order.created_at.desc()).all()

    for order in orders:
        if order.created_at:
            order.created_at_local = local_time(order.created_at)
        else:
            order.created_at_local = None
    return render_template("my_orders.html", orders=orders)


@app.route('/search')
def search_products():
    q = request.args.get('q', '').strip()

    if q:
        user_id = session.get('user_id')
        log = SearchLog(user_id=user_id, query=q)
        db.session.add(log)
        db.session.commit()
        products = Product.query.filter(Product.name.ilike(f'%{q}%')).all()
    else:
        products = []
    return render_template('search_results.html', products=products, query=q)


@app.route('/admiin/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        product.name = request.form['name']
        product.price = request.form['price']
        product.description = request.form['description']
        image = request.files.get('image')
        if image and image.filename:
            filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)
            product.image_filename = filename
        db.session.commit()
        flash("Product updaed successfully.", "success")
        return redirect(url_for('admin_products'))
    return render_template('admin/edit_product.html', product=product)


@app.route('/admin/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    related_orders = Order.query.filter_by(product_id=product.id).count()
    if related_orders > 0:
        flash("Cannot delete product because there are existing orders related to it .", "danger")
        return redirect(url_for('admin_products'))
    try:
        db.session.delete(product)
        db.session.commit()
        flash("Product deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Failed to delete product:" + str(e), "danger")
    return redirect(url_for('admin_products'))


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
