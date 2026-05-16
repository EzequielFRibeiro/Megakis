#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║                    MEGA QUIZ - v1.0                         ║
║         Jogo de Perguntas e Respostas Interativo            ║
╠══════════════════════════════════════════════════════════════╣
║  Categorias: Bíblicas | Conhecimentos Gerais | Inglês      ║
║              Espanhol | Coreano | Informática | Fullstack   ║
╠══════════════════════════════════════════════════════════════╣
║  Direitos Reservados - ezetecf@gmail.com                   ║
╚══════════════════════════════════════════════════════════════╝
"""

import http.server
import socketserver
import json
import sqlite3
import hashlib
import random
import os
import re
import uuid
import time
import webbrowser
import threading
from urllib.parse import urlparse, parse_qs, quote
from html import escape
from pathlib import Path

PORT = 8080
DB_NAME = "mega_quiz.db"
SESSION_TIMEOUT = 86400

sessions = {}

# ==================== DATABASE ====================

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_master INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    # migration: add is_master column if missing
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN is_master INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    # create master user if not exists
    master_hash = hashlib.sha256("Mikelle08".encode()).hexdigest()
    cursor.execute("SELECT id FROM users WHERE first_name = ? AND is_master = 1", ("kiel",))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT OR IGNORE INTO users (first_name, last_name, email, password, is_master) VALUES (?, ?, ?, ?, 1)",
            ("kiel", "kiel", "kiel@master", master_hash)
        )
    conn.commit()
    conn.close()

# ==================== QUESTIONS DATABASE ====================

from questions_data import QUESTIONS, CATEGORY_KEYS

# ==================== SESSION MANAGEMENT ====================

def create_session(user_id, first_name, last_name, email, is_master=0):
    token = str(uuid.uuid4())
    sessions[token] = {
        "user_id": user_id,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "is_master": is_master,
        "created_at": time.time()
    }
    return token

def get_session(token):
    if token and token in sessions:
        sess = sessions[token]
        if time.time() - sess["created_at"] < SESSION_TIMEOUT:
            return sess
        else:
            del sessions[token]
    return None

def clear_session(token):
    if token and token in sessions:
        del sessions[token]

# ==================== WEB HANDLER ====================

class MegaQuizHandler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def get_cookie(self, name):
        cookies = self.headers.get("Cookie", "")
        for c in cookies.split(";"):
            c = c.strip()
            if c.startswith(name + "="):
                return c[len(name)+1:]
        return None

    def set_cookie(self, name, value, max_age=86400):
        self.send_header("Set-Cookie", f"{name}={value}; Path=/; Max-Age={max_age}; HttpOnly")

    def delete_cookie(self, name):
        self.set_cookie(name, "", 0)

    def get_session_user(self):
        token = self.get_cookie("session")
        return get_session(token)

    def send_html(self, html, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Language", "pt-BR")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def redirect(self, path):
        self.send_response(302)
        self.send_header("Location", path)
        self.end_headers()

    def read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return self.rfile.read(length).decode("utf-8")
        return ""

    def parse_post_data(self):
        body = self.read_body()
        return parse_qs(body)

    # ============ LAYOUT ============

    def page(self, title, content, user=None, extra_head=""):
        user_info = ""
        if user:
            admin_link = ""
            if user.get("is_master"):
                admin_link = '<a href="/admin" class="btn-small" style="background:#dc3545;">👑 Admin</a>'
            user_info = f'''
            <div class="user-info">
                <span class="user-welcome">👤 {escape(user["first_name"])}</span>
                <div class="user-links">
                    {admin_link}
                    <a href="/perfil" class="btn-small">Meu Perfil</a>
                    <a href="/logout" class="btn-small btn-danger">Sair</a>
                </div>
            </div>
            '''
        else:
            user_info = '''
            <div class="user-info">
                <a href="/login" class="btn-small">Entrar</a>
                <a href="/registrar" class="btn-small btn-primary">Cadastrar</a>
            </div>
            '''

        html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape(title)} - Mega Quiz</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0c0c1d 0%, #1a1a3e 50%, #0c0c1d 100%);
            color: #e0e0e0;
            min-height: 100vh;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        header {{
            background: rgba(20, 20, 60, 0.95);
            backdrop-filter: blur(20px);
            border-bottom: 2px solid rgba(100, 100, 255, 0.2);
            padding: 15px 0;
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        header .container {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }}
        .logo {{
            font-size: 28px;
            font-weight: 900;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-decoration: none;
        }}
        .logo span {{
            font-size: 14px;
            font-weight: 400;
            -webkit-text-fill-color: #888;
            display: block;
        }}
        .user-info {{
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .user-welcome {{
            color: #aaa;
            font-size: 14px;
        }}
        .btn-small {{
            padding: 8px 18px;
            border-radius: 8px;
            text-decoration: none;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.3s;
            color: #fff;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .btn-small:hover {{
            background: rgba(255,255,255,0.2);
            transform: translateY(-1px);
        }}
        .btn-primary {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            border: none;
        }}
        .btn-primary:hover {{
            background: linear-gradient(135deg, #764ba2, #667eea);
        }}
        .btn-danger {{
            background: rgba(255, 50, 50, 0.2);
            border-color: rgba(255, 50, 50, 0.3);
        }}
        .btn-danger:hover {{
            background: rgba(255, 50, 50, 0.4);
        }}
        main {{
            padding: 40px 0;
        }}
        .card {{
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 16px;
            padding: 30px;
            backdrop-filter: blur(10px);
            transition: all 0.3s;
        }}
        .card:hover {{
            border-color: rgba(100,100,255,0.3);
        }}
        .grid {{
            display: grid;
            gap: 24px;
        }}
        .grid-2 {{ grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }}
        .grid-3 {{ grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); }}
        h1 {{
            font-size: 32px;
            font-weight: 800;
            margin-bottom: 20px;
            background: linear-gradient(135deg, #667eea, #e060ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        h2 {{
            font-size: 22px;
            font-weight: 700;
            margin-bottom: 16px;
            color: #ccc;
        }}
        h3 {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 12px;
            color: #aaa;
        }}
        p {{ color: #999; line-height: 1.7; margin-bottom: 12px; }}
        .text-center {{ text-align: center; }}
        .mt-20 {{ margin-top: 20px; }}
        .mb-20 {{ margin-bottom: 20px; }}
        .btn {{
            display: inline-block;
            padding: 12px 28px;
            border-radius: 10px;
            text-decoration: none;
            font-size: 15px;
            font-weight: 700;
            transition: all 0.3s;
            cursor: pointer;
            border: none;
            color: #fff;
        }}
        .btn-primary-lg {{
            background: linear-gradient(135deg, #667eea, #764ba2);
        }}
        .btn-primary-lg:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(102,126,234,0.4);
        }}
        .btn-success {{
            background: linear-gradient(135deg, #11998e, #38ef7d);
        }}
        .btn-success:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(17,153,142,0.4);
        }}
        .btn-outline {{
            background: transparent;
            border: 2px solid rgba(255,255,255,0.2);
        }}
        .btn-outline:hover {{
            background: rgba(255,255,255,0.1);
            border-color: rgba(255,255,255,0.4);
        }}
        input, select {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            background: rgba(255,255,255,0.05);
            color: #fff;
            font-size: 15px;
            transition: all 0.3s;
            outline: none;
        }}
        input:focus, select:focus {{
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102,126,234,0.2);
        }}
        input::placeholder {{ color: #666; }}
        label {{
            display: block;
            margin-bottom: 6px;
            font-size: 13px;
            font-weight: 600;
            color: #aaa;
        }}
        .form-group {{
            margin-bottom: 18px;
        }}
        .alert {{
            padding: 14px 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        .alert-error {{
            background: rgba(255,50,50,0.15);
            border: 1px solid rgba(255,50,50,0.3);
            color: #ff6b6b;
        }}
        .alert-success {{
            background: rgba(50,255,50,0.1);
            border: 1px solid rgba(50,255,50,0.2);
            color: #51cf66;
        }}
        .leaderboard {{
            width: 100%;
            border-collapse: collapse;
        }}
        .leaderboard th {{
            padding: 12px 16px;
            text-align: left;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #666;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .leaderboard td {{
            padding: 14px 16px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            font-size: 14px;
        }}
        .leaderboard tr:hover td {{
            background: rgba(255,255,255,0.02);
        }}
        .rank {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            font-weight: 800;
            font-size: 14px;
        }}
        .rank-1 {{ background: linear-gradient(135deg, #f7b731, #f39c12); color: #fff; }}
        .rank-2 {{ background: linear-gradient(135deg, #bdc3c7, #95a5a6); color: #fff; }}
        .rank-3 {{ background: linear-gradient(135deg, #e67e22, #d35400); color: #fff; }}
        .rank-other {{ background: rgba(255,255,255,0.1); color: #888; }}
        .category-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }}
        .category-card {{
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px;
            padding: 24px;
            text-align: center;
            transition: all 0.4s;
            cursor: pointer;
        }}
        .category-card:hover {{
            transform: translateY(-4px);
            border-color: rgba(100,100,255,0.3);
            box-shadow: 0 12px 30px rgba(0,0,0,0.3);
            background: rgba(255,255,255,0.08);
        }}
        .category-card .icon {{
            font-size: 48px;
            margin-bottom: 12px;
        }}
        .category-card h3 {{
            font-size: 16px;
            margin-bottom: 6px;
            color: #ddd;
        }}
        .category-card p {{
            font-size: 12px;
            color: #777;
        }}
        .quiz-question {{
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 24px;
            line-height: 1.5;
        }}
        .quiz-option {{
            display: block;
            width: 100%;
            padding: 16px 20px;
            margin-bottom: 12px;
            background: rgba(255,255,255,0.05);
            border: 2px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            color: #ddd;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s;
            text-align: left;
        }}
        .quiz-option:hover {{
            border-color: #667eea;
            background: rgba(102,126,234,0.1);
        }}
        .quiz-option.selected {{
            border-color: #667eea;
            background: rgba(102,126,234,0.2);
        }}
        .quiz-option.correct {{
            border-color: #38ef7d;
            background: rgba(56,239,125,0.15);
        }}
        .quiz-option.wrong {{
            border-color: #ff6b6b;
            background: rgba(255,107,107,0.15);
        }}
        .progress-bar {{
            width: 100%;
            height: 6px;
            background: rgba(255,255,255,0.1);
            border-radius: 3px;
            overflow: hidden;
            margin-bottom: 24px;
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(135deg, #667eea, #764ba2);
            transition: width 0.5s;
        }}
        .result-score {{
            font-size: 64px;
            font-weight: 900;
            background: linear-gradient(135deg, #667eea, #38ef7d);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .result-stats {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin: 24px 0;
        }}
        .stat-box {{
            background: rgba(255,255,255,0.05);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }}
        .stat-number {{
            font-size: 28px;
            font-weight: 800;
            color: #fff;
        }}
        .stat-label {{
            font-size: 12px;
            color: #888;
            margin-top: 4px;
        }}
        .footer {{
            text-align: center;
            padding: 30px 0;
            color: #555;
            font-size: 13px;
            border-top: 1px solid rgba(255,255,255,0.05);
            margin-top: 40px;
        }}
        .footer a {{ color: #667eea; text-decoration: none; }}
        @media (max-width: 600px) {{
            .container {{ padding: 12px; }}
            .logo {{ font-size: 22px; }}
            h1 {{ font-size: 24px; }}
            .result-stats {{ grid-template-columns: 1fr; }}
            .user-info {{ width: 100%; justify-content: center; }}
            header .container {{ justify-content: center; text-align: center; }}
        }}
        .btn-group {{ display: flex; gap: 12px; flex-wrap: wrap; justify-content: center; }}
        .history-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        .history-table th {{
            padding: 10px 14px;
            text-align: left;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #666;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .history-table td {{
            padding: 12px 14px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}
        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
        }}
        .badge-gold {{ background: rgba(247,183,49,0.2); color: #f7b731; }}
        .badge-silver {{ background: rgba(189,195,199,0.2); color: #bdc3c7; }}
        .badge-bronze {{ background: rgba(230,126,34,0.2); color: #e67e22; }}
        .scroll-x {{ overflow-x: auto; }}
    </style>
    {extra_head}
</head>
<body>
    <header>
        <div class="container">
            <a href="/" class="logo">🧠 Mega Quiz <span>Teste seus conhecimentos!</span></a>
            {user_info}
        </div>
    </header>
    <main>
        <div class="container">
            {content}
        </div>
    </main>
    <footer class="footer">
        <div class="container">
            <p>© 2024 Mega Quiz - Todos os direitos reservados</p>
            <p>Desenvolvido por <a href="mailto:ezetecf@gmail.com">ezetecf@gmail.com</a></p>
        </div>
    </footer>
</body>
</html>'''
        return html

    # ============ ROUTES ============

    def do_GET(self):
        try:
            self._handle_get()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"Erro interno: {e}".encode("utf-8"))

    def _handle_get(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)

        user = self.get_session_user()

        if path == "/":
            self.handle_home(user)
        elif path == "/login":
            self.handle_login_page(user)
        elif path == "/registrar":
            self.handle_register_page(user)
        elif path == "/logout":
            self.handle_logout()
        elif path == "/perfil":
            self.handle_profile(user)
        elif path == "/admin" or path == "/admin/usuarios":
            self.handle_admin_users(user)
        elif path == "/quiz":
            self.handle_quiz_page(user, params)
        elif path == "/resultado":
            self.handle_result_page(user, params)
        elif path.startswith("/static/"):
            self.handle_static(path)
        else:
            self.send_html(self.page("Página não encontrada", "<h1>404 - Página não encontrada</h1>", user), 404)

    def do_POST(self):
        try:
            self._handle_post()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8"))

    def _handle_post(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/login":
            self.handle_login_post()
        elif path == "/registrar":
            self.handle_register_post()
        elif path == "/admin/deletar_usuario":
            self.handle_admin_delete_user()
        elif path == "/admin/recadastrar":
            self.handle_admin_recadastrar()
        elif path == "/salvar_resultado":
            self.handle_save_result()
        elif path == "/enviar_feedback":
            self.handle_feedback()
        else:
            self.send_json_response({"error": "Rota não encontrada"}, 404)

    # ============ HOME ============

    def handle_home(self, user):
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT u.first_name, u.last_name, SUM(s.score) as total_score
            FROM scores s
            JOIN users u ON s.user_id = u.id
            GROUP BY s.user_id
            ORDER BY total_score DESC
            LIMIT 5
        ''')
        top_users = cursor.fetchall()
        conn.close()

        leaderboard_rows = ""
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(top_users):
            rank_class = f"rank-{i+1}" if i < 3 else "rank-other"
            medal = medals[i] if i < 3 else f"<span class='rank {rank_class}'>#{i+1}</span>"
            leaderboard_rows += f'''
            <tr>
                <td>{medal}</td>
                <td><strong>{escape(row["first_name"])}</strong></td>
                <td style="color: #667eea; font-weight: 700;">{row["total_score"]} pts</td>
            </tr>
            '''

        if not leaderboard_rows:
            leaderboard_rows = '<tr><td colspan="3" style="text-align:center; padding:30px; color:#666;">Nenhum jogador ainda. Seja o primeiro!</td></tr>'

        categories_html = ""
        for cat in CATEGORY_KEYS:
            qcount = len(QUESTIONS[cat])
            categories_html += f'''
            <a href="/quiz?cat={quote(cat)}" class="category-card" style="text-decoration:none; display:block;">
                <div class="icon">{cat.split()[0]}</div>
                <h3>{escape(cat)}</h3>
                <p>{qcount} perguntas</p>
            </a>
            '''
        categories_html += f'''
            <a href="/quiz?cat=surpresa" class="category-card" style="text-decoration:none; display:block; border-color:rgba(255,215,0,0.3); background:rgba(255,215,0,0.05);">
                <div class="icon">🎲</div>
                <h3>Surpresa Mista</h3>
                <p>Todas as categorias misturadas!</p>
            </a>
            '''

        welcome = ""
        if user:
            welcome = f'''
            <div class="card" style="margin-bottom:30px;">
                <h2>Bem-vindo de volta, {escape(user["first_name"])}! 🎉</h2>
                <p>Escolha uma categoria abaixo para começar a jogar e testar seus conhecimentos!</p>
            </div>
            '''
        else:
            welcome = f'''
            <div class="card" style="margin-bottom:30px;">
                <h2>Bem-vindo ao Mega Quiz! 🧠</h2>
                <p>Teste seus conhecimentos em diversas áreas: Bíblia, Conhecimentos Gerais, Idiomas (Inglês, Espanhol, Coreano), Informática e Programação Fullstack!</p>
                <div class="btn-group mt-20">
                    <a href="/registrar" class="btn btn-primary-lg">📝 Cadastre-se</a>
                    <a href="/login" class="btn btn-outline">🔑 Entrar</a>
                </div>
            </div>
            '''

        content = f'''
        {welcome}

        <div class="card" style="margin-bottom:30px;">
            <h2>🏆 Ranking Top 5</h2>
            <div class="scroll-x">
                <table class="leaderboard">
                    <thead>
                        <tr>
                            <th>Posição</th>
                            <th>Jogador</th>
                            <th>Pontuação</th>
                        </tr>
                    </thead>
                    <tbody>
                        {leaderboard_rows}
                    </tbody>
                </table>
            </div>
        </div>

        <h2>📚 Categorias de Perguntas</h2>
        <div class="category-grid">
            {categories_html}
        </div>
        '''

        self.send_html(self.page("Início", content, user))

    # ============ LOGIN ============

    def handle_login_page(self, user):
        if user:
            self.redirect("/")
            return
        content = self.login_form()
        self.send_html(self.page("Entrar", content, user))

    def handle_login_post(self):
        data = self.parse_post_data()
        username = data.get("username", [""])[0].strip()
        password = data.get("password", [""])[0]

        if not username or not password:
            content = self.alert_error("Preencha nome de usuario e senha.") + self.login_form()
            self.send_html(self.page("Entrar", content))
            return

        conn = get_db()
        cursor = conn.cursor()
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute("SELECT * FROM users WHERE first_name = ? AND password = ?", (username, password_hash))
        user_row = cursor.fetchone()
        conn.close()

        if user_row:
            token = create_session(user_row["id"], user_row["first_name"], user_row["last_name"], user_row["email"], user_row["is_master"])
            self.send_response(302)
            self.set_cookie("session", token)
            self.send_header("Location", "/")
            self.end_headers()
        else:
            content = self.alert_error("Usuario ou senha incorretos.") + self.login_form()
            self.send_html(self.page("Entrar", content))

    def login_form(self):
        return '''
        <div class="card" style="max-width:460px; margin:0 auto;">
            <h1 class="text-center">🔑 Entrar</h1>
            <form method="POST" action="/login">
                <div class="form-group">
                    <label>Nome de Usuario</label>
                    <input type="text" name="username" placeholder="Seu nome de usuario" required>
                </div>
                <div class="form-group">
                    <label>Senha</label>
                    <input type="password" name="password" placeholder="Sua senha" required>
                </div>
                <button type="submit" class="btn btn-primary-lg" style="width:100%;">Entrar</button>
                <p class="text-center mt-20" style="color:#888;">Nao tem conta? <a href="/registrar" style="color:#667eea;">Cadastre-se</a></p>
            </form>
        </div>
        '''

    # ============ REGISTER ============

    def handle_register_page(self, user):
        if user:
            self.redirect("/")
            return
        content = self.register_form()
        self.send_html(self.page("Cadastro", content, user))

    def handle_register_post(self):
        data = self.parse_post_data()
        username = data.get("username", [""])[0].strip()
        password = data.get("password", [""])[0]

        if not username or not password:
            content = self.alert_error("Preencha nome de usuario e senha.") + self.register_form()
            self.send_html(self.page("Cadastro", content))
            return

        if len(password) < 6:
            content = self.alert_error("Senha deve ter no minimo 6 caracteres.") + self.register_form()
            self.send_html(self.page("Cadastro", content))
            return

        if len(username) < 3:
            content = self.alert_error("Nome de usuario deve ter no minimo 3 caracteres.") + self.register_form()
            self.send_html(self.page("Cadastro", content))
            return

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, first_name FROM users WHERE first_name = ?", (username,))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            suggestion = username + str(random.randint(10, 999))
            content = self.alert_error(
                f"Usuario '{username}' ja existe. Tente adicionar um numero: <strong>{suggestion}</strong>"
            ) + self.register_form(suggestion)
            self.send_html(self.page("Cadastro", content))
            return

        password_hash = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute("INSERT INTO users (first_name, last_name, email, password) VALUES (?, ?, ?, ?)",
                       (username, username, f"{username}@local", password_hash))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()

        token = create_session(user_id, username, username, f"{username}@local")
        self.send_response(302)
        self.set_cookie("session", token)
        self.send_header("Location", "/")
        self.end_headers()

    def register_form(self, suggested=""):
        val = f'value="{escape(suggested)}" ' if suggested else ""
        return f'''
        <div class="card" style="max-width:480px; margin:0 auto;">
            <h1 class="text-center">📝 Cadastro</h1>
            <form method="POST" action="/registrar">
                <div class="form-group">
                    <label>Nome de Usuario</label>
                    <input type="text" name="username" placeholder="Ex: Joao123" {val}required>
                </div>
                <div class="form-group">
                    <label>Senha (minimo 6 caracteres)</label>
                    <input type="password" name="password" placeholder="Sua senha" minlength="6" required>
                </div>
                <button type="submit" class="btn btn-primary-lg" style="width:100%;">Criar Conta</button>
                <p class="text-center mt-20" style="color:#888;">Ja tem conta? <a href="/login" style="color:#667eea;">Entrar</a></p>
            </form>
        </div>
        '''

    # ============ LOGOUT ============

    def handle_logout(self):
        token = self.get_cookie("session")
        clear_session(token)
        self.send_response(302)
        self.delete_cookie("session")
        self.send_header("Location", "/")
        self.end_headers()

    # ============ PROFILE ============

    def handle_profile(self, user):
        if not user:
            self.redirect("/login")
            return

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT category, score, total, date FROM scores
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT 50
        ''', (user["user_id"],))
        history = cursor.fetchall()

        cursor.execute('''
            SELECT category, SUM(score) as total_cat, COUNT(*) as games
            FROM scores WHERE user_id = ?
            GROUP BY category ORDER BY total_cat DESC
        ''', (user["user_id"],))
        cats = cursor.fetchall()

        cursor.execute('''
            SELECT SUM(score) as total, COUNT(*) as games
            FROM scores WHERE user_id = ?
        ''', (user["user_id"],))
        stats = cursor.fetchone()

        conn.close()

        history_rows = ""
        for row in history:
            pct = round((row["score"] / row["total"]) * 100) if row["total"] > 0 else 0
            cat_display = "🎲 Surpresa Mista" if row["category"] == "surpresa" else escape(row["category"])
            history_rows += f'''
            <tr>
                <td>{cat_display}</td>
                <td>{row["score"]}/{row["total"]}</td>
                <td>{pct}%</td>
                <td>{row["date"]}</td>
            </tr>
            '''

        if not history_rows:
            history_rows = '<tr><td colspan="4" style="text-align:center; padding:20px; color:#666;">Nenhum jogo ainda. Vamos jogar?</td></tr>'

        cat_stats = ""
        for row in cats:
            cat_stats += f'<div class="stat-box"><div class="stat-number">{row["total_cat"]}</div><div class="stat-label">{escape(row["category"])} ({row["games"]} jogos)</div></div>'

        total_score = stats["total"] if stats["total"] else 0
        total_games = stats["games"] if stats["games"] else 0

        content = f'''
        <div class="card" style="margin-bottom:24px;">
            <h1>👤 Perfil de {escape(user["first_name"])}</h1>
            <div class="result-stats">
                <div class="stat-box">
                    <div class="stat-number">{total_score}</div>
                    <div class="stat-label">Pontos Totais</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{total_games}</div>
                    <div class="stat-label">Jogos Realizados</div>
                </div>
                <div class="stat-box">
                    <div class="stat-number">{round(total_score/max(total_games,1),1)}</div>
                    <div class="stat-label">Média por Jogo</div>
                </div>
            </div>
        </div>

        <div class="card" style="margin-bottom:24px;">
            <h2>📊 Desempenho por Categoria</h2>
            <div class="result-stats">
                {cat_stats}
            </div>
        </div>

        <div class="card">
            <h2>📋 Histórico de Partidas</h2>
            <div class="scroll-x">
                <table class="history-table">
                    <thead>
                        <tr>
                            <th>Categoria</th>
                            <th>Pontos</th>
                            <th>Aproveitamento</th>
                            <th>Data</th>
                        </tr>
                    </thead>
                    <tbody>
                        {history_rows}
                    </tbody>
                </table>
            </div>
        </div>
        '''

        self.send_html(self.page("Meu Perfil", content, user))

    # ============ ADMIN ============

    def _require_master(self, user):
        if not user or not user.get("is_master"):
            return False
        return True

    def handle_admin_users(self, user):
        if not self._require_master(user):
            self.redirect("/login")
            return

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, first_name, last_name, email, is_master, created_at FROM users ORDER BY id")
        rows = cursor.fetchall()
        conn.close()

        rows_html = ""
        for r in rows:
            is_master_badge = ' <span style="color:#dc3545;font-size:11px;">👑 Mestre</span>' if r["is_master"] else ""
            rows_html += f'''
            <tr>
                <td>{r["id"]}</td>
                <td>{escape(r["first_name"])}{is_master_badge}</td>
                <td>{r["created_at"]}</td>
                <td>
                    <form method="POST" action="/admin/recadastrar" style="display:inline-block;">
                        <input type="hidden" name="user_id" value="{r["id"]}">
                        <input type="password" name="new_password" placeholder="Nova senha" required style="padding:4px 8px;border:1px solid #444;border-radius:4px;background:#2a2a3a;color:#fff;font-size:12px;">
                        <button type="submit" class="btn-small" style="background:#f7b731;color:#1a1a2e;">Recadastrar</button>
                    </form>
                </td>
                <td>
                    <form method="POST" action="/admin/deletar_usuario" onsubmit="return confirm('Deletar usuario {escape(r["first_name"])}? Esta acao nao pode ser desfeita.');">
                        <input type="hidden" name="user_id" value="{r["id"]}">
                        <button type="submit" class="btn-small btn-danger">Deletar</button>
                    </form>
                </td>
            </tr>
            '''

        if not rows_html:
            rows_html = '<tr><td colspan="5" style="text-align:center;padding:20px;color:#666;">Nenhum usuario encontrado.</td></tr>'

        content = f'''
        <div class="card">
            <h2>👑 Painel Administrativo</h2>
            <p style="color:#888;margin-bottom:20px;">Gerenciar usuarios: deletar ou recadastrar senha.</p>
            <div class="scroll-x">
                <table class="history-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Usuario</th>
                            <th>Criado em</th>
                            <th>Nova Senha</th>
                            <th>Acao</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
            <div style="margin-top:20px;">
                <a href="/" class="btn btn-outline">Voltar ao Inicio</a>
            </div>
        </div>
        '''

        self.send_html(self.page("Admin - Usuarios", content, user))

    def handle_admin_delete_user(self):
        user = self.get_session_user()
        if not self._require_master(user):
            self.send_json_response({"error": "Nao autorizado"}, 403)
            return

        data = self.parse_post_data()
        user_id = data.get("user_id", [""])[0]
        if not user_id:
            self.redirect("/admin/usuarios")
            return

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT is_master FROM users WHERE id = ?", (user_id,))
        target = cursor.fetchone()
        if target and target["is_master"]:
            conn.close()
            self.send_html(self.page("Erro", self.alert_error("Nao e possivel deletar outro usuario mestre."), user))
            return

        cursor.execute("DELETE FROM scores WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM feedback WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()

        self.redirect("/admin/usuarios")

    def handle_admin_recadastrar(self):
        user = self.get_session_user()
        if not self._require_master(user):
            self.send_json_response({"error": "Nao autorizado"}, 403)
            return

        data = self.parse_post_data()
        user_id = data.get("user_id", [""])[0]
        new_password = data.get("new_password", [""])[0]

        if not user_id or len(new_password) < 6:
            self.redirect("/admin/usuarios")
            return

        password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password = ? WHERE id = ?", (password_hash, user_id))
        conn.commit()
        conn.close()

        self.redirect("/admin/usuarios")

    # ============ QUIZ ============

    def handle_quiz_page(self, user, params):
        if not user:
            self.redirect("/login")
            return

        cat_name = params.get("cat", [None])[0]
        diff = params.get("diff", ["all"])[0]
        started = params.get("start", [None])[0]

        if cat_name == "surpresa":
            display_name = "🎲 Surpresa Mista"
        elif cat_name in QUESTIONS:
            display_name = cat_name
        else:
            content = self.alert_error("Categoria invalida. Escolha uma categoria disponivel.")
            content += '<a href="/" class="btn btn-primary-lg">Voltar ao inicio</a>'
            self.send_html(self.page("Erro", content, user))
            return

        # ── PRE-GAME: show difficulty selector + start button ──
        if started != "1":
            diff_buttons = ""
            labels = {"all": "Todas", "0": "Facil", "1": "Medio", "2": "Dificil"}
            for val, label in labels.items():
                active = "btn-primary-lg" if diff == val else "btn-outline"
                diff_buttons += f'<a href="/quiz?cat={quote(cat_name)}&diff={val}" class="btn {active}" style="font-size:12px; padding:6px 14px;">{label}</a>'

            content = f'''
            <div class="card text-center">
                <h2>{escape(display_name)}</h2>
                <p style="color:#888; margin:20px 0;">Escolha a dificuldade e clique em <strong>Iniciar Jogo</strong>.</p>
                <div style="margin-bottom:24px;">
                    <span style="color:#888;font-size:12px;display:block;margin-bottom:8px;">Dificuldade:</span>
                    {diff_buttons}
                </div>
                <a href="/quiz?cat={quote(cat_name)}&diff={diff}&start=1" class="btn btn-primary-lg" style="font-size:18px; padding:14px 40px;">🎯 Iniciar Jogo</a>
                <div style="margin-top:16px;">
                    <a href="/" class="btn btn-outline">Voltar ao inicio</a>
                </div>
            </div>
            '''
            self.send_html(self.page(f"Quiz: {cat_name}", content, user))
            return

        # ── GAME STARTED ──
        if cat_name == "surpresa":
            pool = []
            for c in CATEGORY_KEYS:
                pool.extend(QUESTIONS[c])
            selected = random.sample(pool, min(10, len(pool)))
        else:
            pool = QUESTIONS[cat_name]
            if diff and diff in ("0","1","2"):
                filtered = [q for q in pool if q.get("d", 0) == int(diff)]
                if len(filtered) < 10:
                    filtered = pool
                selected = random.sample(filtered, min(10, len(filtered)))
            else:
                selected = random.sample(pool, min(10, len(pool)))

        questions_json = json.dumps(selected, ensure_ascii=False)
        cat_json = json.dumps(cat_name, ensure_ascii=False)
        diff_json = json.dumps(diff, ensure_ascii=False)

        content = f'''
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:10px;">
                <h2 style="margin:0;">{escape(display_name)}</h2>
                <span style="color:#888; font-size:14px;">Questao <span id="q-num">1</span>/10</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="progress" style="width:10%;"></div>
            </div>
            <div id="timer" style="font-size:24px;font-weight:800;text-align:center;margin-bottom:20px;color:#667eea;">⏱️ 30s</div>
            <div id="question-container"></div>
            <div id="result-container" style="display:none;"></div>
        </div>

        <script>
        const questions = {questions_json};
        const category = {cat_json};
        const difficulty = {diff_json};
        let current = 0;
        let answers = [];
        let timer = 30;
        let timerInterval;

        function renderQuestion() {{
            if (current >= questions.length) {{
                showResult();
                return;
            }}
            const q = questions[current];
            document.getElementById("q-num").textContent = current + 1;
            document.getElementById("progress").style.width = ((current + 1) / questions.length * 100) + "%";

            let opts = q.o.map((opt, i) =>
                `<button class="quiz-option" onclick="selectOption(${{i}})">${{String.fromCharCode(65 + i)}}. ${{escapeHtml(opt)}}</button>`
            ).join("");

            const qdiffNames = ["🟢 Facil", "🟡 Medio", "🔴 Dificil"];
            const qdiff = q.d !== undefined ? qdiffNames[q.d] || "" : "";
            document.getElementById("question-container").innerHTML =
                `<div style="text-align:right;font-size:12px;color:#888;margin-bottom:4px;">${{qdiff}}</div>` +
                `<div class="quiz-question">${{escapeHtml(q.q)}}</div>` +
                `<div id="options">${{opts}}</div>`;

            resetTimer();
        }}

        function selectOption(idx) {{
            clearInterval(timerInterval);
            const q = questions[current];
            const opts = document.querySelectorAll(".quiz-option");
            opts.forEach((opt, i) => {{
                opt.disabled = true;
                if (i === q.a) opt.classList.add("correct");
                if (i === idx && idx !== q.a) opt.classList.add("wrong");
            }});
            answers.push({{ selected: idx, correct: q.a, isCorrect: idx === q.a }});
            setTimeout(() => {{ current++; renderQuestion(); }}, 1000);
        }}

        function resetTimer() {{
            clearInterval(timerInterval);
            timer = 30;
            document.getElementById("timer").textContent = "⏱️ " + timer + "s";
            timerInterval = setInterval(() => {{
                timer--;
                document.getElementById("timer").textContent = "⏱️ " + timer + "s";
                if (timer <= 5) document.getElementById("timer").style.color = "#ff6b6b";
                if (timer <= 0) {{
                    clearInterval(timerInterval);
                    const q = questions[current];
                    const opts = document.querySelectorAll(".quiz-option");
                    opts.forEach((opt, i) => {{
                        opt.disabled = true;
                        if (i === q.a) opt.classList.add("correct");
                    }});
                    answers.push({{ selected: -1, correct: q.a, isCorrect: false }});
                    setTimeout(() => {{ current++; renderQuestion(); }}, 1000);
                }}
            }}, 1000);
        }}

        function showResult() {{
            document.getElementById("question-container").style.display = "none";
            document.getElementById("timer").style.display = "none";
            document.getElementById("result-container").style.display = "block";

            const correct = answers.filter(a => a.isCorrect).length;
            const wrong = answers.filter(a => !a.isCorrect).length;
            const pct = Math.round((correct / answers.length) * 100);

            let grade = "";
            if (pct >= 90) grade = "🌟 Excelente! Voce e um genio!";
            else if (pct >= 70) grade = "👏 Muito bom! Continue assim!";
            else if (pct >= 50) grade = "👍 Bom, mas pode melhorar!";
            else grade = "📚 Estude mais e tente novamente!";

            const diffNames = ["🟢 Facil", "🟡 Medio", "🔴 Dificil"];
            let review = answers.map((a, i) => {{
                const q = questions[i];
                const status = a.isCorrect ? "✅" : "❌";
                const diff = q.d !== undefined ? diffNames[q.d] || "" : "";
                return `<tr><td>${{status}}</td><td>${{escapeHtml(q.q)}}</td><td>${{escapeHtml(q.o[a.correct])}}</td><td>${{diff}}</td></tr>`;
            }}).join("");

            document.getElementById("result-container").innerHTML =
                `<div class="text-center">
                    <div class="result-score">${{correct}}/${{answers.length}}</div>
                    <div style="font-size:20px; margin:8px 0; color:#ccc;">${{pct}}% de acerto</div>
                    <div style="font-size:18px; margin-bottom:20px; color:#aaa;">${{grade}}</div>
                    <div class="result-stats">
                        <div class="stat-box"><div class="stat-number" style="color:#38ef7d;">${{correct}}</div><div class="stat-label">Acertos</div></div>
                        <div class="stat-box"><div class="stat-number" style="color:#ff6b6b;">${{wrong}}</div><div class="stat-label">Erros</div></div>
                        <div class="stat-box"><div class="stat-number" style="color:#f7b731;">${{pct}}%</div><div class="stat-label">Aproveitamento</div></div>
                    </div>
                    <div class="btn-group mt-20">
                        <a href="/quiz?cat=${{encodeURIComponent(category)}}&diff=${{encodeURIComponent(difficulty)}}" class="btn btn-primary-lg">🔄 Jogar Novamente</a>
                        <a href="/" class="btn btn-outline">🏠 Voltar ao Inicio</a>
                    </div>
                    <h3 style="margin-top:24px;">📋 Revisao das Respostas</h3>
                    <div class="scroll-x">
                        <table class="history-table">
                            <thead><tr><th>Status</th><th>Pergunta</th><th>Resposta Correta</th><th>Dif.</th></tr></thead>
                            <tbody>${{review}}</tbody>
                        </table>
                    </div>
                </div>`;

            fetch("/salvar_resultado", {{
                method: "POST",
                headers: {{ "Content-Type": "application/x-www-form-urlencoded" }},
                body: "category=" + encodeURIComponent(category) + "&score=" + correct + "&total=" + answers.length
            }});
        }}

        function escapeHtml(text) {{
            const div = document.createElement("div");
            div.textContent = text;
            return div.innerHTML;
        }}

        renderQuestion();
        </script>
        '''

        self.send_html(self.page(f"Quiz: {cat_name}", content, user))

    # ============ SAVE RESULT ============

    def handle_save_result(self):
        user = self.get_session_user()
        if not user:
            self.send_json_response({"error": "Não autorizado"}, 401)
            return

        data = self.parse_post_data()
        category = data.get("category", [""])[0]
        score = int(data.get("score", ["0"])[0])
        total = int(data.get("total", ["0"])[0])

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO scores (user_id, category, score, total) VALUES (?, ?, ?, ?)",
                       (user["user_id"], category, score, total))
        conn.commit()
        conn.close()

        self.send_json_response({"success": True})

    # ============ FEEDBACK ============

    def handle_feedback(self):
        user = self.get_session_user()
        data = self.parse_post_data()
        message = data.get("message", [""])[0].strip()

        if not message:
            self.send_json_response({"error": "Mensagem vazia"}, 400)
            return

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO feedback (user_id, message) VALUES (?, ?)",
                       (user["user_id"] if user else None, message))
        conn.commit()
        conn.close()

        self.send_json_response({"success": True})

    # ============ STATIC ============

    def handle_static(self, path):
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Not found")

    # ============ HELPERS ============

    def alert_error(self, msg):
        return f'<div class="alert alert-error">⚠️ {escape(msg)}</div>'

    def alert_success(self, msg):
        return f'<div class="alert alert-success">✅ {escape(msg)}</div>'


# ==================== MAIN ====================

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║                    MEGA QUIZ - v1.0                         ║")
    print("║         Jogo de Perguntas e Respostas Interativo            ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print("║  Categorias: Bíblicas | Conhecimentos Gerais | Inglês      ║")
    print("║              Espanhol | Coreano | Informática | Fullstack   ║")
    print("╠══════════════════════════════════════════════════════════════╣")
    print("║  Direitos Reservados - ezetecf@gmail.com                   ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("🚀 Inicializando servidor...")

    init_db()
    print("✅ Banco de dados inicializado!")

    class ReusableServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
    server = ReusableServer(("0.0.0.0", PORT), MegaQuizHandler)
    print(f"🌐 Servidor rodando em: http://localhost:{PORT}")
    print()
    print("📱 Acesse pelo navegador e comece a jogar!")
    print()

    def _open_browser():
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{PORT}")
    threading.Thread(target=_open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
        print("👋 Servidor encerrado. Até logo!")
        server.server_close()


if __name__ == "__main__":
    main()
