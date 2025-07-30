# frontend\app.py
from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    """
    메인 랜딩 페이지 (Home)를 렌더링합니다.
    """
    return render_template('index.html')

@app.route('/ai-chat')
def ai_chat():
    """
    AI 채팅 페이지를 렌더링합니다.
    """
    return render_template('ai_chat.html')

@app.route('/diary')
def diary():
    """
    오늘 일기 페이지를 렌더링합니다.
    """
    return render_template('diary.html')

@app.route('/keyword')
def keyword():
    """
    키워드 페이지를 렌더링합니다.
    """
    return render_template('keyword.html')

@app.route('/my-changes')
def my_changes():
    """
    나의 변화 페이지를 렌더링합니다.
    """
    return render_template('my_changes.html')


@app.route('/login')
def login():
    """
    로그인 페이지를 렌더링합니다.
    """
    return render_template('login.html')

@app.route('/signup')
def signup():
    """
    회원가입 페이지를 렌더링합니다.
    """
    return render_template('signup.html')

@app.route('/forgot-password') # 새로운 비밀번호 찾기 라우트 추가
def forgot_password():
    """
    비밀번호 찾기 페이지를 렌더링합니다.
    """
    return render_template('forgot_password.html')


if __name__ == '__main__':
    app.run(debug=True, port=8000) # 프론트엔드는 8000번 포트에서 실행 (백엔드와 충돌 방지)