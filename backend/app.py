# backend/app.py
import os
from flask import Flask, render_template, g
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
from extensions import mongo

import click
from maria_models import User, Role
from mongo_models import MenuItem
from werkzeug.security import generate_password_hash
from auth import generate_numeric_uid
from auth import token_required, roles_required # token_required와 roles_required는 여전히 필요할 수 있습니다.
from bson.objectid import ObjectId

load_dotenv()

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

# ✅ 실제 초기화 (이게 반드시 필요)
mongo.init_app(app)
db.init_app(app)
migrate = Migrate(app, db)

mongo_instance = PyMongo(app)

def get_menu_config_collection():
    if 'MONGO_DB' not in app.config:
        from flask_pymongo import PyMongo
        app.config['MONGO_DB'] = PyMongo(app).db
    return app.config['MONGO_DB'].menu_configs


app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(community_bp, url_prefix='/api/community')
app.register_blueprint(diary_bp, url_prefix='/api/diary')
app.register_blueprint(mood_bp, url_prefix='/api/mood')
app.register_blueprint(graph_bp, url_prefix='/api/graph')
app.register_blueprint(admin_bp, url_prefix='/api/admin')


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ai-chat')
# @token_required # AI 챗봇 페이지에 로그인 없이 접근하려면 이 줄을 주석 처리하거나 제거하세요.
def ai_chat():
    return render_template('ai_chat.html')

@app.route('/diary')
# @token_required # 오늘일기 페이지에 로그인 없이 접근하려면 이 줄을 주석 처리하거나 제거하세요.
def diary():
    user_roles = getattr(g, 'user_roles', [])
    return render_template('diary.html', user_roles=user_roles)

@app.route('/keyword')
def keyword():
    return render_template('keyword.html')

@app.route('/my-changes')
# @token_required # 나의 변화 페이지에 로그인 없이 접근하려면 이 줄을 주석 처리하거나 제거하세요.
def my_changes():
    return render_template('my_changes.html')

@app.route('/mypage')
# @token_required # 마이페이지에 로그인 없이 접근하려면 이 줄을 주석 처리하거나 제거하세요.
def mypage():
    user_roles = getattr(g, 'user_roles', [])
    return render_template('mypage.html', user_roles=user_roles)

@app.route('/counseling')
# @token_required # 온라인 상담 페이지에 로그인 없이 접근하려면 이 줄을 주석 처리하거나 제거하세요.
def counseling():
    user_roles = getattr(g, 'user_roles', [])
    return render_template('counseling.html', user_roles=user_roles)


@app.route('/admin-dashboard')
# @token_required # 관리자 대시보드에 로그인 없이 접근하려면 이 줄을 주석 처리하거나 제거하세요. (보안상 매우 위험)
# @roles_required('관리자') # 이 데코레이터도 함께 제거해야 합니다.
def admin_dashboard():
    return render_template('admin_dashboard.html')

@app.route('/user-management')
# @token_required # 사용자 관리에 로그인 없이 접근하려면 이 줄을 주석 처리하거나 제거하세요. (보안상 매우 위험)
# @roles_required('관리자') # 이 데코레이터도 함께 제거해야 합니다.
def user_management():
    return render_template('user_management.html')


@app.route('/menu-management')
# @token_required # 메뉴 관리에 로그인 없이 접근하려면 이 줄을 주석 처리하거나 제거하세요. (보안상 매우 위험)
# @roles_required('관리자') # 이 데코레이터도 함께 제거해야 합니다.
def menu_management():
    return render_template('menu_management.html')

@app.route('/role-menu-assignment')
# @token_required # 권한별 메뉴 설정에 로그인 없이 접근하려면 이 줄을 주석 처리하거나 제거하세요. (보안상 매우 위험)
# @roles_required('관리자') # 이 데코레이터도 함께 제거해야 합니다.
def role_menu_assignment():
    return render_template('role_menu_assignment.html')


@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/forgot-password')
def forgot_password():
    return render_template('forgot_password.html')

@app.route('/community')
def community_list():
    user_roles = getattr(g, 'user_roles', [])
    return render_template('community_list.html', user_roles=user_roles)

@app.route('/community/create')
# @token_required # 게시판 작성 페이지에 로그인 없이 접근하려면 이 줄을 주석 처리하거나 제거하세요.
def community_create():
    user_roles = getattr(g, 'user_roles', [])
    return render_template('community_create.html', user_roles=user_roles)

@app.route('/community/posts/<int:post_id>')
def community_detail(post_id):
    user_roles = getattr(g, 'user_roles', [])
    return render_template('community_detail.html', post_id=post_id, user_roles=user_roles)

@app.route('/community/posts/edit/<int:post_id>')
@token_required
def edit_post(post_id):
    user_roles = getattr(g, 'user_roles', [])
    return render_template('community_edit.html', post_id=post_id, user_roles=user_roles)


