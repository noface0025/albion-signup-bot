
from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080, debug=False)

def keep_alive():
    server = Thread(target=run)
    server.daemon = True
    server.start()
