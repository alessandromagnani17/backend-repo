from flask import Flask, send_file, jsonify, request
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
import cv2
import tensorflow as tf
import numpy as np
from tensorflow.keras.preprocessing import image
import io
import requests
from tensorflow.keras.models import load_model
import matplotlib.pyplot as plt
from io import BytesIO
import h5py


load_dotenv()

app = Flask(__name__)

# Configura CORS per permettere l'accesso da 'http://localhost:8080'
#CORS(app, resources={r"/*": {"origins": "http://localhost:8080"}})
CORS(app, resources={r"/*": {"origins": "*"}})

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


# Funzione per scaricare e caricare i pesi dal bucket
def load_model_from_gcs(bucket_name, blob_name):
    # Inizializza il client e accedi al bucket
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # Scarica i dati in memoria
    model_bytes = BytesIO()
    blob.download_to_file(model_bytes)
    model_bytes.seek(0)  # Riporta il puntatore all'inizio del file

    # Usa Keras per caricare il modello direttamente dal buffer
    with h5py.File(model_bytes, 'r') as h5file:
        model = load_model(h5file)

    print("Modello caricato correttamente dalla memoria!")
    return model

# Nome del bucket e del file
bucket_name = 'osteoarthritis-radiographs-archive'
blob_name = 'MODELLO/pesi.h5'

# Carica il modello direttamente dal bucket
model = load_model_from_gcs(bucket_name, blob_name)




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


def send_email(email, subject, msg):
    sender_email = "andyalemonta@gmail.com"  # Sostituisci con il tuo indirizzo email
    sender_password = "vlpy jeea avjx feql"  # Sostituisci con l'App Password di Gmail

    # Crea il messaggio
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = email
    message["Subject"] = subject

    # Corpo dell'email
    message.attach(MIMEText(msg, "plain"))

    # Invia l'email
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()  # Sicurezza
            server.login(sender_email, sender_password)  # Login
            server.sendmail(sender_email, email, message.as_string())  # Invia l'email
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
            "loginAttemptsLeft": 6
        }

        # Se l'utente è un dottore, aggiungi anche il doctorID
        if data['role'] == 'doctor':
            user_data['doctorID'] = data['doctorID']
        else:
            user_data['DoctorRef'] = data['doctorID']

        # Salva i dati nella collezione 'utenti'
        db.collection('osteoarthritiis-db').document(user.uid).set(user_data)

        # Genera il link di verifica
        verification_link = f"http://34.122.99.160:8080/verify-email/{user.uid}"
        # Invia l'email di verifica
        subject = "Verifica il tuo indirizzo email"
        message = f"Per favore, verifica il tuo indirizzo email cliccando il seguente link: {verification_link}"
        send_email(data['email'], subject, message)

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



@app.route('/get_user/<user_id>', methods=['GET'])
def get_user(user_id):
    user_ref = db.collection('osteoarthritiis-db').document(user_id)
    user_data = user_ref.get()
    if user_data.exists:
        return jsonify(user_data.to_dict()), 200
    else:
        return jsonify({"error": "User not found"}), 404




@app.route('/update_user', methods=['PATCH'])
def update_user():
    data = request.json
    user_id = data.get('userId')  # Ottieni l'ID utente dal payload
    updates = {key: value for key, value in data.items() if key != 'userId'}  # Filtro per escludere l'ID utente

    try:
        user_ref = db.collection('osteoarthritiis-db').document(user_id)
        user_ref.update(updates)  # Aggiorna i dati nel database

        return jsonify({"message": "Dati aggiornati con successo!"}), 200
    except Exception as e:
        print("Errore nell'aggiornamento dei dati:", str(e))
        return jsonify({"error": str(e), "message": "Errore durante l'aggiornamento dei dati."}), 400


