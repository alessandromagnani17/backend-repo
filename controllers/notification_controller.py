from flask import jsonify

class NotificationController:
    def __init__(self, managers):
        self.firestore_manager = managers['firestore']

    def send_notification(self, data):
        """
        Invia una nuova notifica a un paziente.

        Args:
            data (dict): Dizionario contenente i dati della notifica. Deve includere:
                - 'patientId' (str): ID del paziente.
                - 'message' (str): Messaggio della notifica.
                - 'date' (str): Data della notifica.
                - 'time' (str): Ora della notifica.
                - 'sentAt' (str): Timestamp di invio.

        Returns:
            Response: Oggetto JSON con messaggio di successo e codice HTTP 200,
                      oppure errore e codice HTTP 500 in caso di eccezione.
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
        Recupera tutte le notifiche associate a un paziente.

        Args:
            patient_id (str): ID del paziente per cui recuperare le notifiche.

        Returns:
            Response: Oggetto JSON con l'elenco delle notifiche e codice HTTP 200,
                      codice HTTP 400 se manca l'ID del paziente,
                      oppure codice HTTP 500 in caso di eccezione.
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

        Args:
            notification_id (str): ID della notifica da marcare come letta.

        Returns:
            Response: Oggetto JSON con messaggio di successo e codice HTTP 200,
                      codice HTTP 404 se la notifica non viene trovata,
                      oppure codice HTTP 500 in caso di eccezione.
        """
        try:
            success = self.firestore_manager.mark_notification_read(notification_id)
            if success:
                return jsonify({"message": "Notifica segnata come letta"}), 200
            return jsonify({"error": "Notifica non trovata"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        