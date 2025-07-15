# backend/routes/graph_routes.py
from flask import Blueprint, request, jsonify, g, current_app
from flask_pymongo import PyMongo
from auth import token_required
from mongo_models import DiaryEntry, MoodEntry # 필요한 모델 임포트
from datetime import datetime, timedelta

# Blueprint 생성
graph_bp = Blueprint('graph_api', __name__)

@graph_bp.record_once
def record(state):
    # MongoDB 인스턴스를 애플리케이션 컨텍스트에 등록
    state.app.config['MONGO_DB'] = PyMongo(state.app).db

# MongoDB 컬렉션 참조 함수
def get_diary_collection():
    return current_app.config['MONGO_DB'].diaries

def get_mood_collection():
    return current_app.config['MONGO_DB'].mood_entries

# --- 감정 그래프 관련 API 엔드포인트 ---

@graph_bp.route('/mood_summary', methods=['GET'])
@token_required
def get_mood_summary():
    user_id = g.user_id

    # 쿼리 파라미터로 기간 설정 (기본값: 최근 30일)
    # 예: /api/graph/mood_summary?period=7 (최근 7일)
    # 예: /api/graph/mood_summary?start_date=2023-01-01&end_date=2023-01-31
    period_days = request.args.get('period', type=int)
    start_date_str = request.args.get('start_date', type=str)
    end_date_str = request.args.get('end_date', type=str)

    end_date = datetime.utcnow()
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'message': 'Invalid end_date format. Use YYYY-MM-DD'}), 400

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'message': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
    elif period_days:
        start_date = end_date - timedelta(days=period_days)
    else: # 기본값: 최근 30일
        start_date = end_date - timedelta(days=30)

    # MongoDB 쿼리 조건 설정
    query_filter = {
        'user_id': user_id,
        'created_at': {
            '$gte': start_date,
            '$lt': end_date + timedelta(days=1) # end_date의 전체 날짜를 포함하기 위해 +1일
        }
    }

    mood_data = list(get_mood_collection().find(query_filter).sort('created_at', 1)) # 오름차순 정렬
    diary_data = list(get_diary_collection().find(query_filter).sort('created_at', 1)) # 오름차순 정렬

    daily_summary = {}

    # 감정 데이터 처리
    for entry in mood_data:
        # MongoDB의 created_at 필드가 datetime 객체임을 가정
        entry_date = entry['created_at'].strftime('%Y-%m-%d')
        if entry_date not in daily_summary:
            daily_summary[entry_date] = {'mood_counts': {}, 'diary_count': 0}

        mood_type = entry.get('mood_type', 'unknown').lower()
        daily_summary[entry_date]['mood_counts'][mood_type] = \
            daily_summary[entry_date]['mood_counts'].get(mood_type, 0) + 1

    # 일기 데이터 처리 (각 날짜에 일기가 몇 개 있는지 정도만)
    for entry in diary_data:
        entry_date = entry['created_at'].strftime('%Y-%m-%d')
        if entry_date not in daily_summary:
            daily_summary[entry_date] = {'mood_counts': {}, 'diary_count': 0}
        daily_summary[entry_date]['diary_count'] += 1

    # 결과 포맷팅: 날짜를 기준으로 정렬된 리스트로 변환
    # 모든 날짜 범위가 포함되도록 합니다 (데이터가 없는 날짜도 포함)
    date_list = []
    current_iter_date = start_date
    while current_iter_date <= end_date: # end_date도 포함
        date_list.append(current_iter_date.strftime('%Y-%m-%d'))
        current_iter_date += timedelta(days=1)

    graph_data = []
    for date_str in date_list:
        summary = daily_summary.get(date_str, {'mood_counts': {}, 'diary_count': 0})
        graph_data.append({
            'date': date_str,
            'mood_counts': summary['mood_counts'],
            'diary_count': summary['diary_count']
        })

    return jsonify({
        'message': 'Mood summary retrieved successfully',
        'graph_data': graph_data
    }), 200