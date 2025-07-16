# app.py
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
    (아직 키워드 페이지 HTML을 받지 못했지만, 라우트만 미리 추가합니다.)
    """
    return render_template('keyword.html') # 'keyword.html' 파일이 필요합니다.

@app.route('/login')
def login():
    """
    로그인 페이지를 렌더링합니다.
    """
    return render_template('login.html')

@app.route('/signup')
def signup():
    """
    회원가입 페이지는 일반적으로 로그인 페이지와 유사하거나 별도입니다.
    지금은 단순 예시를 위해 로그인 페이지와 동일하게 처리하거나,
    새로운 signup.html을 만들 수 있습니다.
    여기서는 'login.html'과 유사한 레이아웃을 사용한다고 가정하고 라우트만 추가합니다.
    """
    return render_template('signup.html') # 'signup.html' 파일이 필요합니다.


if __name__ == '__main__':
    app.run(debug=True)