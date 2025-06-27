import os
from datetime import timedelta
import logging

class Config:
    """Configuración base de la aplicación Flask"""
    
    # Configuración de base de datos
    # Railway proporciona DATABASE_URL automáticamente
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:jvbnOe7iME83kVQ2@localhost:5432/creditapp_fly"
    )
    
    # Railway usa postgres:// pero SQLAlchemy necesita postgresql://
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
    
    # Configuración de seguridad
    SECRET_KEY = os.getenv("SECRET_KEY", "9b3f37d1a27a46f4ac33dfc34a1c24e9")
    
    # Configuración de SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = False
    
    # Configuración optimizada para Railway (producción)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,        # Verifica conexiones antes de usar
        'pool_recycle': 300,          # Recicla conexiones cada 5 minutos
        'pool_timeout': 30,           # Tiempo de espera para obtener conexión
        'max_overflow': 10,           # Conexiones adicionales permitidas
        'pool_size': 10,              # Tamaño base del pool de conexiones
        'connect_args': {
            'sslmode': 'prefer',      # Usa SSL cuando esté disponible
            'connect_timeout': 10,    # Timeout de conexión
            'application_name': 'CreditApp'
        }
    }
    
    # Configuración de sesiones
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    SESSION_COOKIE_SECURE = os.getenv('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Configuración de archivos y uploads
    STATIC_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    
    # Configuración de logging para producción
    LOG_LEVEL = logging.INFO if os.getenv('FLASK_ENV') == 'production' else logging.DEBUG
    
    # Configuración específica para Railway
    PORT = int(os.getenv('PORT', 8080))
    
    # Configuración de correo (para futuras implementaciones)
    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    
    # Configuración de Redis (para futuras implementaciones de cache)
    REDIS_URL = os.getenv('REDIS_URL')
    
    @staticmethod
    def init_app(app):
        """Inicialización específica de la aplicación"""
        pass

class DevelopmentConfig(Config):
    """Configuración para desarrollo local"""
    DEBUG = True
    SQLALCHEMY_ECHO = False  # Cambia a True para ver queries SQL en desarrollo
    
    # Pool de conexiones más pequeño para desarrollo
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 20,
        'max_overflow': 0,
        'pool_size': 5
    }

class ProductionConfig(Config):
    """Configuración para producción (Railway)"""
    DEBUG = False
    TESTING = False
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Log hacia stdout en producción (Railway lo captura)
        import logging
        from logging import StreamHandler
        
        # Configurar handler para stdout
        handler = StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s %(name)s: %(message)s'
        ))
        
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('CreditApp iniciado en modo producción')

class TestingConfig(Config):
    """Configuración para pruebas"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Mapeo de configuraciones
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

# Configuración de logging global
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Para que Railway capture los logs
    ]
)

# Silenciar logs innecesarios en producción
if os.getenv('FLASK_ENV') == 'production':
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
