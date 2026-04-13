"""FastAPI 웹 서버 메인 애플리케이션"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import json
import os
from typing import Optional

from app.config import SESSION_SECRET_KEY
from app.services.api_client import APIClient
from app.services.auth import (
    get_user_info,
    set_user_info,
    clear_user_info,
    require_login
)

# FastAPI 앱 생성
app = FastAPI(title="삼화페인트 챗봇 클라이언트 테스트")

# 세션 미들웨어 설정
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    max_age=86400  # 24시간
)

# 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """루트 경로 - 로그인 화면으로 리다이렉트"""
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """로그인 화면"""
    # 이미 로그인된 경우 채팅 화면으로 리다이렉트
    if get_user_info(request):
        return RedirectResponse(url="/chat")
    
    api_client = APIClient()
    group_codes = []
    kb_domains = []
    error_message = None
    
    try:
        # Group Code 목록 조회 (로그인 페이지는 헤더 없이 시도, 실패 시 빈 리스트 반환)
        try:
            group_codes = await api_client.get_group_codes()
        except:
            group_codes = []
        # KB Domain 목록 조회
        try:
            kb_domains = await api_client.get_kb_domains()
        except:
            kb_domains = []
    except Exception as e:
        # API 호출 실패 시 에러 메시지 저장
        error_message = f"백엔드 API 호출 실패: {str(e)}"
    finally:
        await api_client.close()
    
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "group_codes": group_codes or [],
            "kb_domains": kb_domains or [],
            "error": error_message
        }
    )


@app.post("/login")
async def login(request: Request):
    """로그인 처리"""
    form = await request.form()
    
    corp_id = form.get("corp_id", "").strip()
    employee_id = form.get("employee_id", "").strip()
    user_name = form.get("user_name", "").strip()
    department = form.get("department", "").strip()
    group_code = form.get("group_code", "").strip()
    
    # 필수 필드 검증
    if not all([corp_id, employee_id, user_name, department, group_code]):
        raise HTTPException(status_code=400, detail="모든 필드를 입력해주세요")
    
    # 사용자 정보 세션에 저장
    user_info = {
        "corp_id": corp_id,
        "employee_id": employee_id,
        "name": user_name,
        "department": department,
        "group_code": group_code
    }
    set_user_info(request, user_info)
    
    return RedirectResponse(url="/chat", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    """로그아웃 처리"""
    clear_user_info(request)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """채팅 화면"""
    # 로그인 확인
    user_info = require_login(request)
    
    api_client = APIClient()
    conversations = []
    error_message = None
    
    try:
        # 대화 목록 조회
        conversations = await api_client.get_conversation_history(
            user_info["corp_id"],
            user_info["employee_id"]
        )
    except Exception as e:
        conversations = []
        error_message = str(e)
    finally:
        await api_client.close()
    
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "user_info": user_info,
            "conversations": conversations or [],
            "error": error_message
        }
    )


@app.post("/chat")
async def send_chat(request: Request):
    """채팅 메시지 전송 (SSE 스트리밍)"""
    # 로그인 확인
    user_info = require_login(request)
    
    body = await request.json()
    message = body.get("message", "").strip()
    conversation_id = body.get("conversation_id")
    
    if not message:
        raise HTTPException(status_code=400, detail="메시지를 입력해주세요")
    
    api_client = APIClient()
    
    async def generate():
        try:
            async for line in api_client.send_chat_message(
                message=message,
                conversation_id=conversation_id,
                group_code=user_info["group_code"],
                corp_id=user_info["corp_id"],
                employee_id=user_info["employee_id"],
                name=user_info["name"],
                department=user_info["department"]
            ):
                yield line + "\n"
        except Exception as e:
            error_msg = str(e)
            print(f"[ERROR] send_chat 에러: {error_msg}")
            import traceback
            print(f"[ERROR] 트레이스백: {traceback.format_exc()}")
            error_data = json.dumps({"error": error_msg})
            yield f"data: {error_data}\n\n"
        finally:
            await api_client.close()
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/conversations")
async def get_conversations(request: Request):
    """대화 목록 조회 (동적 업데이트용)"""
    # 로그인 확인
    user_info = require_login(request)
    
    api_client = APIClient()
    try:
        conversations = await api_client.get_conversation_history(
            user_info["corp_id"],
            user_info["employee_id"]
        )
        return {"conversations": conversations or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.get("/api/history/{conversation_id}")
async def get_conversation(request: Request, conversation_id: str):
    """대화 상세 조회"""
    # 로그인 확인
    user_info = require_login(request)
    
    api_client = APIClient()
    try:
        conversation = await api_client.get_conversation_detail(conversation_id, user_info["employee_id"])
        return conversation
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.put("/api/history/{conversation_id}/title")
async def update_conversation_title(request: Request, conversation_id: str):
    """대화 제목 수정"""
    # 로그인 확인
    user_info = require_login(request)
    
    # 본문에서 title을 받음 (명세서에 따르면 employee_id도 포함)
    body = await request.json()
    title = body.get("title", "").strip()
    
    if not title:
        raise HTTPException(status_code=400, detail="제목을 입력해주세요")
    
    api_client = APIClient()
    try:
        result = await api_client.update_conversation_title(conversation_id, title, user_info["employee_id"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.delete("/api/history/{conversation_id}")
async def delete_conversation(request: Request, conversation_id: str):
    """대화 삭제"""
    # 로그인 확인
    user_info = require_login(request)
    
    api_client = APIClient()
    try:
        await api_client.delete_conversation(conversation_id, user_info["employee_id"])
        return {
            "message": "대화가 성공적으로 삭제되었습니다.",
            "conversation_id": conversation_id,
            "deleted_by": user_info["employee_id"]
        }
    except HTTPException:
        # HTTPException은 그대로 전달
        raise
    except Exception as e:
        # 에러 메시지를 더 자세히 로깅하고 원본 에러 정보 포함
        import traceback
        error_detail = str(e)
        error_trace = traceback.format_exc()
        print(f"DELETE 요청 에러 상세: {error_detail}")
        print(f"에러 트레이스: {error_trace}")
        raise HTTPException(status_code=500, detail=error_detail)
    finally:
        await api_client.close()


@app.post("/api/admin/group-codes")
async def create_group_code(request: Request):
    """Group Code 생성"""
    # 로그인 확인
    user_info = require_login(request)
    
    body = await request.json()
    code = body.get("code", "").strip()
    description = body.get("description", "").strip()
    kb_domains = body.get("kb_domains", [])
    
    # kb_domains가 배열인지 확인
    if not isinstance(kb_domains, list):
        raise HTTPException(status_code=400, detail="kb_domains는 배열 형식이어야 합니다")
    
    if not code:
        raise HTTPException(status_code=400, detail="Code를 입력해주세요")
    
    api_client = APIClient()
    try:
        result = await api_client.create_group_code(code, description, kb_domains, admin_employee_id=user_info["employee_id"])
        # 백엔드 응답의 kb_domains를 문자열로 변환 (응답 스키마가 문자열을 기대)
        if isinstance(result, dict) and 'kb_domains' in result:
            if isinstance(result['kb_domains'], list):
                result['kb_domains'] = ','.join(result['kb_domains'])
        return result
    except Exception as e:
        error_msg = str(e)
        # HTTP 상태 코드가 포함된 에러 메시지에서 상태 코드 추출
        if "HTTP 400" in error_msg or "HTTP 404" in error_msg or "HTTP 409" in error_msg:
            # 백엔드 에러 메시지 파싱 시도
            import json
            try:
                # 에러 메시지에서 JSON 부분 추출
                if "{" in error_msg:
                    json_start = error_msg.find("{")
                    json_str = error_msg[json_start:]
                    error_data = json.loads(json_str)
                    if "detail" in error_data and isinstance(error_data["detail"], dict):
                        message = error_data["detail"].get("message", error_msg)
                        raise HTTPException(status_code=400, detail=message)
            except (json.JSONDecodeError, ValueError):
                pass
            # JSON 파싱 실패 시 원본 메시지 사용
            raise HTTPException(status_code=400, detail=error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    finally:
        await api_client.close()


@app.put("/api/admin/group-codes/{code}")
async def update_group_code(request: Request, code: str):
    """Group Code 수정"""
    # 로그인 확인
    user_info = require_login(request)
    
    body = await request.json()
    description = body.get("description", "").strip()
    kb_domains = body.get("kb_domains", [])
    
    # kb_domains가 배열인지 확인
    if not isinstance(kb_domains, list):
        raise HTTPException(status_code=400, detail="kb_domains는 배열 형식이어야 합니다")
    
    api_client = APIClient()
    try:
        result = await api_client.update_group_code(code, description, kb_domains, admin_employee_id=user_info["employee_id"])
        # 백엔드 응답의 kb_domains를 문자열로 변환 (응답 스키마가 문자열을 기대)
        if isinstance(result, dict) and 'kb_domains' in result:
            if isinstance(result['kb_domains'], list):
                result['kb_domains'] = ','.join(result['kb_domains'])
        return result
    except Exception as e:
        error_msg = str(e)
        # HTTP 상태 코드가 포함된 에러 메시지에서 상태 코드 추출
        if "HTTP 400" in error_msg or "HTTP 404" in error_msg or "HTTP 409" in error_msg:
            # 백엔드 에러 메시지 파싱 시도
            import json
            try:
                # 에러 메시지에서 JSON 부분 추출
                if "{" in error_msg:
                    json_start = error_msg.find("{")
                    json_str = error_msg[json_start:]
                    error_data = json.loads(json_str)
                    if "detail" in error_data and isinstance(error_data["detail"], dict):
                        message = error_data["detail"].get("message", error_msg)
                        raise HTTPException(status_code=400, detail=message)
            except (json.JSONDecodeError, ValueError):
                pass
            # JSON 파싱 실패 시 원본 메시지 사용
            raise HTTPException(status_code=400, detail=error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    finally:
        await api_client.close()


@app.delete("/api/admin/group-codes/{code}")
async def delete_group_code(request: Request, code: str):
    """Group Code 삭제"""
    # 로그인 확인
    user_info = require_login(request)
    
    api_client = APIClient()
    try:
        await api_client.delete_group_code(code, admin_employee_id=user_info["employee_id"])
        return {"message": "Group Code가 삭제되었습니다"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.get("/api/admin/kb-domains")
async def get_kb_domains(request: Request):
    """KB Domain 목록 조회"""
    # 로그인 확인
    user_info = require_login(request)
    
    api_client = APIClient()
    try:
        kb_domains = await api_client.get_kb_domains(admin_employee_id=user_info["employee_id"])
        return {"kb_domains": kb_domains}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.post("/api/admin/kb-domains")
async def create_kb_domain(request: Request):
    """KB Domain 생성"""
    # 로그인 확인
    user_info = require_login(request)
    
    body = await request.json()
    code = body.get("code", "").strip()
    name = body.get("name", "").strip()
    s3_path = body.get("s3_path", "").strip()
    
    if not code:
        raise HTTPException(status_code=400, detail="Code를 입력해주세요")
    
    api_client = APIClient()
    try:
        result = await api_client.create_kb_domain(code, name, s3_path, admin_employee_id=user_info["employee_id"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.put("/api/admin/kb-domains/{code}")
async def update_kb_domain(request: Request, code: str):
    """KB Domain 수정"""
    # 로그인 확인
    user_info = require_login(request)
    
    body = await request.json()
    name = body.get("name", "").strip()
    s3_path = body.get("s3_path", "").strip()
    
    api_client = APIClient()
    try:
        result = await api_client.update_kb_domain(code, name, s3_path, admin_employee_id=user_info["employee_id"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.delete("/api/admin/kb-domains/{code}")
async def delete_kb_domain(request: Request, code: str):
    """KB Domain 삭제"""
    # 로그인 확인
    user_info = require_login(request)
    
    api_client = APIClient()
    try:
        await api_client.delete_kb_domain(code, admin_employee_id=user_info["employee_id"])
        return {"message": "KB Domain이 삭제되었습니다"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.get("/api/admin/monitoring/token-usage")
async def get_total_token_usage(request: Request):
    """전체 토큰 사용량 조회 (관리자용)"""
    # 로그인 확인
    user_info = require_login(request)
    
    # 쿼리 파라미터 추출
    from_date = request.query_params.get("from")
    to_date = request.query_params.get("to")
    tz = request.query_params.get("tz", "Asia/Seoul")
    
    api_client = APIClient()
    try:
        result = await api_client.get_total_token_usage(
            from_date=from_date,
            to_date=to_date,
            tz=tz,
            employee_id=user_info["employee_id"]
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.get("/api/admin/monitoring/users/{employee_id}/token-usage")
async def get_user_token_usage(request: Request, employee_id: str):
    """사용자별 토큰 사용량 조회 (관리자용)"""
    # 로그인 확인
    admin_user_info = require_login(request)
    
    # 쿼리 파라미터 추출
    from_date = request.query_params.get("from")
    to_date = request.query_params.get("to")
    tz = request.query_params.get("tz", "Asia/Seoul")
    
    api_client = APIClient()
    try:
        result = await api_client.get_user_token_usage(
            employee_id=employee_id,
            from_date=from_date,
            to_date=to_date,
            tz=tz,
            admin_employee_id=admin_user_info["employee_id"]
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.get("/api/admin/monitoring/users")
async def get_monitoring_users(request: Request):
    """전체 챗봇 사용자 리스트 조회 (관리자용)"""
    # 로그인 확인
    admin_user_info = require_login(request)
    
    # 쿼리 파라미터 추출
    corp_id = request.query_params.get("corp_id")
    department = request.query_params.get("department")
    q = request.query_params.get("q")
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 50))
    
    api_client = APIClient()
    try:
        result = await api_client.get_monitoring_users(
            corp_id=corp_id,
            department=department,
            q=q,
            page=page,
            page_size=page_size,
            admin_employee_id=admin_user_info["employee_id"]
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.get("/api/admin/monitoring/token-usage/users")
async def get_monitoring_token_usage_users(request: Request):
    """전체 사용자별 토큰 사용량 조회 (관리자용)"""
    # 로그인 확인
    admin_user_info = require_login(request)
    
    # 쿼리 파라미터 추출
    from_date = request.query_params.get("from")
    to_date = request.query_params.get("to")
    corp_id = request.query_params.get("corp_id")
    department = request.query_params.get("department")
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 50))
    
    if not from_date or not to_date:
        raise HTTPException(status_code=400, detail="from과 to 날짜 파라미터는 필수입니다")
    
    api_client = APIClient()
    try:
        result = await api_client.get_monitoring_token_usage_users(
            from_date=from_date,
            to_date=to_date,
            corp_id=corp_id,
            department=department,
            page=page,
            page_size=page_size,
            admin_employee_id=admin_user_info["employee_id"]
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.get("/api/admin/monitoring/token-usage/users/daily")
async def get_monitoring_token_usage_users_daily(request: Request):
    """전체 사용자별 일자별 토큰 사용량 조회 (관리자용)"""
    # 로그인 확인
    admin_user_info = require_login(request)
    
    # 쿼리 파라미터 추출
    from_date = request.query_params.get("from")
    to_date = request.query_params.get("to")
    tz = request.query_params.get("tz", "Asia/Seoul")
    employee_id = request.query_params.get("employee_id")
    
    if not from_date or not to_date:
        raise HTTPException(status_code=400, detail="from과 to 날짜 파라미터는 필수입니다")
    
    api_client = APIClient()
    try:
        result = await api_client.get_monitoring_token_usage_users_daily(
            from_date=from_date,
            to_date=to_date,
            tz=tz,
            employee_id=employee_id,
            admin_employee_id=admin_user_info["employee_id"]
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.get("/api/admin/monitoring/questions/users")
async def get_monitoring_questions_users(request: Request):
    """전체 사용자별 질문 횟수 조회 (관리자용)"""
    # 로그인 확인
    admin_user_info = require_login(request)
    
    # 쿼리 파라미터 추출
    from_date = request.query_params.get("from")
    to_date = request.query_params.get("to")
    department = request.query_params.get("department")
    page = int(request.query_params.get("page", 1))
    page_size = int(request.query_params.get("page_size", 50))
    
    if not from_date or not to_date:
        raise HTTPException(status_code=400, detail="from과 to 날짜 파라미터는 필수입니다")
    
    api_client = APIClient()
    try:
        result = await api_client.get_monitoring_questions_users(
            from_date=from_date,
            to_date=to_date,
            department=department,
            page=page,
            page_size=page_size,
            admin_employee_id=admin_user_info["employee_id"]
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.get("/api/admin/monitoring/history")
async def get_monitoring_history(request: Request):
    """사용자별 대화 이력 목록 조회 (관리자용)"""
    # 로그인 확인
    admin_user_info = require_login(request)
    
    # 쿼리 파라미터 추출
    user_name = request.query_params.get("user_name")
    employee_id = request.query_params.get("employee_id")
    department = request.query_params.get("department")
    page = int(request.query_params.get("page", 1))
    pagesize = int(request.query_params.get("pagesize", 20))
    
    api_client = APIClient()
    try:
        result = await api_client.get_monitoring_history(
            user_name=user_name,
            employee_id=employee_id,
            department=department,
            page=page,
            pagesize=pagesize,
            admin_employee_id=admin_user_info["employee_id"]
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.get("/api/admin/monitoring/history/{conversation_id}")
async def get_monitoring_history_detail(request: Request, conversation_id: str):
    """대화 상세 조회 (관리자용)"""
    # 로그인 확인
    admin_user_info = require_login(request)
    
    api_client = APIClient()
    try:
        result = await api_client.get_monitoring_history_detail(
            conversation_id=conversation_id,
            admin_employee_id=admin_user_info["employee_id"]
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.get("/api/admin/kb/data-sources")
async def get_kb_data_sources(request: Request):
    """데이터 소스 상태 조회 (관리자용)"""
    # 로그인 확인
    admin_user_info = require_login(request)
    
    api_client = APIClient()
    try:
        result = await api_client.get_kb_data_sources(
            admin_employee_id=admin_user_info["employee_id"]
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.get("/api/admin/kb/files")
async def get_kb_files(request: Request):
    """파일 목록 조회 (관리자용)"""
    # 로그인 확인
    admin_user_info = require_login(request)
    
    # 쿼리 파라미터 추출
    path = request.query_params.get("path")
    
    if not path:
        raise HTTPException(status_code=400, detail="path 파라미터는 필수입니다")
    
    api_client = APIClient()
    try:
        result = await api_client.get_kb_files(
            path=path,
            admin_employee_id=admin_user_info["employee_id"]
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await api_client.close()


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    """관리자 화면"""
    # 로그인 확인
    user_info = require_login(request)
    
    api_client = APIClient()
    try:
        group_codes = await api_client.get_group_codes(admin_employee_id=user_info["employee_id"])
        kb_domains = await api_client.get_kb_domains(admin_employee_id=user_info["employee_id"])
    except Exception as e:
        group_codes = []
        kb_domains = []
        error_message = str(e)
    finally:
        await api_client.close()
    
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "user_info": user_info,
            "group_codes": group_codes,
            "kb_domains": kb_domains,
            "error": error_message if 'error_message' in locals() else None
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)

