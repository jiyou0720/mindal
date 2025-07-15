# backend/app.py
import os
from flask import Flask, render_template # render_template 임포트 추가
from flask_pymongo import PyMongo
from dotenv import load_dotenv
from extensions import db
from routes.login_register_routes import auth_bp
from routes.community_routes import community_bp
from routes.diary_routes import diary_bp
from routes.mood_routes import mood_bp
from routes.graph_routes import graph_bp
from routes.admin_routes import admin_bp
from flask_migrate import Migrate

# CLI 명령어를 위한 임포트 추가
import click
from maria_models import User
from werkzeug.security import generate_password_hash
from routes.login_register_routes import generate_numeric_uid

# .env 파일 로드
load_dotenv()

# Flask 앱 초기화 및 템플릿/정적 파일 경로 설정
# 현재 backend/app.py가 있는 위치를 기준으로 frontend 폴더를 찾습니다.
# 예: backend/app.py -> ../frontend/templates
app = Flask(
    __name__,
    template_folder='../frontend/templates',
    static_folder='../frontend/static'
)

app.config["MONGO_URI"] = os.getenv("MONGODB_URI")
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["FLASK_ENV"] = os.getenv("FLASK_ENV")

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("MARIADB_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


db.init_app(app)
migrate = Migrate(app, db)

mongo_instance = PyMongo(app)


# --- API Blueprint 등록 (기존 백엔드 라우트) ---
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(community_bp, url_prefix='/api/community')
app.register_blueprint(diary_bp, url_prefix='/api/diary')
app.register_blueprint(mood_bp, url_prefix='/api/mood')
app.register_blueprint(graph_bp, url_prefix='/api/graph')
app.register_blueprint(admin_bp, url_prefix='/api/admin')


# --- 프론트엔드 HTML 템플릿 렌더링 라우트 (frontend/app.py에서 이동) ---

# --- 프론트엔드 HTML 템플릿 렌더링 라우트 ---

@app.route('/')
def index():
    """메인 랜딩 페이지 (Home)를 렌더링합니다."""
    return render_template('index.html')

@app.route('/ai-chat')
def ai_chat():
    """AI 채팅 페이지를 렌더링합니다."""
    return render_template('ai_chat.html')

@app.route('/diary')
def diary():
    """오늘 일기 페이지를 렌더링합니다."""
    return render_template('diary.html')

@app.route('/keyword')
def keyword():
    """키워드 페이지를 렌더링합니다."""
    return render_template('keyword.html')

@app.route('/my-changes')
def my_changes():
    """나의 변화 페이지를 렌더링합니다."""
    return render_template('my_changes.html')

@app.route('/login')
def login():
    """로그인 페이지를 렌더링합니다."""
    return render_template('login.html')

@app.route('/signup')
def signup():
    """회원가입 페이지를 렌더링합니다."""
    return render_template('signup.html')

@app.route('/forgot-password')
def forgot_password():
    """비밀번호 찾기 페이지를 렌더링합니다."""
    return render_template('forgot_password.html')

# --- 커뮤니티 관련 페이지 라우트 ---

@app.route('/community')
def community_list():
    """게시글 목록 페이지를 렌더링합니다."""
    return render_template('community_list.html')

@app.route('/community/create')
def community_create():
    """새 게시글 작성 페이지를 렌더링합니다."""
    return render_template('community_create.html')

# 게시글 상세 페이지 라우트 (중복 제거 후 하나만 유지)
@app.route('/community/posts/<int:post_id>')
def community_detail(post_id):
    """
    게시글 상세 페이지를 렌더링합니다.
    URL에서 post_id를 받아 JavaScript에서 사용합니다.
    """
    return render_template('community_detail.html', post_id=post_id)

# 게시글 수정 페이지 라우트
@app.route('/community/posts/edit/<int:post_id>')
def edit_post(post_id):
    """
    게시글 수정 페이지를 렌더링합니다.
    URL에서 post_id를 받아 JavaScript에서 해당 게시글을 로드하고 수정합니다.
    """
    return render_template('community_edit.html', post_id=post_id)

# --- CLI 명령어를 위한 부분 (기존 코드 유지) ---
@app.cli.command("create-admin")
@click.argument("email")
@click.argument("password")
@click.argument("username")
def create_admin(email, password, username):
    """관리자 계정을 생성합니다."""
    with app.app_context(): # Flask 애플리케이션 컨텍스트 안에서 DB 접근
        if User.query.filter_by(email=email).first():
            click.echo(f"오류: '{email}' 이메일은 이미 등록되어 있습니다.")
            return
        generated_uid = None
        max_retries = 5
        for _ in range(max_retries):
            temp_uid = generate_numeric_uid()
            if not User.query.filter_by(user_uid=temp_uid).first():
                generated_uid = temp_uid
                break

        if not generated_uid:
            click.echo("오류: 사용자 UID를 생성하지 못했습니다. 다시 시도해주세요.")
            return

        new_admin = User(
            username=username,
            email=email,
            user_uid=generated_uid,
            is_admin=True # 관리자 계정으로 설정
        )
        new_admin.set_password(password)

        db.session.add(new_admin)
        db.session.commit()
        click.echo(f"관리자 계정 '{username}'({email})이 성공적으로 생성되었습니다. UID: {generated_uid}")

if __name__ == '__main__':
    app.run(debug=True) # 개발 모드에서 실행
