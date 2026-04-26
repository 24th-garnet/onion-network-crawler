FROM python:3.11-slim

WORKDIR /work

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /work/requirements.txt
RUN pip install --no-cache-dir -r /work/requirements.txt

COPY src /work/src
COPY config /work/config

ENV PYTHONPATH=/work

CMD ["python", "-m", "src.main", "--help"]