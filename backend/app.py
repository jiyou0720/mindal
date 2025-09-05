import os
import logging
import sys
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, g, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

def create_app(test_config=None):
    # .env 파일에서 환경 변수 로드 (로컬 개발용)
    load_dotenv()

    app = Flask(__name__,
                template_folder='../frontend/templates',
                static_folder='../frontend/static')

    # --- 기본 설정 ---
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')
    if test_config:
        app.config.from_mapping(test_config)

    # --- 데이터베이스 설정 (Railway 최적화) ---
    db_url = os.environ.get('DATABASE_URL')
    mongo_uri = os.environ.get('MONGO_URL')

    # Railway 환경에서는 이 변수들이 반드시 존재해야 함
    if not db_url:
        raise RuntimeError("DATABASE_URL 환경 변수가 없습니다. Railway에서 데이터베이스 서비스를 연결(Link)했는지 확인해주세요.")
    if not mongo_uri:
        raise RuntimeError("MONGO_URL 환경 변수가 없습니다. Railway에서 데이터베이스 서비스를 연결(Link)했는지 확인해주세요.")

    # Railway의 DATABASE_URL 형식은 'mysql://...' 이므로 'mysql+pymysql://...'로 변경
    if db_url.startswith('mysql://'):
        final_db_uri = db_url.replace('mysql://', 'mysql+pymysql://', 1)
    else:
        # 다른 형식의 주소도 일단 그대로 사용
        final_db_uri = db_url

    # --- 디버깅을 위한 출력 ---
    # 이 부분이 실제로 어떤 DB 주소를 사용하는지 로그에 출력합니다.
    print(f"DEBUG: Connecting to DB with URI: {final_db_uri}", file=sys.stderr)
    # -------------------------

    app.config['SQLALCHEMY_DATABASE_URI'] = final_db_uri
    app.config['MONGO_URI'] = mongo_uri
    
    # --- 로깅 설정 ---
    if not os.path.exists('logs'):
        os.mkdir('logs')
    
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Application startup')

    # --- 확장 프로그램 초기화 ---
    from backend.extensions import db, mongo, migrate, jwt, bcrypt
    db.init_app(app)
    mongo.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    bcrypt.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # --- 라우트 등록 ---
    from backend.routes import (
        auth_routes, admin_routes, chat_routes, community_routes,
        dashboard_routes, diary_routes, graph_routes, inquiry_routes,
        mood_routes, psych_test_routes
    )
    app.register_blueprint(auth_routes.bp)
    app.register_blueprint(admin_routes.bp)
    app.register_blueprint(chat_routes.bp)
    app.register_blueprint(community_routes.bp)
    app.register_blueprint(dashboard_routes.bp)
    app.register_blueprint(diary_routes.bp)
    app.register_blueprint(graph_routes.bp)
    app.register_blueprint(inquiry_routes.bp)
    app.register_blueprint(mood_routes.bp)
    app.register_blueprint(psych_test_routes.bp)

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

# Gunicorn이 'app' 인스턴스를 찾을 수 있도록 전역 스코프에서 생성
app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # debug=False로 변경하는 것이 프로덕션 환경에 더 적합합니다.
    app.run(host='0.0.0.0', port=port, debug=False)

