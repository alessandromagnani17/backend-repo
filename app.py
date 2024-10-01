from flask import Flask, jsonify, request
from flask_cors import CORS  # Aggiungi questa importazione
from dotenv import load_dotenv
import os
import boto3
from botocore.exceptions import ClientError

load_dotenv()  # Carica variabili d'ambiente dal file .env

app = Flask(__name__)
CORS(app)  # Abilita CORS per tutte le rotte

# Configura i parametri di AWS Cognito
AWS_REGION = 'eu-north-1'  # Nome coerente per la regione AWS
USER_POOL_ID = 'eu-north-1_e5XGPIsEs'
CLIENT_ID = '2stplsf9hd8d3ks58jlrc2hfth'

cognito_client = boto3.client('cognito-idp', region_name=AWS_REGION)

@app.route('/')
def home():
    # Restituisci un dizionario con le informazioni
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
            Username=data['email'],
            Password=data['password'],
            UserAttributes=[{
                'Name': 'email',
                'Value': data['email']
            }]
        )
        return jsonify({"message": "User registered", "response": response}), 200
    except ClientError as e:
        return jsonify({"error": str(e)}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    try:
        response = cognito_client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': data['email'],
                'PASSWORD': data['password']
            }
        )
        return jsonify({"message": "Login successful", "id_token": response['AuthenticationResult']['IdToken']}), 200
    except ClientError as e:
        return jsonify({"error": str(e)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
