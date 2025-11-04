import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///local.db')
    if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql+psycopg://', 1)
    elif SQLALCHEMY_DATABASE_URI.startswith('postgresql://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgresql://', 'postgresql+psycopg://', 1)

    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-in-prod')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False

    # Very small, safe defaults; can be overridden with env vars
    POOL_SIZE = int(os.environ.get('DB_POOL_SIZE', '2'))
    MAX_OVERFLOW = int(os.environ.get('DB_MAX_OVERFLOW', '2'))
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        'pool_size': POOL_SIZE,
        'max_overflow': MAX_OVERFLOW,
    }

    # Disable auto-create by default in prod-like envs
    CREATE_TABLES_ON_START = os.environ.get('CREATE_TABLES_ON_START', '0') == '1'
