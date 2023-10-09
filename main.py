from flask import Flask, request, render_template, redirect, url_for, session
from flask_socketio import SocketIO, join_room, leave_room, send
import random
import string
from datetime import datetime
from typing import List
from pymongo import MongoClient

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey123'
socketio = SocketIO(app)

# Initialize MongoDB connection
mongo_client = MongoClient("mongodb://your-mongodb-uri")
db = mongo_client.get_database("chat_app")  # Use your database name
messages_collection = db.get_collection("messages")  # Create a collection for messages

def generate_room_code(length: int, existing_codes: List[str]) -> str:
    while True:
        code_chars = [random.choice(string.ascii_letters) for _ in range(length)]
        code = ''.join(code_chars)
        if code not in existing_codes:
            return code

# Build the routes
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        name = request.form.get('name')
        create = request.form.get('create', False)
        code = request.form.get('code')
        join = request.form.get('join', False)
        if not name:
            return render_template('home.html', error='Name is required', code=code)
        if create != False:
            room_code = generate_room_code(6, [room['code'] for room in messages_collection.find()])
            new_room = {
                'code': room_code,
                'members': 0,
                'messages': []
            }
            messages_collection.insert_one(new_room)
        if join != False:
            if not code:
                return render_template('home.html', error="Please enter a room code to enter a chat room", name=name)
            existing_room = messages_collection.find_one({'code': code})
            if not existing_room:
                return render_template('home.html', error="Room code invalid", name=name)
            room_code = code
        session['room'] = room_code
        session['name'] = name
        return redirect(url_for('room'))
    else:
        return render_template('home.html')

@app.route('/room')
def room():
    room_code = session.get('room')
    name = session.get('name')
    if name is None or room_code is None:
        return redirect(url_for('home'))

    # Retrieve messages from MongoDB
    room = messages_collection.find_one({'code': room_code})
    messages = room['messages']

    return render_template('room.html', room=room_code, user=name, messages=messages)

# Build the SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    name = session.get('name')
    room_code = session.get('room')
    if name is None or room_code is None:
        return
    join_room(room_code)
    send({
        "sender": "",
        "message": f"{name} has entered the chat"
    }, to=room_code)

@socketio.on('message')
def handle_message(payload):
    room_code = session.get('room')
    name = session.get('name')
    if room_code is None:
        return

    # Get the current timestamp
    timestamp = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    message = {
        "sender": name,
        "message": payload["message"],
        "timestamp": timestamp
    }

    # Append the message to the room's message list
    messages_collection.update_one({'code': room_code}, {'$push': {'messages': message}})

    send(message, to=room_code)

@socketio.on('disconnect')
def handle_disconnect():
    room_code = session.get('room')
    name = session.get('name')
    if room_code:
        leave_room(room_code)
        send({
            'sender': "",
            'message': f"{name} has left the chat"
        }, to=room_code)

if __name__ == "__main__":
    socketio.run(app, debug=True)
