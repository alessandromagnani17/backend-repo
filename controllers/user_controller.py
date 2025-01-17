from flask import jsonify
from firebase_admin import auth

class UserController:
    def __init__(self, managers):
        self.firestore_manager = managers['firestore']

    def get_user(self, user_id):
        """
        Restituisce i dettagli di un utente dato il suo ID.

        Args:
            user_id (str): ID dell'utente da recuperare.

        Returns:
            Response: Oggetto JSON con i dettagli dell'utente e codice HTTP 200,
                      oppure codice HTTP 404 se l'utente non viene trovato.
        """
        user_data = self.firestore_manager.get_document('users', user_id)
        if user_data:
            return jsonify(user_data), 200
        return jsonify({"error": "User not found"}), 404

    def update_user(self, data):
        """
        Aggiorna le informazioni di un utente nel sistema.

        Args:
            data (dict): Dizionario contenente i dati aggiornati dell'utente. 
                         Deve includere la chiave 'userId' per identificare l'utente.

        Returns:
            Response: Oggetto JSON con messaggio di conferma e codice HTTP 200,
                      codice HTTP 400 in caso di errore di aggiornamento.
        """
        user_id = data.pop('userId')
        try:
            success = self.firestore_manager.update_document('users', user_id, data)
            if success:
                return jsonify({"message": "Dati aggiornati con successo!"}), 200
            return jsonify({"error": "Errore durante l'aggiornamento dei dati."}), 400
        except Exception as e:
            return jsonify({"error": str(e)}), 400

    def get_doctors(self):
        """
        Restituisce l'elenco di tutti i dottori registrati nel sistema.

        Returns:
            Response: Oggetto JSON con l'elenco dei dottori e codice HTTP 200,
                      oppure codice HTTP 404 se non vengono trovati dottori,
                      o codice HTTP 500 in caso di errore interno.
        """
        try:
            doctors = self.firestore_manager.get_users_by_role('doctor')
            if not doctors:
                return jsonify({"message": "Nessun dottore trovato"}), 404
            return jsonify(doctors), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def get_patients(self):
        """
        Restituisce l'elenco di tutti i pazienti registrati nel sistema.

        Returns:
            Response: Oggetto JSON con l'elenco dei pazienti e codice HTTP 200,
                      oppure codice HTTP 404 se non vengono trovati pazienti,
                      o codice HTTP 500 in caso di errore interno.
        """
        try:
            patients = self.firestore_manager.get_users_by_role('patient')
            if not patients:
                return jsonify({"message": "Nessun paziente trovato"}), 404
            return jsonify(patients), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def get_patients_from_doctor(self, doctor_id):
        """
        Restituisce l'elenco dei pazienti associati a un determinato dottore.

        Args:
            doctor_id (str): ID del dottore per cui recuperare i pazienti.

        Returns:
            Response: Oggetto JSON con l'elenco dei pazienti verificati e codice HTTP 200,
                      oppure codice HTTP 404 se non vengono trovati pazienti per il dottore,
                      o codice HTTP 500 in caso di errore interno.
        """
        try:
            patients = self.firestore_manager.get_doctor_patients(doctor_id)
            verified_patients = []
            
            for patient in patients:
                user = auth.get_user(patient['userId'])
                if user.email_verified:
                    verified_patients.append(patient)

            if not verified_patients:
                return jsonify({
                    "message": "Nessun paziente trovato per il dottore selezionato"
                }), 404

            return jsonify(verified_patients), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
        