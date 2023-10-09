from flask import Flask, request, render_template, redirect, url_for, session
from flask_socketio import SocketIO, join_room, leave_room, send
import random
import string
import time
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey123'
socketio = SocketIO(app)

def generate_room_code(length: int, existing_codes: list[str]) -> str:
    while True:
        code_chars = [random.choice(string.ascii_letters) for _ in range(length)]
        code = ''.join(code_chars)
        if code not in existing_codes:
            return code

# A mock database to persist data (chat messages)
rooms = {}

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
            room_code = generate_room_code(6, list(rooms.keys()))
            new_room = {
                'members': 0,
                'messages': []
            }
            rooms[room_code] = new_room
        if join != False:
            if not code:
                return render_template('home.html', error="Please enter a room code to enter a chat room", name=name)
            if code not in rooms:
                return render_template('home.html', error="Room code invalid", name=name)
            room_code = code
        session['room'] = room_code
        session['name'] = name
        return redirect(url_for('room'))
    else:
        return render_template('home.html')

@app.route('/room')
def room():
    room = session.get('room')
    name = session.get('name')
    if name is None or room is None or room not in rooms:
        return redirect(url_for('home'))
    messages = rooms[room]['messages']
    return render_template('room.html', room=room, user=name, messages=messages)

# Build the SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    name = session.get('name')
    room = session.get('room')
    if name is None or room is None:
        return
    if room not in rooms:
        leave_room(room)
    join_room(room)
    send({
        "sender": "",
        "message": f"{name} has entered the chat"
    }, to=room)
    rooms[room]['members'] += 1

@socketio.on('message')
def handle_message(payload):
    room = session.get('room')
    name = session.get('name')
    if room not in rooms:
        return
    # Get the current timestamp
    timestamp = time.time()
    # Format the timestamp as a string
    formatted_timestamp = datetime.fromtimestamp(timestamp).strftime('%d-%m-%Y %H:%M')
    message = {
        "sender": name,
        "message": payload["message"],
        "timestamp": formatted_timestamp
    }
    rooms[room]['messages'].append(message)  # Append the message to the room's message list
    send(message, to=room)

@socketio.on('disconnect')
def handle_disconnect():
    room = session.get('room')
    name = session.get('name')
    leave_room(room)
    if room in rooms:
        rooms[room]['members'] -= 1
        if rooms[room]['members'] <= 0:
            del rooms[room]
        send({
            'sender': "",
            'message': f"{name} has left the chat"
        }, to=room)

if __name__ == "__main__":
    socketio.run(app, debug=True)
