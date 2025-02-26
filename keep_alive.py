
from flask import Flask
import os
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080, threaded=True)

def keep_alive():
    server = Thread(target=run)
    server.daemon = True  # This ensures the thread stops when the main program stops
    server.start()
