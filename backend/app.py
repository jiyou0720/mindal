import os
import logging
import sys
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, g, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# 프로젝트 루트 디렉토리를 Python 경로에 명시적으로 추가
# 이 스크립트가 backend/app.py에 있다고 가정하고,
# 프로젝트 루트는 backend의 부모 디렉토리입니다.
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# .env 파일에서 환경 변수 로드
load_dotenv()

def create_app():
    app = Flask(__name__,
                template_folder='../frontend/templates',
                static_folder='../frontend/static')

    # --- 기본 설정 ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')

    # --- 데이터베이스 설정 ---
    # MariaDB (SQLAlchemy)
    MARIA_USER = os.environ.get("MARIA_USER")
    MARIA_PASSWORD = os.environ.get("MARIA_PASSWORD")
    MARIA_HOST = os.environ.get("MARIA_HOST")
    MARIA_PORT = os.environ.get("MARIA_PORT")
    MARIA_DB = os.environ.get("MARIA_DB")

    app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{MARIA_USER}:{MARIA_PASSWORD}@{MARIA_HOST}:{MARIA_PORT}/{MARIA_DB}?charset=utf8mb4'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ECHO'] = False # SQL 쿼리 로깅 비활성화

    # MongoDB (PyMongo)
    MONGO_URI = os.environ.get("MONGO_URI")
    if not MONGO_URI:
        raise ValueError("No MONGO_URI set for Flask application")
    app.config["MONGO_URI"] = MONGO_URI

    # --- JWT 설정 ---
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY')
    if not app.config['JWT_SECRET_KEY']:
        raise ValueError("No JWT_SECRET_KEY set for Flask application")

    # --- CORS 설정 ---
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # --- 로깅 설정 (터미널 출력 위주로 변경) ---
    # 기존 핸들러 제거 (중복 로깅 방지 및 터미널 출력만 남기기 위함)
    for handler in app.logger.handlers[:]:
        app.logger.removeHandler(handler)
    for handler in logging.getLogger('werkzeug').handlers[:]:
        logging.getLogger('werkzeug').removeHandler(handler)

    # 터미널 출력을 위한 StreamHandler 설정
    stream_handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    stream_handler.setFormatter(formatter)

    # 애플리케이션 로거에 StreamHandler 추가
    app.logger.addHandler(stream_handler)

    # 개발 모드에서는 DEBUG 레벨까지 출력, 운영 모드에서는 INFO
    if app.debug:
        app.logger.setLevel(logging.DEBUG)
    else:
        app.logger.setLevel(logging.INFO)

    app.logger.info('Flask app created')

    # Werkzeug 로거 (HTTP 요청 로깅)에도 StreamHandler 추가
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.addHandler(stream_handler)
    werkzeug_logger.setLevel(logging.INFO) # Werkzeug 로거는 INFO 레벨로 유지


    # --- 확장 초기화 ---
    # backend.extensions 모듈은 이제 sys.path에 추가되었으므로 올바르게 임포트됩니다.
    from backend.extensions import db, migrate, mongo
    db.init_app(app)
    migrate.init_app(app, db)
    mongo.init_app(app)

    # --- 블루프린트 등록 ---
    # API 블루프린트
    from backend.routes.auth_routes import auth_bp
    from backend.routes.admin_routes import admin_bp
    from backend.routes.community_routes import community_bp
    from backend.routes.diary_routes import diary_bp
    from backend.routes.graph_routes import graph_bp
    from backend.routes.mood_routes import mood_bp
    from backend.routes.dashboard_routes import dashboard_bp
    from backend.routes.chat_routes import chat_bp
    from backend.routes.inquiry_routes import inquiry_bp
    from backend.routes.psych_test_routes import psych_test_bp # NEW: 심리 테스트 블루프린트 임포트

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(community_bp, url_prefix='/api/community')
    app.register_blueprint(diary_bp, url_prefix='/api/diary')
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(mood_bp, url_prefix='/api/mood')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(inquiry_bp, url_prefix='/api/inquiry')
    app.register_blueprint(psych_test_bp, url_prefix='/api/psych_test') # NEW: 심리 테스트 블루프린트 등록


    # --- 전역 컨텍스트 및 에러 핸들러 ---
    @app.errorhandler(404)
    def not_found_error(error):
        app.logger.warning(f"404 Not Found: {request.path}")
        if request.path.startswith('/api/'):
            return jsonify({"error": "Not Found", "message": "API endpoint not found"}), 404
        return render_template('404.html'), 404

    @app.errorhandler(Exception)
    def handle_exception(e):
        app.logger.error(f"An unhandled exception occurred: {e}", exc_info=True)
        if request.path.startswith('/api/'):
            return jsonify({"error": "Internal Server Error", "message": "An unexpected error occurred"}), 500
        # 500.html 대신 존재하는 404.html을 사용합니다.
        return render_template('404.html', error_message=str(e)), 500

    # ----------------------------------------------------------------
    # Frontend Routes (HTML Rendering)
    # ----------------------------------------------------------------

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/login')
    def login():
        return render_template('login.html')

    @app.route('/signup')
    def signup():
        return render_template('signup.html')

    @app.route('/forgot_password')
    def forgot_password():
        return render_template('forgot_password.html')

    @app.route('/my_page')
    def my_page():
        return render_template('my_page.html')

    @app.route('/edit_profile')
    def edit_profile():
        return render_template('edit_profile.html')

    @app.route('/my_changes')
    def my_changes():
        return render_template('my_changes.html')

    @app.route('/diary')
    def diary():
        return render_template('diary.html')

    @app.route('/keyword')
    def keyword():
        return render_template('keyword.html')

    @app.route('/ai_chat')
    def ai_chat():
        return render_template('ai_chat.html')

    # --- Community Routes ---
    @app.route('/community_list')
    def community_list():
        return render_template('community_list.html')

    @app.route('/community/create')
    def community_create():
        return render_template('community_create.html')

    @app.route('/community/<int:post_id>')
    def community_detail(post_id):
        return render_template('community_detail.html', post_id=post_id)

    @app.route('/community/edit/<int:post_id>')
    def community_edit(post_id):
        # community_edit.html에서 url_for('community') 대신 url_for('community_list')를 사용해야 합니다.
        # 이 부분은 HTML 템플릿 파일 자체에서 수정되어야 합니다.
        # 여기서는 라우팅 정의에 대한 변경은 없지만, 템플릿에서 오류가 발생하고 있음을 인지합니다.
        return render_template('community_edit.html', post_id=post_id)

    @app.route('/inquiry')
    def inquiry():
        return render_template('inquiry.html')

    # --- NEW: Psych Test Routes ---
    @app.route('/psych_test')
    def psych_test_list():
        return render_template('psych_test_list.html')

    @app.route('/psych_test/<string:test_id>')
    def psych_test_take(test_id):
        return render_template('psych_test_take.html', test_id=test_id)

    @app.route('/psych_test/result/<string:result_id>')
    def psych_test_result(result_id):
        return render_template('psych_test_result.html', result_id=result_id)

    # --- Admin Routes ---
    @app.route('/admin/dashboard')
    def admin_dashboard():
        return render_template('admin_dashboard.html')

    @app.route('/admin/user_management')
    def user_management():
        return render_template('user_management.html')

    @app.route('/admin/menu_management')
    def menu_management():
        return render_template('menu_management.html')

    @app.route('/admin/role_menu_assignment')
    def role_menu_assignment():
        return render_template('role_menu_assignment.html')

    @app.route('/admin/notice_management')
    def notice_management():
        return render_template('notice_management.html')

    @app.route('/admin/db_management')
    def db_management():
        return render_template('db_management.html')

    @app.route('/admin/post_management')
    def post_management():
        return render_template('post_management.html')

    @app.route('/admin/cms_management')
    def cms_management():
        return render_template('cms_management.html')

    @app.route('/admin/data_analytics')
    def data_analytics():
        return render_template('data_analytics.html')

    @app.route('/admin/chatbot_feedback')
    def chatbot_feedback():
        # chatbot_feedback.html 템플릿 파일이 frontend/templates에 있는지 확인해주세요.
        # 만약 없다면, 이 라우트에서 TemplateNotFound 오류가 발생할 수 있습니다.
        return render_template('chatbot_feedback.html')

    @app.route('/admin/inquiry_management')
    def admin_inquiry_management():
        return render_template('admin_inquiry_management.html')

    # --- Error Page Route ---
    @app.route('/404_page')
    def not_found_page():
        return render_template('404.html')

    return app

# uWSGI 또는 다른 WSGI 서버에서 실행할 때를 위한 app 인스턴스
app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)