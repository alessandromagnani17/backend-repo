from flask import request, jsonify
from datetime import datetime
import json
import io
import cv2

def register_routes(app, controllers):
    # Auth Routes
    @app.route('/register', methods=['POST'])
    def register():
        return controllers['auth'].register(request.json)

    @app.route('/login', methods=['POST'])
    def login():
        return controllers['auth'].login(request.json)
        
    @app.route('/check-email-verification', methods=['POST'])
    def check_email_verification():
        return controllers['auth'].check_email_verification(request.json)
        
    @app.route('/verify-email/<string:uid>', methods=['GET'])
    def verify_email(uid):
        return controllers['auth'].verify_email(uid)

    @app.route('/reset-password', methods=['POST'])
    def reset_password():
        return controllers['auth'].reset_password(request.json)

    @app.route('/send-reset-email', methods=['POST'])
    def send_reset_email():
        return controllers['auth'].send_reset_email(request.json)

    @app.route('/decrement-attempts', methods=['POST'])
    def decrement_attempts():
        return controllers['auth'].decrement_attempts(request.json)

    @app.route('/get-attempts-left', methods=['POST'])
    def get_attempts_left():
        return controllers['auth'].get_attempts_left(request.json)

    # User Routes
    @app.route('/api/get_user/<user_id>', methods=['GET'])
    def get_user(user_id):
        return controllers['user'].get_user(user_id)

    @app.route('/update_user', methods=['PATCH'])
    def update_user():
        return controllers['user'].update_user(request.json)

    @app.route('/api/doctors', methods=['GET'])
    def get_doctors():
        return controllers['user'].get_doctors()

    @app.route('/api/patients', methods=['GET'])
    def get_patients():
        return controllers['user'].get_patients()

    @app.route('/api/<doctor_id>/patients', methods=['GET'])
    def get_patients_from_doctor(doctor_id):
        return controllers['user'].get_patients_from_doctor(doctor_id)

    # Operation Routes
    @app.route('/api/operations', methods=['POST'])
    def add_operation():
        return controllers['operation'].add_operation(request.json)

    @app.route('/api/patients/<patient_id>/operations', methods=['GET'])
    def get_patient_operations(patient_id):
        return controllers['operation'].get_patient_operations(patient_id)

    # Notification Routes
    @app.route('/api/notifications', methods=['POST'])
    def send_notification():
        return controllers['notification'].send_notification(request.json)

    @app.route('/api/notifications', methods=['GET'])
    def get_notifications():
        return controllers['notification'].get_notifications(request.args.get('patientId'))

    @app.route('/api/notifications/<notification_id>', methods=['PATCH'])
    def mark_notification_as_read(notification_id):
        return controllers['notification'].mark_notification_as_read(notification_id)

    # Radiograph Routes
    @app.route('/api/patients/<patient_id>/radiographs', methods=['GET'])
    def get_patient_radiographs(patient_id):
        return controllers['radiograph'].get_patient_radiographs(patient_id)

    @app.route('/api/download-radiograph', methods=['GET'])
    def download_radiograph():
        return controllers['radiograph'].download_radiograph(
            request.args.get('url'),
            request.args.get('filename', 'radiograph.png')
        )

    @app.route('/upload-to-dataset', methods=['POST'])
    def upload_to_dataset():
        return controllers['radiograph'].upload_to_dataset(request.files['file'], request.form)

    @app.route('/get_radiographs/<user_uid>', methods=['GET'])
    def get_radiographs(user_uid):
        return controllers['radiograph'].get_radiographs(user_uid)

    @app.route('/get_radiographs_info/<user_uid>/<idx>', methods=['GET'])
    def get_radiographs_info(user_uid, idx):
        return controllers['radiograph'].get_radiographs_info(user_uid, idx)

    @app.route('/predict', methods=['POST'])
    def predict():
        return controllers['radiograph'].predict(request.files['file'], request.form)

    return app
