# Inventory Management System

A Django-based inventory management system with a server-rendered web interface and a Django REST Framework API. The system supports inventory items, categories, rooms, stock transactions, requisitions, room keys, audit logs, reports, user roles, JWT authentication, and password reset by email.

## Features

- Inventory and category management
- Room-based inventory tracking and item history
- Stock transactions and pending approval workflows
- Requisitions and requisition items
- Room key borrowing and key audit logs
- Dashboard, room overview, activity reports, CSV export, and Excel export
- User registration, role-based permissions, and JWT authentication
- Password reset with expiring, one-time tokens
- Django admin interface
- Swagger and ReDoc API documentation

## Requirements

Install the following software before setup:

- Python 3.10 or newer
- Git
- A GitHub account with access to the repository

The project does not require Node.js or npm. The HTML, CSS, and JavaScript frontend is served by Django.

## Import the Project on a New Laptop

### 1. Install Git and Python

Install Git from [git-scm.com](https://git-scm.com/downloads) and Python from [python.org](https://www.python.org/downloads/).

On Windows, enable **Add Python to PATH** during Python installation.

Check the installations:

```powershell
git --version
python --version
```

### 2. Clone the Repository

Using SSH:

```powershell
git clone git@github.com:Atikmorshedsohan/Inventory-Management-System.git
```

If SSH is not configured, use HTTPS:

```powershell
git clone https://github.com/Atikmorshedsohan/Inventory-Management-System.git
```

Enter the project directory:

```powershell
cd Inventory-Management-System
```

The commands below must be run from the directory containing `manage.py`.

### 3. Create and Activate a Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

When activated, the terminal normally shows `(.venv)` before the prompt.

If PowerShell blocks activation, run PowerShell as your normal user and execute:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate the environment again.

### 4. Install Python Dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install Django djangorestframework djangorestframework-simplejwt django-cors-headers drf-yasg django-filter openpyxl
```

### 5. Configure Environment Variables

Copy the example file to a local `.env` file, or set the variables directly in your terminal. `.env` is ignored by Git and must never be committed.

PowerShell example:

```powershell
$env:DJANGO_SECRET_KEY = 'replace-with-a-long-random-secret'
$env:EMAIL_HOST_USER = 'your-email@example.com'
$env:EMAIL_HOST_PASSWORD = 'your-email-app-password'
$env:DEFAULT_FROM_EMAIL = 'CSE Inventory <your-email@example.com>'
```

For a persistent Windows configuration, use `setx` instead of `$env:`. Open a new terminal after using `setx`.

`EMAIL_HOST_PASSWORD` must be an email provider app password, not your normal email password. For Gmail, enable two-factor authentication and create an app password at [Google App Passwords](https://myaccount.google.com/apppasswords).

### 6. Create the Local Database

The repository intentionally excludes `db.sqlite3`. Create it from the committed migrations:

```powershell
python manage.py migrate
```

Create an administrator account interactively:

```powershell
python manage.py createsuperuser
```

You may also use the included development script, but it creates a predictable test password and should not be used in production:

```powershell
python create_admin.py
```

### 7. Add Optional Sample Data

The project includes development seed commands:

```powershell
python manage.py seed_data
python manage.py seed_keys
```

Run these only when sample records are wanted. Do not run a seed command repeatedly if it creates duplicate records.

### 8. Verify the Installation

```powershell
python manage.py check
```

A successful installation reports:

```text
System check identified no issues (0 silenced).
```

### 9. Start the Development Server

```powershell
python manage.py runserver
```

Open the application at:

- Web application: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/
- Swagger API documentation: http://127.0.0.1:8000/swagger/
- ReDoc API documentation: http://127.0.0.1:8000/redoc/

Stop the server with `CTRL+C` in the terminal running it.

## Main Web Pages

- `/` - Home page
- `/register/` - User registration
- `/forgot-password/` - Request a password reset
- `/reset-password/` - Set a new password using a reset token
- `/dashboard/` - Dashboard
- `/items/` - Inventory items
- `/stock/` - Stock management
- `/requisitions/` - Requisitions
- `/reports/` - Reports
- `/audit/` - Audit logs
- `/roomwise-inventory/` - Room-wise inventory

## API Overview

All API routes are under `/api/`. The main resources include:

- `/api/users/`
- `/api/categories/`
- `/api/items/`
- `/api/rooms/`
- `/api/requisitions/`
- `/api/stock-transactions/`
- `/api/room-keys/`
- `/api/key-borrows/`
- `/api/audit-logs/`
- `/api/reports/dashboard/`
- `/api/reports/rooms-overview/`
- `/api/reports/roomwise-activity/`
- `/api/reports/export/csv/`
- `/api/reports/export/excel/`

JWT authentication endpoints:

- `POST /api/auth/register/`
- `POST /api/auth/token/`
- `POST /api/auth/token/refresh/`
- `GET /api/auth/me/`
- `POST /api/auth/password-reset/`
- `POST /api/auth/password-reset/confirm/`

For protected endpoints, send the access token as a Bearer token:

```http
Authorization: Bearer <access-token>
```

The complete interactive API schema is available through Swagger and ReDoc while the development server is running.

## Password Reset Email

The application uses SMTP settings from environment variables. Without valid email credentials, password reset emails cannot be delivered.

For local testing, the existing password reset reference is documented in [PASSWORD_RESET_GUIDE.md](PASSWORD_RESET_GUIDE.md). Never commit real email passwords, app passwords, API keys, or production secret keys.

## Running Tests

The repository contains test scripts for activity APIs, pending workflows, API responses, and viewer restrictions. With the virtual environment active, run:

```powershell
python test_activity_api.py
python test_api_response.py
python test_pending.py
python test_pending_workflow.py
python test_viewer_restrictions.py
```

If a test requires a running server, start `python manage.py runserver` in a separate terminal first.

## Important Project Files

```text
manage.py                         Django command-line entry point
inventory_backend/settings.py      Django configuration
inventory_backend/urls.py          Website and API route registration
inventory/                         Main Django application
inventory/migrations/              Database migrations
templates/                         HTML templates
static/                            CSS and JavaScript assets
.env.example                       Environment variable template
.gitignore                         Ignored local files and secrets
```

## Data and Security Notes

- `db.sqlite3` is local development data and is intentionally ignored.
- Create a new database with `python manage.py migrate` on each new laptop.
- Never commit `.env` or real credentials.
- Replace the development `DJANGO_SECRET_KEY` before deployment.
- Set `DEBUG = False`, configure `ALLOWED_HOSTS`, and use HTTPS in production.
- Do not use the sample admin password in production.
- Rotate any credential that has ever been exposed in source code, chat, screenshots, or logs.
- Configure a production database and regular backups before deployment.

## Updating the Project

After the project is already cloned:

```powershell
git pull origin master
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade Django djangorestframework djangorestframework-simplejwt django-cors-headers drf-yasg django-filter openpyxl
python manage.py migrate
python manage.py check
```

## Common Problems

### `python` is not recognized

Reinstall Python with **Add Python to PATH** enabled, or use the Python launcher:

```powershell
py --version
py -m venv .venv
```

### `ModuleNotFoundError`

Activate `.venv` and install the dependencies again:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install Django djangorestframework djangorestframework-simplejwt django-cors-headers drf-yasg django-filter openpyxl
```

### Database table does not exist

Run:

```powershell
python manage.py migrate
```

### Port 8000 is already in use

Run the server on another port:

```powershell
python manage.py runserver 8001
```

Then open http://127.0.0.1:8001/.

### PowerShell activation is blocked

Run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate `.venv` again.
