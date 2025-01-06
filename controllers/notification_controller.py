from flask import jsonify

class NotificationController:
    def __init__(self, managers):
        self.firestore_manager = managers['firestore']

    def send_notification(self, data):
        """
        Invia una nuova notifica a un paziente.
        """
        try:
            notification_data = {
                'patientId': data['patientId'],
                'message': data['message'],
                'date': data['date'],
                'time': data['time'],
                'sentAt': data['sentAt']
            }

            _, created_notification = self.firestore_manager.create_notification(notification_data)
            return jsonify({"message": "Notifica inviata con successo"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def get_notifications(self, patient_id):
        """
        Recupera tutte le notifiche di un paziente.
        """
        try:
            if not patient_id:
                return jsonify({"error": "patientId è richiesto"}), 400
            
            notifications = self.firestore_manager.get_user_notifications(patient_id)
            return jsonify({"notifications": notifications}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def mark_notification_as_read(self, notification_id):
        """
        Segna una notifica come letta.
        """
        try:
            success = self.firestore_manager.mark_notification_read(notification_id)
            if success:
                return jsonify({"message": "Notifica segnata come letta"}), 200
            return jsonify({"error": "Notifica non trovata"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500