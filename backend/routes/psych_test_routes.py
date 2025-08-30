# backend/routes/psych_test_routes.py
from flask import Blueprint, request, jsonify, g, current_app
from backend.extensions import mongo
from backend.routes.auth_routes import token_required
from backend.mongo_models import PsychTest, PsychQuestion, PsychTestResult
from bson.objectid import ObjectId
import datetime

psych_test_bp = Blueprint('psych_test_api', __name__)

# 테스트 목록 조회
@psych_test_bp.route('/tests', methods=['GET'])
@token_required
def get_tests():
    """사용 가능한 심리 테스트 목록을 조회합니다."""
    try:
        tests = list(mongo.db.psych_tests.find({}).sort('created_at', 1))
        for test in tests:
            test['_id'] = str(test['_id'])
            test['questions'] = [str(q_id) for q_id in test.get('questions', [])] # 질문 ID를 문자열로 변환
            if 'created_at' in test and isinstance(test['created_at'], datetime.datetime):
                test['created_at'] = test['created_at'].isoformat()
        return jsonify({'tests': tests}), 200
    except Exception as e:
        current_app.logger.error(f"심리 테스트 목록 조회 중 오류 발생: {e}", exc_info=True)
        return jsonify({'message': '테스트 목록을 불러오는 데 실패했습니다.'}), 500

# 특정 테스트 질문 조회
@psych_test_bp.route('/tests/<string:test_id>/questions', methods=['GET'])
@token_required
def get_test_questions(test_id):
    """특정 심리 테스트의 질문 목록을 조회합니다."""
    try:
        test = mongo.db.psych_tests.find_one({'_id': ObjectId(test_id)})
        if not test:
            return jsonify({'message': '테스트를 찾을 수 없습니다.'}), 404
        
        # 테스트 문서에 질문 ID 목록이 저장되어 있다고 가정하고, 해당 ID로 질문들을 조회
        question_ids = test.get('questions', [])
        questions = list(mongo.db.psych_questions.find({'_id': {'$in': [ObjectId(q_id) for q_id in question_ids]}}).sort('order', 1))

        for q in questions:
            q['_id'] = str(q['_id'])
            q['test_id'] = str(q['test_id']) # test_id도 문자열로 변환
        
        return jsonify({'test_title': test['title'], 'questions': questions}), 200
    except Exception as e:
        current_app.logger.error(f"테스트 질문 조회 중 오류 발생 (test_id: {test_id}): {e}", exc_info=True)
        return jsonify({'message': '테스트 질문을 불러오는 데 실패했습니다.'}), 500

# 테스트 결과 제출 및 계산
@psych_test_bp.route('/tests/<string:test_id>/submit_result', methods=['POST'])
@token_required
def submit_test_result(test_id):
    """심리 테스트 결과를 제출하고 계산합니다."""
    user_id = g.user_id
    data = request.get_json()
    answers = data.get('answers') # [{"question_id": "...", "selected_option_index": 0}]

    if not answers:
        return jsonify({'message': '제출된 답변이 없습니다.'}), 400

    try:
        test = mongo.db.psych_tests.find_one({'_id': ObjectId(test_id)})
        if not test:
            return jsonify({'message': '테스트를 찾을 수 없습니다.'}), 404
        
        # 질문들을 미리 불러와서 답변 점수 계산에 사용
        question_ids_in_test = test.get('questions', [])
        test_questions = list(mongo.db.psych_questions.find({'_id': {'$in': [ObjectId(q_id) for q_id in question_ids_in_test]}}))
        questions_map = {str(q['_id']): q for q in test_questions}

        total_score = 0
        processed_answers = []
        for ans in answers:
            q_id = ans.get('question_id')
            selected_option_index = ans.get('selected_option_index')

            question = questions_map.get(q_id)
            if not question or not isinstance(selected_option_index, int) or \
               selected_option_index < 0 or selected_option_index >= len(question.get('options', [])):
                current_app.logger.warning(f"유효하지 않은 답변: question_id={q_id}, selected_option_index={selected_option_index}")
                continue # 유효하지 않은 답변은 건너뜜

            option = question['options'][selected_option_index]
            score = option.get('score', 0)
            total_score += score
            processed_answers.append({
                "question_id": q_id,
                "selected_option_index": selected_option_index,
                "score": score
            })

        # --- 결과 요약 및 상세 계산 로직 (예시) ---
        # 실제로는 테스트 유형에 따라 복잡한 로직이 필요합니다.
        result_summary = "테스트 결과 요약"
        result_details = {"total_score": total_score}

        if test['test_type'] == 'personality':
            if total_score >= 80:
                result_summary = "당신은 매우 외향적인 성격입니다."
                result_details['type'] = "Extrovert"
            elif total_score >= 50:
                result_summary = "당신은 중간 정도의 외향성을 가집니다."
                result_details['type'] = "Ambivert"
            else:
                result_summary = "당신은 내향적인 성격입니다."
                result_details['type'] = "Introvert"
            
            # 예시: 각 옵션별 점수 합산하여 상세 결과 구성
            score_by_option_type = {} # 예시: {"긍정": 30, "부정": 20}
            for ans in processed_answers:
                q = questions_map[ans['question_id']]
                option_text = q['options'][ans['selected_option_index']]['text']
                # 실제 테스트에서는 옵션에 점수 외에 다른 유형 정보가 있을 수 있음
                score_by_option_type[option_text] = score_by_option_type.get(option_text, 0) + ans['score']
            result_details['scores_by_option'] = score_by_option_type

        elif test['test_type'] == 'emotion_diagnosis':
            if total_score >= 70:
                result_summary = "현재 높은 수준의 스트레스를 경험하고 있습니다. 전문가와 상담을 고려해보세요."
                result_details['level'] = "High Stress"
            elif total_score >= 40:
                result_summary = "일반적인 수준의 스트레스를 경험하고 있습니다. 휴식이 필요합니다."
                result_details['level'] = "Moderate Stress"
            else:
                result_summary = "현재 안정적인 감정 상태입니다."
                result_details['level'] = "Low Stress"
            
            # 감정별 점수 분포 등 상세 결과 구성 가능
            result_details['emotional_indicators'] = {"stress_score": total_score, "anxiety_score": 0} # 예시

        # PsychTestResult 모델을 사용하여 결과 저장
        new_result = PsychTestResult(
            user_id=user_id,
            test_id=test_id,
            answers=processed_answers,
            result_summary=result_summary,
            result_details=result_details
        )
        result_db = mongo.db.psych_test_results.insert_one(new_result.to_dict())
        
        return jsonify({
            'message': '테스트 결과가 성공적으로 제출되었습니다.',
            'result_id': str(result_db.inserted_id),
            'summary': result_summary
        }), 201

    except Exception as e:
        current_app.logger.error(f"테스트 결과 제출 중 오류 발생 (test_id: {test_id}, user_id: {user_id}): {e}", exc_info=True)
        return jsonify({'message': '테스트 결과 제출에 실패했습니다.'}), 500

