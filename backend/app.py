import os
import sys
from flask import Flask, render_template, g, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
import logging
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse

# --- 경로 설정 ---
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

load_dotenv(os.path.join(project_root, '.env'))

def create_app(test_config=None):
    app = Flask(__name__,
                template_folder=os.path.join(project_root, 'frontend', 'templates'),
                static_folder=os.path.join(project_root, 'frontend', 'static'))

    # --- 로깅 설정 ---
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/mindbridge.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('MindBridge startup')

    # --- 기본 설정 ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY')
    
    if test_config:
        app.config.from_mapping(test_config)

    # --- 데이터베이스 설정 ---
    print(">>> 데이터베이스 설정을 시작합니다...")
    # MariaDB (MySQL)
    mysql_url = os.environ.get("MYSQL_URL")
    if not mysql_url:
        MYSQL_USER = os.environ.get("MYSQL_USER")
        MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD")
        MYSQL_HOST = os.environ.get("MYSQL_HOST")
        MYSQL_PORT = os.environ.get("MYSQL_PORT")
        MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE")
        mysql_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    
    app.config['SQLALCHEMY_DATABASE_URI'] = mysql_url.replace('mysql://', 'mysql+pymysql://', 1) if mysql_url.startswith('mysql://') else mysql_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    print(f"INFO: MariaDB(MySQL) URI: {app.config['SQLALCHEMY_DATABASE_URI'][:30]}...")

    # MongoDB
    mongo_uri = os.environ.get("MONGO_URL") or os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URI")
    app.config["MONGO_URI"] = mongo_uri
    
    db_name = None
    if mongo_uri:
        try:
            parsed_uri = urlparse(mongo_uri)
            db_name = parsed_uri.path.lstrip('/')
        except Exception:
            db_name = None
    
    if not db_name:
        db_name = 'mindbridge_db'
        print("INFO: MongoDB 데이터베이스 이름을 URI에서 찾을 수 없습니다. 기본값 'mindbridge_db'을 사용합니다.")

    app.config["MONGO_DBNAME"] = db_name
    print(f"INFO: MongoDB URI: {str(mongo_uri)[:30]}...")
    print(f"INFO: MongoDB DBNAME: {db_name}")

    print(">>> 데이터베이스 설정 완료.")
    
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}})

    # --- Flask 확장 프로그램 초기화 ---
    from backend.extensions import db, mongo, migrate, jwt, bcrypt
    db.init_app(app)
    mongo.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    bcrypt.init_app(app)

    # --- API 블루프린트 등록 ---
    from backend.routes.auth_routes import auth_bp
    from backend.routes.diary_routes import diary_bp
    from backend.routes.community_routes import community_bp
    from backend.routes.admin_routes import admin_bp
    from backend.routes.dashboard_routes import dashboard_bp
    from backend.routes.graph_routes import graph_bp
    from backend.routes.inquiry_routes import inquiry_bp
    from backend.routes.psych_test_routes import psych_test_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(diary_bp, url_prefix='/api/diary')
    app.register_blueprint(community_bp, url_prefix='/api/community')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(graph_bp, url_prefix='/api/graph')
    app.register_blueprint(inquiry_bp, url_prefix='/api/inquiry')
    app.register_blueprint(psych_test_bp, url_prefix='/api/psych_test')

    # --- CLI 명령어 등록 ---
    @app.cli.command("init-db")
    def init_db_command():
        """데이터베이스를 초기화합니다."""
        print("--- [CLI] 데이터베이스 초기화 시작 ---")
        from backend.initialize_roles_and_admin import initialize_database
        from backend.initialize_menus import initialize_menus
        initialize_database()
        initialize_menus()
        print("--- [CLI] 데이터베이스 초기화 완료 ---")

    # --- HTML 페이지 렌더링 라우트 ---
    @app.route('/', endpoint='index')
    def index(): return render_template('index.html')
    
    @app.route('/login', endpoint='login')
    def login_page(): return render_template('login.html')

    @app.route('/signup', endpoint='signup')
    def signup_page(): return render_template('signup.html')

    @app.route('/profile', endpoint='profile')
    def profile_page(): return render_template('profile.html')

    @app.route('/community_list', endpoint='community_list')
    def community_list_page(): return render_template('community_list.html')

    @app.route('/post_detail/<int:post_id>', endpoint='post_detail')
    def post_detail_page(post_id): return render_template('post_detail.html')

    @app.route('/post_editor', endpoint='post_editor')
    def post_editor_page(): return render_template('post_editor.html')

    @app.route('/diary', endpoint='diary')
    def diary_page(): return render_template('diary.html')

    @app.route('/ai_chat', endpoint='ai_chat')
    def ai_chat_page(): return render_template('ai_chat.html')

    @app.route('/my_changes', endpoint='my_changes')
    def my_changes_page(): return render_template('my_changes.html')
    
    @app.route('/inquiry', endpoint='inquiry')
    def inquiry_page(): return render_template('inquiry.html')
    
    @app.route('/psych_test', endpoint='psych_test')
    def psych_test_page(): return render_template('psych_test.html')

    # Admin pages
    @app.route('/admin/dashboard', endpoint='admin_dashboard')
    def admin_dashboard_page(): return render_template('admin_dashboard.html')

    @app.route('/admin/user_management', endpoint='user_management')
    def user_management_page(): return render_template('user_management.html')

    @app.route('/admin/menu_management', endpoint='menu_management')
    def menu_management_page(): return render_template('menu_management.html')
    
    @app.route('/admin/role_menu_assignment', endpoint='role_menu_assignment')
    def role_menu_assignment_page(): return render_template('role_menu_assignment.html')

    @app.route('/admin/notice_management', endpoint='notice_management')
    def notice_management_page(): return render_template('notice_management.html')

    @app.route('/admin/db_management', endpoint='db_management')
    def db_management_page(): return render_template('db_management.html')

    @app.route('/admin/post_management', endpoint='post_management')
    def post_management_page(): return render_template('post_management.html')

    @app.route('/admin/cms_management', endpoint='cms_management')
    def cms_management_page(): return render_template('cms_management.html')

    @app.route('/admin/data_analytics', endpoint='data_analytics')
    def data_analytics_page(): return render_template('data_analytics.html')

    @app.route('/admin/chatbot_feedback', endpoint='chatbot_feedback')
    def chatbot_feedback_page(): return render_template('chatbot_feedback.html')

    @app.route('/admin/inquiry_management', endpoint='admin_inquiry_management')
    def admin_inquiry_management_page(): return render_template('admin_inquiry_management.html')
    
    # --- 에러 핸들러 ---
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    return app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

