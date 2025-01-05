from firebase_admin import firestore, auth
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

class FirestoreManager:
    def __init__(self, db: firestore.Client):
        self.db = db


    # Funzioni generiche CRUD
    def create_document(self, collection: str, data: Dict, doc_id: Optional[str] = None) -> Tuple[str, Dict]:
        """
        Crea un nuovo documento in una collezione specificata.

        Args:
            collection: Nome della collezione Firestore.
            data: Dizionario contenente i dati del documento.
            doc_id: (Opzionale) ID specifico del documento.

        Returns:
            Tuple[str, Dict]: ID del documento creato e i dati associati.
        """
        if doc_id:
            doc_ref = self.db.collection(collection).document(doc_id)
            doc_ref.set(data)
        else:
            doc_ref = self.db.collection(collection).add(data)
            doc_id = doc_ref[1].id
        
        return doc_id, data


    def get_document(self, collection: str, doc_id: str) -> Optional[Dict]:
        """
        Recupera un documento specifico da una collezione.

        Args:
            collection: Nome della collezione Firestore.
            doc_id: ID del documento.

        Returns:
            Optional[Dict]: Dizionario con i dati del documento, se esiste; altrimenti `None`.
        """
        doc_ref = self.db.collection(collection).document(doc_id)
        doc = doc_ref.get()
        
        return doc.to_dict() if doc.exists else None


    def update_document(self, collection: str, doc_id: str, data: Dict) -> bool:
        """
        Aggiorna un documento esistente.

        Args:
            collection: Nome della collezione Firestore.
            doc_id: ID del documento.
            data: Dizionario contenente i dati da aggiornare.

        Returns:
            bool: `True` se l'aggiornamento ha successo; altrimenti `False`.
        """
        try:
            self.db.collection(collection).document(doc_id).update(data)
            return True
        except Exception as e:
            print(f"Errore nell'aggiornamento del documento: {str(e)}")
            return False


    def query_documents(self, collection: str, conditions: List[Tuple]) -> List[Dict]:
        """
        Esegue una query con condizioni multiple.

        Args:
            collection: Nome della collezione Firestore.
            conditions: Lista di tuple (campo, operatore, valore) per filtrare i risultati.

        Returns:
            List[Dict]: Lista di dizionari rappresentanti i documenti che soddisfano le condizioni.
        """
        query = self.db.collection(collection)
        for field, op, value in conditions:
            query = query.where(field, op, value)
        
        results = []
        for doc in query.stream():
            doc_data = doc.to_dict()
            doc_data['id'] = doc.id
            results.append(doc_data)
        
        return results


    # Funzioni specifiche per gli utenti
    def create_user(self, auth_data: Dict, user_data: Dict) -> Tuple[str, Dict]:
        """
        Crea un nuovo utente sia in Authentication che in Firestore.

        Args:
            auth_data: Dizionario con i dati di autenticazione (email, password, ecc.).
            user_data: Dizionario con i dati dell'utente per Firestore.

        Returns:
            Tuple[str, Dict]: ID dell'utente creato e i dati salvati in Firestore.
        """
        try:
            # Crea l'utente in Firebase Authentication
            user = auth.create_user(
                email=auth_data['email'],
                password=auth_data['password'],
                display_name=auth_data.get('username'),
                disabled=False
            )

            # Prepara i dati comuni per Firestore
            firestore_data = {
                **user_data,
                "userId": user.uid,
                "loginAttemptsLeft": 6
            }

            # Salva i dati in Firestore
            return self.create_document('users', firestore_data, user.uid)
        
        except Exception as e:
            print(f"Errore nella creazione dell'utente: {str(e)}")
            raise


    def get_users_by_role(self, role: str) -> List[Dict]:
        """
        Recupera tutti gli utenti con un ruolo specifico.

        Args:
            role: Ruolo dell'utente (es. "doctor", "patient").

        Returns:
            List[Dict]: Lista di utenti con il ruolo specificato.
        """
        return self.query_documents('users', [('role', '==', role)])


    def get_doctor_patients(self, doctor_id: str) -> List[Dict]:
        """
        Recupera tutti i pazienti associati a un dottore specifico.

        Args:
            doctor_id: ID del dottore.

        Returns:
            List[Dict]: Lista di pazienti associati al dottore.
        """
        return self.query_documents('users', [
            ('role', '==', 'patient'),
            ('DoctorRef', '==', doctor_id)
        ])


    # Funzioni specifiche per le operazioni
    def create_operation(self, operation_data: Dict) -> Tuple[str, Dict]:
        """
        Crea una nuova operazione con validazione.

        Args:
            operation_data: Dizionario con i dati dell'operazione.

        Returns:
            Tuple[str, Dict]: ID dell'operazione creata e i dati associati.

        Raises:
            ValueError: Se la data dell'operazione è nel passato.
        """
        try:
            # Validazione della data
            operation_date = datetime.fromisoformat(operation_data['operationDate'])
            if operation_date < datetime.now():
                raise ValueError("La data deve essere futura")

            # Prepara i dati dell'operazione
            operation = {
                **operation_data,
                "notificationStatus": "pending",
                "createdAt": datetime.now().isoformat()
            }

            return self.create_document('operations', operation)

        except Exception as e:
            print(f"Errore nella creazione dell'operazione: {str(e)}")
            raise


    # Funzioni specifiche per le notifiche
    def create_notification(self, notification_data: Dict) -> Tuple[str, Dict]:
        """
        Crea una nuova notifica.

        Args:
            notification_data: Dizionario con i dati della notifica.

        Returns:
            Tuple[str, Dict]: ID della notifica creata e i dati associati.
        """
        notification = {
            **notification_data,
            "isRead": False
        }
        return self.create_document('notifications', notification)


    def get_user_notifications(self, user_id: str) -> List[Dict]:
        """
        Recupera tutte le notifiche di un utente.

        Args:
            user_id: ID dell'utente.

        Returns:
            List[Dict]: Lista di notifiche associate all'utente.
        """
        return self.query_documents('notifications', [('patientId', '==', user_id)])


    def mark_notification_read(self, notification_id: str) -> bool:
        """
        Segna una notifica come letta.

        Args:
            notification_id: ID della notifica.

        Returns:
            bool: `True` se l'aggiornamento ha successo; altrimenti `False`.
        """
        return self.update_document('notifications', notification_id, {'isRead': True})


    # Funzioni per la gestione dei tentativi di login
    def update_login_attempts(self, user_id: str, reset: bool = False) -> bool:
        """
        Aggiorna i tentativi di login di un utente.

        Args:
            user_id: ID dell'utente.
            reset: (Opzionale) Se `True`, ripristina i tentativi a 6; altrimenti li decrementa.

        Returns:
            bool: `True` se l'aggiornamento ha successo; altrimenti `False`.
        """
        user_data = self.get_document('users', user_id)
        if not user_data:
            return False

        attempts = 6 if reset else max(0, user_data.get('loginAttemptsLeft', 0) - 1)
        return self.update_document('users', user_id, {'loginAttemptsLeft': attempts})


    def get_patient_information(self, uid: str) -> Dict[str, Any]:
        """
        Recupera le informazioni di un paziente.

        Args:
            uid: ID dell'utente (paziente).

        Returns:
            Dict[str, Any]: Dizionario con le informazioni principali del paziente (es. nome, data di nascita, ecc.).
        """     
        try:
            patient_data = self.get_document('users', uid)
            
            if patient_data:
                return {
                    "name": patient_data.get("name", ""),
                    "family_name": patient_data.get("family_name", ""),
                    "birthdate": patient_data.get("birthdate", ""),
                    "tax_code": patient_data.get("tax_code", ""),
                    "address": patient_data.get("address", ""),
                    "cap_code": patient_data.get("cap_code", ""),
                    "gender": patient_data.get("gender", "")
                }
            return {}
        except Exception as e:
            print(f"Errore nel recupero delle informazioni del paziente: {str(e)}")
            return {}
