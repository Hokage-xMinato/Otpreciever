# backend_app.py

from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import os
import asyncio
import random
import string

# --- TELETHON IMPORTS ---
# You'll need to make sure Telethon is installed: pip install Telethon
from telethon import TelegramClient, events
from telethon.sessions import StringSession
import logging

# Set up logging for Telethon (optional but useful for debugging)
logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s', level=logging.WARNING)

# ------------------------

app = Flask(__name__, static_folder='.', static_url_path='') # Serve static files from current directory
# Configure SocketIO for CORS to allow connections from your frontend
# In production, replace '*' with your actual frontend domain(s) if frontend and backend are separate services.
# If they are on the same Render service, use the Render domain.
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent') # Using gevent for async

# --- Global dictionary to store active Telegram clients and their associated Socket.IO SIDs ---
# In a real app, this should be backed by a persistent database (e.g., Redis, PostgreSQL)
# and handle multiple users securely. For simplicity, this is in-memory for a single instance.
active_telegram_sessions = {} # {socket_id: {'client': TelegramClient, 'api_id': int, 'api_hash': str, 'session_string': str}}
# ---------------------------------------------------------------------------------------------

@app.route('/')
def index_html():
    """Serves the index.html file directly from the root."""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/save-credentials', methods=['POST'])
async def save_credentials():
    """
    Receives API ID, API Hash, and Session String from the frontend.
    Initializes/manages the Telegram client for the specific user.
    """
    data = request.json
    api_id = int(data.get('api_id')) # Ensure it's an integer
    api_hash = data.get('api_hash')
    session_string = data.get('session_string')
    client_socket_id = data.get('socket_id') # Get the Socket.IO ID from frontend

    if not all([api_id, api_hash, session_string, client_socket_id]):
        return jsonify({"status": "error", "message": "Missing API ID, API Hash, Session String, or Socket ID"}), 400

    print(f"Received credentials for Socket.IO client {client_socket_id}:")
    print(f"  API ID: {api_id}")
    print(f"  API Hash: {api_hash[:4]}...")
    print(f"  Session String: {session_string[:10]}...")

    if client_socket_id in active_telegram_sessions:
        # If client already exists, disconnect and re-initialize to use new credentials
        print(f"Disconnecting existing client for {client_socket_id}...")
        try:
            await active_telegram_sessions[client_socket_id]['client'].disconnect()
        except Exception as e:
            print(f"Error disconnecting existing client: {e}")
        del active_telegram_sessions[client_socket_id]

    try:
        # Initialize Telethon client
        # IMPORTANT: When running Telethon for the first time with a new session string,
        # it might need to send a code to your Telegram account and then receive it
        # to properly authenticate. This typically requires interactive input or a
        # pre-authenticated session string.
        # This example assumes a valid, pre-generated session string is provided.
        client = TelegramClient(StringSession(session_string), api_id, api_hash)

        # Attach an event handler to listen for new messages
        @client.on(events.NewMessage(incoming=True))
        async def handler(event):
            # Check if the message contains common OTP phrases
            message_text = event.message.text
            if message_text and ("login code" in message_text.lower() or "otp is" in message_text.lower() or "telegram code" in message_text.lower()):
                print(f"Detected potential OTP for {client_socket_id}: {message_text}")
                # Emit the OTP back to the specific client that owns this session
                socketio.emit('otp_received', {'otp': message_text}, room=client_socket_id)

        # Connect the Telegram client in a non-blocking way
        # asyncio.create_task ensures it runs in the background
        async def start_telegram_client():
            try:
                print(f"Attempting to start Telegram client for {client_socket_id}...")
                await client.connect()
                if not await client.is_user_authorized():
                    print(f"Client {client_socket_id} not authorized. Session string might be invalid or requires re-login.")
                    # In a real app, you'd send a request for phone number and then OTP here
                    socketio.emit('backend_status', {'message': 'Telegram client needs re-authorization. Session string might be invalid.'}, room=client_socket_id)
                    # You might need to call client.start() and handle phone/OTP input if session is new
                else:
                    print(f"Telegram client for {client_socket_id} authorized and running.")
                    socketio.emit('backend_status', {'message': 'Telegram client connected and authorized! Waiting for OTPs...'}, room=client_socket_id)
                await client.run_until_disconnected() # Keep the client running
            except Exception as e:
                print(f"Error starting Telegram client for {client_socket_id}: {e}")
                socketio.emit('backend_status', {'message': f'Error connecting Telegram client: {e}'}, room=client_socket_id)

        # Store the client and its info, and run it
        active_telegram_sessions[client_socket_id] = {
            'client': client,
            'api_id': api_id,
            'api_hash': api_hash,
            'session_string': session_string,
            'task': asyncio.create_task(start_telegram_client()) # Run as a background task
        }

        response_message = "Credentials received. Telegram client attempting connection and listening for OTPs."
        return jsonify({"status": "success", "message": response_message})

    except Exception as e:
        print(f"Error initializing Telegram client setup: {e}")
        return jsonify({"status": "error", "message": f"Failed to setup Telegram client: {str(e)}"}), 500

@socketio.on('connect')
def handle_connect():
    """Called when a new client connects via WebSocket."""
    print(f"Client connected: {request.sid}")
    # You might want to send the current status of their Telegram client here if it exists
    if request.sid in active_telegram_sessions and active_telegram_sessions[request.sid]['client'].is_connected():
        emit('backend_status', {'message': f"Reconnected to backend. Telegram client for your session is active."}, room=request.sid)
    else:
        emit('backend_status', {'message': f"Connected to backend! Your session ID is {request.sid}. Please submit credentials."}, room=request.sid)


@socketio.on('disconnect')
async def handle_disconnect():
    """Called when a client disconnects from WebSocket."""
    print(f"Client disconnected: {request.sid}")
    # In a real app, you might stop the associated Telegram client here
    if request.sid in active_telegram_sessions:
        print(f"Stopping Telegram client for disconnected SID: {request.sid}")
        client_info = active_telegram_sessions.pop(request.sid)
        try:
            await client_info['client'].disconnect()
            client_info['task'].cancel() # Cancel the background task
        except Exception as e:
            print(f"Error during client cleanup for {request.sid}: {e}")

@socketio.on('request_otp_simulation')
def handle_otp_simulation():
    """
    A conceptual event to trigger OTP simulation from the backend.
    This demonstrates real-time push via WebSockets.
    """
    print(f"Received request for OTP simulation from {request.sid}")
    # Simulate receiving an OTP
    simulated_otp = f"SIMULATED OTP: {''.join(random.choices(string.digits, k=5))} (from backend)"
    print(f"Emitting simulated OTP: {simulated_otp}")
    emit('otp_received', {'otp': simulated_otp}, room=request.sid)

if __name__ == '__main__':
    # When running locally, use localhost and a default port.
    # When deploying to Render, the 'PORT' environment variable will be set.
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask-SocketIO app on port {port}...")
    # Use allow_unsafe_werkzeug=True for development if needed, but not for production
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
