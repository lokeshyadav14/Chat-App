from flask import Flask, request, render_template, redirect, url_for, session
from flask_socketio import SocketIO, join_room, leave_room, send
import random
import string
from datetime import datetime
from typing import List
import pymongo

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey123'
socketio = SocketIO(app)

# Initialize MongoDB connection
mongo_uri = 'mongodb+srv://lokeshyadav0412:lokeshyadav0412@cluster0.y28ogfm.mongodb.net/?retryWrites=true&w=majority'
mongo_client = pymongo.MongoClient(mongo_uri)
db = mongo_client['chat_app']
messages_collection = db['messages']

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
            room_data = messages_collection.find_one({'code': code})
            if not room_data:
                return render_template('home.html', error="Room code invalid", name=name)
            room_code = room_data['code']
        session['room'] = room_code
        session['name'] = name
        return redirect(url_for('room'))
    else:
        return render_template('home.html')

@app.route('/room')
def room():
    room = session.get('room')
    name = session.get('name')
    if name is None or room is None:
        return redirect(url_for('home'))

    # Retrieve messages from MongoDB
    room_data = messages_collection.find_one({'code': room})
    if room_data:
        messages = room_data.get('messages', [])
    else:
        messages = []

    return render_template('room.html', room=room, user=name, messages=messages)

# Build the SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    name = session.get('name')
    room = session.get('room')
    if name is None or room is None:
        return
    join_room(room)
    send({
        "sender": "",
        "message": f"{name} has entered the chat"
    }, to=room)

@socketio.on('message')
def handle_message(payload):
    room = session.get('room')
    name = session.get('name')
    if room is None:
        return

    # Get the current timestamp
    timestamp = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    message = {
        "sender": name,
        "message": payload["message"],
        "timestamp": timestamp
    }

    # Append the message to the room's message list
    messages_collection.update_one({'code': room}, {'$push': {'messages': message}})

    send(message, to=room)

@socketio.on('disconnect')
def handle_disconnect():
    room = session.get('room')
    name = session.get('name')
    if room is None:
        return
    leave_room(room)
    send({
        'sender': "",
        'message': f"{name} has left the chat"
    }, to=room)

if __name__ == "__main__":
    socketio.run(app, debug=True)
