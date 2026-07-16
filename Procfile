release: python manage.py migrate && python manage.py seed_plans && python manage.py seed_taxonomy
web: gunicorn config.wsgi --log-file - --workers 2 --threads 2 --timeout 30
