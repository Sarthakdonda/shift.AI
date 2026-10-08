FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-writer libreoffice-impress poppler-utils tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin tesseract-ocr-guj tesseract-ocr-spa tesseract-ocr-fra tesseract-ocr-deu tesseract-ocr-ara fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
COPY convert.py /opt/convert.py
USER 10001:10001
ENV HOME=/tmp PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["python", "/opt/convert.py"]
