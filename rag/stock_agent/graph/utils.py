"""
Stock Agent 공통 유틸리티 함수들
결과 개수 관리, 데이터 포맷팅 등 공통 기능 제공
"""

from typing import List, Dict, Any, Optional
from .constant import (
    DEFAULT_RESULT_COUNT,
    MAX_RESULT_COUNT,
    TECHNICAL_INDICATOR_SETTINGS,
    FORMATTING_SETTINGS,
)


def get_result_count(
    indicator_type: Optional[str] = None,
    requested_count: Optional[int] = None,
    total_available: int = 0,
) -> int:
    """
    결과 개수를 결정하는 함수

    Args:
        indicator_type: 기술적 지표 타입 (RSI, BOLLINGER_BANDS 등)
        requested_count: 사용자가 요청한 개수
        total_available: 실제 사용 가능한 총 개수
    """
    # 1. 사용자가 요청한 개수가 있으면 우선 적용 (최대값 제한)
    if requested_count is not None:
        max_allowed = MAX_RESULT_COUNT
        if indicator_type and indicator_type in TECHNICAL_INDICATOR_SETTINGS:
            max_allowed = TECHNICAL_INDICATOR_SETTINGS[indicator_type]["max_count"]

        return min(requested_count, max_allowed, total_available)

    # 2. 지표별 기본값 적용
    if indicator_type and indicator_type in TECHNICAL_INDICATOR_SETTINGS:
        default_count = TECHNICAL_INDICATOR_SETTINGS[indicator_type]["default_count"]
    else:
        default_count = DEFAULT_RESULT_COUNT

    # 3. 실제 사용 가능한 개수와 비교하여 최소값 반환
    return min(default_count, total_available)


def limit_results(
    data: List[Dict[str, Any]],
    count: int,
    sort_key: Optional[str] = None,
    reverse: bool = False,
) -> List[Dict[str, Any]]:
    """
    결과를 제한하고 정렬하는 함수

    Args:
        data: 원본 데이터 리스트
        count: 반환할 개수
        sort_key: 정렬 기준 키
        reverse: 역순 정렬 여부
    """
    if not data:
        return []

    # 정렬
    if sort_key:
        data = sorted(data, key=lambda x: x.get(sort_key, 0), reverse=reverse)

    # 개수 제한
    return data[:count]


def create_result_response(
    data: List[Dict[str, Any]],
    total_count: int,
    indicator_type: Optional[str] = None,
    requested_count: Optional[int] = None,
    sort_key: Optional[str] = None,
    reverse: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    """
    표준화된 결과 응답을 생성하는 함수

    Args:
        data: 결과 데이터
        total_count: 총 개수
        indicator_type: 지표 타입
        requested_count: 요청된 개수
        **kwargs: 추가 메타데이터

    Returns:
        Dict[str, Any]: 표준화된 응답
    """
    actual_count = get_result_count(indicator_type, requested_count, total_count)
    limited_data = limit_results(data, actual_count, sort_key, reverse)

    response = {
        "total_count": total_count,
        "returned_count": len(limited_data),
        "results": limited_data,
        **kwargs,
    }

    return response
