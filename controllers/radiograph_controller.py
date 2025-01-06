from flask import jsonify, send_file
import json
import io
import requests
import uuid
from datetime import datetime
import cv2

class RadiographController:
    def __init__(self, managers):
        self.gcs_manager = managers['gcs']
        self.model_manager = managers['model']
        self.firestore_manager = managers['firestore']

    def get_patient_radiographs(self, patient_id):
        try:
            radiographs = self.gcs_manager.list_patient_radiographs(patient_id)
            response = [{
                "url": rad.url,
                "name": rad.name,
                "date": rad.created_at.strftime("%Y-%m-%d")
            } for rad in radiographs]
            return jsonify(response), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def download_radiograph(self, file_url, filename):
        try:
            if not file_url:
                return jsonify({"error": "File URL is missing"}), 400

            response = requests.get(file_url)
            if response.status_code != 200:
                return jsonify({"error": "Failed to fetch radiograph"}), 500

            file_stream = io.BytesIO(response.content)
            return send_file(
                file_stream,
                mimetype='image/png',
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def upload_to_dataset(self, file, form_data):
        try:
            patient_id = form_data.get('patientID')
            side = form_data.get('side', 'Unknown')
            file_name = f"{patient_id}_{side}_{file.filename}"
            
            url = self.gcs_manager.upload_file(
                file=file,
                destination_path=f"dataset/{file_name}",
                make_public=True,
                content_type=file.content_type
            )
            
            return jsonify({
                "message": "File caricato con successo.",
                "url": url
            }), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def get_radiographs(self, user_uid):
        try:
            num_radiographs = self.gcs_manager.count_patient_radiographs(user_uid)
            if num_radiographs == 0:
                return jsonify([])

            radiographs = []
            for i in range(1, num_radiographs + 1):
                try:
                    original_blob = self.gcs_manager.bucket.blob(
                        f"{user_uid}/Radiografia{i}/original_image{i}.png"
                    )
                    gradcam_blob = self.gcs_manager.bucket.blob(
                        f"{user_uid}/Radiografia{i}/gradcam_image{i}.png"
                    )
                    
                    if not original_blob.exists() or not gradcam_blob.exists():
                        continue

                    original_blob.make_public()
                    gradcam_blob.make_public()

                    info = self.gcs_manager.get_radiograph_info(user_uid, i)
                    radiographs.append({
                        'original_image': original_blob.public_url,
                        'gradcam_image': gradcam_blob.public_url,
                        'info_txt': None,
                        'radiograph_id': info.get('ID radiografia', '')
                    })
                except Exception:
                    continue

            return jsonify(radiographs)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def get_radiographs_info(self, user_uid, idx):
        try:
            info = self.gcs_manager.get_radiograph_info(user_uid, int(idx))
            
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
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        

    def predict(self, file, form_data):
        try:
            doctor_data = json.loads(form_data.get('userData'))
            patient_uid = form_data.get('selectedPatientID')
            knee_side = form_data.get('selectedSide')

            num_folder = self.gcs_manager.count_patient_radiographs(patient_uid)

            # Preprocessa e predici
            img_array, img_rgb = self.model_manager.preprocess_image(file)
            predicted_class, confidence = self.model_manager.predict_class(img_array)

            # Genera Grad-CAM
            superimposed_img = self.model_manager.generate_gradcam(img_array, predicted_class, img_rgb)
            
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

            patient_info = self.firestore_manager.get_patient_information(patient_uid)
            if not patient_info:
                return jsonify({'error': 'Unable to retrieve patient information'}), 400

            # Verifica campi necessari
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

            # Salva i file
            urls = self.gcs_manager.save_radiograph(
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

        except Exception as e:
            return jsonify({'error': str(e)}), 500