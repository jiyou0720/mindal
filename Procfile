web: export FLASK_APP=backend.app && flask db upgrade && python backend/initialize_roles_and_admin.py && python backend/initialize_menus.py && gunicorn backend.app:app
