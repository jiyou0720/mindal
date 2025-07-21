# backend/auth.py
from flask import g, jsonify, request
from functools import wraps
import jwt
import datetime
import os
from extensions import db
from maria_models import User, Role # Role도 임포트
import random
import string

# JWT 토큰을 요구하는 데코레이터
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1] # "Bearer <token>"
        
        if not token:
            print("DEBUG: Token is missing from request headers!")
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            print(f"DEBUG: Backend received token: {token}")
            secret_key = os.getenv('JWT_SECRET_KEY')
            print(f"DEBUG: Backend's JWT_SECRET_KEY from env: {secret_key}")
            if not secret_key:
                print("DEBUG: JWT_SECRET_KEY is None! Check .env file and server restart.")
            
            data = jwt.decode(token, secret_key, algorithms=["HS256"])
            print(f"DEBUG: Decoded token data: {data}")
            
            current_user = db.session.get(User, data['user_id']) 
            if not current_user:
                print(f"DEBUG: User not found for user_id: {data.get('user_id')}")
                return jsonify({'message': 'Token is invalid or user not found!'}), 401
            
            g.user_id = current_user.id
            g.user_uid = current_user.user_uid
            
            # --- MODIFIED: More robust role extraction with type checking ---
            user_roles_names = []
            if current_user.roles: # Ensure roles list is not empty
                for role_obj_or_str in current_user.roles:
                    print(f"DEBUG: Processing role_obj_or_str: {role_obj_or_str}, Type: {type(role_obj_or_str)}")
                    if isinstance(role_obj_or_str, Role): # Role 객체인 경우
                        user_roles_names.append(role_obj_or_str.name)
                    elif isinstance(role_obj_or_str, str): # 문자열인 경우 (예상치 못한 경우)
                        user_roles_names.append(role_obj_or_str) # 문자열 자체를 역할 이름으로 사용
                        print(f"WARNING: Element in current_user.roles is a string ('{role_obj_or_str}'), expected a Role object. This indicates a potential ORM or data issue.")
                    else: # 그 외 예상치 못한 타입인 경우
                        print(f"ERROR: Unexpected type found in current_user.roles: {type(role_obj_or_str)} for value: {role_obj_or_str}")
            
            g.user_roles = user_roles_names
            print(f"DEBUG: User {g.user_uid} (ID: {g.user_id}) with roles {g.user_roles} authenticated.")

        except jwt.ExpiredSignatureError:
            print("DEBUG: Token has expired!")
            return jsonify({'message': 'Token has expired!'}), 401
        except (jwt.InvalidTokenError, KeyError) as e:
            print(f"DEBUG: Token invalid or malformed error: {type(e).__name__}: {e}")
            return jsonify({'message': 'Token is invalid or malformed! Please log in again.'}), 401
        except Exception as e:
            print(f"DEBUG: Unexpected error in token processing: {str(e)}")
            return jsonify({'message': f'An unexpected error occurred during token processing: {str(e)}'}), 500

        return f(*args, **kwargs)
    return decorated

# 역할 기반 접근 제어 데코레이터
def roles_required(*required_roles):
    def wrapper(f):
        @wraps(f)
        @token_required
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user_roles'):
                print("DEBUG: Access forbidden: User roles not found on g object.")
                return jsonify({'message': 'Access forbidden: User roles not found.'}), 403
            
            has_permission = False
            for role in g.user_roles:
                if role in required_roles:
                    has_permission = True
                    break
            
            if not has_permission:
                print(f"DEBUG: Access forbidden: User roles {g.user_roles} do not match required roles: {required_roles}")
                return jsonify({'message': f'Access forbidden: Insufficient permissions. Required roles: {", ".join(required_roles)}'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return wrapper

# 숫자 user_uid 생성 함수
def generate_numeric_uid(length=6):
    while True:
        uid = ''.join(random.choices(string.digits, k=length))
        if not User.query.filter_by(user_uid=uid).first():
            return uid
