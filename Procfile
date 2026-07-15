release: python manage.py migrate && python manage.py seed_plans
web: gunicorn config.wsgi --log-file - --workers 2 --threads 2 --timeout 30
