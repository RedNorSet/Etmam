# Etmam — Setup Guide

## What you need installed
- Python 3.11+
- PostgreSQL 14+
- Git

---

## Step 1 — Clone the project
```
git clone https://github.com/RedNorSet/etmam.git
cd etmam
```

## Step 2 — Install dependencies
```
pip install -r requirements.txt
```

## Step 3 — Create the database
Open pgAdmin or your PostgreSQL terminal and run:
```sql
CREATE DATABASE gpms_db;
```

## Step 4 — Create the .env file
Create a file called `.env` in the root of the project (same folder as manage.py) with this content:
```
DEBUG=True
SECRET_KEY=django-insecure-gpms-change-this-in-production
DATABASE_URL=postgres://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/gpms_db
ALLOWED_HOSTS=localhost,127.0.0.1
```
Replace `YOUR_POSTGRES_PASSWORD` with your PostgreSQL password.

## Step 5 — Run migrations
```
python manage.py migrate
```

## Step 6 — Load the data (users, teams, etc.)
```
python manage.py loaddata data.json
```

## Step 7 — Run the server
```
python manage.py runserver
```

Go to `http://localhost:8000` in your browser.

---

## Default admin account
- Username: `admin`
- Password: `admin123`

Log in and go to `http://localhost:8000/admin/` to manage users.

---

## Notes
- The `.env` file is never pushed to GitHub — you must create it yourself
- If `loaddata` fails, just run `python manage.py createsuperuser` to create a fresh admin account
- Static files (CSS, images) are served automatically in development
- Put the Etmam logo at `static/images/logo_trans.png`
