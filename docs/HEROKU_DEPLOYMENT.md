# Heroku deployment

The repository is deployable as a Django web process using `Procfile`,
`requirements.txt`, `.python-version`, `app.json`, and `.slugignore`.

## Required production configuration

- Provision Heroku Postgres so Heroku supplies `DATABASE_URL`.
- Set `SECRET_KEY` to a long random value.
- Keep `DEBUG=False` and `SECURE_SSL_REDIRECT=True`.
- Set `ALLOWED_HOSTS` to the exact Heroku/custom domains where possible.
- Add Google and LinkedIn credentials only after their callback URLs are registered.
- Keep `STRIPE_MOCK_MODE=True` for preview deployments. Live payments must not be
  enabled until Stripe webhook signatures and Checkout Session payment status are
  verified server-side.

The release phase runs database migrations. The `app.json` post-deploy step seeds
the subscription plans for newly created review apps.

## 30-day CV retention

The app includes an idempotent cleanup command:

```text
python manage.py purge_expired_cvs
```

Heroku Scheduler is declared in `app.json`. In the Scheduler dashboard, configure
the command above to run daily. A daily run enforces a rolling 30-day policy;
running it only monthly could retain a CV for nearly 60 days. Test the selection
without deleting anything with:

```text
python manage.py purge_expired_cvs --dry-run
```

The retention period is controlled by `CV_RETENTION_DAYS` and defaults to 30.

## CV storage warning

Heroku dyno files are ephemeral. `MEDIA_ROOT` is suitable only for temporary
processing and must not be treated as durable CV storage. Before production use,
configure private object storage (such as S3-compatible storage) or intentionally
store encrypted CV bytes in PostgreSQL. Access must always be authenticated and
audited; public media URLs must not expose CVs.

## Commands after CLI authentication

```text
heroku create <app-name>
heroku addons:create heroku-postgresql:essential-0
heroku addons:create scheduler:standard
heroku config:set DEBUG=False SECURE_SSL_REDIRECT=True
git push heroku main
heroku run python manage.py seed_plans
heroku run python manage.py purge_expired_cvs --dry-run
```
