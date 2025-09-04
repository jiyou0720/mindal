import os
import sys
from flask import Flask, render_template
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

# 로컬 개발을 위해 .env 파일에서 환경 변수를 로드합니다.
# Railway와 같은 배포 환경에서는 이 파일을 사용하지 않고, 플랫폼에 설정된 환경 변수를 직접 사용합니다.
load_dotenv()

def create_app(test_config=None):
    """
    Flask 애플리케이션 인스턴스를 생성하고 설정하는 '애플리케이션 팩토리' 함수입니다.
    """
    # 'backend'와 같은 내부 모듈을 올바르게 임포트하기 위해 프로젝트 루트 경로를 추가합니다.
    script_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    app = Flask(__name__,
                template_folder='../frontend/templates',
                static_folder='../frontend/static')

    # --- 기본 설정 ---
    # 세션 관리, CSRF 보호 등에 사용되는 보안 키를 설정합니다.
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_default_key_for_dev')
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY')
    
    if test_config:
        app.config.from_mapping(test_config)

    # --- 데이터베이스 설정 (Railway 호환) ---
    # 1. Railway에서 주입하는 'DATABASE_URL' 환경 변수를 최우선으로 확인합니다.
    db_url = os.environ.get('DATABASE_URL')
    
    # 2. 'DATABASE_URL'이 없을 경우 (로컬 환경), .env 파일의 개별 변수를 조합하여 연결 문자열을 만듭니다.
    if not db_url:
        MYSQL_USER = os.environ.get("MYSQL_USER")
        MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "") 
        MYSQL_HOST = os.environ.get("MYSQL_HOST")
        MYSQL_PORT = os.environ.get("MYSQL_PORT")
        MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE")
        
        # 비밀번호는 선택 사항이므로, 필수 값들만 있는지 확인합니다.
        if all([MYSQL_USER, MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE]):
            db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

    # 3. Railway의 DB URL 형식('mysql://')을 SQLAlchemy 드라이버 형식('mysql+pymysql://')으로 변환합니다.
    if db_url and db_url.startswith('mysql://'):
        db_url = db_url.replace('mysql://', 'mysql+pymysql://', 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # --- MongoDB 설정 (Railway 호환) ---
    # Railway의 'MONGO_URL' 또는 로컬의 'MONGO_URI'를 사용합니다.
    mongo_url = os.environ.get('MONGO_URL') or os.environ.get('MONGO_URI')
    app.config['MONGO_URI'] = mongo_url

    # --- 확장(Extensions) 초기화 ---
    # 순환 참조(Circular Import) 문제를 방지하기 위해 함수 내에서 임포트하고 초기화합니다.
    from backend.extensions import db, mongo, migrate, jwt
    db.init_app(app)
    mongo.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # 프록시 서버(예: Nginx, Gunicorn) 뒤에서 실행될 때 올바른 클라이언트 정보를 얻기 위해 미들웨어를 설정합니다.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    # --- 블루프린트(Blueprint) 등록 ---
    # 각 기능별로 분리된 라우트들을 애플리케이션에 연결합니다.
    from backend.routes import (
        auth_routes, admin_routes, community_routes, dashboard_routes,
        diary_routes, graph_routes, inquiry_routes, mood_routes,
        psych_test_routes, chat_routes
    )
    app.register_blueprint(auth_routes.auth_bp)
    app.register_blueprint(admin_routes.admin_bp)
    app.register_blueprint(community_routes.community_bp)
    app.register_blueprint(dashboard_routes.dashboard_bp)
    app.register_blueprint(diary_routes.diary_bp)
    app.register_blueprint(graph_routes.graph_bp)
    app.register_blueprint(inquiry_routes.inquiry_bp)
    app.register_blueprint(mood_routes.mood_bp)
    app.register_blueprint(psych_test_routes.psych_test_bp)
    app.register_blueprint(chat_routes.chat_bp)

    # --- 프론트엔드 템플릿 렌더링 라우트 ---
    # 이 라우트들은 Flask가 직접 HTML 페이지를 렌더링하는 역할을 합니다.
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
    
    @app.route('/psych_test_list')
    def psych_test_list():
        return render_template('psych_test_list.html')
    
    @app.route('/psych_test_take')
    def psych_test_take():
        return render_template('psych_test_take.html')
    
    @app.route('/psych_test_result')
    def psych_test_result():
        return render_template('psych_test_result.html')
    
    @app.route('/community_list')
    def community_list():
        return render_template('community_list.html')

    @app.route('/community_create')
    def community_create():
        return render_template('community_create.html')

    @app.route('/community_detail')
    def community_detail():
        return render_template('community_detail.html')
    
    @app.route('/community_edit')
    def community_edit():
        return render_template('community_edit.html')

    @app.route('/inquiry')
    def inquiry():
        return render_template('inquiry.html')
    
    @app.route('/ai_chat')
    def ai_chat():
        return render_template('ai_chat.html')

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
        return render_template('charbot_feedback.html')

    @app.route('/admin/inquiry_management')
    def admin_inquiry_management():
        return render_template('admin_inquiry_management.html')

    # --- 에러 페이지 라우트 ---
    @app.route('/404_page')
    def not_found_page():
        return render_template('404.html')

    return app

# Gunicorn과 같은 WSGI 서버가 'app' 인스턴스를 찾을 수 있도록 
# create_app()을 호출하여 app 변수를 모듈의 최상단 레벨에 생성합니다.
app = create_app()

# 이 스크립트가 직접 실행될 때 (예: python backend/app.py)
if __name__ == '__main__':
    # Railway는 PORT 환경 변수를 통해 사용할 포트를 동적으로 지정합니다.
    port = int(os.environ.get('PORT', 5000))
    # Gunicorn과 같은 전문 WSGI 서버를 배포 환경에서 사용하므로, debug=True는 로컬 개발 시에만 유용합니다.
    app.run(host='0.0.0.0', port=port, debug=True)

