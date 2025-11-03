from flask import Flask, Response
from prometheus_client import Counter, generate_latest

app = Flask(__name__)

# Example metric
request_count = Counter("flask_requests_total", "Total requests to Flask app")

@app.route("/")
def hello():
    request_count.inc()  # increment counter
    return "Hello, Flask with Prometheus!"

@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype="text/plain")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
