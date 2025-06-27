import os
from datetime import timedelta
import logging

class Config:
    """Configuración de la aplicación Flask"""
    
    # Base de datos - Railway proporciona DATABASE_URL automáticamente
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    
    # Railway a veces usa postgres:// pero SQLAlchemy necesita postgresql://
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
    
    # Seguridad
    SECRET_KEY = os.getenv("SECRET_KEY", "clave-temporal-para-desarrollo")
    
    # Configuración de SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 30,
        'max_overflow': 10,
        'pool_size': 10
    }
    
    # Sesiones
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    
    # Archivos
    STATIC_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
