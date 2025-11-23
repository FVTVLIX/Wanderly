from app import app, db
import os

print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
db_path = os.path.join(app.root_path, 'site.db')
print(f"Expected DB Path: {db_path}")

if os.path.exists(db_path):
    print("Removing existing database file...")
    try:
        os.remove(db_path)
        print("File removed.")
    except Exception as e:
        print(f"Error removing file: {e}")

print("Creating new database...")
with app.app_context():
    db.drop_all()
    db.create_all()
    print("Database created successfully with new schema.")
