"""백엔드 API 클라이언트"""
import httpx
from typing import AsyncIterator, Dict, Any, Optional
from app.config import BACKEND_API_URL


class APIClient:
    """AWS ECS 백엔드 API 호출 클라이언트"""
    
    def __init__(self):
        self.base_url = BACKEND_API_URL
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
            headers={"X-Admin-User": "test"}  # 관리자 API 테스트용
        )
    
    async def get_group_codes(self, admin_employee_id: str = "") -> list:
        """Group Code 목록 조회"""
        try:
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id
            }
            response = await self.client.get("/admin/group-codes", headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # 딕셔너리 형태로 받은 경우 리스트로 변환
            if isinstance(data, dict):
                # 딕셔너리의 값들을 리스트로 변환
                # kb_domains는 배열로 유지
                result = []
                for code, info in data.items():
                    kb_domains = info.get('kb_domains', [])
                    # 문자열인 경우 배열로 변환
                    if isinstance(kb_domains, str):
                        kb_domains = [d.strip() for d in kb_domains.split(',') if d.strip()] if kb_domains else []
                    elif not isinstance(kb_domains, list):
                        kb_domains = []
                    
                    group_code = {
                        'code': info.get('code', code),
                        'description': info.get('description', ''),
                        'kb_domains': kb_domains
                    }
                    result.append(group_code)
                return result
            elif isinstance(data, list):
                return data
            else:
                return []
        except httpx.HTTPStatusError as e:
            error_msg = f"Group Code 조회 실패 (HTTP {e.response.status_code}): {e.response.text}"
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"Group Code 조회 실패: {str(e)}"
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Group Code 조회 중 오류 발생: {str(e)}"
            raise Exception(error_msg)
    
    async def get_kb_domains(self, admin_employee_id: str = "") -> list:
        """KB Domain 목록 조회"""
        try:
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id
            }
            response = await self.client.get("/admin/kb-domains", headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # 딕셔너리 형태로 받은 경우 리스트로 변환
            if isinstance(data, dict):
                # 딕셔너리의 값들을 리스트로 변환
                result = []
                for code, info in data.items():
                    kb_domain = {
                        'code': info.get('code', code),
                        'name': info.get('name', ''),
                        's3_path': info.get('s3_path', ''),
                        'description': info.get('description', '')
                    }
                    result.append(kb_domain)
                return result
            elif isinstance(data, list):
                return data
            else:
                return []
        except httpx.HTTPStatusError as e:
            error_msg = f"KB Domain 조회 실패 (HTTP {e.response.status_code}): {e.response.text}"
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"KB Domain 조회 실패: {str(e)}"
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"KB Domain 조회 중 오류 발생: {str(e)}"
            raise Exception(error_msg)
    
    async def init_chat(
        self,
        corp_id: str,
        employee_id: str,
        name: str,
        department: str
    ) -> Dict[str, Any]:
        """대화 세션 초기화 및 conversation_id 획득"""
        try:
            request_data = {
                "user_info": {
                    "corp_id": corp_id,
                    "employee_id": employee_id,
                    "name": name,
                    "department": department
                }
            }
            
            response = await self.client.post(
                "/chat/init",
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            
            response.raise_for_status()
            result = response.json()
            return result
        except httpx.HTTPStatusError as e:
            error_msg = f"대화 초기화 실패 (HTTP {e.response.status_code}): {e.response.text}"
            print(f"[ERROR] {error_msg}")
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"대화 초기화 실패: {str(e)}"
            print(f"[ERROR] {error_msg}")
            raise Exception(error_msg)
    
    async def send_chat_message(
        self,
        message: str,
        conversation_id: Optional[str],
        group_code: str,
        corp_id: str,
        employee_id: str,
        name: str,
        department: str
    ) -> AsyncIterator[str]:
        """채팅 메시지 전송 (SSE 스트리밍)"""
        # 명세서에 따르면 conversation_id가 없으면 먼저 /chat/init 호출
        if not conversation_id:
            init_response = await self.init_chat(corp_id, employee_id, name, department)
            conversation_id = init_response.get("conversation_id")
            if not conversation_id:
                raise Exception("conversation_id를 받지 못했습니다")
        
        # /chat/{conversation_id} 경로로 메시지 전송
        message_data = {
            "message": message,
            "user_info": {
                "corp_id": corp_id,
                "employee_id": employee_id,
                "name": name,
                "department": department
            },
            "group_code": group_code
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream"
        }
        
        try:
            async with self.client.stream(
                "POST",
                f"/chat/{conversation_id}",
                json=message_data,
                headers=headers
            ) as response:
                # 스트리밍 응답에서 에러 발생 시 응답 본문 읽기
                if response.status_code >= 400:
                    # 스트리밍 응답의 경우 전체 본문을 읽어야 함
                    error_body = ""
                    async for chunk in response.aiter_bytes():
                        error_body += chunk.decode('utf-8', errors='ignore')
                    error_msg = f"채팅 메시지 전송 실패 (HTTP {response.status_code}): {error_body}"
                    print(f"[ERROR] {error_msg}")
                    raise Exception(error_msg)
                
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        yield line
        except httpx.HTTPStatusError as e:
            # 스트리밍 응답이 아닌 경우
            try:
                error_text = e.response.text
            except:
                error_text = "응답 본문을 읽을 수 없습니다"
            error_msg = f"채팅 메시지 전송 실패 (HTTP {e.response.status_code}): {error_text}"
            print(f"[ERROR] {error_msg}")
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"채팅 메시지 전송 실패: {str(e)}"
            print(f"[ERROR] {error_msg}")
            raise Exception(error_msg)
    
    async def get_conversation_history(self, corp_id: str, employee_id: str, page: int = 1, pagesize: int = 20) -> list:
        """대화 목록 조회"""
        try:
            # 서버 변경: GET /history?employee_id=xxx&page=1&pagesize=20
            # 서버에서 내부적으로 page/pagesize를 limit/offset으로 변환
            response = await self.client.get(
                "/history",
                headers={
                    "Content-Type": "application/json"
                },
                params={
                    "employee_id": employee_id,
                    "page": page,
                    "pagesize": pagesize
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # 명세서 응답 형식: {"data": [...], "pagination": {...}}
            if isinstance(data, dict):
                if "data" in data and isinstance(data["data"], list):
                    return data["data"]
                # 호환성을 위해 다른 형식도 처리
                if "conversations" in data and isinstance(data["conversations"], list):
                    return data["conversations"]
                # 그 외의 경우는 딕셔너리의 값들을 리스트로 변환
                result = []
                for key, value in data.items():
                    # 메타데이터는 제외
                    if key in ["data", "pagination", "conversations", "total", "page", "page_size", "total_pages"]:
                        continue
                    if isinstance(value, dict):
                        conv = value.copy()
                        if 'conversation_id' not in conv:
                            conv['conversation_id'] = key
                        result.append(conv)
                    elif isinstance(value, list):
                        result.extend(value)
                return result
            elif isinstance(data, list):
                return data
            else:
                return []
        except httpx.HTTPError as e:
            error_msg = f"대화 목록 조회 실패: {str(e)}"
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"대화 목록 조회 중 오류 발생: {str(e)}"
            raise Exception(error_msg)
    
    async def get_conversation_detail(self, conversation_id: str, employee_id: str) -> Dict[str, Any]:
        """대화 상세 조회"""
        try:
            # 명세서: GET /history/{conversation_id}?employee_id=xxx
            response = await self.client.get(
                f"/history/{conversation_id}",
                params={"employee_id": employee_id}
            )
            response.raise_for_status()
            data = response.json()
            return data
        except httpx.HTTPStatusError as e:
            error_msg = f"대화 상세 조회 실패 (HTTP {e.response.status_code}): {e.response.text}"
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"대화 상세 조회 실패: {str(e)}"
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"대화 상세 조회 중 오류 발생: {str(e)}"
            raise Exception(error_msg)
    
    async def update_conversation_title(
        self,
        conversation_id: str,
        title: str,
        employee_id: str
    ) -> Dict[str, Any]:
        """대화 제목 수정"""
        try:
            # 명세서: PUT /history/{conversation_id}/title
            # Request Body에 employee_id와 title 포함
            response = await self.client.put(
                f"/history/{conversation_id}/title",
                json={
                    "employee_id": employee_id,
                    "title": title
                }
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise Exception(f"대화 제목 수정 실패: {str(e)}")
    
    async def delete_conversation(self, conversation_id: str, employee_id: str) -> None:
        """대화 삭제"""
        try:
            # 명세서: DELETE /history/{conversation_id}
            # Request Body에 employee_id 포함
            # httpx의 DELETE 메서드는 json 파라미터를 지원하지 않으므로
            # content와 headers를 명시적으로 설정
            import json as json_lib
            response = await self.client.request(
                "DELETE",
                f"/history/{conversation_id}",
                content=json_lib.dumps({"employee_id": employee_id}),
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            error_msg = f"대화 삭제 실패 (HTTP {e.response.status_code}): {e.response.text}"
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            raise Exception(f"대화 삭제 실패: {str(e)}")
    
    async def create_group_code(self, code: str, description: str, kb_domains: list, admin_employee_id: str = "") -> Dict[str, Any]:
        """Group Code 생성"""
        try:
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id
            }
            response = await self.client.post(
                "/admin/group-codes",
                json={
                    "code": code,
                    "description": description,
                    "kb_domains": kb_domains
                },
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if e.response else str(e)
            error_msg = f"Group Code 생성 실패 (HTTP {e.response.status_code}): {error_detail}"
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            raise Exception(f"Group Code 생성 실패: {str(e)}")
    
    async def update_group_code(
        self,
        code: str,
        description: str,
        kb_domains: list,
        admin_employee_id: str = ""
    ) -> Dict[str, Any]:
        """Group Code 수정"""
        try:
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id
            }
            response = await self.client.put(
                f"/admin/group-codes/{code}",
                json={
                    "description": description,
                    "kb_domains": kb_domains
                },
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text if e.response else str(e)
            error_msg = f"Group Code 수정 실패 (HTTP {e.response.status_code}): {error_detail}"
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            raise Exception(f"Group Code 수정 실패: {str(e)}")
    
    async def delete_group_code(self, code: str, admin_employee_id: str = "") -> None:
        """Group Code 삭제"""
        try:
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id
            }
            response = await self.client.delete(f"/admin/group-codes/{code}", headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise Exception(f"Group Code 삭제 실패: {str(e)}")
    
    async def create_kb_domain(
        self,
        code: str,
        name: str,
        s3_path: str,
        admin_employee_id: str = ""
    ) -> Dict[str, Any]:
        """KB Domain 생성"""
        try:
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id
            }
            response = await self.client.post(
                "/admin/kb-domains",
                json={
                    "code": code,
                    "name": name,
                    "s3_path": s3_path
                },
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise Exception(f"KB Domain 생성 실패: {str(e)}")
    
    async def update_kb_domain(
        self,
        code: str,
        name: str,
        s3_path: str,
        admin_employee_id: str = ""
    ) -> Dict[str, Any]:
        """KB Domain 수정"""
        try:
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id
            }
            response = await self.client.put(
                f"/admin/kb-domains/{code}",
                json={
                    "name": name,
                    "s3_path": s3_path
                },
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise Exception(f"KB Domain 수정 실패: {str(e)}")
    
    async def delete_kb_domain(self, code: str, admin_employee_id: str = "") -> None:
        """KB Domain 삭제"""
        try:
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id
            }
            response = await self.client.delete(f"/admin/kb-domains/{code}", headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise Exception(f"KB Domain 삭제 실패: {str(e)}")
    
    async def get_total_token_usage(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        tz: str = "Asia/Seoul",
        employee_id: str = ""
    ) -> Dict[str, Any]:
        """전체 토큰 사용량 조회 (관리자용)"""
        try:
            params = {"tz": tz}
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": employee_id
            }
            
            response = await self.client.get(
                "/admin/monitoring/token-usage",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"전체 토큰 사용량 조회 실패 (HTTP {e.response.status_code}): {e.response.text}"
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"전체 토큰 사용량 조회 실패: {str(e)}"
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"전체 토큰 사용량 조회 중 오류 발생: {str(e)}"
            raise Exception(error_msg)
    
    async def get_user_token_usage(
        self,
        employee_id: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        tz: str = "Asia/Seoul",
        admin_employee_id: str = ""
    ) -> Dict[str, Any]:
        """사용자별 토큰 사용량 조회 (관리자용)"""
        try:
            params = {"tz": tz}
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id or employee_id
            }
            
            response = await self.client.get(
                f"/admin/monitoring/users/{employee_id}/token-usage",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"사용자별 토큰 사용량 조회 실패 (HTTP {e.response.status_code}): {e.response.text}"
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"사용자별 토큰 사용량 조회 실패: {str(e)}"
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"사용자별 토큰 사용량 조회 중 오류 발생: {str(e)}"
            raise Exception(error_msg)
    
    async def get_monitoring_users(
        self,
        corp_id: Optional[str] = None,
        department: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        admin_employee_id: str = ""
    ) -> Dict[str, Any]:
        """전체 챗봇 사용자 리스트 조회 (관리자용)"""
        try:
            params = {"page": page, "page_size": page_size}
            if corp_id:
                params["corp_id"] = corp_id
            if department:
                params["department"] = department
            if q:
                params["q"] = q
            
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id
            }
            
            response = await self.client.get(
                "/admin/monitoring/users",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"사용자 리스트 조회 실패 (HTTP {e.response.status_code}): {e.response.text}"
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"사용자 리스트 조회 실패: {str(e)}"
            raise Exception(error_msg)
    
    async def get_monitoring_token_usage_users(
        self,
        from_date: str,
        to_date: str,
        corp_id: Optional[str] = None,
        department: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        admin_employee_id: str = ""
    ) -> Dict[str, Any]:
        """전체 사용자별 토큰 사용량 조회 (관리자용)"""
        try:
            params = {
                "from": from_date,
                "to": to_date,
                "page": page,
                "page_size": page_size
            }
            if corp_id:
                params["corp_id"] = corp_id
            if department:
                params["department"] = department
            
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id
            }
            
            response = await self.client.get(
                "/admin/monitoring/token-usage/users",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"사용자별 토큰 사용량 조회 실패 (HTTP {e.response.status_code}): {e.response.text}"
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"사용자별 토큰 사용량 조회 실패: {str(e)}"
            raise Exception(error_msg)
    
    async def get_monitoring_token_usage_users_daily(
        self,
        from_date: str,
        to_date: str,
        tz: str = "Asia/Seoul",
        employee_id: Optional[str] = None,
        admin_employee_id: str = ""
    ) -> Dict[str, Any]:
        """전체 사용자별 일자별 토큰 사용량 조회 (관리자용)"""
        try:
            params = {
                "from": from_date,
                "to": to_date,
                "tz": tz
            }
            if employee_id:
                params["employee_id"] = employee_id
            
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id
            }
            
            response = await self.client.get(
                "/admin/monitoring/token-usage/users/daily",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"일자별 토큰 사용량 조회 실패 (HTTP {e.response.status_code}): {e.response.text}"
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"일자별 토큰 사용량 조회 실패: {str(e)}"
            raise Exception(error_msg)
    
    async def get_monitoring_questions_users(
        self,
        from_date: str,
        to_date: str,
        department: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
        admin_employee_id: str = ""
    ) -> Dict[str, Any]:
        """전체 사용자별 질문 횟수 조회 (관리자용)"""
        try:
            params = {
                "from": from_date,
                "to": to_date,
                "page": page,
                "page_size": page_size
            }
            if department:
                params["department"] = department
            
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id
            }
            
            response = await self.client.get(
                "/admin/monitoring/questions/users",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"사용자별 질문 횟수 조회 실패 (HTTP {e.response.status_code}): {e.response.text}"
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"사용자별 질문 횟수 조회 실패: {str(e)}"
            raise Exception(error_msg)
    
    async def get_monitoring_history(
        self,
        user_name: Optional[str] = None,
        employee_id: Optional[str] = None,
        department: Optional[str] = None,
        page: int = 1,
        pagesize: int = 20,
        admin_employee_id: str = ""
    ) -> Dict[str, Any]:
        """사용자별 대화 이력 목록 조회 (관리자용)"""
        try:
            params = {"page": page, "pagesize": pagesize}
            if user_name:
                params["user_name"] = user_name
            if employee_id:
                params["employee_id"] = employee_id
            if department:
                params["department"] = department
            
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id
            }
            
            response = await self.client.get(
                "/admin/monitoring/history",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"대화 이력 목록 조회 실패 (HTTP {e.response.status_code}): {e.response.text}"
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"대화 이력 목록 조회 실패: {str(e)}"
            raise Exception(error_msg)
    
    async def get_monitoring_history_detail(
        self,
        conversation_id: str,
        admin_employee_id: str = ""
    ) -> Dict[str, Any]:
        """대화 상세 조회 (관리자용)"""
        try:
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id
            }
            
            response = await self.client.get(
                f"/admin/monitoring/history/{conversation_id}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"대화 상세 조회 실패 (HTTP {e.response.status_code}): {e.response.text}"
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"대화 상세 조회 실패: {str(e)}"
            raise Exception(error_msg)
    
    async def get_kb_data_sources(
        self,
        admin_employee_id: str = ""
    ) -> Dict[str, Any]:
        """데이터 소스 상태 조회 (관리자용)"""
        try:
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id
            }
            
            response = await self.client.get(
                "/admin/kb/data-sources",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"데이터 소스 상태 조회 실패 (HTTP {e.response.status_code}): {e.response.text}"
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"데이터 소스 상태 조회 실패: {str(e)}"
            raise Exception(error_msg)
    
    async def get_kb_files(
        self,
        path: str,
        admin_employee_id: str = ""
    ) -> Dict[str, Any]:
        """파일 목록 조회 (관리자용)"""
        try:
            params = {"path": path}
            headers = {
                "X-Role": "admin",
                "X-Employee-Id": admin_employee_id
            }
            
            response = await self.client.get(
                "/admin/kb/files",
                params=params,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            error_msg = f"파일 목록 조회 실패 (HTTP {e.response.status_code}): {e.response.text}"
            raise Exception(error_msg)
        except httpx.HTTPError as e:
            error_msg = f"파일 목록 조회 실패: {str(e)}"
            raise Exception(error_msg)
    
    async def close(self):
        """클라이언트 종료"""
        await self.client.aclose()