@app.route('/check-email-verification', methods=['POST'])
def check_email_verification():
    data = request.json
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required"}), 400

    try:
        # Recupera l'utente da Firebase usando l'email
        user = auth.get_user_by_email(email)

        # Controlla se l'email è verificata
        if user.email_verified:
            return jsonify({"message": "Email verified"}), 200
        else:
            return jsonify({"error": "La tua email non è stata verificata. Verifica la tua email prima di accedere."}), 403
    except firebase_admin.auth.UserNotFoundError:
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        print("Errore durante la verifica dell'email:", str(e))
        return jsonify({"error": "Internal server error"}), 500


@app.route('/decrement-attempts', methods=['POST'])
def decrement_attempts():
    data = request.json
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Recupera il documento dell'utente da Firestore cercando per email
    user_query = db.collection('osteoarthritiis-db').where('email', '==', email).stream()

    user_data = None
    uid = None
    for user_doc in user_query:
        user_data = user_doc.to_dict()  # Se trovi l'utente, ottieni i suoi dati
        uid = user_doc.id  # Ottieni l'ID del documento

    if user_data is None:
        print("Non trovo nessun utente")
        return jsonify({"error": "User not found"}), 404

    # Decrementa i tentativi
    attempts_left = user_data.get('loginAttemptsLeft', 0)

    if attempts_left > 0:
        db.collection('osteoarthritiis-db').document(uid).update({
            'loginAttemptsLeft': attempts_left - 1
        })
        attempts_left -= 1  # Decrementa il valore per la risposta

    return jsonify({"message": "Attempts decremented", "loginAttemptsLeft": attempts_left}), 200


@app.route('/get-attempts-left', methods=['POST'])
def get_attempts_left():
    data = request.json
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Recupera il documento dell'utente da Firestore cercando per email
    user_query = db.collection('osteoarthritiis-db').where('email', '==', email).stream()

    user_data = None
    uid = None
    for user_doc in user_query:
        user_data = user_doc.to_dict()  # Se trovi l'utente, ottieni i suoi dati
        uid = user_doc.id  # Ottieni l'ID del documento

    if user_data is None:
        print("Non trovo nessun utente")
        return jsonify({"error": "User not found"}), 404

    attempts_left = user_data.get('loginAttemptsLeft', 0)

    return jsonify({"loginAttemptsLeft": attempts_left}), 200

@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    try:
        # Recupera tutti gli utenti con il ruolo 'doctor' dal database Firestore
        doctors_ref = db.collection('osteoarthritiis-db').where('role', '==', 'doctor').stream()
        
        doctors = []
        for doctor in doctors_ref:
            doctor_data = doctor.to_dict()
            doctors.append(doctor_data)

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

        # Restituisci la lista dei pazienti come risposta JSON
        return jsonify(patients), 200
    
    except Exception as e:
        print("Errore nel recupero dei dottori:", str(e))
        return jsonify({"error": str(e)}), 500



