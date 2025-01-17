from flask import jsonify

class OperationController:
    def __init__(self, managers):
        self.firestore_manager = managers['firestore']

    def add_operation(self, data):
        """
        Aggiunge una nuova operazione per un paziente.

        Args:
            data (dict): Dizionario contenente i dati dell'operazione. Deve includere:
                - 'doctorId' (str): ID del dottore che pianifica l'operazione.
                - 'patientId' (str): ID del paziente per cui è pianificata l'operazione.
                - 'operationDate' (str): Data dell'operazione.
                - 'description' (str, opzionale): Descrizione dell'operazione.

        Returns:
            Response: Oggetto JSON con il messaggio di conferma e i dettagli dell'operazione 
                      con codice HTTP 201 se la creazione ha successo,
                      codice HTTP 400 in caso di input non valido,
                      oppure codice HTTP 500 per errori interni.
        """
        try:
            operation_data = {
                "doctorId": data['doctorId'],
                "patientId": data['patientId'],
                "operationDate": data['operationDate'],
                "description": data.get('description', '')
            }

            _, created_operation = self.firestore_manager.create_operation(operation_data)

            return jsonify({
                "message": "Operazione pianificata",
                "operation": created_operation
            }), 201
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            return jsonify({"error": "Errore interno del server"}), 500

    def get_patient_operations(self, patient_id):
        """
        Recupera tutte le operazioni pianificate per un paziente.

        Args:
            patient_id (str): ID del paziente per cui recuperare le operazioni.

        Returns:
            Response: Oggetto JSON con l'elenco delle operazioni e codice HTTP 200,
                      oppure codice HTTP 500 in caso di errore interno.
        """
        try:
            operations = self.firestore_manager.query_documents(
                'operations',
                [('patientId', '==', patient_id)]
            )
            return jsonify(operations), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        