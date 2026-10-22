# face-service : IA legere de reconnaissance faciale (OpenCV Haar + LBPH).
# Image reproductible et hors-ligne : le detecteur Haar est embarque, aucun modele
# n'est telecharge au runtime.
FROM python:3.11-slim

WORKDIR /app

# libglib2.0-0 : dependance runtime d'opencv headless (pas de libs graphiques).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY haarcascade_frontalface_default.xml /app/haarcascade_frontalface_default.xml
COPY app/ /app/app/

ENV FACE_DATA_DIR=/data/faces
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
