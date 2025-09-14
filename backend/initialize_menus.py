import time
from flask import current_app
from pymongo.errors import ConnectionFailure
from backend.extensions import mongo, db
from backend.maria_models import Role, Menu, RoleMenu

# 메뉴 구조 정의
MENUS = {
    '사용자 메뉴': [
        {'name': 'AI챗봇', 'endpoint': 'ai_chat'},
        {'name': '마음일기', 'endpoint': 'diary'},
        {'name': '커뮤니티', 'endpoint': 'community_list'},
        {'name': '심리검사', 'endpoint': 'psych_test_list'},
        {'name': '문의하기', 'endpoint': 'inquiry'}
    ],
    '마이페이지': [
        {'name': '나의기분', 'endpoint': 'my_changes'},
        {'name': '마이페이지', 'endpoint': 'my_page'}
    ]
}

def initialize_menus():
    print("메뉴 초기화를 시작합니다...")
    
    # 더 안전한 방법으로 데이터베이스 객체 가져오기
    try:
        # mongo.db는 현재 앱 컨텍스트에 연결된 데이터베이스 객체를 제공합니다.
        mongodb = mongo.db
        db_name = mongodb.name
        # 연결 테스트
        mongodb.client.admin.command('ping')
        print(f"MongoDB 연결 성공 (시도). Database: '{db_name}'")
    except ConnectionFailure as e:
        print(f"MongoDB 연결 실패: {e}")
        # 여러 번 재시도하는 로직을 추가할 수 있습니다.
        return
    except Exception as e:
        print(f"MongoDB 데이터베이스를 가져오는 중 에러 발생: {e}")
        return

    # MariaDB에서 역할 가져오기
    roles = Role.query.all()
    role_map = {role.name: role for role in roles}

    # 메뉴 아이템 확인 및 생성
    for category, items in MENUS.items():
        for item in items:
            menu_name = item['name']
            menu_endpoint = item['endpoint']
            
            # MariaDB에서 메뉴 확인 또는 생성
            menu_obj = Menu.query.filter_by(name=menu_name, endpoint=menu_endpoint, category=category).first()
            if not menu_obj:
                menu_obj = Menu(name=menu_name, endpoint=menu_endpoint, category=category)
                db.session.add(menu_obj)
                db.session.commit()
                print(f"메뉴 아이템 생성됨: '{category} - {menu_name}'")

            # 모든 역할에 메뉴 할당
            for role in roles:
                existing_assignment = RoleMenu.query.filter_by(role_id=role.id, menu_id=menu_obj.id).first()
                if not existing_assignment:
                    new_assignment = RoleMenu(role_id=role.id, menu_id=menu_obj.id)
                    db.session.add(new_assignment)
                    print(f"'{role.name}' 역할에 '{menu_name}' 메뉴 할당됨.")

    db.session.commit()
    print("모든 역할에 대한 메뉴 할당 완료.")
    print("메뉴 초기화가 성공적으로 완료되었습니다.")
