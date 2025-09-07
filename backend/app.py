import os
import sys
from flask import Flask, render_template
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

# --- 경로 설정 ---
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 로컬 개발을 위해 .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

# --- 애플리케이션 팩토리 함수 ---
def create_app(test_config=None):
    """
    Flask 애플리케이션 인스턴스를 생성하고 설정합니다.
    """
    app = Flask(__name__,
                template_folder='../frontend/templates',
                static_folder='../frontend/static')

    # --- 기본 설정 ---
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'a_very_secret_default_key_for_dev'),
        JWT_SECRET_KEY=os.environ.get('JWT_SECRET_KEY')
    )
    
    if test_config:
        app.config.from_mapping(test_config)

    # --- 데이터베이스 설정 (Railway 호환) ---
    print(">>> 데이터베이스 설정을 시작합니다...")
    mysql_url = os.environ.get("MYSQL_URL")
    mongo_url = os.environ.get("MONGO_URL") or os.environ.get("MONGODB_URI")

    if not mysql_url:
        print("INFO: Railway MYSQL_URL이 없습니다. 로컬 .env 설정을 시도합니다.")
        MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE = (
            os.environ.get("MYSQL_USER"), os.environ.get("MYSQL_PASSWORD"),
            os.environ.get("MYSQL_HOST"), os.environ.get("MYSQL_PORT"),
            os.environ.get("MYSQL_DATABASE")
        )
        if all([MYSQL_USER, MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE]):
            password_segment = f":{MYSQL_PASSWORD}" if MYSQL_PASSWORD else ""
            mysql_url = f"mysql+pymysql://{MYSQL_USER}{password_segment}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    
    if not mongo_url:
        print("INFO: Railway MONGO_URL이 없습니다. 로컬 .env 설정을 시도합니다.")
        mongo_url = os.environ.get("MONGO_URI")

    if not mongo_url:
        raise ValueError("MongoDB URI를 찾을 수 없습니다. MONGO_URL 또는 MONGODB_URI 환경 변수를 설정해주세요.")

    app.config['SQLALCHEMY_DATABASE_URI'] = (
        mysql_url.replace('mysql://', 'mysql+pymysql://', 1)
        if mysql_url and mysql_url.startswith('mysql://')
        else mysql_url
    )
    app.config["MONGO_URI"] = mongo_url

    print(f"INFO: MariaDB(MySQL) URI: {str(app.config.get('SQLALCHEMY_DATABASE_URI'))[:30]}...")
    print(f"INFO: MongoDB URI: {str(app.config.get('MONGO_URI'))[:30]}...")
    print(">>> 데이터베이스 설정 완료.")

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    CORS(app, supports_credentials=True)

    # --- Flask 확장 프로그램 초기화 ---
    from backend.extensions import db, mongo, migrate, jwt, bcrypt
    db.init_app(app)
    mongo.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    bcrypt.init_app(app)

    # --- API 블루프린트 등록 ---
    with app.app_context():
        from backend.routes import (
            auth_routes, login_register_routes, diary_routes, mood_routes,
            chat_routes, community_routes, psych_test_routes, admin_routes,
            dashboard_routes, graph_routes, inquiry_routes
        )
        app.register_blueprint(auth_routes.auth_bp, url_prefix='/api/auth')
        app.register_blueprint(login_register_routes.user_bp, url_prefix='/api/user')
        app.register_blueprint(diary_routes.diary_bp, url_prefix='/api/diary')
        app.register_blueprint(mood_routes.mood_bp, url_prefix='/api/mood')
        app.register_blueprint(chat_routes.chat_bp, url_prefix='/api/chat')
        app.register_blueprint(community_routes.community_bp, url_prefix='/api/community')
        app.register_blueprint(psych_test_routes.psych_test_bp, url_prefix='/api/psych-test')
        app.register_blueprint(admin_routes.admin_bp, url_prefix='/api/admin')
        app.register_blueprint(dashboard_routes.dashboard_bp, url_prefix='/api/dashboard')
        app.register_blueprint(graph_routes.graph_bp, url_prefix='/api/graph')
        app.register_blueprint(inquiry_routes.inquiry_bp, url_prefix='/api/inquiry')

    # --- HTML 페이지 렌더링 라우트 ---
    # (라우트 코드는 이전과 동일하므로 생략)
    @app.route('/', endpoint='index')
    def index_page():
        return render_template('index.html')
    # ... 모든 HTML 라우트들 ...
    @app.route('/admin/inquiry_management', endpoint='admin_inquiry_management')
    def admin_inquiry_management_page():
        return render_template('admin_inquiry_management.html')

    # --- 에러 핸들러 ---
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404
        
    # --- CLI 명령어 등록 ---
    @app.cli.command("init-db")
    def init_db_command():
        """데이터베이스를 초기화합니다."""
        from backend.initialize_roles_and_admin import initialize_database
        from backend.initialize_menus import initialize_menus
        
        print("--- [CLI] 데이터베이스 초기화 시작 ---")
        initialize_database()
        initialize_menus()
        print("--- [CLI] 데이터베이스 초기화 완료 ---")

    return app

# --- 애플리케이션 생성 ---
# Gunicorn, Flask CLI 등이 이 'app' 변수를 참조합니다.
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

