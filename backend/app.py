import os
import sys
from flask import Flask, render_template
from flask_cors import CORS
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

# 로컬 개발을 위해 .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

def create_app(test_config=None):
    """
    Flask 애플리케이션 인스턴스를 생성하고 설정하는 '애플리케이션 팩토리' 함수입니다.
    """
    # --- 경로 설정 수정 ---
    script_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    # --- 임포트 충돌 방지 패치 ---
    if 'backend.maria_models' not in sys.modules:
        import backend.maria_models
    if 'maria_models' not in sys.modules:
        sys.modules['maria_models'] = sys.modules['backend.maria_models']

    app = Flask(__name__,
                template_folder='../frontend/templates',
                static_folder='../frontend/static')

    # --- 기본 설정 ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_default_key_for_dev')
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY')
    
    if test_config:F
        app.config.from_mapping(test_config)

    # --- 데이터베이스 설정 (Railway 호환) ---
    mysql_url = os.environ.get("MYSQL_URL")
    mongo_url = os.environ.get("MONGO_URL")

    if not mysql_url:
        MYSQL_USER = os.environ.get("MYSQL_USER")
        MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
        MYSQL_HOST = os.environ.get("MYSQL_HOST")
        MYSQL_PORT = os.environ.get("MYSQL_PORT")
        MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE")
        if all([MYSQL_USER, MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE]):
            mysql_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

    if not mongo_url:
        mongo_url = os.environ.get("MONGO_URI")

    if not mysql_url or not mongo_url:
        raise RuntimeError("데이터베이스 연결 정보를 찾을 수 없습니다. Railway 환경 변수를 확인하세요.")

    if mysql_url.startswith('mysql://'):
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

    # --- HTML 페이지 렌더링 라우트 (API 블루프린트보다 먼저 위치해도 괜찮음) ---
    @app.route('/', endpoint='index')
    def index_page():
        return render_template('index.html')

    @app.route('/login', endpoint='login')
    def login_page():
        return render_template('login.html')

    @app.route('/signup', endpoint='signup')
    def signup_page():
        return render_template('signup.html')
    
    @app.route('/my-page', endpoint='my_page')
    def my_page():
        return render_template('my_page.html')

    @app.route('/edit-profile', endpoint='edit_profile')
    def edit_profile_page():
        return render_template('edit_profile.html')

    @app.route('/forgot-password', endpoint='forgot_password')
    def forgot_password_page():
        return render_template('forgot_password.html')
        
    @app.route('/ai-chat', endpoint='ai_chat')
    def ai_chat_page():
        return render_template('ai_chat.html')

    @app.route('/diary', endpoint='diary')
    def diary_page():
        return render_template('diary.html')

    @app.route('/community', endpoint='community_list')
    def community_list_page():
        return render_template('community_list.html')
    
    @app.route('/community/create', endpoint='community_create')
    def community_create_page():
        return render_template('community_create.html')

    @app.route('/community/post/<int:post_id>', endpoint='community_detail')
    def community_detail_page(post_id):
        return render_template('community_detail.html', post_id=post_id)

    @app.route('/community/edit/<int:post_id>', endpoint='community_edit')
    def community_edit_page(post_id):
        return render_template('community_edit.html', post_id=post_id)

    @app.route('/psych-test', endpoint='psych_test_list')
    def psych_test_list_page():
        return render_template('psych_test_list.html')
        
    @app.route('/psych-test/<string:test_type>', endpoint='psych_test_take')
    def psych_test_take_page(test_type):
        return render_template('psych_test_take.html', test_type=test_type)

    @app.route('/psych-test/result/<int:result_id>', endpoint='psych_test_result')
    def psych_test_result_page(result_id):
        return render_template('psych_test_result.html', result_id=result_id)
        
    @app.route('/inquiry', endpoint='inquiry')
    def inquiry_page():
        return render_template('inquiry.html')
    
    @app.route('/my-changes', endpoint='my_changes')
    def my_changes_page():
        return render_template('my_changes.html')

    # --- 관리자 페이지 라우트 ---
    @app.route('/admin/dashboard', endpoint='admin_dashboard')
    def admin_dashboard_page():
        return render_template('admin_dashboard.html')

    @app.route('/admin/user_management', endpoint='user_management')
    def user_management_page():
        return render_template('user_management.html')

    @app.route('/admin/menu_management', endpoint='menu_management')
    def menu_management_page():
        return render_template('menu_management.html')

    @app.route('/admin/role_menu_assignment', endpoint='role_menu_assignment')
    def role_menu_assignment_page():
        return render_template('role_menu_assignment.html')

    @app.route('/admin/notice_management', endpoint='notice_management')
    def notice_management_page():
        return render_template('notice_management.html')

    @app.route('/admin/db_management', endpoint='db_management')
    def db_management_page():
        return render_template('db_management.html')

    @app.route('/admin/post_management', endpoint='post_management')
    def post_management_page():
        return render_template('post_management.html')

    @app.route('/admin/cms_management', endpoint='cms_management')
    def cms_management_page():
        return render_template('cms_management.html')

    @app.route('/admin/data_analytics', endpoint='data_analytics')
    def data_analytics_page():
        return render_template('data_analytics.html')

    @app.route('/admin/chatbot_feedback', endpoint='chatbot_feedback')
    def chatbot_feedback_page():
        return render_template('charbot_feedback.html')

    @app.route('/admin/inquiry_management', endpoint='admin_inquiry_management')
    def admin_inquiry_management_page():
        return render_template('admin_inquiry_management.html')

    # --- 에러 핸들러 ---
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    # --- API 블루프린트 등록 (가장 마지막에 위치) ---
    # 순환 참조 오류를 방지하기 위해, 모든 설정이 완료된 후 라우트들을 임포트하고 등록합니다.
    with app.app_context():
        from backend.routes.auth_routes import auth_bp
        from backend.routes.login_register_routes import user_bp
        from backend.routes.diary_routes import diary_bp
        from backend.routes.mood_routes import mood_bp
        from backend.routes.chat_routes import chat_bp
        from backend.routes.community_routes import community_bp
        from backend.routes.psych_test_routes import psych_test_bp
        from backend.routes.admin_routes import admin_bp
        from backend.routes.dashboard_routes import dashboard_bp
        from backend.routes.graph_routes import graph_bp
        from backend.routes.inquiry_routes import inquiry_bp

        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        app.register_blueprint(user_bp, url_prefix='/api/user')
        app.register_blueprint(diary_bp, url_prefix='/api/diary')
        app.register_blueprint(mood_bp, url_prefix='/api/mood')
        app.register_blueprint(chat_bp, url_prefix='/api/chat')
        app.register_blueprint(community_bp, url_prefix='/api/community')
        app.register_blueprint(psych_test_bp, url_prefix='/api/psych-test')
        app.register_blueprint(admin_bp, url_prefix='/api/admin')
        app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
        app.register_blueprint(graph_bp, url_prefix='/api/graph')
        app.register_blueprint(inquiry_bp, url_prefix='/api/inquiry')

    return app

# Gunicorn과 같은 WSGI 서버는 이 'app' 변수를 찾아 실행합니다.
app = create_app()

# 이 스크립트가 직접 실행될 때 (예: python backend/app.py)
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

