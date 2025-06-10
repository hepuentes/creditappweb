# Usa una imagen oficial de Python
FROM python:3.11-slim

# Establece el directorio de trabajo
WORKDIR /app

# Copia todos los archivos al contenedor
COPY . .

# Instala las dependencias
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Exponer el puerto
EXPOSE 5000

# Comando para iniciar la aplicación con Gunicorn
CMD ["gunicorn", "--worker-class", "gevent", "--bind", "0.0.0.0:5000", "run:app"]
