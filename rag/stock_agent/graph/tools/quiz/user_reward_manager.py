from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from db.sqlite_db import SqliteDBClient
from utils.logger import get_logger

logger = get_logger(__name__)


class UserRewardManager:
    """사용자별 퀴즈 보상 관리 클래스"""

    # 보상 지급 간격 (시간)
    REWARD_INTERVAL_HOURS = 24

    @staticmethod
    def check_reward_eligibility(request_id: str) -> Tuple[bool, Optional[str]]:
        """
        사용자가 보상을 받을 수 있는지 확인합니다.

        Args:
            request_id: 사용자 요청 고유 ID

        Returns:
            (보상 가능 여부, 다음 보상 가능 시간)
        """
        try:
            if not request_id:
                logger.warning("request_id가 제공되지 않았습니다.")
                return True, None  # request_id가 없으면 일단 허용

            db = SqliteDBClient()

            # 최근 1시간 내 정답 및 보상 받은 이력 조회
            cutoff_time = datetime.now() - timedelta(
                hours=UserRewardManager.REWARD_INTERVAL_HOURS
            )
            cutoff_time_str = cutoff_time.isoformat()

            query = """
                SELECT completed_at, reward_stock, reward_amount 
                FROM quiz_history 
                WHERE request_id = ? 
                  AND is_correct = 1 
                  AND reward_amount > 0
                  AND completed_at > ?
                ORDER BY completed_at DESC
                LIMIT 1
            """

            results, columns = db.fetch_query(query, [request_id, cutoff_time_str])
            db.close()

            if not results:
                # 24시간 내 보상 이력이 없음 - 지급 가능
                logger.debug(
                    f"사용자 {request_id}: 24시간 내 보상 이력 없음 - 지급 가능"
                )
                return True, None

            # 최근 보상 시간 계산
            last_reward_time_str = results[0][0]
            last_reward_time = datetime.fromisoformat(
                last_reward_time_str.replace("Z", "+00:00").replace("+00:00", "")
            )

            # 다음 보상 가능 시간 계산
            next_reward_time = last_reward_time + timedelta(
                hours=UserRewardManager.REWARD_INTERVAL_HOURS
            )

            if datetime.now() >= next_reward_time:
                logger.debug(f"사용자 {request_id}: 24시간 경과 - 지급 가능")
                return True, None
            else:
                next_time_str = next_reward_time.strftime("%Y-%m-%d %H:%M:%S")
                logger.info(
                    f"사용자 {request_id}: 24시간 미경과 - 다음 가능 시간: {next_time_str}"
                )
                return False, next_time_str

        except Exception as e:
            logger.error(f"보상 자격 확인 중 오류: {e}")
            return True, None  # 오류 시 일단 허용

    @staticmethod
    def get_user_total_rewards(request_id: str) -> Dict[str, Any]:
        """
        사용자의 전체 보상 현황을 조회합니다.

        Args:
            request_id: 사용자 요청 고유 ID

        Returns:
            사용자 보상 현황 딕셔너리
        """
        try:
            if not request_id:
                return {
                    "success": False,
                    "message": "사용자 식별 정보가 없습니다.",
                    "total_rewards": {},
                    "total_count": 0,
                }

            db = SqliteDBClient()

            # 사용자의 모든 정답 및 보상 이력 조회
            query = """
                SELECT reward_stock, reward_amount, completed_at
                FROM quiz_history 
                WHERE request_id = ? 
                  AND is_correct = 1 
                  AND reward_amount > 0
                ORDER BY completed_at DESC
            """

            results, columns = db.fetch_query(query, [request_id])
            db.close()

            if not results:
                return {
                    "success": True,
                    "message": "아직 받은 보상이 없습니다.",
                    "total_rewards": {},
                    "total_count": 0,
                }

            # 주식별 보상 집계
            stock_rewards = defaultdict(float)
            for row in results:
                stock_name = row[0]
                amount = float(row[1])
                stock_rewards[stock_name] += amount

            # 결과 포맷팅
            formatted_rewards = {}
            for stock, total_amount in stock_rewards.items():
                formatted_rewards[stock] = round(total_amount, 7)  # 소수점 7자리까지

            logger.info(
                f"사용자 {request_id} 보상 현황: {len(formatted_rewards)}종목, 총 {len(results)}회 보상"
            )

            return {
                "success": True,
                "message": f"총 {len(results)}회 퀴즈 정답으로 {len(formatted_rewards)}종목의 주식을 받았습니다.",
                "total_rewards": formatted_rewards,
                "total_count": len(results),
                "last_reward_time": results[0][2] if results else None,
            }

        except Exception as e:
            logger.error(f"사용자 보상 현황 조회 중 오류: {e}")
            return {
                "success": False,
                "message": f"보상 현황 조회 중 오류가 발생했습니다: {str(e)}",
                "total_rewards": {},
                "total_count": 0,
            }

    @staticmethod
    def format_user_rewards_display(rewards_info: Dict[str, Any]) -> str:
        """
        사용자 보상 현황을 표시용 텍스트로 포맷팅합니다.

        Args:
            rewards_info: get_user_total_rewards의 결과

        Returns:
            포맷된 텍스트
        """
        try:
            if not rewards_info.get("success", False):
                return f"⚠️ {rewards_info.get('message', '보상 현황을 조회할 수 없습니다.')}"

            total_rewards = rewards_info.get("total_rewards", {})
            total_count = rewards_info.get("total_count", 0)

            if not total_rewards:
                return "📊 **현재 보유 주식**\n아직 받은 보상이 없습니다."

            lines = ["📊 **현재 보유 주식**"]

            for stock_name, amount in total_rewards.items():
                lines.append(f"• {stock_name}: {amount}주")

            lines.append(
                f"\n총 {total_count}회 퀴즈 정답으로 {len(total_rewards)}종목 보유"
            )

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"보상 현황 포맷팅 중 오류: {e}")
            return "📊 **현재 보유 주식**\n보상 현황 표시 중 오류가 발생했습니다."

    @staticmethod
    def format_reward_limit_message(next_reward_time: str) -> str:
        """
        보상 제한 메시지를 포맷팅합니다.

        Args:
            next_reward_time: 다음 보상 가능 시간

        Returns:
            포맷된 제한 메시지
        """
        try:
            return f"""⏰ **보상 지급 제한**

하루에 한 번만 주식 보상을 받을 수 있습니다.
다음 보상 가능 시간: {next_reward_time}

그래도 퀴즈는 계속 풀 수 있으니 도전해보세요!"""

        except Exception as e:
            logger.error(f"제한 메시지 포맷팅 중 오류: {e}")
            return "⏰ 하루에 한 번만 주식 보상을 받을 수 있습니다."


# 전역 인스턴스
user_reward_manager = UserRewardManager()
