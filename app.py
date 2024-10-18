from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
import boto3
from botocore.exceptions import ClientError
import jwt
import firebase_admin
from firebase_admin import credentials, auth, firestore

load_dotenv()

app = Flask(__name__)

# Configura CORS per permettere l'accesso da 'http://localhost:8080'
CORS(app, resources={r"/*": {"origins": "http://localhost:8080"}})

# Inizializza Firebase Admin
cred = credentials.Certificate('config/firebase-adminsdk.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

@app.route('/')
def home():
    return jsonify({"message": "Welcome to the API!"})


@app.route('/register', methods=['POST'])
def register():
    data = request.json
    print("Dati ricevuti per la registrazione:", data)

    try:
        # Crea l'utente in Firebase Authentication
        user = auth.create_user(
            email=data['email'],
            password=data['password'],
            display_name=data.get('username'),  # Username
            disabled=False
        )
        print(f"Utente creato con successo: {user.uid}")

        # Dati comuni tra dottori e pazienti
        user_data = {
            "userId": user.uid,
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

        # Se l'utente è un dottore, aggiungi anche il doctorID
        if data['role'] == 'doctor':
            user_data['doctorID'] = data['doctorID']
        else:
            user_data['DoctorRef'] = data['doctorID']

        # Salva i dati nella collezione 'utenti'
        db.collection('osteoarthritiis-db').document(user.uid).set(user_data)
        print("Dati utente salvati nel database:", user_data)

        return jsonify({
            "message": "User registered successfully. Please check your email for the confirmation link.",
            "response": user_data
        }), 200
    
    except Exception as e:
        print("Errore nella registrazione:", str(e))
        return jsonify({"error": str(e), "message": "Controlla i dati forniti."}), 400



@app.route('/confirm', methods=['POST'])
def confirm_registration():
    data = request.json
    print("Dati ricevuti per la conferma dell'email:", data)

    if 'email' not in data:
        return jsonify({"error": "Email is required"}), 400

    try:
        # In link-based verification, the user will click the link, no manual confirmation is needed.
        return jsonify({
            "message": "Email verified through link. No further action required."
        }), 200

    except ClientError as e:
        print("Errore nella conferma dell'email:", str(e))
        return jsonify({
            "error": str(e),
            "code": e.response['Error']['Code'] if e.response else None,
            "message": e.response['Error']['Message'] if e.response else "Unknown error"
        }), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    print("Ricevuti dati di login:", data)  # Stampa i dati ricevuti dal client

    if 'idToken' not in data:
        return jsonify({"error": "ID token is required"}), 400

    try:
        # Verifica il token ID ricevuto dal client
        decoded_token = auth.verify_id_token(data['idToken'])
        uid = decoded_token['uid']  # UID dell'utente autenticato
        print("Token ID verificato. UID:", uid)  # Stampa l'UID dell'utente autenticato

        # Recupera l'utente da Firebase
        user = auth.get_user(uid)
        print("Utente recuperato:", user.email)  # Stampa l'email dell'utente recuperato

        return jsonify({
            "message": "Login successful",
            "email": user.email,  # Puoi includere ulteriori informazioni se necessario
        }), 200

    except firebase_admin.auth.InvalidIdTokenError:
        print("Token ID non valido.")  # Stampa se il token ID non è valido
        return jsonify({"error": "Invalid ID token"}), 401
    except firebase_admin.auth.UserNotFoundError:
        print("Utente non trovato per UID:", uid)  # Stampa se l'utente non è trovato
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        print("Errore nel login:", str(e))  # Stampa l'errore generico
        return jsonify({"error": str(e)}), 500


@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    try:
        # Recupera tutti gli utenti con il ruolo 'doctor' dal database Firestore
        doctors_ref = db.collection('osteoarthritiis-db').where('role', '==', 'doctor').stream()
        
        doctors = []
        for doctor in doctors_ref:
            doctor_data = doctor.to_dict()
            doctors.append(doctor_data)
            print(f"Dottore recuperato: {doctor_data}")  # Stampa i dati di ogni dottore

        # Restituisci la lista dei dottori come risposta JSON
        return jsonify(doctors), 200
    
    except Exception as e:
        print("Errore nel recupero dei dottori:", str(e))
        return jsonify({"error": str(e)}), 500



@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:8080') 
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)