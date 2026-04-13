# 삼화페인트 챗봇 클라이언트 테스트 프로젝트

## 개요

이 프로젝트는 고객사 클라이언트보다 먼저 클라이언트 테스트를 진행하기 위한 독립된 테스트 환경입니다.

**중요**: 이 프로젝트를 원격 저장소에 업로드하기 전에 민감정보 포함 여부를 반드시 확인하세요.

## 기술 스택

- **Backend Framework**: FastAPI 0.104.1
- **Web Server**: Uvicorn
- **Template Engine**: Jinja2
- **HTTP Client**: httpx
- **Environment**: python-dotenv

## 프로젝트 구조

```
samhwa-chatbot-client/
├── README.md               # 이 파일
├── requirements.txt        # 의존성 패키지 정보
├── .env                    # 실제 환경변수 파일 (로컬에서 생성)
├── .gitignore              # Git 무시 파일 목록
├── docs/                   # 문서 디렉토리
├── app/                    # 애플리케이션 코드
│   ├── main.py             # FastAPI 웹 서버
│   ├── config.py           # 설정 관리
│   ├── static/             # 정적 파일 (CSS, JS, 이미지)
│   ├── templates/          # HTML 템플릿
│   └── services/           # 백엔드 API 연동 서비스
└── tests/                  # 테스트 코드
```

## 설치 및 실행

### 1. 가상환경 생성 및 활성화

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python -m venv venv
source venv/bin/activate
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정

`.env` 파일을 직접 생성하고 필요한 값을 입력하세요.

### 4. 서버 실행

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 3000
```

### 5. 브라우저에서 접속

- 로그인 화면: http://localhost:3000/
- 채팅 화면: http://localhost:3000/chat
- 관리자 화면: http://localhost:3000/admin

## 주요 기능

1. **로그인 화면** (`/login`)
   - 사용자 정보 입력 (법인 코드, 사번, 이름, 부서)
   - Group Code 선택
   - KB Domains 표시

2. **채팅 화면** (`/chat`)
   - 대화 목록 조회
   - 채팅 메시지 전송 및 SSE 스트리밍 응답 수신
   - 대화 제목 수정 및 삭제

3. **관리자 화면** (`/admin`)
   - Group Code 관리 (생성/수정/삭제)
   - KB Domain 관리 (생성/수정/삭제)

## 주의사항

- `.env` 파일은 Git에 커밋하지 않음
