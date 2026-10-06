import os, logging, json
from flask import Flask, jsonify
from prometheus_flask_exporter import PrometheusMetrics

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}')
log = logging.getLogger("app")

app = Flask(__name__)
metrics = PrometheusMetrics(app)  # exposes /metrics

@app.route("/")
def index():
    log.info("index requested")
    return jsonify(message="Hello from devops-pipeline", env=os.getenv("APP_ENV", "dev"))

@app.route("/health")
def health():
    return jsonify(status="ok"), 200