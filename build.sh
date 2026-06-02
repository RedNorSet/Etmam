#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py shell -c "
from accounts.models import User
if not User.objects.filter(username='admin').exists():
    u = User.objects.create_superuser('admin', 'admin@etmam.com', 'Admin@11')
    u.role = 'administrator'
    u.full_name = 'Admin'
    u.save()
    print('Superuser created.')
else:
    u = User.objects.get(username='admin')
    u.role = 'administrator'
    u.save()
    print('Superuser role updated.')
"
