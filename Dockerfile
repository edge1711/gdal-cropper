FROM ghcr.io/osgeo/gdal:ubuntu-full-latest

WORKDIR /app

RUN apt-get update && \
    apt-get install -y python3-pip python3-gdal python3-numpy python3-flask && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY . .

CMD ["python3", "./your-project/server.py"]