@app.cli.command("create-admin")
@click.argument("email")
@click.argument("password")
@click.argument("username")
def create_admin(email, password, username):
    with app.app_context():
        if User.query.filter_by(email=email).first():
            click.echo(f"오류: '{email}' 이메일은 이미 등록되어 있습니다.")
            return
        
        if User.query.filter_by(username=username).first():
            click.echo(f"오류: '{username}' 사용자 이름은 이미 사용 중입니다.")
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
            password_hash=generate_password_hash(password),
            user_uid=generated_uid,
            nickname='관리자',
            gender='미정',
            age=0,
            major='관리'
        )
        db.session.add(new_admin)
        db.session.commit()
        print(f"관리자 사용자 '{username}' 생성 완료.")
        
        admin_role = Role.query.filter_by(name='관리자').first()
        if not admin_role:
            click.echo("오류: '관리자' 역할을 찾을 수 없습니다. 역할 초기화 스크립트를 먼저 실행해주세요.")
            db.session.rollback()
            return
        
        if admin_role not in new_admin.roles.all():
            new_admin.roles.append(admin_role)
            db.session.commit()
            click.echo(f"관리자 계정 '{username}'({email})에 '관리자' 역할 부여.")
        else:
            click.echo(f"관리자 계정 '{username}'은(는) 이미 '관리자' 역할을 가지고 있습니다.")

        click.echo(f"관리자 계정 '{username}'({email})이 성공적으로 생성되었습니다. UID: {generated_uid}")


@app.cli.command("assign-role")
@click.argument("email")
@click.argument("role_name")
def assign_role_to_user_cli(email, role_name):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            click.echo(f"오류: 이메일 '{email}'을(를) 가진 사용자를 찾을 수 없습니다.")
            return

        role = Role.query.filter_by(name=role_name).first()
        if not role:
            click.echo(f"오류: 역할 '{role_name}'을(를) 찾을 수 없습니다. 역할 초기화 스크립트를 먼저 실행했는지 확인하세요.")
            return

        if role not in user.roles.all():
            user.roles.append(role)
            db.session.commit()
            click.echo(f"사용자 '{user.username}'에게 역할 '{role_name}'을(를) 성공적으로 부여했습니다.")
        else:
            click.echo(f"사용자 '{user.username}'은(는) 이미 역할 '{role_name}'을(를) 가지고 있습니다.")

@app.cli.command("init-default-menus")
def init_default_menus():
    with app.app_context():
        print("기본 메뉴 항목 초기화 시작...")
        menu_collection = get_menu_config_collection()

        all_users_role = Role.query.filter_by(name='모든 사용자').first()
        all_users_role_name = all_users_role.name if all_users_role else None

        if not all_users_role_name:
            click.echo("오류: '모든 사용자' 역할을 MariaDB Role 테이블에서 찾을 수 없습니다. 역할 초기화 스크립트를 먼저 실행했는지 확인하세요.")
            return

        default_menus = [
            MenuItem(name="홈", path="index", icon_class="fas fa-home", required_roles=[all_users_role_name]),
            MenuItem(name="오늘, 일기", path="diary", icon_class="fas fa-book", required_roles=['일반 사용자', '에디터', '운영자', '관리자']),
            MenuItem(name="커뮤니티", path="community_list", icon_class="fas fa-users", required_roles=[all_users_role_name]),
            MenuItem(name="AI 챗봇", path="ai_chat", icon_class="fas fa-robot", required_roles=['일반 사용자', '에디터', '운영자', '관리자']),
            MenuItem(name="마이페이지", path="mypage", icon_class="fas fa-user", required_roles=['일반 사용자', '에디터', '운영자', '관리자']),
            MenuItem(name="나의 변화", path="my_changes", icon_class="fas fa-chart-line", required_roles=['일반 사용자', '에디터', '운영자', '관리자']),
            MenuItem(name="온라인 상담", path="counseling", icon_class="fas fa-comments", required_roles=['일반 사용자', '에디터', '운영자', '관리자']), # 상담 메뉴 추가
            MenuItem(name="관리자 대시보드", path="admin_dashboard", icon_class="fas fa-tachometer-alt", required_roles=['관리자']),
            MenuItem(name="사용자 관리", path="user_management", icon_class="fas fa-users-cog", required_roles=['관리자']),
            MenuItem(name="메뉴 관리", path="menu_management", icon_class="fas fa-bars", required_roles=['관리자']),
            MenuItem(name="권한별 메뉴 설정", icon_class="fas fa-user-shield", path="role_menu_assignment", required_roles=['관리자']),
        ]

        for menu_item in default_menus:
            # path와 name으로 기존 메뉴를 찾지 않고, _id가 없는 경우에만 새로 추가하도록 변경
            # 이렇게 하면 기존에 _id가 null로 잘못 저장된 항목이 있어도 새로운 ObjectId로 추가됩니다.
            existing_menu = menu_collection.find_one({'path': menu_item.path, 'name': menu_item.name})
            if existing_menu and existing_menu.get('_id') is not None: # 유효한 _id를 가진 중복 메뉴는 허용 안 함
                click.echo(f"메뉴 '{menu_item.name}' ({menu_item.path})은(는) 이미 유효한 _id로 존재합니다. 건너뜀.")
            else:
                # 기존에 동일한 path와 name이 있지만 _id가 없거나, 아예 없는 경우 새로 추가
                if existing_menu:
                    click.echo(f"경고: 메뉴 '{menu_item.name}' ({menu_item.path})이(가) 존재하지만 유효한 _id가 없어 삭제 후 재추가합니다.")
                    menu_collection.delete_one({'_id': existing_menu['_id']}) # 기존 잘못된 항목 삭제
                
                # MenuItem 생성 시 ObjectId가 자동으로 생성되므로, to_dict() 호출 시 올바른 _id 포함
                menu_collection.insert_one(menu_item.to_dict())
                click.echo(f"메뉴 '{menu_item.name}' ({menu_item.path}) 추가됨.")
        
        print("기본 메뉴 항목 초기화 완료.")


if __name__ == '__main__':
    app.run(debug=True)
