from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os
import firebase_admin
from factories.manager_factory import ManagerFactory
from controllers.auth_controller import AuthController
from controllers.user_controller import UserController
from controllers.operation_controller import OperationController
from controllers.notification_controller import NotificationController
from controllers.radiograph_controller import RadiographController
from routes.api_routes import register_routes
from config.app_config import AppConfig

load_dotenv()

def create_app():
    app = Flask(__name__)

    # Set Google Cloud credentials environment variable
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = AppConfig.GCS_CRED_PATH

    # Configure CORS using AppConfig
    CORS(app, resources={r"/*": {"origins": AppConfig.CORS_ORIGIN}})

    # Initialize Firebase Admin
    cred = firebase_admin.credentials.Certificate(AppConfig.FIREBASE_CRED_PATH)
    firebase_admin.initialize_app(cred)

    # Inizializza managers
    managers = ManagerFactory.create_managers(app.config)

    # Inizializza controllers
    controllers = {
        'auth': AuthController(managers),
        'user': UserController(managers),
        'operation': OperationController(managers),
        'notification': NotificationController(managers),
        'radiograph': RadiographController(managers)
    }

    # Registra routes
    register_routes(app, controllers)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)