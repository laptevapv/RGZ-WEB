from flask import Flask, redirect, request, render_template, current_app, url_for, session, jsonify
import psycopg2
import os
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
from os import path



app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'секретно-секретный секрет')
app.config['DB_TYPE'] = os.getenv('DB_TYPE', 'postgres')

def db_connect(db_type):
    if db_type == 'postgres':
        conn = psycopg2.connect(
            host='127.0.0.1',
            database='rgz_web',
            user='rgz_web',
            password='12345'
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
    else:
        dir_path = path.dirname(path.realpath(__file__))
        db_path = path.join(dir_path, "database.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

    return conn, cur

def db_close(conn, cur):
    conn.commit()
    cur.close()
    conn.close()


@app.route('/')
def menu():
    user_status = session.get('login', 'Аноним')
    return render_template('menu.html', user_status=user_status)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    
    login = request.form.get('login')
    password = request.form.get('password')
    if not (login and password):
        return render_template('register.html', error='Заполните все поля')
    
    conn, cur = db_connect(app.config['DB_TYPE'])

    if app.config['DB_TYPE'] == 'postgres':
        cur.execute("SELECT login FROM users WHERE login=%s;", (login,))
    else:
        cur.execute("SELECT login FROM users WHERE login=?;", (login,))

    if cur.fetchone():
        db_close(conn, cur)
        return render_template('register.html', error='Такой пользователь уже существует')

    password_hash = generate_password_hash(password)

    if app.config['DB_TYPE'] == 'postgres':
        cur.execute("INSERT INTO users (login, password) VALUES (%s, %s);", (login, password_hash))
    else:
        cur.execute("INSERT INTO users (login, password) VALUES (?, ?);", (login, password_hash))

    db_close(conn, cur)
    return render_template('success.html', login=login)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    
    login = request.form.get('login')
    password = request.form.get('password')
    if not (login and password):
        return render_template('login.html', error='Заполните все поля')
    
    # Передаем аргумент db_type при вызове db_connect
    conn, cur = db_connect(app.config['DB_TYPE'])
    
    if app.config['DB_TYPE'] == 'postgres':
        cur.execute("SELECT * FROM users WHERE login=%s;", (login,))
    else:
        cur.execute("SELECT * FROM users WHERE login=?;", (login,))

    user = cur.fetchone()
    if not user or not check_password_hash(user['password'], password):
        db_close(conn, cur)
        return render_template('login.html', error='Логин и/или пароль неверны')
    session['login'] = login
    db_close(conn, cur)
    return redirect(url_for('menu'))  # Перенаправляем на главную страницу после входа

@app.route('/logout')
def logout():
    session.pop('login', None)  # Удаление логина из сессии
    return redirect(url_for('menu'))  # Перенаправляем на главную страницу после выхода

rooms = []
for i in range(1, 101):
    rooms.append({'number': i, 'tenant': ""})

@app.route('/rooms/json-rpc-api', methods=['POST'])
def api():
    data = request.json
    id = data['id']
    if data['method'] == 'info':
        return {
            'jsonrpc': '2.0',
            'result': rooms,
            'id': id
        }
    login = session.get('login')
    if not login: 
        return {
            'jsonrpc': '2.0', 
            'error': {
                'code': 1,
                'message': 'Unauthorized'
            },
            'id': id
        }
    if data['method'] == 'booking':
        room_number = data['params']
        for room in rooms:
            if room['number'] == room_number:
                if room['tenant'] != '':
                    return {
                        'jsonrpc': '2.0', 
                        'error': {
                            'code': 2,
                            'message': 'Already'
                        },
                        'id': id
                    }
                room['tenant'] = login
                return {
                    'jsonrpc': '2.0', 
                    'result': 'success',
                    'id': id
                }
    if data['method'] == 'cancellation':
        room_number = data['params']
        for room in rooms:
            if room['number'] == room_number:
                if room['tenant'] != login:
                    return {
                        'jsonrpc': '2.0',
                        'error': {
                            'code': 3,
                            'message': 'Forbidden'
                        },
                        'id': id
                    }
                room['tenant'] = ''
                return {
                    'jsonrpc': '2.0',
                    'result': 'success',
                    'id': id
                }
    return {
        'jsonrpc': '2.0', 
        'error': {
            'code': -32601,
            'message': 'Method not found'
        },
        'id': id
    }