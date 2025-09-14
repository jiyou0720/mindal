import os
from flask import Blueprint, request, jsonify, g
from backend.extensions import db, bcrypt, jwt
# 'UserRole' is no longer needed and has been removed from the import.
from backend.maria_models import User, Role, NicknameHistory
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from functools import wraps
import datetime
import logging

auth_bp = Blueprint('auth', __name__)

# Set up logging
logger = logging.getLogger(__name__)

# --- Custom Decorators ---
def token_required(f):
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        try:
            user_id = get_jwt_identity()
            g.user_id = user_id
            
            # Add token blacklist check
            jti = get_jwt()['jti']
            # This part requires a token blacklist implementation (e.g., using Redis or a DB table)
            # For now, we assume tokens are valid until they expire.
            
            return f(*args, **kwargs)
        except Exception as e:
            logger.warning(f"token_required: {str(e)}")
            return jsonify({'message': 'Token is invalid or expired!'}), 401
    return decorated

# --- User Registration ---
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    nickname = data.get('nickname')

    if not all([username, email, password, nickname]):
        return jsonify({'message': 'Missing required fields'}), 400

    logger.info(f"Register attempt for username: {username}, email: {email}")

    if User.query.filter((User.username == username) | (User.email == email) | (User.nickname == nickname)).first():
        existing_user = User.query.filter(User.email == email).first()
        if existing_user:
             logger.warning(f"Registration failed: Email '{email}' already registered.")
             return jsonify({'message': f"Email '{email}' is already registered."}), 409
        existing_user = User.query.filter(User.username == username).first()
        if existing_user:
             logger.warning(f"Registration failed: Username '{username}' already registered.")
             return jsonify({'message': f"Username '{username}' is already registered."}), 409
        existing_user = User.query.filter(User.nickname == nickname).first()
        if existing_user:
             logger.warning(f"Registration failed: Nickname '{nickname}' already registered.")
             return jsonify({'message': f"Nickname '{nickname}' is already registered."}), 409

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    
    # Assign '일반 사용자' role by default
    default_role = Role.query.filter_by(name='일반 사용자').first()
    if not default_role:
        # Fallback in case roles are not initialized
        return jsonify({'message': 'Default user role not found. Please contact administrator.'}), 500

    new_user = User(username=username, email=email, password_hash=hashed_password, nickname=nickname)
    # The relationship is now a standard many-to-many, so we append the role object.
    new_user.roles.append(default_role)

    try:
        db.session.add(new_user)
        db.session.commit()
        logger.info(f"User {username} registered successfully.")
        return jsonify({'message': 'User registered successfully'}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error during registration for user {username}: {e}", exc_info=True)
        return jsonify({'message': 'Registration failed due to a server error.'}), 500

# --- User Login ---
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'message': 'Email and password are required'}), 400

    user = User.query.filter_by(email=email).first()

    if user and bcrypt.check_password_hash(user.password_hash, password):
        # Get user roles from the relationship
        roles = [role.name for role in user.roles]
        
        access_token = create_access_token(
            identity=user.id, 
            expires_delta=datetime.timedelta(days=7),
            additional_claims={'roles': roles, 'nickname': user.nickname}
        )
        logger.info(f"User {user.username} logged in successfully.")
        return jsonify(access_token=access_token), 200
    else:
        logger.warning(f"Login failed for email: {email}")
        return jsonify({'message': 'Invalid credentials'}), 401

# --- Token Verification ---
@auth_bp.route('/verify-token', methods=['GET'])
@jwt_required()
def verify_token():
    try:
        user_id = get_jwt_identity()
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"msg": "User not found"}), 404
            
        roles = [role.name for role in user.roles]
        
        return jsonify({
            'user_id': user.id,
            'username': user.username,
            'email': user.email,
            'nickname': user.nickname,
            'roles': roles
        }), 200
    except Exception as e:
        return jsonify({"msg": "Token is invalid or expired"}), 401

