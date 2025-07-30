from app import app, db, User

with app.app_context():
    if not User.query.filter_by(username='admin').first():
        admin = User(
            name="Admin",
            username="anik",
            phone="0000000000",
            email="admin@example.com",
            address="Admin HQ",
            is_admin=True
        )
        admin.set_password("!!!anikking")
        db.session.add(admin)
        db.session.commit()
        print("Admin user created.")
    else:
        print("Admin user already exists.")
