FROM node:22-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python3 -m pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 8080
CMD ["uvicorn", "control_plane:app", "--host", "0.0.0.0", "--port", "8080"]
