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

Note: You may need to set `SECURE_SSL_REDIRECT=False` in your environment when running tests locally to avoid HTTP to HTTPS redirects failing the tests.

```shell
SECURE_SSL_REDIRECT=False python3 manage.py test user_system.tests
```

Or from `PyCharm`

* `Run` menu
* `Edit Configurations` option 
* `+` option 
* `Python`
* Set `manage.py` as script and `test user_system.tests` as parameter
* Set the environment variable `SECURE_SSL_REDIRECT` to `False`