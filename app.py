from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
import os
import boto3
from botocore.exceptions import ClientError

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configura i parametri di AWS Cognito
AWS_REGION = 'us-east-1'
USER_POOL_ID = 'us-east-1_2usqleEd6'
CLIENT_ID = '33qm0bgkrnilkc5lrkrh6hpkv'

cognito_client = boto3.client('cognito-idp', region_name=AWS_REGION)

@app.route('/')
def home():
    return jsonify({
        "AWS_REGION": AWS_REGION,
        "COGNITO_USER_POOL_ID": USER_POOL_ID
    })

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    try:
        response = cognito_client.sign_up(
            ClientId=CLIENT_ID,
            Username=data['username'],
            Password=data['password'],
            UserAttributes=[
                {'Name': 'email', 'Value': data['email']},
                {'Name': 'name', 'Value': data['nome']},
                {'Name': 'family_name', 'Value': data['cognome']},
                {'Name': 'birthdate', 'Value': data['data']},  # Formato YYYY-MM-DD
                {'Name': 'phone_number', 'Value': data['telefono']},  # Formato internazionale (+39 per l'Italia)
                {'Name': 'gender', 'Value': data['gender']},  # Aggiungi attributo gender
                {'Name': 'address', 'Value': data['address']},  # Aggiungi attributo address
                {'Name': 'custom:CAP_code', 'Value': data['cap_code']},  # Aggiungi attributo custom:CAP_code
                {'Name': 'custom:Tax_code', 'Value': data['tax_code']}  # Aggiungi attributo custom:Tax_code
            ]
        )
        return jsonify({"message": "User registered", "response": response}), 200
    except ClientError as e:
        return jsonify({"error": str(e)}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    
    # Controlla che le chiavi email e password siano presenti
    if 'email' not in data or 'password' not in data:
        return jsonify({"error": "Email and password are required"}), 400

    try:
        # Esegui il login con Cognito
        response = cognito_client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': data['email'],
                'PASSWORD': data['password']
            }
        )
        
        # Se il login è andato a buon fine, restituisci il token di autenticazione
        return jsonify({
            "message": "Login successful",
            "id_token": response['AuthenticationResult']['IdToken']
        }), 200

    except cognito_client.exceptions.NotAuthorizedException:
        # L'utente non è autorizzato (password errata o account bloccato)
        return jsonify({"error": "Invalid credentials"}), 401
    
    except cognito_client.exceptions.UserNotFoundException:
        # L'utente non è stato trovato
        return jsonify({"error": "User does not exist"}), 404
    
    except ClientError as e:
        # Cattura altri errori generici dal client Cognito
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
