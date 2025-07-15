from werkzeug.security import generate_password_hash, check_password_hash

# 테스트할 비밀번호
password_to_test = "password123"
wrong_password = "wrongpassword"

print(f"--- Werkzeug Security 독립 테스트 ---")

# 1. 비밀번호 해싱 테스트
print(f"\n1. '{password_to_test}' 비밀번호 해싱 시도...")
hashed_password = generate_password_hash(password_to_test)
print(f"생성된 해시: {hashed_password}")

# 2. 올바른 비밀번호로 해시 검증 테스트
print(f"\n2. 올바른 비밀번호 '{password_to_test}'로 해시 검증 시도...")
is_correct = check_password_hash(hashed_password, password_to_test)
print(f"검증 결과 (올바름): {is_correct}")

# 3. 잘못된 비밀번호로 해시 검증 테스트
print(f"\n3. 잘못된 비밀번호 '{wrong_password}'로 해시 검증 시도...")
is_wrong = check_password_hash(hashed_password, wrong_password)
print(f"검증 결과 (틀림): {is_wrong}")

print(f"\n--- 테스트 완료 ---")