FROM python:3.9

# Aggiungi i pacchetti necessari per OpenCV
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Imposta la directory di lavoro
WORKDIR /osteoarthritis-project/backend/app

# Copia i file del progetto nella directory di lavoro
COPY . .

# Installa le dipendenze dal file requirements.txt
RUN pip install --no-cache-dir -r requirements-vm.txt

# Espone la porta 5000 per il server Flask
EXPOSE 5000

# Comando per avviare l'applicazione
CMD ["python", "./app.py"]
