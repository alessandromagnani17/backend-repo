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
            "role": data['role']  # Aggiungi il ruolo (dottore o paziente)
        }

        # Se l'utente è un dottore, aggiungi anche il doctorID
        if data['role'] == 'doctor':
            user_data['doctorID'] = data['doctorID']

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
    '''data = request.json
    if 'email' not in data or 'password' not in data:
        return jsonify({"error": "Email and password are required"}), 400

    try:
        # Initiate Cognito login
        response = cognito_client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': data['email'],
                'PASSWORD': data['password']
            }
        )

                # Decodifica il token ID per ottenere lo 'sub' (userId)
        id_token = response['AuthenticationResult']['IdToken']
        user_info = jwt.decode(id_token, options={"verify_signature": False})
        user_id = user_info['sub']  # Questo è il Cognito userId


        # Estrai le altre informazioni dall'IdToken
        data = {
            'email': user_info.get('email'),
            'nome': user_info.get('name'),
            'cognome': user_info.get('family_name'),
            'data': user_info.get('birthdate'),
            'telefono': user_info.get('phone_number'),
            'gender': user_info.get('gender'),
            'address': user_info.get('address'),
            'cap_code': user_info.get('custom:CAP_code'),
            'tax_code': user_info.get('custom:Tax_code')
        }

        # Salva l'utente in DynamoDB con 'userId' come chiave primaria
        save_user_to_dynamodb(user_id, data)

        # Successful login
        if 'AuthenticationResult' in response:
            # Return the IdToken along with other tokens
            return jsonify({
                "message": "Login successful",
                "id_token": response['AuthenticationResult']['IdToken'],
                "access_token": response['AuthenticationResult']['AccessToken'],  # Optionally include the AccessToken
                "refresh_token": response['AuthenticationResult']['RefreshToken']  # Optionally include the RefreshToken
            }), 200

        return jsonify({"error": "Authentication failed. Please check your credentials."}), 400

    except cognito_client.exceptions.NotAuthorizedException:
        return jsonify({"error": "Invalid credentials"}), 401

    except ClientError as e:
        print("Errore nel login:", str(e))
        return jsonify({"error": str(e)}, 400)


def save_user_to_dynamodb(user_id, user_data):
    item = {
        'UserId': user_id,  # Usando lo 'userId' come chiave primaria
        'email': user_data['email'],  # Email
        'name': user_data['nome'],  # Nome
        'family_name': user_data['cognome'],  # Cognome
        'birthdate': user_data['data'],  # Data di nascita (YYYY-MM-DD)
        'phone_number': user_data['telefono'],  # Numero di telefono in formato internazionale
        'gender': user_data['gender'],  # Genere
        'address': user_data['address'],  # Indirizzo
        'custom:CAP_code': str(user_data['cap_code']),  # Codice CAP personalizzato
        'custom:Tax_code': user_data['tax_code']  # Codice fiscale personalizzato
    }
    table.put_item(Item=item)'''

'''
# Endpoint per ottenere i pazienti associati a un dottore
@app.route('/doctors/<doctor_id>/patients', methods=['GET'])
def get_patients(doctor_id):
    # Qui dovresti recuperare i pazienti associati a doctor_id da DynamoDB
    # Supponiamo di avere una funzione che lo fa:
    patients = fetch_patients_by_doctor(doctor_id)  # Funzione da implementare
    return jsonify(patients), 200

# Funzione per recuperare pazienti da DynamoDB (da implementare)
def fetch_patients_by_doctor(doctor_id):
    # Implementa la logica per interagire con DynamoDB e ottenere i pazienti
    pass

# Endpoint per caricare una radiografia
@app.route('/patients/<patient_id>/radiographs', methods=['POST'])
def upload_radiograph(patient_id):
    if 'file' not in request.files:
        return jsonify({"error": "File is required"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Carica il file su S3
    s3_key = f'radiographs/{patient_id}/{file.filename}'
    try:
        s3_client.upload_fileobj(file, S3_BUCKET, s3_key)
    except ClientError as e:
        return jsonify({"error": str(e)}), 500

    # Qui dovresti anche salvare l'URL della radiografia in DynamoDB
    # Supponiamo di avere una funzione che lo fa:
    save_radiograph_to_dynamodb(patient_id, s3_key)  # Funzione da implementare

    return jsonify({"message": "Radiograph uploaded successfully", "url": s3_key}), 200

# Funzione per salvare la radiografia in DynamoDB (da implementare)
def save_radiograph_to_dynamodb(patient_id, s3_key):
    # Implementa la logica per interagire con DynamoDB e salvare l'URL della radiografia
    pass

# Endpoint per ottenere le radiografie di un paziente
@app.route('/patients/<patient_id>/radiographs', methods=['GET'])
def get_radiographs(patient_id):
    # Qui dovresti recuperare le radiografie associate a patient_id da DynamoDB
    radiographs = fetch_radiographs_by_patient(patient_id)  # Funzione da implementare
    return jsonify(radiographs), 200

# Funzione per recuperare le radiografie da DynamoDB (da implementare)
def fetch_radiographs_by_patient(patient_id):
    # Implementa la logica per interagire con DynamoDB e ottenere le radiografie
    pass
'''


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:8080') 
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)