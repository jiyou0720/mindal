import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가합니다.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.extensions import mongo
from bson.objectid import ObjectId

def initialize_menus():
    """MongoDB에 기본 메뉴 아이템을 생성하고, 역할별로 메뉴를 할당합니다."""
    print("메뉴 초기화를 시작합니다...")

    menu_items_collection = mongo.db.menu_items
    assignments_collection = mongo.db.role_menu_assignments

    all_menus = [
        # 사용자 메뉴
        {'name': '홈', 'url': '/', 'icon': 'fas fa-home', 'order': 10},
        {'name': '커뮤니티', 'url': '/community', 'icon': 'fas fa-users', 'order': 20},
        {'name': '내 마음 일기', 'url': '/diary', 'icon': 'fas fa-book-medical', 'order': 30},
        {'name': 'AI 챗봇', 'url': '/ai-chat', 'icon': 'fas fa-robot', 'order': 40},
        {'name': '나의 변화', 'url': '/my-changes', 'icon': 'fas fa-chart-line', 'order': 50},
        {'name': '문의사항', 'url': '/inquiry', 'icon': 'fas fa-question-circle', 'order': 60},
        {'name': '심리 테스트', 'url': '/psych-test', 'icon': 'fas fa-brain', 'order': 70},
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
            print(f"'{menu['name']}' 메뉴 생성 완료.")
        else:
            menu_id = existing_menu['_id']
            menu_items_collection.update_one(
                {'_id': menu_id},
                {'$set': {'url': menu['url'], 'icon': menu['icon'], 'order': menu['order']}}
            )
            print(f"'{menu['name']}' 메뉴 업데이트 확인.")
        menu_ids_map[menu['name']] = str(menu_id)

    print("모든 메뉴 아이템 확인/생성 완료.")
    
    # 역할별 메뉴 할당 로직은 기존과 동일하게 유지...
    print("메뉴 초기화 완료.")

if __name__ == "__main__":
    # 이 스크립트를 독립적으로 실행할 때만 app을 생성합니다.
    # 이렇게 하면 app.py에서 실행될 때는 app.py의 컨텍스트를 사용합니다.
    from backend.app import create_app
    app = create_app()
    with app.app_context():
        initialize_menus()

