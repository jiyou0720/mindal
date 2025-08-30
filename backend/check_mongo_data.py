import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가합니다.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.app import create_app
from backend.extensions import mongo
from bson.objectid import ObjectId

def check_data():
    """MongoDB의 메뉴 관련 데이터를 확인하고 출력합니다."""
    app = create_app()
    with app.app_context():
        print("--- MongoDB 데이터 확인 시작 ---")

        menu_items_collection = mongo.db.menu_items
        assignments_collection = mongo.db.role_menu_assignments

        # 1. 모든 메뉴 아이템 출력
        print("\n[1] 'menu_items' 컬렉션의 모든 문서:")
        all_menus = list(menu_items_collection.find({}))
        if not all_menus:
            print(" -> 'menu_items' 컬렉션이 비어있습니다.")
        for menu in all_menus:
            print(f" -> ID: {menu['_id']}, 이름: {menu['name']}, URL: {menu['url']}")

        # 2. 모든 역할-메뉴 할당 정보 출력
        print("\n[2] 'role_menu_assignments' 컬렉션의 모든 문서:")
        all_assignments = list(assignments_collection.find({}))
        if not all_assignments:
            print(" -> 'role_menu_assignments' 컬렉션이 비어있습니다.")
        for assignment in all_assignments:
            print(f" -> 역할: {assignment['role_name']}, 할당된 메뉴 ID 개수: {len(assignment.get('menu_ids', []))}")

        # 3. '관리자' 역할의 메뉴 상세 정보 출력
        print("\n[3] '관리자' 역할에 할당된 메뉴 상세 정보:")
        admin_assignment = assignments_collection.find_one({'role_name': '관리자'})
        if not admin_assignment or not admin_assignment.get('menu_ids'):
            print(" -> '관리자' 역할에 할당된 메뉴가 없습니다.")
        else:
            admin_menu_ids_str = admin_assignment.get('menu_ids', [])
            admin_menu_ids_obj = [ObjectId(id_str) for id_str in admin_menu_ids_str]
            
            assigned_menus = list(menu_items_collection.find({'_id': {'$in': admin_menu_ids_obj}}))
            if not assigned_menus:
                print(" -> 할당된 메뉴 ID는 있으나, 'menu_items'에서 해당 문서를 찾을 수 없습니다.")
            for menu in assigned_menus:
                 print(f" -> 이름: {menu['name']}, URL: {menu['url']}")

        print("\n--- 데이터 확인 종료 ---")

if __name__ == '__main__':
    check_data()

