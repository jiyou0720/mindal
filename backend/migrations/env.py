import os
import sys
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from dotenv import load_dotenv

# --- 경로 설정 ---
# 이 스크립트가 어디서 실행되든 프로젝트의 루트 폴더를 찾아서 경로에 추가합니다.
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 이제 backend.extensions를 안전하게 임포트할 수 있습니다.
from backend.extensions import db 
load_dotenv(os.path.join(project_root, '.env')) # 루트 폴더의 .env도 로드할 수 있도록 경로 수정

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- 데이터베이스 URL 설정 (님의 아이디어 적용) ---
# Flask 앱에 의존하지 않고, 환경 변수를 직접 읽어옵니다.
db_url = os.environ.get('MYSQL_URL') # MYSQL_URL을 찾도록 변경

if not db_url: # 로컬 환경을 위한 폴백(fallback) 로직
    MYSQL_USER = os.environ.get("MYSQL_USER")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_HOST = os.environ.get("MYSQL_HOST")
    MYSQL_PORT = os.environ.get("MYSQL_PORT")
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE")
    if all([MYSQL_USER, MYSQL_HOST, MYSQL_PORT, MYSQL_DATABASE]):
        db_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"

if not db_url:
    raise RuntimeError("데이터베이스 URL을 찾을 수 없습니다. .env 파일 또는 Railway 환경 변수를 확인해주세요.")

# SQLAlchemy가 PyMySQL 드라이버를 사용하도록 주소 형식을 변환합니다.
if db_url.startswith('mysql://'):
    db_url = db_url.replace('mysql://', 'mysql+pymysql://', 1)

config.set_main_option('sqlalchemy.url', str(db_url))
target_metadata = db.metadata

def run_migrations_offline() -> None:
    """오프라인 모드에서 마이그레이션을 실행합니다."""
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
    """온라인 모드에서 마이그레이션을 실행합니다."""
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

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()