import os

class AppConfig:
    # Environment
    DEBUG = os.environ.get('DEBUG', 'True') == 'True'
    
    # LOCALE
    CORS_ORIGIN = os.environ.get('CORS_ORIGIN', 'http://localhost:8080')
    
    # VM
    # CORS_ORIGIN = os.environ.get('CORS_ORIGIN', 'http://34.122.99.160:8080')

    # Firebase
    FIREBASE_CRED_PATH = os.path.join(
        os.path.abspath(os.path.dirname(__file__)), 
        '..', 
        'config', 
        'firebase-adminsdk.json'
    )
    
    # Google Cloud Storage
    GCS_CRED_PATH = os.path.join(
        os.path.abspath(os.path.dirname(__file__)), 
        '..', 
        'config', 
        'meta-geography-438711-r1-de4779cd8c73.json'
    )
    GCS_BUCKET_NAME = 'osteoarthritis-portal-archive'
    
    # Email
    #SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
    SMTP_USERNAME = 'andyalemonta999@gmail.com'
    SMTP_PASSWORD = "xqnk mrct xtns lvrw"
    #SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
    
    # Model
    MODEL_PATH = 'MODELLO/pesi.h5'