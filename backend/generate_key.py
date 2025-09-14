
import secrets
import string

def generate_jwt_secret_key(length=32):
    """
    안전하고 무작위적인 JWT Secret Key를 생성합니다.
    기본 길이는 32바이트(256비트)입니다.
    """
    alphabet = string.ascii_letters + string.digits + string.punctuation
    # secrets.token_urlsafe는 URL-safe한 임의의 텍스트 문자열을 생성합니다.
    # Base64 인코딩된 문자열이므로, 32바이트는 약 43자의 문자열이 됩니다.
    return secrets.token_urlsafe(length)

# 키 생성 예시
jwt_secret = generate_jwt_secret_key(32)
print(f"생성된 JWT Secret Key: {jwt_secret}")
print(f"키 길이 (문자 수): {len(jwt_secret)}")