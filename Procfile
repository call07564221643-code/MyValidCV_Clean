release: python manage.py migrate && python manage.py seed_plans && python manage.py seed_taxonomy && python manage.py seed_management_roles && python manage.py seed_growth_providers
web: gunicorn config.wsgi --log-file - --workers 2 --threads 2 --timeout 30
