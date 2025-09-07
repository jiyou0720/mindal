import os
import sys
from flask import Flask, render_template
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

# --- 경로 설정 ---
# 'backend'와 같은 내부 모듈 및 루트의 스크립트를 올바르게 임포트하기 위해 프로젝트 루트 경로를 추가합니다.
# 이 코드를 파일 최상단으로 이동하여 항상 먼저 실행되도록 합니다.
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 로컬 개발을 위해 .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

def create_app(test_config=None):
    """
    Flask 애플리케이션 인스턴스를 생성하고 설정하는 '애플리케이션 팩토리' 함수입니다.
    """
    app = Flask(__name__,
                template_folder='../frontend/templates',
                static_folder='../frontend/static')

    # --- 기본 설정 ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_default_key_for_dev')
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY')
    
    if test_config:
        app.config.from_mapping(test_config)

    # --- 데이터베이스 설정 (Railway 호환) ---
    mysql_url = os.environ.get("MYSQL_URL")
    mongo_url = os.environ.get("MONGO_URL") or os.environ.get("MONGODB_URI")

    if not mysql_url:
        MYSQL_USER = os.environ.get("MYSQL_USER")
        MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD")
        MYSQL_HOST = os.environ.get("MYSQL_HOST")
        MYSQL_PORT = os.environ.get("MYSQL_PORT")
        MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE")
        if all([MYSQL_USER, MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE]):
            password_segment = f":{MYSQL_PASSWORD}" if MYSQL_PASSWORD else ""
            mysql_url = f"mysql+pymysql://{MYSQL_USER}{password_segment}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    
    if not mongo_url:
        mongo_url = os.environ.get("MONGO_URI")

    if mysql_url and mysql_url.startswith('mysql://'):
         app.config['SQLALCHEMY_DATABASE_URI'] = mysql_url.replace('mysql://', 'mysql+pymysql://', 1)
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = mysql_url

    app.config["MONGO_URI"] = mongo_url
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    CORS(app, supports_credentials=True)

    # --- Flask 확장 프로그램 초기화 ---
    from backend.extensions import db, mongo, migrate, jwt, bcrypt
    db.init_app(app)
    mongo.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    bcrypt.init_app(app)

    # --- API 블루프린트(라우트 그룹) 등록 ---
    with app.app_context():
        from backend.routes.auth_routes import auth_bp
        from backend.routes.login_register_routes import user_bp
        from backend.routes.diary_routes import diary_bp
        # ... 다른 블루프린트 임포트 ...
        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        app.register_blueprint(user_bp, url_prefix='/api/user')
        app.register_blueprint(diary_bp, url_prefix='/api/diary')
        # ... 다른 블루프린트 등록 ...

    # --- HTML 페이지 렌더링 라우트 ---
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def catch_all(path):
        # 모든 프론트엔드 라우트를 index.html로 리디렉션합니다.
        # 실제 파일(예: /static/...)에 대한 요청은 Flask가 자동으로 처리합니다.
        return render_template("index.html")

    # --- 에러 핸들러 ---
    @app.errorhandler(404)
    def page_not_found(e):
        # API 요청에 대한 404는 JSON으로, 그 외에는 HTML 페이지로 응답할 수 있습니다.
        return render_template('404.html'), 404

    return app

# --- 애플리케이션 생성 및 초기화 ---
# Gunicorn, Flask CLI 등 어디에서 실행되든 이 로직이 실행됩니다.
from backend.initialize_roles_and_admin import initialize_database
from backend.initialize_menus import initialize_menus

app = create_app()

with app.app_context():
    print(">>> 초기화 시작")
    initialize_database()  # 역할 및 관리자 계정 초기화
    initialize_menus()     # 메뉴 초기화
    print(">>> 초기화 완료")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port, debug=False)