# 사용자 테스트 결과 조회
@psych_test_bp.route('/results/<string:result_id>', methods=['GET'])
@token_required
def get_test_result(result_id):
    """특정 테스트 결과를 조회합니다."""
    user_id = g.user_id
    try:
        result = mongo.db.psych_test_results.find_one({'_id': ObjectId(result_id), 'user_id': user_id})
        if not result:
            return jsonify({'message': '테스트 결과를 찾을 수 없거나 접근 권한이 없습니다.'}), 404
        
        result['_id'] = str(result['_id'])
        result['test_id'] = str(result['test_id'])
        if 'created_at' in result and isinstance(result['created_at'], datetime.datetime):
            result['created_at'] = result['created_at'].isoformat()

        # 테스트 정보도 함께 제공 (제목, 설명 등)
        test_info = mongo.db.psych_tests.find_one({'_id': ObjectId(result['test_id'])})
        if test_info:
            result['test_title'] = test_info.get('title')
            result['test_description'] = test_info.get('description')
            result['test_type'] = test_info.get('test_type')

        return jsonify({'result': result}), 200
    except Exception as e:
        current_app.logger.error(f"테스트 결과 조회 중 오류 발생 (result_id: {result_id}, user_id: {user_id}): {e}", exc_info=True)
        return jsonify({'message': '테스트 결과를 불러오는 데 실패했습니다.'}), 500

# 사용자 모든 테스트 결과 목록 조회 (마이페이지 등에서 활용)
@psych_test_bp.route('/my_results', methods=['GET'])
@token_required
def get_my_test_results():
    """현재 사용자의 모든 심리 테스트 결과 목록을 조회합니다."""
    user_id = g.user_id
    try:
        results = list(mongo.db.psych_test_results.find({'user_id': user_id}).sort('created_at', -1))
        
        results_data = []
        for res in results:
            res['_id'] = str(res['_id'])
            res['test_id'] = str(res['test_id'])
            if 'created_at' in res and isinstance(res['created_at'], datetime.datetime):
                res['created_at'] = res['created_at'].isoformat()
            
            # 각 결과에 대한 테스트 제목만 추가
            test_info = mongo.db.psych_tests.find_one({'_id': ObjectId(res['test_id'])}, {'title': 1})
            res['test_title'] = test_info.get('title') if test_info else '알 수 없는 테스트'
            
            results_data.append(res)
            
        return jsonify({'results': results_data}), 200
    except Exception as e:
        current_app.logger.error(f"사용자 테스트 결과 목록 조회 중 오류 발생 (user_id: {user_id}): {e}", exc_info=True)
        return jsonify({'message': '내 테스트 결과를 불러오는 데 실패했습니다.'}), 500
