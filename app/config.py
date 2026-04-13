"""설정 관리 모듈"""
import os
from dotenv import load_dotenv

load_dotenv()

# AWS ECS에 배포된 백엔드 API URL (기본값)
# 로컬 백엔드 테스트 시 .env 파일에서 http://localhost:8000으로 변경 가능
BACKEND_API_URL = os.getenv(
    "BACKEND_API_URL",
    "http://samwha-lb-1905937519.ap-northeast-2.elb.amazonaws.com"
)

# 세션 시크릿 키
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "change-this-to-random-string")

# 디버그 모드
DEBUG = os.getenv("DEBUG", "True").lower() == "true"









