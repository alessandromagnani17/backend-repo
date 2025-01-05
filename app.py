from flask import Flask, send_file, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
import firebase_admin
from firebase_admin import credentials, auth, firestore, messaging
from google.cloud import storage
from google.oauth2 import service_account 
import tensorflow as tf
import io
import requests
from io import BytesIO
from datetime import datetime
from utils.gcs_utils import GCSManagerException
from config.app_config import AppConfig
from factories.manager_factory import ManagerFactory
import cv2


load_dotenv()

# Set Google Cloud credentials environment variable
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = AppConfig.GCS_CRED_PATH

app = Flask(__name__)

# Configure CORS using AppConfig
CORS(app, resources={r"/*": {"origins": AppConfig.CORS_ORIGIN}})

# Initialize Firebase Admin
cred = credentials.Certificate(AppConfig.FIREBASE_CRED_PATH)
firebase_admin.initialize_app(cred)

# Initialize all managers using ManagerFactory
managers = ManagerFactory.create_managers(AppConfig)
firestore_manager = managers['firestore']
gcs_manager = managers['gcs']
model_manager = managers['model']
email_manager = managers['email']
    

@app.route('/')
def home():
    return jsonify({"message": "Welcome to the API!"})


@app.route('/register', methods=['POST'])
def register():
    data = request.json
    print("Dati ricevuti per la registrazione:", data)

    try:
        # Utilizzo del manager per creare l'utente
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

        # Aggiungi doctorID in base al ruolo
        if data['role'] == 'doctor':
            user_data['doctorID'] = data['doctorID']
        else:
            user_data['DoctorRef'] = data['doctorID']

        uid, created_user = firestore_manager.create_user(auth_data, user_data)

        # Genera il link di verifica
        verification_link = f"http://34.122.99.160:8080/verify-email/{uid}"
        subject = "Verifica il tuo indirizzo email"
        message = f"Per favore, verifica il tuo indirizzo email cliccando il seguente link: {verification_link}"
        email_manager.send_email(data['email'], subject, message)

        return jsonify({
            "message": "User registered successfully. Please check your email for the confirmation link.",
            "response": created_user
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
        decoded_token = auth.verify_id_token(data['idToken'])
        uid = decoded_token['uid']
        user = auth.get_user(uid)
        
        # Usa il manager per ottenere i dati dell'utente
        user_data = firestore_manager.get_document('users', uid)
        
        if not user_data:
            return jsonify({"error": "User data not found in Firestore"}), 404

        # Aggiungi attributi di autenticazione
        user_data['uid'] = user.uid
        user_data['email'] = user.email
        user_data['attemptsLeft'] = user_data.get('loginAttemptsLeft', 0)

        return jsonify({
            "message": "Login successful",
            "user": user_data
        }), 200

    except firebase_admin.auth.InvalidIdTokenError as e:
        return jsonify({"error": "Invalid ID token", "details": str(e)}), 401
    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


@app.route('/api/get_user/<user_id>', methods=['GET'])
def get_user(user_id):
    print(f"Richiesta utente con ID: {user_id}")
    
    user_data = firestore_manager.get_document('users', user_id)
    
    if user_data:
        return jsonify(user_data), 200
    else:
        print(f"Utente con ID {user_id} non trovato.")
        return jsonify({"error": "User not found"}), 404


@app.route('/update_user', methods=['PATCH'])
def update_user():
    data = request.json
    user_id = data.pop('userId')  # Rimuovi userId dai dati da aggiornare
    
    try:
        success = firestore_manager.update_document('users', user_id, data)
        if success:
            return jsonify({"message": "Dati aggiornati con successo!"}), 200
        return jsonify({"error": "Errore durante l'aggiornamento dei dati."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/decrement-attempts', methods=['POST'])
def decrement_attempts():
    data = request.json
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Usa il manager per trovare l'utente tramite email
    users = firestore_manager.query_documents('users', [('email', '==', email)])
    
    if not users:
        return jsonify({"error": "User not found"}), 404

    user_data = users[0]
    user_id = user_data['id']
    
    # Usa il manager per decrementare i tentativi
    success = firestore_manager.update_login_attempts(user_id, reset=False)
    
    if success:
        return jsonify({
            "message": "Attempts decremented",
            "loginAttemptsLeft": max(0, user_data.get('loginAttemptsLeft', 0) - 1)
        }), 200
    return jsonify({"error": "Failed to update attempts"}), 400


@app.route('/get-attempts-left', methods=['POST'])
def get_attempts_left():
    data = request.json
    email = data.get('email')

    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Usa il manager per trovare l'utente tramite email
    users = firestore_manager.query_documents('users', [('email', '==', email)])
    
    if not users:
        return jsonify({"error": "User not found"}), 404

    attempts_left = users[0].get('loginAttemptsLeft', 0)
    return jsonify({"loginAttemptsLeft": attempts_left}), 200


@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    try:
        doctors = firestore_manager.get_users_by_role('doctor')
        
        if not doctors:
            return jsonify({"message": "Nessun dottore trovato"}), 404

        return jsonify(doctors), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/patients', methods=['GET'])
def get_patients():
    try:
        patients = firestore_manager.get_users_by_role('patient')
        
        if not patients:
            return jsonify({"message": "Nessun paziente trovato"}), 404

        return jsonify(patients), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/<doctor_id>/patients', methods=['GET'])
def get_patients_from_doctor(doctor_id):
    try:
        patients = firestore_manager.get_doctor_patients(doctor_id)
        
        # Filtra i pazienti verificati
        verified_patients = []
        for patient in patients:
            user = auth.get_user(patient['userId'])
            if user.email_verified:
                verified_patients.append(patient)

        if not verified_patients:
            return jsonify({"message": "Nessun paziente trovato per il dottore selezionato"}), 404

        return jsonify(verified_patients), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/reset-password', methods=['POST'])
def reset_password():
    try:
        data = request.json
        uid = data.get('uid')
        new_password = data.get('password')

        if not uid or not new_password:
            return jsonify({"error": "UID e password sono obbligatori."}), 400

        # Aggiorna la password
        auth.update_user(uid, password=new_password)
        
        # Reset tentativi di login
        success = firestore_manager.update_login_attempts(uid, reset=True)
        
        if not success:
            return jsonify({"error": "Errore durante l'aggiornamento dei tentativi di login"}), 500

        return jsonify({"message": "Password aggiornata con successo."}), 200

    except Exception as e:
        return jsonify({"error": f"Errore: {str(e)}"}), 500


@app.route('/api/operations', methods=['POST'])
def add_operation():
    try:
        data = request.json
        print("Dati ricevuti:", data)
        
        operation_data = {
            "doctorId": data['doctorId'],
            "patientId": data['patientId'],
            "operationDate": data['operationDate'],
            "description": data.get('description', '')
        }

        _, created_operation = firestore_manager.create_operation(operation_data)

        return jsonify({
            "message": "Operazione pianificata",
            "operation": created_operation
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Errore interno del server"}), 500


@app.route('/api/patients/<patient_id>/operations', methods=['GET'])
def get_patient_operations(patient_id):
    try:
        operations = firestore_manager.query_documents(
            'operations',
            [('patientId', '==', patient_id)]
        )
        return jsonify(operations), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/notifications', methods=['POST'])
def send_notification():
    try:
        data = request.json
        notification_data = {
            'patientId': data['patientId'],
            'message': data['message'],
            'date': data['date'],
            'time': data['time'],
            'sentAt': data['sentAt']
        }

        _, created_notification = firestore_manager.create_notification(notification_data)
        return jsonify({"message": "Notifica inviata con successo"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    try:
        patient_id = request.args.get('patientId')
        
        if not patient_id:
            return jsonify({"error": "patientId è richiesto"}), 400
        
        notifications = firestore_manager.get_user_notifications(patient_id)
        return jsonify({"notifications": notifications}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/notifications/<notification_id>', methods=['PATCH'])
def mark_notification_as_read(notification_id):
    try:
        success = firestore_manager.mark_notification_read(notification_id)
        if success:
            return jsonify({"message": "Notifica segnata come letta"}), 200
        return jsonify({"error": "Notifica non trovata"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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

        try:
            # Recupera l'UID dell'utente dall'email
            user = auth.get_user_by_email(email)
        except Exception as e:
            # Gestione dell'errore quando l'utente non è trovato
            return jsonify({"error": "Errore durante l'invio del link di reset: User not found"}), 500

        verification_link = f"http://34.122.99.160:8080/reset-password/{user.uid}"
        # Invia l'email di verifica
        subject = "Resetta la tua password"
        message = f"Per favore, resetta la tua password cliccando il seguente link: {verification_link}"
        
        try:
            email_manager.send_email(email, subject, message)
        except Exception as e:
            # Gestione dell'errore durante l'invio dell'email
            return jsonify({"error": "Errore durante l'invio del link di reset: " + str(e)}), 500

        print("uid letto + " + user.uid)

        return jsonify({"message": "Email di reset inviata con successo"}), 200

    except Exception as e:
        # Gestione dell'errore generico
        return jsonify({"error": f"Errore durante l'invio del link di reset: {str(e)}"}), 500


@app.route('/api/patients/<patient_id>/radiographs', methods=['GET'])
def get_patient_radiographs(patient_id):
    """
    Endpoint per ottenere tutte le radiografie di un paziente.
    """
    try:
        radiographs = gcs_manager.list_patient_radiographs(patient_id)
        
        response = [{
            "url": rad.url,
            "name": rad.name,
            "date": rad.created_at.strftime("%Y-%m-%d")
        } for rad in radiographs]
        
        return jsonify(response), 200
    except GCSManagerException as e:
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
    """
    Genera una heatmap Grad-CAM per l'immagine data.
    """
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


@app.route('/upload-to-dataset', methods=['POST'])
def upload_to_dataset():
    """
    Endpoint per caricare un'immagine nel dataset.
    """
    try:
        file = request.files['file']
        patient_id = request.form.get('patientID')
        side = request.form.get('side', 'Unknown')
        
        file_name = f"{patient_id}_{side}_{file.filename}"
        
        url = gcs_manager.upload_file(
            file=file,
            destination_path=f"dataset/{file_name}",
            make_public=True,
            content_type=file.content_type
        )
        
        return jsonify({"message": "File caricato con successo.", "url": url}), 200
    except GCSManagerException as e:
        return jsonify({"error": str(e)}), 500


@app.route('/get_radiographs/<user_uid>', methods=['GET'])
def get_radiographs(user_uid):
    """
    Endpoint per ottenere tutte le radiografie di un utente.
    """
    try:
        print(" -- userID: ", user_uid)
        num_radiographs = gcs_manager.count_patient_radiographs(user_uid)
        print(" -- numero radiografie: ", num_radiographs)
        if num_radiographs == 0:
            return jsonify([])

        radiographs = []
        for i in range(1, num_radiographs + 1):
            try:
                # Genera URL pubblici per le immagini
                original_blob = gcs_manager.bucket.blob(f"{user_uid}/Radiografia{i}/original_image{i}.png")
                gradcam_blob = gcs_manager.bucket.blob(f"{user_uid}/Radiografia{i}/gradcam_image{i}.png")
                
                if not original_blob.exists() or not gradcam_blob.exists():
                    print(f" -- Radiografia {i} non trovata")
                    continue

                original_blob.make_public()
                gradcam_blob.make_public()

                original_url = original_blob.public_url
                gradcam_url = gradcam_blob.public_url

                # Recupera informazioni dalla radiografia
                info = gcs_manager.get_radiograph_info(user_uid, i)

                radiographs.append({
                    'original_image': original_url,
                    'gradcam_image': gradcam_url,
                    'info_txt': None,
                    'radiograph_id': info.get('ID radiografia', '')
                })
            except GCSManagerException as e:
                print(f"Errore per la radiografia {i}: {str(e)}")
                continue

        return jsonify(radiographs)
    except GCSManagerException as e:
        return jsonify({'error': str(e)}), 500


@app.route('/get_radiographs_info/<user_uid>/<idx>', methods=['GET'])
def get_radiographs_info(user_uid, idx):
    """
    Endpoint per ottenere le informazioni di una specifica radiografia.
    """
    try:
        info = gcs_manager.get_radiograph_info(user_uid, int(idx))
        
        radiograph_info = {
            "name": info.get('Nome paziente', ''),
            "surname": info.get('Cognome paziente', ''),
            "birthdate": info.get('Data di nascita paziente', ''),
            "tax_code": info.get('Codice fiscale paziente', ''),
            "address": info.get('Indirizzo paziente', ''),
            "cap_code": info.get('CAP paziente', ''),
            "gender": info.get('Genere paziente', ''),
            "userId": info.get('UID paziente', ''),
            "radiograph_id": info.get('ID radiografia', ''),
            "date": info.get('Data di caricamento', ''),
            "prediction": info.get('Classe predetta', ''),
            "side": info.get('Lato del ginocchio', ''),
            "confidence": info.get('Confidenza', ''),
            "doctorLoaded": info.get('Radiografia caricata da', ''),
            "doctorUid": info.get('UID dottore', ''),
            "doctorID": info.get('Codice identificativo dottore', '')
        }
        
        return jsonify(radiograph_info)
    except GCSManagerException as e:
        return jsonify({'error': str(e)}), 500
    
def read_radiograph_id_from_info(file_path):
    """Legge l'ID della radiografia dal file info.txt all'interno del bucket di Google Cloud Storage."""
    bucket = gcs_manager.bucket()  # Ottiene il bucket
    info_blob = bucket.blob(file_path)
    info_content = info_blob.download_as_text()
    
    # Trova la riga con l'ID della radiografia
    radiograph_id = None
    for line in info_content.splitlines():
        if line.startswith("ID radiografia:"):
            radiograph_id = line.split(":")[1].strip()
            break
    
    return radiograph_id



from datetime import datetime
import json
import uuid

@app.route('/predict', methods=['POST'])
def predict():
    """
    Endpoint per predire la classe di una radiografia e salvarla.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    try:
        doctor_data = json.loads(request.form.get('userData'))
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid user data'}), 400

    patient_uid = request.form.get('selectedPatientID')
    knee_side = request.form.get('selectedSide')

    try:
        num_folder = gcs_manager.count_patient_radiographs(patient_uid)

        # Preprocessa e predici
        img_array, img_rgb = model_manager.preprocess_image(file)
        predicted_class, confidence = model_manager.predict_class(img_array)

        # Genera Grad-CAM
        superimposed_img = model_manager.generate_gradcam(img_array, predicted_class, img_rgb)
        
        # Prepara i file per il caricamento
        gradcam_file = io.BytesIO()
        _, buffer = cv2.imencode('.png', superimposed_img)
        gradcam_file.write(buffer)
        gradcam_file.seek(0)

        # Prepara le informazioni
        class_labels = {
            0: 'Classe 1: Normale',
            1: 'Classe 2: Lieve osteoartrite',
            2: 'Classe 3: Moderata osteoartrite',
            3: 'Classe 4: Grave osteoartrite',
            4: 'Classe 5: Avanzata osteoartrite'
        }
        predicted_label = class_labels.get(predicted_class, 'Unknown class')
        radiograph_id = str(uuid.uuid4())

        patient_info = firestore_manager.get_patient_information(patient_uid)
        if not patient_info:
            return jsonify({'error': 'Unable to retrieve patient information'}), 400

        # Verifica che tutti i campi necessari siano presenti
        required_fields = ['name', 'family_name', 'birthdate', 'tax_code', 'address', 'cap_code', 'gender']
        missing_fields = [field for field in required_fields if not patient_info.get(field)]
        if missing_fields:
            return jsonify({'error': f'Missing patient information: {", ".join(missing_fields)}'}), 400
        
        info_content = (
            f"UID paziente: {patient_uid}\n"
            f"Nome paziente: {patient_info['name']}\n"  
            f"Cognome paziente: {patient_info['family_name']}\n"
            f"Data di nascita paziente: {patient_info['birthdate']}\n"
            f"Codice fiscale paziente: {patient_info['tax_code']}\n"
            f"Indirizzo paziente: {patient_info['address']}\n"
            f"CAP paziente: {patient_info['cap_code']}\n"
            f"Genere paziente: {patient_info['gender']}\n"
            f"ID radiografia: {radiograph_id}\n"
            f"Data di caricamento: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Classe predetta: {predicted_label}\n"
            f"Lato del ginocchio: {knee_side}\n"
            f"Confidenza: {confidence:.2f}\n"
            f"Radiografia caricata da: {doctor_data['name']} {doctor_data['family_name']}\n"
            f"UID dottore: {doctor_data['uid']}\n"
            f"Codice identificativo dottore: {doctor_data['doctorID']}\n"
        )

        # Salva tutti i file
        urls = gcs_manager.save_radiograph(
            patient_id=patient_uid,
            original_image=file,
            gradcam_image=gradcam_file,
            info_content=info_content,
            index=num_folder + 1
        )

        return jsonify({
            'predicted_class': predicted_label,
            'confidence': confidence,
            'original_image': urls['original_image'],
            'gradcam_image': urls['gradcam_image'],
            'info_file': urls['info_file']
        })

    except GCSManagerException as e:
        return jsonify({'error': str(e)}), 500



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
