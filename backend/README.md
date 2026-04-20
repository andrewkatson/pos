# Positive Only Social Backend

## Description 

Positive Only Social's backend code. Written in 
Python using the Django framework.

## Setup

### Packages 

You will need to run the following command

```shell
pip install -r requirements.txt
```

## Migrations 

From folder `backend`

```shell
python3 manage.py makemigrations
```

```shell
python3 manage.py migrate
```

## Testing 

### For tools

From folder `backend`

```shell
python3 pytest tests
```

### For backend 
From folder `backend`

Make sure to match the SSL redirect settings used in `.github/workflows/backend-tests.yml`. Specifically, set the environment variable `SECURE_SSL_REDIRECT` to `False` when running tests locally to avoid HTTP to HTTPS redirects failing the tests.

**Mac/Linux:**
```shell
SECURE_SSL_REDIRECT=False python manage.py test user_system.tests
```

**Windows (PowerShell):**
```powershell
$env:SECURE_SSL_REDIRECT="False"; python manage.py test user_system.tests
```

Or from `PyCharm`

* `Run` menu
* `Edit Configurations` option 
* `+` option 
* `Python`
* Set `manage.py` as script and `test user_system.tests` as parameter
* Set the environment variable `SECURE_SSL_REDIRECT` to `False`