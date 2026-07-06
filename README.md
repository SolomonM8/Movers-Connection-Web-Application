# Movers Connection Web Application

A Django web application. This is currently a local test/dev environment that will later be ported to a Linux VPS.

## Setup

1. Create and activate a virtual environment:
   ```
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Apply migrations:
   ```
   python manage.py migrate
   ```
4. Run the dev server:
   ```
   python manage.py runserver
   ```
