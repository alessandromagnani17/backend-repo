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
from google.cloud import storage
from google.oauth2 import service_account 


load_dotenv()

app = Flask(__name__)

# Configura CORS per permettere l'accesso da 'http://localhost:8080'
CORS(app, resources={r"/*": {"origins": "http://localhost:8080"}})

# Percorso dei file delle credenziali
basedir = os.path.abspath(os.path.dirname(__file__))
firebase_cred_path = os.path.join(basedir, 'config', 'firebase-adminsdk.json')
gcs_cred_path = os.path.join(basedir, 'config', 'meta-geography-438711-r1-de4779cd8c73.json')

# Imposta la variabile d'ambiente per le credenziali di Google Cloud Storage
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = gcs_cred_path

# Inizializza Firebase Admin
cred = credentials.Certificate(firebase_cred_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Crea il client di Google Cloud Storage
storage_client = storage.Client()


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
            "email": data['email'],
            "name": data['nome'],
            "family_name": data['cognome'],
            "birthdate": data['data'],
            "phone_number": data['telefono'],
            "gender": data['gender'],
            "address": data['address'],
            "cap_code": data['cap_code'],
            "tax_code": data['tax_code'],
            "role": data['role'],
            "loginAttemptsLeft": 5
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

    if 'idToken' not in data:
        return jsonify({"error": "ID token is required"}), 400

    try:
        # Verifica il token ID ricevuto dal client
        decoded_token = auth.verify_id_token(data['idToken'])
        uid = decoded_token['uid']  # UID dell'utente autenticato

        # Recupera l'utente da Firebase
        user = auth.get_user(uid)
        print("Utente recuperato:", {key: value for key, value in user.__dict__.items()})

        if not user.email_verified:
            print("Email NON verificata!!")
            return jsonify({
                "message": "Email not verified"
            }), 403
        else:
            print("Email verificata!!")

        user_doc = db.collection('osteoarthritiis-db').document(uid).get()

        if not user_doc.exists:
            return jsonify({"error": "User data not found in Firestore"}), 404

        user_data = user_doc.to_dict()

        attempts_left = user_data.get('loginAttemptsLeft', 0)

        # Aggiungo attributi di autenticazione a quelli della collezione su firestore
        user_data['uid'] = user.uid
        user_data['email'] = user.email
        user_data['attemptsLeft'] = attempts_left

        return jsonify({
            "message": "Login successful",
            "user": user_data,  
        }), 200

    except firebase_admin.auth.InvalidIdTokenError as e:
        print("Token ID non valido:", e)  # Stampa se il token ID non è valido
        return jsonify({"error": "Invalid ID token", "details": str(e)}), 401
    except firebase_admin.auth.UserNotFoundError as e:
        print("Utente non trovato per UID:", uid, "Errore:", e)  # Stampa se l'utente non è trovato
        return jsonify({"error": "User not found", "details": str(e)}), 404
    except Exception as e:
        print("Errore nel login:", str(e))  # Stampa l'errore generico
        return jsonify({"error": "Internal server error", "details": str(e)}), 500




@app.route('/decrement-attempts', methods=['POST'])
def decrement_attempts():
    data = request.json
    email = data.get('email')  

    print("Email ricevuta: " + email)

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Recupera il documento dell'utente da Firestore cercando per email
    user_query = db.collection('osteoarthritiis-db').where('email', '==', email).stream()

    user_data = None
    for user_doc in user_query:
        user_data = user_doc.to_dict()  # Se trovi l'utente, ottieni i suoi dati
        uid = user_doc.id  # Ottieni l'ID del documento
        print("Uid trovato: " + uid)

    if user_data is None:
        print("Non trovo nessun utente")
        return jsonify({"error": "User not found"}), 404

    # Decrementa i tentativi
    attempts_left = user_data.get('loginAttemptsLeft', 0)

    print("Tentativi letti: " + str(attempts_left))

    if attempts_left > 0:
        db.collection('osteoarthritiis-db').document(uid).update({
            'loginAttemptsLeft': attempts_left - 1
        })
        attempts_left -= 1  # Decrementa il valore per la risposta

    return jsonify({"message": "Attempts decremented", "loginAttemptsLeft": attempts_left}), 200




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



@app.route('/api/<doctor_id>/patients', methods=['GET'])
def get_patients_from_doctor(doctor_id):
    try:
        print(f"Richiesta ricevuta per Doctor ID: {doctor_id}")  # Debug
        # Recupera tutti i pazienti associati al dottore corrente in Firestore
        patients_ref = db.collection('osteoarthritiis-db').where('DoctorRef', '==', doctor_id).stream()

        patients = []
        for patient in patients_ref:
            patient_data = patient.to_dict()
            patients.append(patient_data)
            print(f"Paziente recuperato per il dottore {doctor_id}: {patient_data}")

        print("patients: ", patients)  # Stampa la lista dei pazienti
        # Restituisci la lista dei pazienti come risposta JSON
        return jsonify(patients), 200

    except Exception as e:
        print(f"Errore nel recupero dei pazienti per il dottore {doctor_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500



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



@app.route('/patients/<string:patient_id>/radiographs', methods=['GET'])
def get_radiographs(patient_id):
    try:
        # Recupera le radiografie per il paziente specificato
        # Supponendo che tu abbia una collezione "radiographs" nel tuo database Firestore
        radiographs_ref = db.collection('radiographs').where('patientId', '==', patient_id).stream()

        radiographs = []
        for radiograph in radiographs_ref:
            radiographs.append(radiograph.to_dict())

        return jsonify(radiographs), 200
    
    except Exception as e:
        print("Errore nel recupero delle radiografie:", str(e))
        return jsonify({"error": str(e)}), 500
    


def upload_file_to_gcs(file, patient_id):
    """Funzione per caricare file su Google Cloud Storage."""
    print(f"File ricevuto: {file.filename}, Tipo: {file.content_type}")  # Debug

    # Crea un client per Google Cloud Storage
    storage_client = storage.Client()
    
    # Nome del bucket su Google Cloud Storage
    bucket_name = 'osteoarthritis-radiographs-archive'
    bucket = storage_client.bucket(bucket_name)
    
    # Definisci il nome del file all'interno del bucket
    blob = bucket.blob(f"{patient_id}/{file.filename}")
    
    # Carica il file
    blob.upload_from_file(file, content_type=file.content_type)    

    # Restituisci l'URL pubblico del file
    blob.make_public()
    return blob.public_url


@app.route('/api/patients/<patient_id>/radiographs', methods=['POST']) 
def upload_radiograph(patient_id):
    print("Ricevuta richiesta di caricamento radiografia")  # Debug

    if 'file' not in request.files or 'patientId' not in request.form:
        print("File o patientId mancante")  # Debug
        return jsonify({"error": "File o patientId mancante"}), 400

    file = request.files['file']
    patient_id = request.form['patientId']

    if file.filename == '':
        print("Nessun file selezionato")  # Debug
        return jsonify({"error": "Nessun file selezionato"}), 400

    try:
        print(f"File ricevuto: {file.filename}, ID Paziente: {patient_id}")  # Debug
        # Carica il file su Google Cloud Storage
        file_url = upload_file_to_gcs(file, patient_id)

        # Salva l'URL del file nella documentazione del paziente su Firestore
        patient_ref = db.collection('osteoarthritiis-db').document(patient_id)
        patient_ref.update({
            'radiographs': firestore.ArrayUnion([file_url])
        })

        print(f"File caricato con successo, URL: {file_url}")  # Debug
        return jsonify({"message": "Radiografia caricata con successo!", "fileUrl": file_url}), 200

    except Exception as e:
        print(f"Errore durante l'upload: {str(e)}")  # Stampa l'errore
        return jsonify({"error": str(e)}), 500



import tensorflow as tf
import numpy as np
from tensorflow.keras.preprocessing import image
import io

# Ricrea il modello usato durante il training
img_shape = (224, 224, 3)

base_model = tf.keras.applications.ResNet50(
    input_shape=img_shape,
    include_top=False,
    weights=None  # Non caricare i pesi pre-addestrati di ImageNet, poiché caricherai i tuoi pesi
)

# Rendi i layer del modello base addestrabili (come nel tuo codice di training)
for layer in base_model.layers:
    layer.trainable = True

# Ricrea la parte superiore del modello
model = tf.keras.models.Sequential([
    base_model,
    tf.keras.layers.GlobalAveragePooling2D(),
    tf.keras.layers.Dropout(0.2),
    tf.keras.layers.Dense(5, activation='softmax')  # Assumendo che tu abbia 5 classi
])

model.load_weights(r"C:\Users\Utente\Downloads\weights_epoch_89.weights.h5")



@app.route('/predict', methods=['POST'])
def predict():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']

    # Carica l'immagine direttamente dalla memoria
    img = image.load_img(io.BytesIO(file.read()), target_size=(224, 224))

    # Prepara l'immagine per la predizione
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)  # Aggiungi dimensione batch
    img_array /= 255.0  # Normalizza l'immagine

    # Fai la predizione
    predictions = model.predict(img_array)

    # Trova la classe con la massima probabilità
    predicted_class = np.argmax(predictions[0])  
    confidence = float(np.max(predictions[0]))  # Fiducia nella previsione

    # Mappa personalizzata per le tue 5 classi
    class_labels = {
        0: 'Classe 1: Normale',
        1: 'Classe 2: Lieve osteoartrite',
        2: 'Classe 3: Moderata osteoartrite',
        3: 'Classe 4: Grave osteoartrite',
        4: 'Classe 5: Avanzata osteoartrite'
    }

    # Gestisci i casi in cui predicted_class non è in class_labels (non necessario in questo caso, ma per sicurezza)
    predicted_label = class_labels.get(predicted_class, 'Unknown class')

    return jsonify({
        'predicted_class': predicted_label,
        'confidence': confidence  # Restituisce anche la fiducia della previsione
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)