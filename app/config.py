import os
from datetime import timedelta
import logging

class Config:
    # Configuración básica
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///local.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 20,
        'max_overflow': 0,
        'pool_size': 5
    }

    # Configuración de la sesión
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)

    # Configuración de archivos estáticos
    STATIC_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

    # Configuración de subida de archivos
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
