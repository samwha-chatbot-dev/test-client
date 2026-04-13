"""세션 기반 인증 관리"""
from fastapi import Request
from typing import Optional, Dict, Any


def get_user_info(request: Request) -> Optional[Dict[str, Any]]:
    """세션에서 사용자 정보 가져오기"""
    return request.session.get("user_info")


def set_user_info(request: Request, user_info: Dict[str, Any]):
    """세션에 사용자 정보 저장"""
    request.session["user_info"] = user_info


def clear_user_info(request: Request):
    """세션에서 사용자 정보 제거"""
    request.session.clear()


def require_login(request: Request) -> Dict[str, Any]:
    """로그인이 필요한 페이지에서 사용자 정보 확인
    
    Returns:
        사용자 정보 딕셔너리
        
    Raises:
        HTTPException: 로그인되지 않은 경우
    """
    user_info = get_user_info(request)
    if not user_info:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    return user_info









