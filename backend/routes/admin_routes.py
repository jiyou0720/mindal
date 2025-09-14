import os
from flask import Blueprint, request, jsonify, current_app
from backend.extensions import db
from backend.routes.auth_routes import token_required
# 'UserRole' is no longer needed and has been removed from the import.
from backend.maria_models import User, Post, Comment, Role, Notice, PostLike
from werkzeug.utils import secure_filename
from datetime import datetime

admin_bp = Blueprint('admin_api', __name__)

# --- 파일 업로드 설정 ---
UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'frontend', 'static', 'uploads', 'admin'))
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    current_app.logger.info(f"ADMIN UPLOAD_FOLDER created: {UPLOAD_FOLDER}")
else:
    current_app.logger.info(f"ADMIN UPLOAD_FOLDER already exists: {UPLOAD_FOLDER}")

# --- 사용자 관리 API ---

@admin_bp.route('/users', methods=['GET'])
@token_required 
def get_users():
    # '관리자' 역할이 있는지 확인하는 로직 추가 필요
    users = User.query.all()
    users_data = [{
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'nickname': user.nickname,
        'created_at': user.created_at.isoformat(),
        'roles': [role.name for role in user.roles] # Correctly fetch roles
    } for user in users]
    return jsonify(users_data)

@admin_bp.route('/users/<int:user_id>/assign-role', methods=['POST'])
@token_required
def assign_role_to_user(user_id):
    data = request.get_json()
    role_name = data.get('role_name')
    
    user = db.session.get(User, user_id)
    role = Role.query.filter_by(name=role_name).first()

    if not user or not role:
        return jsonify({'message': 'User or Role not found'}), 404
    
    # Check if user already has the role
    if role in user.roles:
        return jsonify({'message': 'User already has this role'}), 400

    # Assign role using the relationship
    user.roles.append(role)
    db.session.commit()
    
    return jsonify({'message': f"Role '{role_name}' assigned to user '{user.username}'"}), 200

@admin_bp.route('/users/<int:user_id>/remove-role', methods=['POST'])
@token_required
def remove_role_from_user(user_id):
    data = request.get_json()
    role_name = data.get('role_name')
    
    user = db.session.get(User, user_id)
    role = Role.query.filter_by(name=role_name).first()

    if not user or not role:
        return jsonify({'message': 'User or Role not found'}), 404
        
    # Check if user has the role to remove
    if role not in user.roles:
        return jsonify({'message': 'User does not have this role'}), 400
        
    # Remove role using the relationship
    user.roles.remove(role)
    db.session.commit()

    return jsonify({'message': f"Role '{role_name}' removed from user '{user.username}'"}), 200


# --- 게시글 관리 API (기능 미구현) ---
@admin_bp.route('/posts', methods=['GET'])
@token_required
def admin_get_posts():
    return jsonify({'message': 'Admin post management not implemented'}), 501

@admin_bp.route('/posts/<int:post_id>/suspend', methods=['POST'])
@token_required
def suspend_post(post_id):
    return jsonify({'message': 'Post suspension not implemented'}), 501

# --- 공지사항 관리 API (기능 미구현) ---
@admin_bp.route('/notices', methods=['POST'])
@token_required
def create_notice():
    return jsonify({'message': 'Notice creation not implemented'}), 501

