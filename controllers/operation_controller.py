from flask import jsonify

class OperationController:
    def __init__(self, managers):
        self.firestore_manager = managers['firestore']

    def add_operation(self, data):
        """
        Aggiunge una nuova operazione per un paziente.
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
        Recupera tutte le operazioni di un paziente.
        """
        try:
            operations = self.firestore_manager.query_documents(
                'operations',
                [('patientId', '==', patient_id)]
            )
            return jsonify(operations), 200
        except Exception as e:
            return jsonify({'error': str(e)}), 500