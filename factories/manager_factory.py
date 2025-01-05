from utils.firestore_utils import FirestoreManager
from utils.gcs_utils import GCSManager
from utils.model_utils import ModelManager
from utils.email_utils import EmailManager
from firebase_admin import firestore
from config.app_config import AppConfig

# Classe per inizializzare tutti i manager (sfruttando le chiavi di AppConfig)
class ManagerFactory:
    @staticmethod
    def create_managers(app_config):
        # Inizializza Firestore
        db = firestore.client()
        firestore_manager = FirestoreManager(db)
        
        # Inizializza GCS
        gcs_manager = GCSManager(AppConfig.GCS_BUCKET_NAME)
        
        # Inizializza Model
        model = gcs_manager.load_model(AppConfig.MODEL_PATH)
        model_manager = ModelManager(model)
        
        # Inizializza Email
        email_manager = EmailManager(
            sender_email=AppConfig.SMTP_USERNAME,
            sender_password=AppConfig.SMTP_PASSWORD
        )
        
        return {
            'firestore': firestore_manager,
            'gcs': gcs_manager,
            'model': model_manager,
            'email': email_manager
        }