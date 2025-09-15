import json
import requests
from typing import List, Dict, Any, Optional
from utils.logger import get_logger
import os
from dotenv import load_dotenv

load_dotenv()

logger = get_logger(__name__)

_session = None


def get_session():
    """HTTP 세션을 재사용하여 연결 풀링 효과를 얻습니다."""
    global _session
    if _session is None:
        _session = requests.Session()
        # 연결 풀 설정
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10, pool_maxsize=20, max_retries=3, pool_block=False
        )
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)
    return _session


def call_clova_function_calling(
    messages: List[Dict[str, str]],
    tools: List[Dict[str, Any]],
    api_key: Optional[str] = None,
    request_id: Optional[str] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    Clova Studio Function Calling API를 호출합니다.
    HTTP 세션 재사용과 타임아웃 설정을 적용합니다.
    """
    if not api_key:
        api_key = os.getenv("CLOVASTUDIO_API_KEY")

    url = "https://clovastudio.stream.ntruss.com/v3/chat-completions/HCX-005"

    # 민감정보 노출 방지: API 키 값은 로그/출력하지 않습니다.
    logger.debug("Clova API 호출 준비: API 키 제공 여부=%s", bool(api_key))

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": f"{request_id}",
    }

    payload = {
        "messages": messages,
        "tools": tools,
        "temperature": 0,
        "max_tokens": 4000,
    }

    session = get_session()

    try:
        response = session.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.error(f"API 호출 타임아웃 (timeout: {timeout}s)")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"API 호출 실패: {e}")
        raise
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}")
        raise


def execute_tool(
    tool_call: Dict[str, Any], tool_functions: Dict[str, Any]
) -> Dict[str, Any]:
    """
    단일 도구를 실행합니다.
    """
    try:
        function_name = tool_call["function"]["name"]
        arguments = tool_call["function"]["arguments"]

        # arguments가 문자열인 경우에만 JSON 파싱
        if isinstance(arguments, str):
            arguments = json.loads(arguments)

        # 도구 실행 전 파라미터 로그
        logger.info(f"도구 실행 시작: {function_name} - 파라미터: {arguments}")

        if function_name in tool_functions:
            tool = tool_functions[function_name]
            # 간단한 도구 호출
            result = tool.invoke(arguments)
            return {
                "tool_call_id": tool_call["id"],
                "function_name": function_name,
                "arguments": arguments,
                "result": result,
                "success": True,
            }
        else:
            logger.error(f"함수 {function_name}를 찾을 수 없습니다.")
            return {
                "tool_call_id": tool_call["id"],
                "function_name": function_name,
                "arguments": arguments,
                "result": f"함수 {function_name}를 찾을 수 없습니다.",
                "success": False,
            }
    except Exception as e:
        logger.error(f"도구 실행 중 오류 ({function_name}): {e}")
        return {
            "tool_call_id": tool_call["id"],
            "function_name": function_name,
            "arguments": arguments,
            "result": f"도구 실행 중 오류: {str(e)}",
            "success": False,
        }


def process_function_calling(
    initial_messages: List[Dict[str, str]],
    tools: List[Dict[str, Any]],
    tool_functions: Dict[str, Any],
    feedback: str = "",
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Function Calling 프로세스를 실행합니다.
    한 번만 실행하고 실패 시 바로 종료합니다.
    """
    messages = initial_messages.copy()

    if feedback:
        messages.append(
            {
                "role": "user",
                "content": f"이전 응답에 대한 피드백: {feedback}\n이 피드백을 반영하여 다시 응답해주세요.",
            }
        )

    try:
        # Step 1: Function Calling API 호출
        response = call_clova_function_calling(messages, tools, api_key)

        # Clova Studio v3 API 응답 형식 처리
        if "result" in response and "message" in response["result"]:
            message = response["result"]["message"]
        elif "choices" in response and response["choices"]:
            choice = response["choices"][0]
            message = choice["message"]
        else:
            logger.error("API 응답에 유효한 메시지가 없습니다.")
            return {
                "success": False,
                "error": "Invalid API response",
                "tool_results": [],
            }
        # 도구 호출이 없는 경우 종료
        if "toolCalls" not in message and "tool_calls" not in message:
            logger.info("도구 호출이 없습니다. 프로세스를 종료합니다.")
            return {
                "success": True,
                "tool_results": [],
                "final_response": message.get("content", ""),
            }

        # 도구 호출 결과를 순차적으로 실행
        tool_calls = message.get("toolCalls", message.get("tool_calls", []))
        tool_results = []

        # 순차적으로 도구 실행
        for tool_call in tool_calls:
            result = execute_tool(tool_call, tool_functions)
            tool_results.append(result)
            logger.info(
                f"도구 실행 완료: {result['function_name']} - 결과: {len(str(result['result']))}자"
            )

        # 도구 실행 결과를 메시지에 추가
        tool_messages = []
        for result in tool_results:
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": result["tool_call_id"],
                    "content": json.dumps(result["result"], ensure_ascii=False),
                }
            )

        messages.extend([message] + tool_messages)

        # 모든 도구가 성공적으로 실행되었는지 확인
        all_successful = all(result["success"] for result in tool_results)

        if all_successful:
            logger.info(
                f"모든 도구가 성공적으로 실행되었습니다. (총 {len(tool_results)}개)"
            )
            return {
                "success": True,
                "tool_results": tool_results,
                "final_response": None,  # Step 2 제거로 인해 None 반환
            }
        else:
            logger.error("일부 도구 실행이 실패했습니다.")
            failed_tools = [r for r in tool_results if not r["success"]]
            error_messages = [
                f"{r['function_name']}: {r['result']}" for r in failed_tools
            ]
            return {
                "success": False,
                "error": f"도구 실행 실패: {'; '.join(error_messages)}",
                "tool_results": tool_results,
            }

    except Exception as e:
        logger.error(f"Function calling 프로세스 중 오류: {e}")
        return {"success": False, "error": str(e), "tool_results": []}
