import csv
import io
import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from flask import Flask, abort, flash, jsonify, redirect, render_template, request, Response, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE = Path(__file__).resolve().parent
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.config['DATABASE'] = os.environ.get('DATABASE_PATH', str(BASE / 'learning.sqlite3'))
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')
if os.environ.get('COOKIE_SECURE') == '1':
    app.config['SESSION_COOKIE_SECURE'] = True
CONTENT = json.loads((BASE / 'data/content.json').read_text(encoding='utf-8'))
# The 46 basic modern gojuon, ordered in traditional rows (no archaic wi/we).
ROMAJI = ['a','i','u','e','o','ka','ki','ku','ke','ko','sa','shi','su','se','so','ta','chi','tsu','te','to','na','ni','nu','ne','no','ha','hi','fu','he','ho','ma','mi','mu','me','mo','ya','yu','yo','ra','ri','ru','re','ro','wa','wo','n']
HIRAGANA = list('あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん')
KATAKANA = list('アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン')
assert len(HIRAGANA) == len(KATAKANA) == len(ROMAJI) == 46
KANA = {'hiragana': list(zip(HIRAGANA, ROMAJI)), 'katakana': list(zip(KATAKANA, ROMAJI))}
LESSONS = {x['id']: x for x in CONTENT['lessons']}


def db():
    connection = sqlite3.connect(app.config['DATABASE'])
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


def init_db():
    with db() as con:
        con.executescript('''
          CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'student',
            created_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            kind TEXT NOT NULL, unit TEXT NOT NULL, score INTEGER NOT NULL,
            total INTEGER NOT NULL, created_at TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY, attempt_id INTEGER NOT NULL REFERENCES attempts(id),
            question TEXT NOT NULL, chosen TEXT NOT NULL,
            correct TEXT NOT NULL, is_correct INTEGER NOT NULL);
        ''')


def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    with db() as con:
        user = con.execute('SELECT id, username, role FROM users WHERE id=?', (uid,)).fetchone()
    return dict(user) if user else None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            if request.path.startswith('/api/'):
                return jsonify(error='Inicia sesión primero.'), 401
            return redirect(url_for('login'))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if current_user()['role'] != 'admin':
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


@app.before_request
def csrf_check():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(24)
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        token = request.headers.get('X-CSRF-Token') or request.form.get('csrf_token')
        if not secrets.compare_digest(token or '', session['csrf_token']):
            abort(400, description='Token de seguridad inválido.')


@app.context_processor
def globals_for_templates():
    return {'user': current_user(), 'csrf_token': session.get('csrf_token', '')}


@app.route('/')
def home():
    return render_template('index.html', lessons=CONTENT['lessons'])


@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not (3 <= len(username) <= 40 and username.replace('_', '').isalnum()):
            flash('Usa un nombre de 3–40 letras, números o guiones bajos.')
        elif len(password) < 8:
            flash('La contraseña debe tener al menos 8 caracteres.')
        else:
            try:
                with db() as con:
                    con.execute('INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)',
                                (username, generate_password_hash(password), 'student', now()))
                flash('Cuenta creada. Inicia sesión.')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('Este nombre de usuario ya está registrado.')
    return render_template('auth.html', mode='register')


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        with db() as con:
            row = con.execute('SELECT * FROM users WHERE username=?', (request.form.get('username','').strip(),)).fetchone()
        if row and check_password_hash(row['password_hash'], request.form.get('password','')):
            session.clear()
            session['user_id'] = row['id']
            session['csrf_token'] = secrets.token_hex(24)
            return redirect(url_for('dashboard'))
        flash('Usuario o contraseña incorrectos.')
    return render_template('auth.html', mode='login')


