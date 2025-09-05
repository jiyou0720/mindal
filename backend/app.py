import os
import sys
from flask import Flask, render_template, g, request, jsonify
from dotenv import load_dotenv

def create_app(test_config=None):
    """
    Flask 애플리케이션 인스턴스를 생성하고 설정하는 '애플리케이션 팩토리' 함수입니다.
    """
    # .env 파일에서 환경 변수 로드 (주로 로컬 개발 시 사용)
    load_dotenv()

    # 'backend'와 같은 내부 모듈을 올바르게 임포트하기 위해 프로젝트 루트 경로를 추가합니다.
    script_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    app = Flask(__name__,
                template_folder='../frontend/templates',
                static_folder='../frontend/static')

    # --- 기본 설정 ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_default_key_for_dev')
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'a_very_secret_jwt_key_for_dev')
    
    if test_config:
        app.config.from_mapping(test_config)

    # --- 데이터베이스 설정 (님의 아이디어 적용) ---
    # 1. Railway 배포 환경을 위해 MYSQL_URL과 MONGO_URL을 먼저 찾습니다.
    mysql_url = os.environ.get("MYSQL_URL")
    mongo_url = os.environ.get("MONGO_URL")

    # 2. 만약 위 변수들이 없다면 (로컬 개발 환경), .env 파일의 개별 값을 조합하여 사용합니다.
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

    # 3. 최종적으로 얻은 주소를 Flask 설정에 적용합니다.
    if not mysql_url or not mongo_url:
        raise RuntimeError("데이터베이스 URL을 찾을 수 없습니다. .env 파일 또는 Railway 환경 변수를 확인해주세요.")

    # SQLAlchemy가 PyMySQL 드라이버를 사용하도록 주소 형식을 변환합니다.
    if mysql_url.startswith('mysql://'):
         app.config['SQLALCHEMY_DATABASE_URI'] = mysql_url.replace('mysql://', 'mysql+pymysql://', 1)
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = mysql_url

    app.config["MONGO_URI"] = mongo_url

    # --- Flask 확장 프로그램 초기화 ---
    from backend.extensions import db, mongo, migrate, jwt, bcrypt
    db.init_app(app)
    mongo.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    bcrypt.init_app(app)

    # --- 블루프린트(라우트) 등록 ---
    from backend.routes.auth_routes import auth_bp
    from backend.routes.community_routes import community_bp
    from backend.routes.diary_routes import diary_bp
    from backend.routes.mood_routes import mood_bp
    from backend.routes.psych_test_routes import psych_test_bp
    from backend.routes.admin_routes import admin_bp
    from backend.routes.chat_routes import chat_bp
    from backend.routes.graph_routes import graph_bp
    from backend.routes.inquiry_routes import inquiry_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(community_bp)
    app.register_blueprint(diary_bp)
    app.register_blueprint(mood_bp)
    app.register_blueprint(psych_test_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(graph_bp)
    app.register_blueprint(inquiry_bp)
    

    # --- 프론트엔드 페이지 렌더링 라우트 ---
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/login')
    def login_page():
        return render_template('login.html')

    @app.route('/signup')
    def signup_page():
        return render_template('signup.html')

    @app.route('/forgot-password')
    def forgot_password_page():
        return render_template('forgot_password.html')

    @app.route('/community')
    def community_list_page():
        return render_template('community_list.html')
    
    @app.route('/community/create')
    def community_create_page():
        return render_template('community_create.html')
    
    @app.route('/community/view/<int:post_id>')
    def community_detail_page(post_id):
        return render_template('community_detail.html', post_id=post_id)

    @app.route('/community/edit/<int:post_id>')
    def community_edit_page(post_id):
        return render_template('community_edit.html', post_id=post_id)
    
    @app.route('/diary')
    def diary_page():
        return render_template('diary.html')

    @app.route('/my-changes')
    def my_changes_page():
        return render_template('my_changes.html')

    @app.route('/ai-chat')
    def ai_chat_page():
        return render_template('ai_chat.html')

    @app.route('/psych-test')
    def psych_test_list_page():
        return render_template('psych_test_list.html')
    
    @app.route('/psych-test/take/<int:test_id>')
    def psych_test_take_page(test_id):
        return render_template('psych_test_take.html', test_id=test_id)

    @app.route('/psych-test/result/<int:result_id>')
    def psych_test_result_page(result_id):
        return render_template('psych_test_result.html', result_id=result_id)

    @app.route('/my-page')
    def my_page():
        return render_template('my_page.html')

    @app.route('/edit-profile')
    def edit_profile_page():
        return render_template('edit_profile.html')

    @app.route('/inquiry')
    def inquiry_page():
        return render_template('inquiry.html')
    
    @app.route('/keyword')
    def keyword_page():
        return render_template('keyword.html')

    # --- Admin Page Routes ---
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

    # --- Error Page Route ---
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

   
    return app

# Gunicorn과 같은 WSGI 서버가 이 'app' 변수를 찾아서 실행합니다.
app = create_app()

# 로컬에서 직접 python backend/app.py로 실행할 때를 위한 코드
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # debug=False로 변경하여 운영 환경과 유사하게 실행
    app.run(host='0.0.0.0', port=port, debug=False)

