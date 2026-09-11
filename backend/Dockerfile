FROM python:3.13-slim
WORKDIR /workspace
COPY backend/requirements.lock /workspace/backend/requirements.lock
RUN pip install --no-cache-dir -r backend/requirements.lock
COPY backend /workspace/backend
COPY sample_data /workspace/sample_data
RUN useradd --create-home --uid 10001 railblox && chown -R railblox:railblox /workspace
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER railblox
WORKDIR /workspace/backend
# Render supplies PORT at runtime. Keep 8000 as the local/compose fallback.
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
