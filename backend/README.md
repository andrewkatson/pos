# Positive Only Social Backend

## Description 

Positive Only Social's backend code. Written in 
Python using the Django framework.

## Setup

### Packages 

You will need to run the following command

```shell
pip install django
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

From folder `backend`

```shell
python3 manage.py test
```

Or from `PyCharm`

* `Run` menu
* `Edit Configurations` option 
* `+` option 
* `Python`
* Set `manage.py` as script and `test` as parameter