@app.post('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def attempt_rows(uid):
    with db() as con:
        return [dict(x) for x in con.execute('SELECT * FROM attempts WHERE user_id=? ORDER BY id DESC', (uid,))]


def best_scores(uid):
    with db() as con:
        rows = con.execute('SELECT kind, unit, MAX(score * 1.0 / total) AS best FROM attempts WHERE user_id=? GROUP BY kind,unit', (uid,)).fetchall()
    return {(x['kind'], x['unit']): x['best'] for x in rows}


@app.route('/dashboard')
@login_required
def dashboard():
    scores = best_scores(current_user()['id'])
    attempts = attempt_rows(current_user()['id'])
    mastered = sum(v >= 0.8 for v in scores.values())
    return render_template('dashboard.html', attempts=attempts, mastered=mastered, scores=scores)


@app.route('/kana/<script>')
@login_required
def kana(script):
    if script not in KANA:
        abort(404)
    scores = best_scores(current_user()['id'])
    groups = [{'number': i + 1, 'letters': [{'symbol': sym, 'romaji': rom} for sym, rom in KANA[script][i*5:i*5+5]],
               'best': scores.get((script, str(i+1)))} for i in range(10)]
    return render_template('kana.html', script=script, groups=groups)


@app.route('/lesson/<lesson_id>')
@login_required
def lesson(lesson_id):
    if lesson_id not in LESSONS:
        abort(404)
    lesson_obj = LESSONS[lesson_id]
    scores = best_scores(current_user()['id'])
    return render_template('lesson.html', lesson=lesson_obj, best=scores.get(('lesson', lesson_id)))


def pool(kind, unit):
    if kind in KANA:
        try:
            idx = int(unit)
        except ValueError:
            abort(404)
        if not (1 <= idx <= 10):
            abort(404)
        return [{'prompt': item[0], 'correct': item[1]} for item in KANA[kind][(idx-1)*5:idx*5]]
    if kind == 'lesson' and unit in LESSONS:
        return [{'prompt': word[0], 'correct': word[2]} for word in LESSONS[unit]['words']]
    abort(404)


def choices_for(kind, unit, correct, question_index):
    # A deterministic per-unit answer set so submissions can be validated without trusting the browser.
    import hashlib
    if kind in KANA:
        alternatives = list(dict.fromkeys(ROMAJI))
    else:
        alternatives = [w[2] for lesson in CONTENT['lessons'] for w in lesson['words']]
    alternatives = [a for a in alternatives if a != correct]
    digest = hashlib.sha256(f'{kind}|{unit}|{question_index}'.encode()).digest()
    offset = int.from_bytes(digest[:4], 'big') % len(alternatives)
    order = alternatives[offset:] + alternatives[:offset]
    answers = [correct] + order[:3]
    position = digest[4] % 4
    answers.insert(position, answers.pop(0))
    return answers


@app.get('/api/quiz/<kind>/<unit>')
@login_required
def quiz_get(kind, unit):
    return jsonify(questions=[{'prompt': item['prompt'], 'choices': choices_for(kind, unit, item['correct'], i)}
                              for i, item in enumerate(pool(kind, unit))])


@app.post('/api/quiz/<kind>/<unit>')
@login_required
def quiz_submit(kind, unit):
    questions = pool(kind, unit)
    payload = request.get_json(silent=True) or {}
    selected = payload.get('answers')
    if not isinstance(selected, list) or len(selected) != len(questions) or any(not isinstance(a, str) for a in selected):
        return jsonify(error='Responde todas las preguntas.'), 400
    for i, (item, answer) in enumerate(zip(questions, selected)):
        if answer not in choices_for(kind, unit, item['correct'], i):
            return jsonify(error='Respuesta inválida.'), 400
    result = [{'prompt': q['prompt'], 'chosen': a, 'correct': q['correct'], 'is_correct': a == q['correct']}
              for q, a in zip(questions, selected)]
    score = sum(x['is_correct'] for x in result)
    with db() as con:
        cur = con.execute('INSERT INTO attempts(user_id,kind,unit,score,total,created_at) VALUES(?,?,?,?,?,?)',
                          (current_user()['id'], kind, unit, score, len(result), now()))
        con.executemany('INSERT INTO answers(attempt_id,question,chosen,correct,is_correct) VALUES(?,?,?,?,?)',
                        [(cur.lastrowid, x['prompt'], x['chosen'], x['correct'], int(x['is_correct'])) for x in result])
    return jsonify(score=score, total=len(result), passed=(score / len(result) >= .8), detail=result)


@app.get('/export/me.csv')
@login_required
def export_me():
    return export_results(current_user()['id'])


def export_results(uid=None):
    query = '''SELECT u.username, a.id AS attempt_id, a.kind, a.unit, a.score, a.total,
                     a.created_at, q.question, q.chosen, q.correct, q.is_correct
               FROM attempts a JOIN users u ON u.id=a.user_id
               JOIN answers q ON q.attempt_id=a.id'''
    args = ()
    if uid is not None:
        query += ' WHERE u.id=?'
        args = (uid,)
    query += ' ORDER BY a.created_at DESC, a.id DESC, q.id'
    with db() as con:
        records = con.execute(query, args).fetchall()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['usuario','intento_id','tipo','unidad','aciertos','preguntas','fecha_utc','pregunta','respuesta','correcta','acierto'])
    writer.writerows(tuple(record) for record in records)
    filename = 'mi_progreso.csv' if uid is not None else 'resultados_todos.csv'
    return Response('\ufeff' + out.getvalue(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@app.get('/admin')
@admin_required
def admin():
    with db() as con:
        students = [dict(row) for row in con.execute('''SELECT u.id, u.username, COUNT(a.id) AS attempts,
           ROUND(AVG(a.score * 100.0 / a.total), 1) AS avg_score,
           MAX(a.created_at) AS last_activity FROM users u LEFT JOIN attempts a ON a.user_id=u.id
           WHERE u.role='student' GROUP BY u.id ORDER BY u.username''')]
    return render_template('admin.html', students=students)


@app.get('/admin/export.csv')
@admin_required
def admin_export():
    return export_results()


@app.get('/admin/student/<int:uid>')
@admin_required
def admin_student(uid):
    with db() as con:
        student = con.execute('SELECT username FROM users WHERE id=? AND role="student"', (uid,)).fetchone()
    if not student:
        abort(404)
    return render_template('dashboard.html', attempts=attempt_rows(uid),
                           mastered=sum(v >= .8 for v in best_scores(uid).values()),
                           scores=best_scores(uid), student_name=student['username'])


# Initialize schema on import for both Flask CLI/WSGI and local execution.
init_db()

if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
