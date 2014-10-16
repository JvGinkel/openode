DATABASE_ENGINE = 'postgresql_psycopg2'  # only postgres (>8.3) and mysql are supported so far others have not been tested yet
DATABASE_NAME = 'openode'             # Or path to database file if using sqlite3.
DATABASE_USER = 'openode'             # Not used with sqlite3.
DATABASE_PASSWORD = 'yourpass'         # Not used with sqlite3.
DATABASE_HOST = ''             # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.

# Your domain name
DOMAIN_NAME = 'localhost'

# Make up some unique string, and don't share it with anybody.
SECRET_KEY = '3#&ds&r_!m2bz+f&$37nlfb4t81t@^&ql6au4rolas(of0dq&s'

# enable asynchronous calls
CELERY_ALWAYS_EAGER = False

DEBUG = True

# mayan server IP
DOCUMENT_SERVER_IP = "127.0.0.1"

# SECRET key, random hash
DOCUMENT_HMAC_KEY = "sd1fg86ds4f6sd8hg4sd6fg68sdf746g4"

# SECRET id, random hash
DOCUMENT_URI_ID = "1sadfasfg468h7j9g7j9h78gk6g54fg6f"

# mayan port, example.
DOCUMENT_URI_PORT = 33333
