from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
from dotenv import load_dotenv
import os
import boto3
from botocore.exceptions import ClientError

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
    print("Dati ricevuti per il login:", data)  # Aggiunto per debug

    # Controlla che le chiavi email e password siano presenti
    if 'email' not in data or 'password' not in data:
        print("Errore: Email o password non forniti.")  # Aggiunto per debug
        return jsonify({"error": "Email and password are required"}), 400

    try:
        # Esegui il login con Cognito
        response = cognito_client.initiate_auth(
            ClientId=CLIENT_ID,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': data['email'],  # Usa email come username
                'PASSWORD': data['password']
            }
        )
        print("Risposta del login:", response)  # Aggiunto per debug

        # Se il login è andato a buon fine, restituisci il token di autenticazione
        return jsonify({
            "message": "Login successful",
            "id_token": response['AuthenticationResult']['IdToken']
        }), 200

    except cognito_client.exceptions.NotAuthorizedException:
        print("Errore: Credenziali non autorizzate.")  # Aggiunto per debug
        return jsonify({"error": "Invalid credentials"}), 401
    
    except cognito_client.exceptions.UserNotFoundException:
        print("Errore: Utente non trovato.")  # Aggiunto per debug
        return jsonify({"error": "User does not exist"}), 404

    except cognito_client.exceptions.UserNotConfirmedException:
        print("Errore: Utente non confermato.")  # Aggiunto per debug
        return jsonify({"error": "User is not confirmed. Please confirm your email."}), 400

    except ClientError as e:
        print("Errore generico del ClientError:", str(e))  # Aggiunto per debug
        return jsonify({"error": str(e)}), 400


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:8080')
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
