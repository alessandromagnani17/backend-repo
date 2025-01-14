from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

class EmailManager:
    def __init__(self, sender_email: str, sender_password: str):
        """
        Inizializza il gestore email con le credenziali del mittente.

        Args:
            sender_email: Indirizzo email del mittente.
            sender_password: Password applicativa dell'email del mittente.
        """
        self.sender_email = sender_email
        self.sender_password = sender_password


    def send_email(self, recipient_email: str, subject: str, msg: str) -> bool:
        """
        Invia un'email usando SMTP.

        Args:
            recipient_email: Indirizzo email del destinatario.
            subject: Oggetto dell'email.
            msg: Corpo del messaggio da inviare.

        Returns:
            bool: `True` se l'email è stata inviata con successo; altrimenti `False`.
        """
        message = MIMEMultipart()
        message["From"] = self.sender_email
        message["To"] = recipient_email
        message["Subject"] = subject
        message.attach(MIMEText(msg, "plain"))

        try:
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.set_debuglevel(1)
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, recipient_email, message.as_string())
            return True
        except Exception as e:
            print("Errore nell'invio dell'email:", e)
            return False