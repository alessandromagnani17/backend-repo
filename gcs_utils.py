from google.cloud import storage
from google.cloud.exceptions import NotFound
from typing import Optional, List, Dict, Union, BinaryIO
from datetime import datetime
import io
import cv2
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from tensorflow.keras.models import load_model
import h5py

@dataclass
class BlobInfo:
    """Classe di supporto per informazioni sui blob."""
    name: str
    url: Optional[str]
    created_at: datetime
    content_type: Optional[str]

class GCSManagerException(Exception):
    """Classe personalizzata per le eccezioni del GCS Manager."""
    pass

class GCSManager:
    """
    Gestore per le operazioni su Google Cloud Storage.
    Fornisce metodi per operazioni CRUD e funzionalità specifiche per il dominio.
    """

    def __init__(self, bucket_name: str):
        """
        Inizializza il gestore GCS.
        
        Args:
            bucket_name (str): Nome del bucket GCS
        
        Raises:
            GCSManagerException: Se la connessione al bucket fallisce
        """
        try:
            self.storage_client = storage.Client()
            self.bucket = self.storage_client.bucket(bucket_name)
            self.bucket_name = bucket_name
        except Exception as e:
            raise GCSManagerException(f"Errore di inizializzazione: {str(e)}")


    # Operazioni CRUD (Create, Read, Update, Delete) di Base
    def upload_file(self, 
                   file: Union[BinaryIO, io.BytesIO], 
                   destination_path: str, 
                   make_public: bool = False,
                   content_type: Optional[str] = None) -> str:
        """
        Carica un file sul bucket GCS.
        
        Args:
            file: File da caricare (file-like object)
            destination_path: Percorso di destinazione nel bucket
            make_public: Se rendere il file pubblicamente accessibile
            content_type: Tipo di contenuto del file
        
        Returns:
            str: URL pubblico del file se make_public=True, altrimenti path del blob
            
        Raises:
            GCSManagerException: Se il caricamento fallisce
        """
        try:
            blob = self.bucket.blob(destination_path)
            blob.upload_from_file(file, content_type=content_type, rewind=True)
            
            if make_public:
                blob.make_public()
                return blob.public_url
            return destination_path
        except Exception as e:
            raise GCSManagerException(f"Errore nel caricamento del file: {str(e)}")


    def download_file(self, source_path: str) -> io.BytesIO:
        """
        Scarica un file dal bucket GCS.
        
        Args:
            source_path: Percorso del file nel bucket
            
        Returns:
            io.BytesIO: Contenuto del file
            
        Raises:
            GCSManagerException: Se il download fallisce
        """
        try:
            blob = self.bucket.blob(source_path)
            file_obj = io.BytesIO()
            blob.download_to_file(file_obj)
            file_obj.seek(0)
            return file_obj
        except NotFound:
            raise GCSManagerException(f"File non trovato: {source_path}")
        except Exception as e:
            raise GCSManagerException(f"Errore nel download del file: {str(e)}")


    def delete_file(self, file_path: str) -> bool:
        """
        Elimina un file dal bucket GCS.
        
        Args:
            file_path: Percorso del file da eliminare
            
        Returns:
            bool: True se l'eliminazione è riuscita
            
        Raises:
            GCSManagerException: Se l'eliminazione fallisce
        """
        try:
            blob = self.bucket.blob(file_path)
            blob.delete()
            return True
        except Exception as e:
            raise GCSManagerException(f"Errore nell'eliminazione del file: {str(e)}")


    # Operazioni Specifiche per il Dominio
    def list_patient_radiographs(self, patient_id: str) -> List[BlobInfo]:
        """
        Elenca tutte le radiografie di un paziente.
        
        Args:
            patient_id: ID del paziente
            
        Returns:
            List[BlobInfo]: Lista di informazioni sui blob delle radiografie
        """
        try:
            prefix = f"{patient_id}/"
            blobs = list(self.bucket.list_blobs(prefix=prefix))
            
            radiographs = []
            for blob in blobs:
                if 'original_image' in blob.name and blob.name.endswith('.png'):
                    blob.make_public()
                    radiographs.append(BlobInfo(
                        name=blob.name,
                        url=blob.public_url,
                        created_at=blob.time_created,
                        content_type=blob.content_type
                    ))
            return radiographs
        except Exception as e:
            raise GCSManagerException(f"Errore nel recupero delle radiografie: {str(e)}")


    def get_radiograph_info(self, patient_id: str, radiograph_idx: int) -> Dict[str, str]:
        """
        Recupera le informazioni di una specifica radiografia.
        
        Args:
            patient_id: ID del paziente
            radiograph_idx: Indice della radiografia
            
        Returns:
            Dict[str, str]: Dizionario con le informazioni della radiografia
        """
        try:
            path = f"{patient_id}/Radiografia{radiograph_idx}/info.txt"
            blob = self.bucket.blob(path)
            info_content = blob.download_as_text()
            
            info_dict = {}
            for line in info_content.splitlines():
                if ':' in line:
                    key, value = line.split(':', 1)
                    info_dict[key.strip()] = value.strip()
            
            return info_dict
        except Exception as e:
            raise GCSManagerException(f"Errore nel recupero delle informazioni: {str(e)}")


    def save_radiograph(self, 
                       patient_id: str,
                       original_image: io.BytesIO,
                       gradcam_image: io.BytesIO,
                       info_content: str,
                       index: int) -> Dict[str, str]:
        """
        Salva una nuova radiografia con le relative informazioni.
        
        Args:
            patient_id: ID del paziente
            original_image: Immagine originale
            gradcam_image: Immagine Grad-CAM
            info_content: Contenuto del file info
            index: Indice della radiografia
            
        Returns:
            Dict[str, str]: URLs dei file caricati
        """
        try:
            base_path = f"{patient_id}/Radiografia{index}"
            
            # Carica l'immagine originale
            original_url = self.upload_file(
                original_image, 
                f"{base_path}/original_image{index}.png",
                make_public=True,
                content_type="image/png"
            )
            
            # Carica l'immagine Grad-CAM
            gradcam_url = self.upload_file(
                gradcam_image,
                f"{base_path}/gradcam_image{index}.png",
                make_public=True,
                content_type="image/png"
            )
            
            # Carica il file info
            info_file = io.BytesIO(info_content.encode('utf-8'))
            info_url = self.upload_file(
                info_file,
                f"{base_path}/info.txt",
                make_public=True,
                content_type="text/plain"
            )
            
            return {
                'original_image': original_url,
                'gradcam_image': gradcam_url,
                'info_file': info_url
            }
        except Exception as e:
            raise GCSManagerException(f"Errore nel salvataggio della radiografia: {str(e)}")


    def count_patient_radiographs(self, patient_id: str) -> int:
        """
        Conta il numero di radiografie per un paziente.
        
        Args:
            patient_id: ID del paziente
            
        Returns:
            int: Numero di radiografie
        """
        try:
            prefix = f"{patient_id}/"
            blobs = list(self.bucket.list_blobs(prefix=prefix))
            folders = set()
            
            for blob in blobs:
                folder_name = '/'.join(blob.name.split('/')[:-1])
                if folder_name:
                    folders.add(folder_name)
            
            print(" -- folders: ", folders)
            print(" -- lunghezza folder: ", len(folders))
            return len(folders)
        except Exception as e:
            raise GCSManagerException(f"Errore nel conteggio delle radiografie: {str(e)}")
        

    def load_model(self, model_path):
        """
        Carica un modello Keras da Google Cloud Storage.
        
        Args:
            model_path: Percorso del modello nel bucket (es. 'MODELLO/pesi.h5')
        Returns:
            Il modello Keras caricato
        """
        try:
            # Scarica i dati in memoria
            blob = self.bucket.blob(model_path)
            model_bytes = io.BytesIO()
            blob.download_to_file(model_bytes)
            model_bytes.seek(0)

            # Carica il modello direttamente dal buffer
            with h5py.File(model_bytes, 'r') as h5file:
                model = load_model(h5file)

            print("Modello caricato correttamente dalla memoria!")
            return model
            
        except Exception as e:
            raise GCSManagerException(f"Errore nel caricamento del modello: {str(e)}")
        

    def get_public_url(self, blob_path: str) -> Optional[str]:
        """
        Ottiene l'URL pubblico di un blob.

        Args:
            blob_path: Il percorso del blob nel bucket.

        Returns:
            Optional[str]: L'URL pubblico del blob, o None se il blob non esiste.

        Raises:
            GCSManagerException: Se si verifica un errore nel recupero dell'URL pubblico.
        """
        try:
            blob = self.bucket.blob(blob_path)
            if blob.exists():
                blob.make_public()
                return blob.public_url
            return None
        except Exception as e:
            raise GCSManagerException(f"Errore nel recupero dell'URL pubblico: {str(e)}")


    def save_gradcam_image(self, image_array: np.ndarray, destination_path: str) -> str:
        """
        Salva un'immagine Grad-CAM nel bucket.

        Args:
            image_array: Array numpy che rappresenta l'immagine Grad-CAM.
            destination_path: Percorso di destinazione del file nel bucket.

        Returns:
            str: URL pubblico dell'immagine salvata.

        Raises:
            GCSManagerException: Se si verifica un errore durante il salvataggio dell'immagine.
        """
        try:
            # Converti l'immagine in bytes
            gradcam_file = io.BytesIO()
            _, buffer = cv2.imencode('.png', image_array)
            gradcam_file.write(buffer)
            gradcam_file.seek(0)

            # Carica nel bucket
            return self.upload_file(
                gradcam_file,
                destination_path,
                make_public=True,
                content_type="image/png"
            )
        except Exception as e:
            raise GCSManagerException(f"Errore nel salvataggio dell'immagine Grad-CAM: {str(e)}")


    def process_radiograph_folder(self, patient_id: str, folder_index: int) -> Dict[str, str]:
        """
        Processa una cartella di radiografie e restituisce le informazioni necessarie.

        Args:
            patient_id: ID del paziente.
            folder_index: Indice della cartella delle radiografie.

        Returns:
            Dict[str, str]: Dizionario contenente:
                - 'original_image': URL pubblico dell'immagine originale.
                - 'gradcam_image': URL pubblico dell'immagine Grad-CAM.
                - 'info_txt': Valore di compatibilità, impostato a None.
                - 'radiography_id': ID della radiografia.

        Raises:
            GCSManagerException: Se si verifica un errore durante il processamento della cartella.
        """
        try:
            base_path = f"{patient_id}/Radiografia{folder_index}"
            
            original_url = self.get_public_url(f"{base_path}/original_image{folder_index}.png")
            gradcam_url = self.get_public_url(f"{base_path}/gradcam_image{folder_index}.png")
            info = self.get_radiograph_info(patient_id, folder_index)
            
            return {
                'original_image': original_url,
                'gradcam_image': gradcam_url,
                'info_txt': None,  # Mantenuto per compatibilità
                'radiography_id': info.get('ID radiografia', '')
            }
        except Exception as e:
            raise GCSManagerException(f"Errore nel processamento della cartella: {str(e)}")

    