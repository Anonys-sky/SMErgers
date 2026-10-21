"""Entry point. Starts the web app (built up over the following commits)."""
import os

from flask import Flask

app = Flask(__name__)


@app.get("/")
def home():
    return (
        "<h1>OnRecord (working name)</h1>"
        "<p>Turns what was agreed in WhatsApp into approved changes "
        "and a correct draft final bill.</p>"
        "<p>All data in this prototype is synthetic.</p>"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
