FROM python:3.11-slim

WORKDIR /work

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    tor \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /work/requirements.txt
RUN pip install --no-cache-dir -r /work/requirements.txt

COPY src /work/src
COPY config /work/config
COPY data /work/data
COPY backend /work/backend
COPY scripts /work/scripts

ENV PYTHONPATH=/work

RUN chmod +x /work/scripts/start-render-api.sh

CMD ["/work/scripts/start-render-api.sh"]