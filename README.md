# Sakura Nihongo 🌸 — Flask learning platform

An editable beginner Japanese learning site, with **Spanish interface**, 46 basic hiragana, 46 basic katakana, flip cards, browser speech synthesis, five illustrated vocabulary lessons, server-scored quizzes, accounts, SQLite-based progress history, and teacher CSV exports.

## Start

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# On Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. Database is created in `learning.sqlite3` on first run. For a deployment, run `flask --app app init-db` instead or initialize it with `python -c "from app import init_db; init_db()"` before launching WSGI.

## Create a teacher account (one-time local management)

After registering your own account in the browser, run this from the project folder:

```bash
python -c "from app import db; c=db(); c.execute('UPDATE users SET role=? WHERE username=?', ('admin','YOUR_USERNAME')); c.commit(); c.close()"
```

Replace `YOUR_USERNAME` with the account you just created. The **Docente** link will then appear after logging back in. Do not expose the local administration command to learners.

## Where to edit

- `data/content.json`: 5 units, Japanese words, romaji, Spanish translations and visual emoji.
- `app.py`: 46+46 kana arrays, quiz logic, accounts, database, CSV reporting.
- `templates/`: separate pages; `base.html` shared navigation.
- `static/css/style.css`: colors, responsive layout, appearance.
- `static/js/app.js`: flip card animation, audio, quiz behavior.
- `static/img/fuji.svg`: Mount Fuji artwork from the first project.

## Evaluation model

- Nine 5-character batches plus a final 1-character batch **per syllabary** (46 total).
- Every batch can be retaken. Score threshold is 80%; last one-character batch is 0% or 100%.
- Every vocabulary lesson has a six-question mini-quiz.
- Every submission is stored with UTC time, raw selected answer, correct answer and correctness per item.
- Students see their own history and CSV; teacher sees all students and a detailed export.
- These are recognition checks, **not** independently validated evidence of retention. For better learning measurement, add delayed post-tests and randomized question banks later.

## Production notes

This is a functional **learning MVP**. For public deployment, configure a persistent `SECRET_KEY`, `COOKIE_SECURE=1` with HTTPS, proper production WSGI hosting, database backups, rate limiting, account recovery, privacy notice, retention policies, and consent where appropriate (especially minors). SQLite is adequate for a small pilot; migrate to PostgreSQL for heavier use. The hosted system should never be run with Flask debug mode. Audio uses device Japanese TTS, which may depend on browser voice availability. Illustrations use Unicode emoji; replace them with licensed local image assets if needed.

Inspired by general **Marugoto Starter A1** themes (Japan Foundation), not affiliated with or a reproduction of Minato course content. Animal/color units are supplementary beginner-friendly topics.
