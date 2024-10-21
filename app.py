from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
import boto3
from botocore.exceptions import ClientError
import jwt
import firebase_admin
from firebase_admin import credentials, auth, firestore
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

def get_user_data_from_database(uid):
    user_ref = db.collection('osteoarthritiis-db').document(uid)
    user_data = user_ref.get()
    if user_data.exists:
        return user_data.to_dict()
    else:
        return None  # Se l'utente non esiste


def send_verification_email(email, link):
    sender_email = "andyalemonta@gmail.com"  # Sostituisci con il tuo indirizzo email
    sender_password = "vlpy jeea avjx feql"  # Sostituisci con l'App Password di Gmail

    # Crea il messaggio
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = email
    message["Subject"] = "Verifica il tuo indirizzo email"

    # Corpo dell'email
    body = f"Per favore, verifica il tuo indirizzo email cliccando il seguente link: {link}"
    message.attach(MIMEText(body, "plain"))

    # Invia l'email
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()  # Sicurezza
            server.login(sender_email, sender_password)  # Login
            server.sendmail(sender_email, email, message.as_string())  # Invia l'email
            print("Email di verifica inviata con successo!")
    except Exception as e:
        print("Errore nell'invio dell'email:", e)

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
            "email": data['email'],
            "username": data.get('username'),
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

        # Genera il link di verifica
        verification_link = f"http://localhost:8080/verify-email/{user.uid}"
        # Invia l'email di verifica
        send_verification_email(data['email'], verification_link)

        return jsonify({
            "message": "User registered successfully. Please check your email for the confirmation link.",
            "response": user_data
        }), 200
    
    except Exception as e:
        print("Errore nella registrazione:", str(e))
        return jsonify({"error": str(e), "message": "Controlla i dati forniti."}), 400


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
        print("Utente recuperato:", {key: value for key, value in user.__dict__.items()})


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
    

@app.route('/api/patients', methods=['GET'])
def get_patients():
    try:
        # Recupera tutti gli utenti con il ruolo 'patient' dal database Firestore
        patients_ref = db.collection('osteoarthritiis-db').where('role', '==', 'patient').stream()
        
        patients = []
        for patient in patients_ref:
            patient_data = patient.to_dict()
            patients.append(patient_data)
            print(f"Dottore recuperato: {patient_data}")  # Stampa i dati di ogni dottore

        # Restituisci la lista dei pazienti come risposta JSON
        return jsonify(patients), 200
    
    except Exception as e:
        print("Errore nel recupero dei dottori:", str(e))
        return jsonify({"error": str(e)}), 500


@app.route('/doctors/<int:doctor_id>/patients', methods=['GET'])
def get_patients_from_doctor(doctor_id):
    # Recupera i pazienti associati al dottore corrente
    patients = User.query.filter_by(DoctorRef=doctor_id).all()
    
    # Trasforma i pazienti in un dizionario per la risposta
    patients_list = [{
        'id': patient.id,
        'name': patient.name,
        'DoctorRef': patient.DoctorRef,
        # Aggiungi altri campi se necessario
    } for patient in patients]
    
    return jsonify(patients_list)


@app.route('/verify-email/<string:uid>', methods=['GET'])
def verify_email(uid):
    if not uid:
        return jsonify({"error": "Missing user ID"}), 400
    
    try:
        # Verifica che l'utente esista su Firebase
        user = auth.get_user(uid)
        
        # Imposta l'email come verificata
        auth.update_user(uid, email_verified=True)

        return jsonify({"message": "Email verificata con successo!"}), 200
    except auth.UserNotFoundError:
        return jsonify({"error": "Utente non trovato"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:8080') 
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)