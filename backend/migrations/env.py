import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from dotenv import load_dotenv

from alembic import context

# --- 설정 시작 ---

# Alembic Config 객체에 접근합니다. 이 객체는 alembic.ini 파일의 값들을 담고 있습니다.
config = context.config

# .ini 파일의 로깅 설정을 해석하여 적용합니다.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- 데이터베이스 연결 정보 설정 (Railway 호환) ---
# 이 마이그레이션 스크립트는 'flask db' CLI 명령어로 실행되므로,
# 실행 중인 Flask 앱 컨텍스트(current_app)에 의존하지 않고 환경 변수를 직접 읽어오는 것이 안정적입니다.

# 1. 프로젝트 루트 경로를 시스템 경로에 추가하여 'backend' 모듈을 찾을 수 있도록 합니다.
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 2. 로컬 개발을 위해 backend/.env 파일을 명시적으로 로드합니다.
dotenv_path = os.path.join(project_root, 'backend', '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)

# 3. app.py와 동일한 로직으로 데이터베이스 URL을 결정합니다.
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    MYSQL_USER = os.environ.get("MYSQL_USER")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD")
    MYSQL_HOST = os.environ.get("MYSQL_HOST")
    MYSQL_PORT = os.environ.get("MYSQL_PORT")
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE")
    if all([MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE]):
        db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

# 4. Railway의 'mysql://' 형식을 'mysql+pymysql://'로 변환합니다.
if db_url and db_url.startswith('mysql://'):
    db_url = db_url.replace('mysql://', 'mysql+pymysql://', 1)

# 5. 최종적으로 얻은 데이터베이스 URL을 Alembic 설정에 지정합니다.
config.set_main_option('sqlalchemy.url', db_url)

# --- 모델 메타데이터 설정 ---
# 'autogenerate' 기능을 사용하기 위해, Alembic이 추적해야 할 모델들의 정보를 알려주어야 합니다.
# Flask 앱 컨텍스트 없이 직접 db 객체를 임포트하여 메타데이터를 가져옵니다.
from backend.maria_models import db
target_metadata = db.metadata

# --- 마이그레이션 실행 함수 ---

def run_migrations_offline() -> None:
    """'오프라인' 모드(DB 연결 없이 SQL 스크립트만 생성)로 마이그레이션을 실행합니다."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """'온라인' 모드(DB에 직접 연결하여 마이그레이션 적용)로 마이그레이션을 실행합니다."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

# 현재 실행 모드(온라인/오프라인)에 따라 적절한 함수를 호출합니다.
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

