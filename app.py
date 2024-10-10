from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
from dotenv import load_dotenv
import os
import boto3
from botocore.exceptions import ClientError
import qrcode
from io import BytesIO
import base64
import json

load_dotenv()

app = Flask(__name__)

# Configura CORS per permettere l'accesso da 'http://localhost:8080'
CORS(app, resources={r"/*": {"origins": "http://localhost:8080"}})

# Configura i parametri di AWS Cognito
AWS_REGION = 'us-east-1'
USER_POOL_ID = 'us-east-1_2usqleEd6'
CLIENT_ID = '33qm0bgkrnilkc5lrkrh6hpkv'
COGNITO_DOMAIN = 'https://osteoarthritis.auth.us-east-1.amazoncognito.com'

cognito_client = boto3.client('cognito-idp', region_name=AWS_REGION)

# Configura i parametri di AWS S3
S3_BUCKET = 'osteoarthritis-bucket'
s3_client = boto3.client('s3')

@app.route('/')
def home():
    return jsonify({
        "AWS_REGION": AWS_REGION,
        "COGNITO_USER_POOL_ID": USER_POOL_ID,
        "COGNITO_DOMAIN": COGNITO_DOMAIN
    })

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    print("Dati ricevuti per la registrazione:", data)  # Aggiunto per debug
    try:
        # Usa il 'username' personalizzato per il campo 'Username'
        response = cognito_client.sign_up(
            ClientId=CLIENT_ID,
            Username=data['username'],  # Il valore di 'email' sarà usato per identificare l'utente
            Password=data['password'],
            UserAttributes=[
                {'Name': 'email', 'Value': data['email']},  # Email come attributo per l'utente
                {'Name': 'name', 'Value': data['nome']},
                {'Name': 'family_name', 'Value': data['cognome']},
                {'Name': 'birthdate', 'Value': data['data']},  # Formato YYYY-MM-DD
                {'Name': 'phone_number', 'Value': data['telefono']},  # Formato internazionale (+39 per l'Italia)
                {'Name': 'gender', 'Value': data['gender']},  # Aggiungi attributo gender
                {'Name': 'address', 'Value': data['address']},  # Aggiungi attributo address
                {'Name': 'custom:CAP_code', 'Value': str(data['cap_code'])},  # Aggiungi attributo custom:CAP_code
                {'Name': 'custom:Tax_code', 'Value': data['tax_code']}  # Aggiungi attributo custom:Tax_code
            ]
        )
        print("Risposta della registrazione:", response)  # Aggiunto per debug
        
        # Step to trigger the email link via Cognito.
        return jsonify({
            "message": "User registered successfully. Please check your email for the confirmation link.",
            "response": response
        }), 200
    except ClientError as e:
        print("Errore nella registrazione:", str(e))  # Aggiunto per debug
        return jsonify({"error": str(e)}), 400


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

        # Successful login
        if 'AuthenticationResult' in response:
            # print("SUCCESSOOOOOOOOO --> " + repr(response))
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



@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:8080') 
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