@app.route('/api/<doctor_id>/patients', methods=['GET'])
def get_patients_from_doctor(doctor_id):
    try:
        # Recupera tutti i pazienti associati al dottore corrente in Firestore
        patients_ref = db.collection('osteoarthritiis-db').where('DoctorRef', '==', doctor_id).stream()

        patients = []
        for patient in patients_ref:
            patient_data = patient.to_dict()
            user = auth.get_user(patient_data['userId'])
            if user.email_verified:
              patients.append(patient_data)

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
        # Recupera i dati dell'utente da Firebase
        user = auth.get_user(uid)

        # Controlla se l'email è già verificata
        if user.email_verified:
            return jsonify({"message": "Email già verificata!"}), 200

        # Imposta l'email come verificata
        auth.update_user(uid, email_verified=True)
        
        return jsonify({"message": "Email verificata con successo!"}), 200
    except auth.UserNotFoundError:
        return jsonify({"error": "Utente non trovato"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/send-reset-email', methods=['POST'])
def send_reset_email():
    try:
        # Recupera l'email dal corpo della richiesta
        data = request.json
        email = data.get('email')

        if not email:
            return jsonify({"error": "L'email è obbligatoria"}), 400

        # Recupera l'UID dell'utente dall'email
        user = auth.get_user_by_email(email)

        verification_link = f"http://localhost:8080/reset-password/{user.uid}"
        # Invia l'email di verifica
        subject = "Resetta la tua password"
        message = f"Per favore, resetta la tua password cliccando il seguente link: {verification_link}"
        send_email(email, subject, message)

        print("uid letto + " + user.uid)

        return jsonify({"message": "Email di reset inviata con successo"}), 200

    except Exception as e:
        print("Errore durante l'invio del link di reset:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/reset-password', methods=['POST'])
def reset_password():
    try:
        # Ottieni i dati dalla richiesta
        data = request.json
        uid = data.get('uid')
        new_password = data.get('password')

        # Validazione input
        if not uid or not new_password:
            return jsonify({"error": "UID e password sono obbligatori."}), 400

        # Aggiorna la password dell'utente
        try:
            auth.update_user(uid, password=new_password)
        except Exception as e:
            return jsonify({"error": f"Errore durante l'aggiornamento della password: {str(e)}"}), 500


        try:
            db.collection('osteoarthritiis-db').document(uid).update({
                'loginAttemptsLeft': 6
            })
        except Exception as e:
            return jsonify({"error": f"Errore durante l'aggiornamento dei tentativi di login: {str(e)}"}), 500


        return jsonify({"message": "Password aggiornata con successo."}), 200

    except firebase_admin.exceptions.FirebaseError as e:
        # Gestione errori Firebase
        return jsonify({"error": f"Errore Firebase: {str(e)}"}), 500

    except Exception as e:
        # Gestione errori generici
        return jsonify({"error": f"Errore: {str(e)}"}), 500


@app.route('/patients/<string:patient_id>/radiographs', methods=['GET'])
def get_user_radiographs(patient_id):
    try:
        # Recupera le radiografie per il paziente specificato
        radiographs_ref = db.collection('radiographs').where('patientId', '==', patient_id).stream()

        radiographs = []
        for radiograph in radiographs_ref:
            radiographs.append(radiograph.to_dict())

        return jsonify(radiographs), 200
    
    except Exception as e:
        print("Errore nel recupero delle radiografie:", str(e))
        return jsonify({"error": str(e)}), 500
    

def get_gcs_bucket():
    """Ottiene il bucket di Google Cloud Storage."""
    storage_client = storage.Client()
    bucket_name = 'osteoarthritis-radiographs-archive'
    print(f"Connessione al bucket: {bucket_name}")
    return storage_client.bucket(bucket_name)


@app.route('/api/patients/<patient_id>/radiographs', methods=['GET'])
def get_patient_radiographs(patient_id):
    try:        
        # Ottieni il bucket
        bucket = get_gcs_bucket()

        # Elenco di radiografie associate all'ID del paziente
        prefix = f"{patient_id}/"
        
        blobs = list(bucket.list_blobs(prefix=prefix))

        # Crea una lista di URL delle radiografie che rispettano il formato
        radiographs = []
        
        for blob in blobs:
            # Filtra solo i file con nome 'original_imageX.png'
            if 'original_image' in blob.name and blob.name.endswith('.png'):
                try:
                    # Verifica che l'URL pubblico sia accessibile prima di aggiungerlo alla lista
                    response = requests.head(blob.public_url)
                    
                    if response.status_code == 200:
                        radiographs.append({
                            "url": blob.public_url,
                            "name": blob.name,
                            "date": blob.time_created.strftime("%Y-%m-%d")
                        })
                    else:
                        print(f"File non accessibile (HTTP {response.status_code}): {blob.name}")
                except Exception as e:
                    print(f"[ERROR] Errore di accesso per il blob {blob.name}: {e}")
            else:
                print(f"Blob ignorato: {blob.name}")

        # Restituisci l'elenco filtrato delle radiografie come JSON
        return jsonify(radiographs), 200

    except Exception as e:
        print(f"[ERROR] Errore durante il recupero delle radiografie: {str(e)}")
        return jsonify({"error": str(e)}), 500





@app.route('/api/download-radiograph', methods=['GET'])
def download_radiograph():
    try:
        # Recupera l'URL del file dai parametri della richiesta
        file_url = request.args.get('url')
        filename = request.args.get('filename', 'radiograph.png')

        if not file_url:
            return jsonify({"error": "File URL is missing"}), 400

        # Scarica il file dall'URL pubblico di Google Cloud Storage
        response = requests.get(file_url)

        if response.status_code != 200:
            return jsonify({"error": "Failed to fetch radiograph"}), 500

        # Leggi il file e prepara il buffer per l'invio
        file_stream = io.BytesIO(response.content)

        # Invia il file al client con il nome specificato
        return send_file(
            file_stream,
            mimetype='image/png',  # Imposta il MIME type corretto per PNG
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        print(f"Errore durante il download della radiografia: {str(e)}")
        return jsonify({"error": str(e)}), 500


def make_gradcam_heatmap(img_array, model, last_conv_layer_name, pred_index=None):
    resnet_model = model.get_layer('resnet50')
    last_conv_layer = resnet_model.get_layer(last_conv_layer_name)
    last_conv_layer_model = tf.keras.models.Model(resnet_model.input, last_conv_layer.output)
    classifier_input = tf.keras.layers.Input(shape=last_conv_layer.output.shape[1:])
    x = classifier_input
    for layer in model.layers[1:]:
        x = layer(x)
    classifier_model = tf.keras.models.Model(classifier_input, x)

    with tf.GradientTape() as tape:
        last_conv_layer_output = last_conv_layer_model(img_array)
        tape.watch(last_conv_layer_output)
        preds = classifier_model(last_conv_layer_output)
        if pred_index is None:
            pred_index = tf.argmax(preds[0])
        class_channel = preds[:, pred_index]

    grads = tape.gradient(class_channel, last_conv_layer_output)
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))
    last_conv_layer_output = last_conv_layer_output[0]
    heatmap = last_conv_layer_output @ pooled_grads[..., tf.newaxis]
    heatmap = tf.squeeze(heatmap)
    heatmap = tf.maximum(heatmap, 0) / tf.math.reduce_max(heatmap)
    return heatmap.numpy()

def preprocess_image(file):
    img = cv2.imdecode(np.frombuffer(file.read(), np.uint8), cv2.IMREAD_GRAYSCALE)
    equalized_img = cv2.equalizeHist(img)
    img_rgb = cv2.cvtColor(equalized_img, cv2.COLOR_GRAY2RGB)
    img_array = tf.keras.utils.img_to_array(img_rgb)
    img_array = np.expand_dims(img_array, axis=0)
    img_array = tf.keras.applications.resnet50.preprocess_input(img_array)
    return img_array, img_rgb

def predict_class(img_array, model):
    predictions = model.predict(img_array)
    predicted_class = np.argmax(predictions[0])
    confidence = float(np.max(predictions[0]))
    return predicted_class, confidence


def generate_gradcam(img_array, model, predicted_class, img_rgb):
    heatmap = make_gradcam_heatmap(img_array, model, "conv5_block3_out", pred_index=predicted_class)
    heatmap = np.uint8(255 * heatmap)  # Normalizza la heatmap
    heatmap = cv2.resize(heatmap, (img_rgb.shape[1], img_rgb.shape[0]))  # Ridimensiona
    heatmap = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)  # Applica una mappa di colore
    superimposed_img = cv2.addWeighted(img_rgb, 0.6, heatmap, 0.4, 0)  # Sovrapponi la heatmap
    return superimposed_img


def save_gradcam_image(superimposed_img, user_uid):
    gradcam_file = io.BytesIO()
    _, buffer = cv2.imencode('.png', superimposed_img)
    gradcam_file.write(buffer)
    gradcam_file.seek(0)

    return gradcam_file


def upload_file_to_gcs(file, path, name, content_type=None):
    """Funzione per caricare file su Google Cloud Storage."""

    # Ottieni il bucket
    bucket = get_gcs_bucket()
    blob = bucket.blob(f"{path}/{name}")

    # Carica il file
    blob.upload_from_file(file, content_type=content_type, rewind=True)

    # Restituisci l'URL pubblico del file
    blob.make_public()
    return blob.public_url


@app.route('/upload-to-dataset', methods=['POST'])
def upload_to_dataset():
    try:
        # Ottieni i dati dal form
        file = request.files['file']
        patient_id = request.form.get('patientID')
        side = request.form.get('side', 'Unknown')  # Default: Unknown side

        # Imposta il nome del file
        file_name = f"{patient_id}_{side}_{file.filename}"

        # Carica il file nella cartella 'dataset'
        upload_file_to_gcs(file, "dataset", file_name, file.content_type)

        return {"message": "File caricato con successo."}, 200

    except Exception as e:
        print(f"Errore durante il caricamento del file: {e}")
        return {"error": str(e)}, 500


def get_image_url(user_uid, folder_name, image_name):
    """Restituisce l'URL di un'immagine nel bucket Google Cloud Storage."""
    # Path dell'immagine
    path = f"{user_uid}/{folder_name}/{image_name}"

    # Ottieni il bucket
    bucket = get_gcs_bucket()
    blob = bucket.blob(path)

    # Verifica se il blob esiste prima di renderlo pubblico
    if blob.exists():
        blob.make_public()
        return blob.public_url
    else:
        print(f"Debug: Immagine {path} non trovata.")
        return None


from concurrent.futures import ThreadPoolExecutor

def process_folder(bucket, user_uid, folder_name, folder_index):
    """
    Processa una singola cartella nel bucket e restituisce i dati della radiografia.
    """
    try:
        original_url = get_image_url(user_uid, folder_name, f"original_image{folder_index}.png")
        gradcam_url = get_image_url(user_uid, folder_name, f"gradcam_image{folder_index}.png")
        info_txt = get_image_url(user_uid, folder_name, f"info.txt")
        radiography_id = read_radiograph_id_from_info(f"{user_uid}/{folder_name}/info.txt")

        return {
            'original_image': original_url,
            'gradcam_image': gradcam_url,
            'info_txt': info_txt,
            'radiography_id': radiography_id,
        }
    except Exception as e:
        print(f"Errore durante l'elaborazione della cartella {folder_name}: {str(e)}")
        return None


@app.route('/get_radiographs/<user_uid>', methods=['GET'])
def get_radiographs(user_uid):
    try:
        bucket = get_gcs_bucket()
        num_folders, folders = count_existing_folders(user_uid, return_folders=True)

        if num_folders == 0:
            return jsonify([])

        # Parallelizza il caricamento dei dati delle cartelle
        with ThreadPoolExecutor() as executor:
            radiographs = list(executor.map(
                lambda folder: process_folder(bucket, user_uid, folder.split('/')[-1], int(folder.split('/')[-1].replace('Radiografia', ''))),
                folders
            ))

        return jsonify(radiographs)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    
@app.route('/get_radiographs_info/<user_uid>/<idx>', methods=['GET'])
def get_radiographs_info(user_uid, idx):
    bucket = get_gcs_bucket()
    path = "" + str(user_uid) + "/Radiografia" + str(idx) + "/info.txt"
    info_blob = bucket.blob(path)
    info_content = info_blob.download_as_text()

    radiographyInfo = {
        "name": "",
        "surname": "",
        "birthdate": "",
        "tax_code": "",
        "address": "",
        "cap_code": "",
        "gender": "",
        "userId": "",
        "radiography_id": "",
        "date": "",
        "prediction": "",
        "side": "",
        "confidence": "",
        "doctorLoaded": "",
        "doctorUid": "",
        "doctorID": "",
    }

    for line in info_content.splitlines():
        if line.startswith("UID paziente:"):
            radiographyInfo["userId"] = line.split(": ", 1)[1].strip()
        elif line.startswith("Nome paziente:"):
            radiographyInfo["name"] = line.split(": ", 1)[1].strip()
        elif line.startswith("Cognome paziente:"):
            radiographyInfo["surname"] = line.split(": ", 1)[1].strip()
        elif line.startswith("Data di nascita paziente:"):
            radiographyInfo["birthdate"] = line.split(": ", 1)[1].strip()
        elif line.startswith("Codice fiscale paziente:"):
            radiographyInfo["tax_code"] = line.split(": ", 1)[1].strip()
        elif line.startswith("Indirizzo paziente:"):
            radiographyInfo["address"] = line.split(": ", 1)[1].strip()
        elif line.startswith("CAP paziente:"):
            radiographyInfo["cap_code"] = line.split(": ", 1)[1].strip()
        elif line.startswith("Genere paziente:"):
            radiographyInfo["gender"] = line.split(": ", 1)[1].strip()
        elif line.startswith("ID radiografia:"):
            radiographyInfo["radiography_id"] = line.split(": ", 1)[1].strip()            
        elif line.startswith("Data di caricamento:"):
            radiographyInfo["date"] = line.split(": ", 1)[1].strip()
        elif line.startswith("Classe predetta:"):
            radiographyInfo["prediction"] = line.split(": ", 1)[1].strip()
        elif line.startswith("Lato del ginocchio:"):
            radiographyInfo["side"] = line.split(": ", 1)[1].strip()
        elif line.startswith("Confidenza:"):
            radiographyInfo["confidence"] = line.split(": ", 1)[1].strip()
        elif line.startswith("Radiografia caricata da:"):
            radiographyInfo["doctorLoaded"] = line.split(": ", 1)[1].strip()
        elif line.startswith("UID dottore:"):
            radiographyInfo["doctorUid"] = line.split(": ", 1)[1].strip()
        elif line.startswith("Codice identificativo dottore:"):
            radiographyInfo["doctorID"] = line.split(": ", 1)[1].strip()

    return jsonify(radiographyInfo)
    
def read_radiograph_id_from_info(file_path):
    """Legge l'ID della radiografia dal file info.txt all'interno del bucket di Google Cloud Storage."""
    bucket = get_gcs_bucket()  # Ottiene il bucket
    info_blob = bucket.blob(file_path)
    info_content = info_blob.download_as_text()
    
    # Trova la riga con l'ID della radiografia
    radiograph_id = None
    for line in info_content.splitlines():
        if line.startswith("ID radiografia:"):
            radiograph_id = line.split(":")[1].strip()
            break
    
    return radiograph_id


def count_existing_folders(user_uid, return_folders=False):
    """
    Conta il numero di cartelle per un dato UID utente e, opzionalmente, restituisce l'elenco delle cartelle.
    """
    bucket = get_gcs_bucket()
    all_blobs = bucket.list_blobs(prefix=f"{user_uid}/")

    found_folders = set()

    for blob in all_blobs:
        folder_name = '/'.join(blob.name.split('/')[:-1])
        if folder_name:  # Ignora i blob senza una struttura di cartelle
            found_folders.add(folder_name)

    if return_folders:
        # Ordina le cartelle per numero crescente
        sorted_folders = sorted(found_folders, key=lambda x: int(x.split('/')[-1].replace('Radiografia', '')))
        return len(sorted_folders), sorted_folders

    return len(found_folders)


from datetime import datetime
import json
import uuid

@app.route('/predict', methods=['POST'])
def predict():
    if 'file' not in request.files:
        print("Debug: Nessun file trovato nella richiesta.")
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    doctor_data = request.form.get('userData')
    patient_uid = request.form.get('selectedPatientID')
    knee_side = request.form.get('selectedSide')

    try:
        doctor_data_dict = json.loads(doctor_data)
    except json.JSONDecodeError:
        print("Debug: Errore nella decodifica di doctor_data.")
        return jsonify({'error': 'Invalid user data'}), 400

    try:
        # Conta le radiografie esistenti
        num_folder = count_existing_folders(patient_uid)

        # Pre-processa e carica l'immagine originale
        img_array, img_rgb = preprocess_image(file)
        original_image_url = upload_file_to_gcs(
            file, f"{patient_uid}/Radiografia{num_folder + 1}", f"original_image{num_folder + 1}.png"
        )

        # Predici la classe
        predicted_class, confidence = predict_class(img_array, model)
        #print(f"Debug: Classe predetta - {predicted_class}, Confidenza: {confidence}")

        # Genera l'immagine Grad-CAM
        superimposed_img = generate_gradcam(img_array, model, predicted_class, img_rgb)
        gradcam_file = save_gradcam_image(superimposed_img, patient_uid)
        gradcam_image_url = upload_file_to_gcs(
            gradcam_file, f"{patient_uid}/Radiografia{num_folder + 1}", f"gradcam_image{num_folder + 1}.png"
        )

        # Definisce l'etichetta della classe
        class_labels = {
            0: 'Classe 1: Normale',
            1: 'Classe 2: Lieve osteoartrite',
            2: 'Classe 3: Moderata osteoartrite',
            3: 'Classe 4: Grave osteoartrite',
            4: 'Classe 5: Avanzata osteoartrite'
        }
        predicted_label = class_labels.get(predicted_class, 'Unknown class')

        radiograph_id = str(uuid.uuid4())

        name, surname, birthdate, tax_code, address, cap_code, gender = get_patient_information(patient_uid)

        # Crea il contenuto del file di testo
        info_content = (
            f"UID paziente: {patient_uid}\n"
            f"Nome paziente: {name}\n"
            f"Cognome paziente: {surname}\n"
            f"Data di nascita paziente: {birthdate}\n"
            f"Codice fiscale paziente: {tax_code}\n"
            f"Indirizzo paziente: {address}\n"
            f"CAP paziente: {cap_code}\n"
            f"Genere paziente: {gender}\n"
            f"ID radiografia: {radiograph_id}\n"
            f"Data di caricamento: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Classe predetta: {predicted_label}\n"
            f"Lato del ginocchio: {knee_side}\n"
            f"Confidenza: {confidence:.2f}\n"
            f"Radiografia caricata da: {doctor_data_dict['name']} {doctor_data_dict['family_name']}\n"
            f"UID dottore: {doctor_data_dict['uid']}\n"
            f"Codice identificativo dottore: {doctor_data_dict['doctorID']}\n"
        )

        info_file = io.BytesIO(info_content.encode('utf-8'))

        # Carica il "file" di testo su Google Cloud Storage
        info_file_url = upload_file_to_gcs(
            info_file,
            f"{patient_uid}/Radiografia{num_folder + 1}",
            "info.txt",
            content_type="text/plain"
        )

        return jsonify({
            'predicted_class': predicted_label,
            'confidence': confidence,
            'original_image': original_image_url,
            'gradcam_image': gradcam_image_url,
            'info_file': info_file_url
        })

    except Exception as e:
        print(f"Debug: Errore durante la predizione - {str(e)}")
        return jsonify({'error': str(e)}), 500

def get_patient_information(uid):
    try:
        # Recupera il documento del paziente dal database Firestore
        patient_ref = db.collection('osteoarthritiis-db').document(uid)
        patient = patient_ref.get()

        if patient.exists:
            patient_data = patient.to_dict()
            
            # Estrai i dettagli del paziente
            name = patient_data.get("name", "")
            surname = patient_data.get("family_name", "")
            birthdate = patient_data.get("birthdate", "")
            tax_code = patient_data.get("tax_code", "")
            address = patient_data.get("address", "")
            cap_code = patient_data.get("cap_code", "")
            gender = patient_data.get("gender", "")
            
            return name, surname, birthdate, tax_code, address, cap_code, gender
        else:
            print(f"Nessun paziente trovato con UID: {uid}")
            return None  # Oppure una tupla di valori vuoti se preferisci

    except Exception as e:
        print("Errore nel recupero delle informazioni del paziente:", str(e))
        return None  # Oppure una tupla di valori vuoti in caso di errore


@app.route('/images/<path:image_name>', methods=['GET'])
def get_image(image_name):
    try:
        bucket = get_gcs_bucket()
        blob = bucket.blob(image_name)

        # Scarica il contenuto dell'immagine come bytes
        image_data = blob.download_as_bytes()

        # Crea un oggetto file in memoria per l'immagine
        image_stream = io.BytesIO(image_data)

        # Invia l'immagine come file di risposta
        return send_file(image_stream, mimetype='image/png')  # Specifica il mimetype corretto se diverso

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)