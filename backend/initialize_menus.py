import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가합니다.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.extensions import mongo
from bson.objectid import ObjectId # ObjectId 임포트 추가

def initialize_menus():
    """MongoDB에 기본 메뉴 아이템을 생성하고, 관리자 역할에 메뉴를 할당합니다."""
    print("메뉴 초기화를 시작합니다...")

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
        {'name': '심리 테스트', 'url': '/psych_test', 'icon': 'fas fa-brain', 'order': 70}, # NEW: 심리 테스트 메뉴 추가
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

    menu_ids_map = {} # 메뉴 이름과 MongoDB _id를 매핑
    for menu in all_menus:
        # 기존 메뉴가 있는지 확인하고, 없으면 새로 생성
        existing_menu = menu_items_collection.find_one({'name': menu['name']})
        if not existing_menu:
            result = menu_items_collection.insert_one(menu)
            menu_id = result.inserted_id
            print(f"'{menu['name']}' 메뉴 생성 완료.")
        else:
            menu_id = existing_menu['_id']
            # 기존 메뉴의 URL, 아이콘, 순서 업데이트 (필요시)
            menu_items_collection.update_one(
                {'_id': menu_id},
                {'$set': {
                    'url': menu['url'],
                    'icon': menu['icon'],
                    'order': menu['order']
                }}
            )
            print(f"'{menu['name']}' 메뉴 업데이트 확인.")
        
        menu_ids_map[menu['name']] = str(menu_id)

    print("모든 메뉴 아이템 확인/생성 완료.")

    # 3. 역할별 메뉴 할당
    # '관리자' 역할에는 모든 메뉴를 할당
    admin_menu_names = [
        '홈', '커뮤니티', '내 마음 일기', 'AI 챗봇', '나의 변화', '문의사항', '심리 테스트', # 심리 테스트 추가
        '관리자 대시보드', '사용자 관리', '메뉴 관리', '역할-메뉴 할당', '공지사항 관리',
        'DB 관리', '게시글 관리', 'CMS 관리', '데이터 분석', '챗봇 피드백', '문의사항 관리'
    ]
    admin_menu_ids = [menu_ids_map[name] for name in admin_menu_names if name in menu_ids_map]
    
    assignments_collection.update_one(
        {'role_name': '관리자'},
        {'$set': {'menu_ids': admin_menu_ids}},
        upsert=True
    )
    print("'관리자' 역할에 메뉴 할당 완료.")

    # '운영자' 역할에는 특정 메뉴를 할당 (공지사항 관리, 게시글 관리, 문의사항 관리 포함)
    operator_menu_names = [
        '홈', '커뮤니티', '내 마음 일기', 'AI 챗봇', '나의 변화', '문의사항', '심리 테스트', # 심리 테스트 추가
        '공지사항 관리', '게시글 관리', '문의사항 관리'
    ]
    operator_menu_ids = [menu_ids_map[name] for name in operator_menu_names if name in menu_ids_map]
    
    assignments_collection.update_one(
        {'role_name': '운영자'},
        {'$set': {'menu_ids': operator_menu_ids}},
        upsert=True
    )
    print("'운영자' 역할에 메뉴 할당 완료.")

    # '개발자' 역할에는 특정 메뉴를 할당 (DB 관리, 챗봇 피드백, 문의사항 포함)
    developer_menu_names = [
        '홈', '커뮤니티', '내 마음 일기', 'AI 챗봇', '나의 변화', '문의사항', '심리 테스트', # 심리 테스트 추가
        'DB 관리', '챗봇 피드백' 
    ]
    developer_menu_ids = [menu_ids_map[name] for name in developer_menu_names if name in menu_ids_map]
    assignments_collection.update_one(
        {'role_name': '개발자'},
        {'$set': {'menu_ids': developer_menu_ids}},
        upsert=True
    )
    print("'개발자' 역할에 메뉴 할당 완료.")

    # '연구자' 역할에는 특정 메뉴를 할당 (DB 관리, 데이터 분석, 문의사항 포함)
    researcher_menu_names = [
        '홈', '커뮤니티', '내 마음 일기', 'AI 챗봇', '나의 변화', '문의사항', '심리 테스트', # 심리 테스트 추가
        'DB 관리', '데이터 분석'
    ]
    researcher_menu_ids = [menu_ids_map[name] for name in researcher_menu_names if name in menu_ids_map]
    assignments_collection.update_one(
        {'role_name': '연구자'},
        {'$set': {'menu_ids': researcher_menu_ids}},
        upsert=True
    )
    print("'연구자' 역할에 메뉴 할당 완료.")

    # '일반 사용자' 역할에는 사용자 메뉴만 할당 (문의사항, 심리 테스트 포함)
    user_menu_names = ['홈', '커뮤니티', '내 마음 일기', 'AI 챗봇', '나의 변화', '문의사항', '심리 테스트'] # 심리 테스트 메뉴 추가
    user_menu_ids = [menu_ids_map[name] for name in user_menu_names if name in menu_ids_map]
    
    assignments_collection.update_one(
        {'role_name': '일반 사용자'},
        {'$set': {'menu_ids': user_menu_ids}},
        upsert=True
    )
    print("'일반 사용자' 역할에 메뉴 할당 완료.")

    print("메뉴 초기화 완료.")
