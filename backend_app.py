# backend_app.py

from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
import os
import json

# --- IMPORT YOUR TELEGRAM LIBRARY HERE ---
# from telethon import TelegramClient, events
# from pyrogram import Client, filters, idle
# ----------------------------------------

app = Flask(__name__)
# Configure SocketIO for CORS to allow connections from your frontend (localhost:5000)
# In production, replace '*' with your actual frontend domain(s)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Global dictionary to store active Telegram clients (for simplicity, in memory) ---
# In a real app, you'd manage persistent storage and potentially multiple users
telegram_clients = {} # {sid: telegram_client_instance}
# ------------------------------------------------------------------------------------

@app.route('/')
def index():
    """Serves the index page (optional, for testing if backend is running)."""
    return "Backend is running. Connect your frontend!"

@app.route('/save-credentials', methods=['POST'])
def save_credentials():
    """
    Receives API ID, API Hash, and Session String from the frontend.
    This is where you would initialize/manage your Telegram client.
    """
    data = request.json
    api_id = data.get('api_id')
    api_hash = data.get('api_hash')
    session_string = data.get('session_string')
    client_sid = request.sid # Get the session ID of the client making the request

    if not all([api_id, api_hash, session_string]):
        return jsonify({"status": "error", "message": "Missing credentials"}), 400

    print(f"Received credentials for client {client_sid}:")
    print(f"  API ID: {api_id}")
    print(f"  API Hash: {api_hash[:4]}...") # Print only first few chars for security
    print(f"  Session String: {session_string[:10]}...") # Print only first few chars

    try:
        # --- TELEGRAM CLIENT INITIALIZATION LOGIC GOES HERE ---
        # This is highly conceptual. A real implementation would:
        # 1. Initialize Telethon/Pyrogram client with session_string
        # 2. Add event handlers to listen for new messages (OTPs)
        # 3. Connect the client and keep it running

        # Example placeholder:
        # from telethon import TelegramClient
        # client = TelegramClient(session_string, api_id, api_hash)
        #
        # @client.on(events.NewMessage(pattern=r'.*login code.*|.*OTP is.*', incoming=True))
        # async def handler(event):
        #     print(f"Detected potential OTP: {event.message.text}")
        #     # Emit the OTP back to the specific client that submitted these credentials
        #     socketio.emit('otp_received', {'otp': event.message.text}, room=client_sid)
        #
        # await client.start()
        # telegram_clients[client_sid] = client # Store client instance keyed by sid

        # For demonstration, we'll just acknowledge receipt
        response_message = f"Credentials received. Backend is now conceptually 'listening' for OTPs for your session."
        socketio.emit('backend_status', {'message': response_message}, room=client_sid)

        return jsonify({"status": "success", "message": response_message})

    except Exception as e:
        print(f"Error initializing Telegram client: {e}")
        return jsonify({"status": "error", "message": f"Failed to initialize Telegram client: {str(e)}"}), 500

@socketio.on('connect')
def test_connect():
    """Called when a new client connects via WebSocket."""
    print(f"Client connected: {request.sid}")
    emit('backend_status', {'message': f"Connected to backend! Your session ID is {request.sid}"})

@socketio.on('disconnect')
def test_disconnect():
    """Called when a client disconnects from WebSocket."""
    print(f"Client disconnected: {request.sid}")
    # In a real app, you might stop the associated Telegram client here
    # if request.sid in telegram_clients:
    #     client = telegram_clients.pop(request.sid)
    #     client.disconnect() # or client.stop()

@socketio.on('request_otp_simulation')
def handle_otp_simulation(data):
    """
    A conceptual event to trigger OTP simulation from the frontend.
    In a real app, OTPs would be triggered by actual Telegram events.
    """
    print(f"Received request for OTP simulation from {request.sid}")
    # Simulate receiving an OTP
    simulated_otp = f"SIMULATED OTP: {os.urandom(3).hex().upper()} (from backend)"
    print(f"Emitting simulated OTP: {simulated_otp}")
    emit('otp_received', {'otp': simulated_otp})

if __name__ == '__main__':
    # You can change the port if needed, e.g., port=5000
    socketio.run(app, debug=True, port=5000)
