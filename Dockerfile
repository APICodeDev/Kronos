FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/home/kronos/.cache/huggingface

WORKDIR /app

RUN useradd --create-home --uid 10001 kronos \
    && mkdir -p /app/data /app/webui/prediction_results "$HF_HOME" \
    && chown -R kronos:kronos /app /home/kronos

COPY webui/requirements.txt /tmp/requirements.txt

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu "torch>=2.1.0" \
    && python -m pip install --no-cache-dir -r /tmp/requirements.txt

COPY model/ /app/model/
COPY webui/app.py /app/webui/app.py
COPY webui/kraken_data.py /app/webui/kraken_data.py
COPY webui/templates/ /app/webui/templates/
COPY webui/static/ /app/webui/static/

RUN mkdir -p /app/webui/uploads && chown kronos:kronos /app/webui/uploads

USER kronos
WORKDIR /app/webui
EXPOSE 7070

CMD ["gunicorn", "--bind", "0.0.0.0:7070", "--workers", "1", "--threads", "4", "--timeout", "600", "app:app"]
