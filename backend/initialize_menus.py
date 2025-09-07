import sys
import os
import time
from pymongo.errors import ConnectionFailure

# 프로젝트 루트 디렉토리를 Python 경로에 추가합니다.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.extensions import mongo
from bson.objectid import ObjectId

def initialize_menus():
    """MongoDB에 기본 메뉴 아이템을 생성하고, 관리자 역할에 메뉴를 할당합니다."""
    print("메뉴 초기화를 시작합니다...")

    # --- [수정] MongoDB 연결 재시도 로직 ---
    retries = 5
    delay = 3  # 재시도 간 3초 대기
    for i in range(retries):
        try:
            # mongo.db가 None인지 직접 확인하여 연결 상태를 테스트합니다.
            if mongo.db is None:
                raise AttributeError("mongo.db is None, a connection has not been established.")
            
            # MongoDB 서버에 'ping'을 보내 연결이 살아있는지 최종 확인합니다.
            mongo.db.command('ping')
            print(f"MongoDB 연결 성공 (시도 {i + 1}/{retries}).")
            break  # 연결에 성공하면 재시도 루프를 중단합니다.
        except (ConnectionFailure, AttributeError) as e:
            print(f"MongoDB 연결 대기 중... (시도 {i + 1}/{retries}): {e}")
            if i < retries - 1:
                print(f"{delay}초 후 재시도합니다.")
                time.sleep(delay)
            else:
                print("최대 재시도 횟수를 초과했습니다. 메뉴 초기화에 실패했습니다.")
                raise  # 모든 재시도 실패 시, 오류를 발생시켜 배포를 중단합니다.
    
    # --- 기존 메뉴 초기화 로직 ---
    menu_items_collection = mongo.db.menu_items
    assignments_collection = mongo.db.role_menu_assignments

    # 1. 애플리케이션의 모든 메뉴 아이템 정의
    all_menus = [
        # 사용자 메뉴
        {'name': '홈', 'url': '/', 'icon': 'fas fa-home', 'order': 10},
        {'name': '커뮤니티', 'url': '/community_list', 'icon': 'fas fa-users', 'order': 20},
        {'name': '내 마음 일기', 'url': '/diary', 'icon': 'fas fa-book-medical', 'order': 30},
        {'name': 'AI 챗봇', 'url': '/ai_chat', 'icon': 'fas fa-robot', 'order': 40},
        {'name': '나의 변화', 'url': '/my_changes', 'icon': 'fas fa-chart-line', 'order': 50},
        {'name': '문의사항', 'url': '/inquiry', 'icon': 'fas fa-question-circle', 'order': 60},
        {'name': '심리 테스트', 'url': '/psych_test', 'icon': 'fas fa-brain', 'order': 70},
        # 관리자 메뉴
        {'name': '관리자 대시보드', 'url': '/admin/dashboard', 'icon': 'fas fa-tachometer-alt', 'order': 100},
        {'name': '사용자 관리', 'url': '/admin/user_management', 'icon': 'fas fa-users-cog', 'order': 110},
        {'name': '메뉴 관리', 'url': '/admin/menu_management', 'icon': 'fas fa-bars', 'order': 120},
        {'name': '역할-메뉴 할당', 'url': '/admin/role_menu_assignment', 'icon': 'fas fa-user-tag', 'order': 130},
        {'name': '공지사항 관리', 'url': '/admin/notice_management', 'icon': 'fas fa-bullhorn', 'order': 140},
        {'name': 'DB 관리', 'url': '/admin/db_management', 'icon': 'fas fa-database', 'order': 150},
        {'name': '게시글 관리', 'url': '/admin/post_management', 'icon': 'fas fa-file-alt', 'order': 160},
        {'name': 'CMS 관리', 'url': '/admin/cms_management', 'icon': 'fas fa-cogs', 'order': 170},
        {'name': '데이터 분석', 'url': '/admin/data_analytics', 'icon': 'fas fa-chart-pie', 'order': 180},
        {'name': '챗봇 피드백', 'url': '/admin/chatbot_feedback', 'icon': 'fas fa-comments', 'order': 190},
        {'name': '문의사항 관리', 'url': '/admin/inquiry_management', 'icon': 'fas fa-envelope-open-text', 'order': 195},
    ]

    menu_ids_map = {}
    for menu in all_menus:
        existing_menu = menu_items_collection.find_one({'name': menu['name']})
        if not existing_menu:
            result = menu_items_collection.insert_one(menu)
            menu_id = result.inserted_id
        else:
            menu_id = existing_menu['_id']
            menu_items_collection.update_one(
                {'_id': menu_id},
                {'$set': {'url': menu['url'], 'icon': menu['icon'], 'order': menu['order']}}
            )
        menu_ids_map[menu['name']] = str(menu_id)
    print("모든 메뉴 아이템 확인/생성 완료.")

    # 3. 역할별 메뉴 할당
    role_menus = {
        '관리자': ['홈', '커뮤니티', '내 마음 일기', 'AI 챗봇', '나의 변화', '문의사항', '심리 테스트',
                   '관리자 대시보드', '사용자 관리', '메뉴 관리', '역할-메뉴 할당', '공지사항 관리',
                   'DB 관리', '게시글 관리', 'CMS 관리', '데이터 분석', '챗봇 피드백', '문의사항 관리'],
        '운영자': ['홈', '커뮤니티', '내 마음 일기', 'AI 챗봇', '나의 변화', '문의사항', '심리 테스트',
                   '공지사항 관리', '게시글 관리', '문의사항 관리'],
        '개발자': ['홈', '커뮤니티', '내 마음 일기', 'AI 챗봇', '나의 변화', '문의사항', '심리 테스트',
                   'DB 관리', '챗봇 피드백'],
        '연구자': ['홈', '커뮤니티', '내 마음 일기', 'AI 챗봇', '나의 변화', '문의사항', '심리 테스트',
                   'DB 관리', '데이터 분석'],
        '일반 사용자': ['홈', '커뮤니티', '내 마음 일기', 'AI 챗봇', '나의 변화', '문의사항', '심리 테스트']
    }

    for role, menu_names in role_menus.items():
        menu_ids = [menu_ids_map[name] for name in menu_names if name in menu_ids_map]
        assignments_collection.update_one(
            {'role_name': role},
            {'$set': {'menu_ids': menu_ids}},
            upsert=True
        )
        print(f"'{role}' 역할에 메뉴 할당 완료.")

    print("메뉴 초기화가 성공적으로 완료되었습니다.")

