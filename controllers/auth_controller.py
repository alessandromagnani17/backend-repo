from flask import jsonify
from firebase_admin import auth

class AuthController:
    def __init__(self, managers):
        self.firestore_manager = managers['firestore']
        self.email_manager = managers['email']

    def register(self, data):
        try:
            auth_data = {
                'email': data['email'],
                'password': data['password'],
                'username': data.get('username')
            }
            
            user_data = {
                "username": data.get('username'),
                "email": data['email'],
                "name": data['nome'],
                "family_name": data['cognome'],
                "birthdate": data['data'],
                "phone_number": data['telefono'],
                "gender": data['gender'],
                "address": data['address'],
                "cap_code": data['cap_code'],
                "tax_code": data['tax_code'],
                "role": data['role']
            }

            if data['role'] == 'doctor':
                user_data['doctorID'] = data['doctorID']
            else:
                user_data['DoctorRef'] = data['doctorID']

            uid, created_user = self.firestore_manager.create_user(auth_data, user_data)

            verification_link = f"http://34.122.99.160:8080/verify-email/{uid}"
            self.email_manager.send_email(
                data['email'],
                "Verifica il tuo indirizzo email",
                f"Per favore, verifica il tuo indirizzo email cliccando il seguente link: {verification_link}"
            )

            return jsonify({
                "message": "User registered successfully. Please check your email for the confirmation link.",
                "response": created_user
            }), 200

        except Exception as e:
            return jsonify({"error": str(e), "message": "Controlla i dati forniti."}), 400

    def login(self, data):
        if 'idToken' not in data:
            return jsonify({"error": "ID token is required"}), 400

        try:
            decoded_token = auth.verify_id_token(data['idToken'])
            uid = decoded_token['uid']
            user = auth.get_user(uid)
            
            user_data = self.firestore_manager.get_document('users', uid)
            
            if not user_data:
                return jsonify({"error": "User data not found in Firestore"}), 404

            user_data['uid'] = user.uid
            user_data['email'] = user.email
            user_data['attemptsLeft'] = user_data.get('loginAttemptsLeft', 0)

            return jsonify({
                "message": "Login successful",
                "user": user_data
            }), 200

        except auth.InvalidIdTokenError as e:
            return jsonify({"error": "Invalid ID token", "details": str(e)}), 401
        except Exception as e:
            return jsonify({"error": "Internal server error", "details": str(e)}), 500

    def check_email_verification(self, data):
        email = data.get('email')
        if not email:
            return jsonify({"error": "Email is required"}), 400

        try:
            user = auth.get_user_by_email(email)
            if user.email_verified:
                return jsonify({"message": "Email verified"}), 200
            return jsonify({
                "error": "La tua email non è stata verificata. Verifica la tua email prima di accedere."
            }), 403
        except auth.UserNotFoundError:
            return jsonify({"error": "User not found"}), 404
        except Exception as e:
            return jsonify({"error": "Internal server error"}), 500

    def verify_email(self, uid):
        if not uid:
            return jsonify({"error": "Missing user ID"}), 400
        
        try:
            user = auth.get_user(uid)
            if user.email_verified:
                return jsonify({"message": "Email già verificata!"}), 200

            auth.update_user(uid, email_verified=True)
            return jsonify({"message": "Email verificata con successo!"}), 200
        except auth.UserNotFoundError:
            return jsonify({"error": "Utente non trovato"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def reset_password(self, data):
        try:
            uid = data.get('uid')
            new_password = data.get('password')

            if not uid or not new_password:
                return jsonify({"error": "UID e password sono obbligatori."}), 400

            auth.update_user(uid, password=new_password)
            success = self.firestore_manager.update_login_attempts(uid, reset=True)
            
            if not success:
                return jsonify({
                    "error": "Errore durante l'aggiornamento dei tentativi di login"
                }), 500

            return jsonify({"message": "Password aggiornata con successo."}), 200
        except Exception as e:
            return jsonify({"error": f"Errore: {str(e)}"}), 500

    def send_reset_email(self, data):
        try:
            email = data.get('email')
            if not email:
                return jsonify({"error": "L'email è obbligatoria"}), 400

            user = auth.get_user_by_email(email)
            verification_link = f"http://34.122.99.160:8080/reset-password/{user.uid}"
            
            self.email_manager.send_email(
                email,
                "Resetta la tua password",
                f"Per favore, resetta la tua password cliccando il seguente link: {verification_link}"
            )

            return jsonify({"message": "Email di reset inviata con successo"}), 200
        except Exception as e:
            return jsonify({
                "error": f"Errore durante l'invio del link di reset: {str(e)}"
            }), 500

    def decrement_attempts(self, data):
        email = data.get('email')
        if not email:
            return jsonify({"error": "Email is required"}), 400

        users = self.firestore_manager.query_documents('users', [('email', '==', email)])
        if not users:
            return jsonify({"error": "User not found"}), 404

        user_data = users[0]
        user_id = user_data['id']
        
        success = self.firestore_manager.update_login_attempts(user_id, reset=False)
        
        if success:
            return jsonify({
                "message": "Attempts decremented",
                "loginAttemptsLeft": max(0, user_data.get('loginAttemptsLeft', 0) - 1)
            }), 200
        return jsonify({"error": "Failed to update attempts"}), 400

    def get_attempts_left(self, data):
        email = data.get('email')
        if not email:
            return jsonify({"error": "Email is required"}), 400

        users = self.firestore_manager.query_documents('users', [('email', '==', email)])
        if not users:
            return jsonify({"error": "User not found"}), 404

        attempts_left = users[0].get('loginAttemptsLeft', 0)
        return jsonify({"loginAttemptsLeft": attempts_left}), 200
    