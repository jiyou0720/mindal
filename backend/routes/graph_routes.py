from flask import Blueprint, jsonify, request, current_app, g
from backend.extensions import mongo
from backend.routes.auth_routes import token_required
from collections import Counter
# FIX: Correct the import path for mongo_models
from backend.mongo_models import DiaryEntry, MoodEntry 

graph_bp = Blueprint('graph_api', __name__)

# 감정 데이터 조회 API
@graph_bp.route('/mood_distribution', methods=['GET'])
@token_required
def get_mood_distribution():
    user_id = g.user_id
    try:
        mood_entries = mongo.db.mood_entries.find({'user_id': user_id})
        
        moods = [entry['mood'] for entry in mood_entries]
        mood_counts = Counter(moods)
        
        # Chart.js가 요구하는 형식으로 데이터 구성
        data = {
            'labels': list(mood_counts.keys()),
            'datasets': [{
                'label': '감정 분포',
                'data': list(mood_counts.values()),
                'backgroundColor': [
                    'rgba(255, 99, 132, 0.7)',
                    'rgba(54, 162, 235, 0.7)',
                    'rgba(255, 206, 86, 0.7)',
                    'rgba(75, 192, 192, 0.7)',
                    'rgba(153, 102, 255, 0.7)',
                    'rgba(255, 159, 64, 0.7)',
                    'rgba(199, 199, 199, 0.7)'
                ],
                'borderColor': [
                    'rgba(255, 99, 132, 1)',
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 206, 86, 1)',
                    'rgba(75, 192, 192, 1)',
                    'rgba(153, 102, 255, 1)',
                    'rgba(255, 159, 64, 1)',
                    'rgba(199, 199, 199, 1)'
                ],
                'borderWidth': 1
            }]
        }
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"감정 데이터 조회 중 오류 발생: {e}", exc_info=True)
        return jsonify({'message': '데이터를 불러오는 데 실패했습니다.'}), 500

# 키워드 데이터 조회 API
@graph_bp.route('/keyword_frequency', methods=['GET'])
@token_required
def get_keyword_frequency():
    user_id = g.user_id
    try:
        diary_entries = mongo.db.diary_entries.find({'user_id': user_id})
        
        all_keywords = []
        for entry in diary_entries:
            all_keywords.extend(entry.get('keywords', []))
            
        keyword_counts = Counter(all_keywords)
        
        # 가장 빈번한 10개 키워드만 선택
        top_10_keywords = keyword_counts.most_common(10)
        
        if not top_10_keywords:
             return jsonify({'labels': [], 'datasets': [{'label': '키워드 빈도', 'data': []}]})

        labels, values = zip(*top_10_keywords)
        
        data = {
            'labels': labels,
            'datasets': [{
                'label': '키워드 빈도',
                'data': values,
                'backgroundColor': 'rgba(75, 192, 192, 0.7)',
                'borderColor': 'rgba(75, 192, 192, 1)',
                'borderWidth': 1
            }]
        }
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"키워드 데이터 조회 중 오류 발생: {e}", exc_info=True)
        return jsonify({'message': '데이터를 불러오는 데 실패했습니다.'}), 500