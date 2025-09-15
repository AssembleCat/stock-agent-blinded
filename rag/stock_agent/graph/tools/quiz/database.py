from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
from db.sqlite_db import SqliteDBClient
from utils.logger import get_logger

logger = get_logger(__name__)


class QuizDatabase:
    """퀴즈 이력 데이터베이스 관리 클래스"""

    @staticmethod
    def generate_session_id() -> str:
        """세션 ID를 생성합니다."""
        return str(uuid.uuid4())[:8]

    @staticmethod
    def save_quiz_result(
        request_id: str,
        quiz_id: int,
        quiz_question: str,
        correct_answer: str,
        user_answer: str,
        is_correct: bool,
        hint_used: bool,
        reward_stock: str,
        reward_amount: float,
    ) -> bool:
        """
        퀴즈 결과를 데이터베이스에 저장합니다.

        Args:
            request_id: 사용자 요청 고유 ID
            quiz_id: 퀴즈 문제 번호
            quiz_question: 문제 내용
            correct_answer: 정답 기업명
            user_answer: 사용자 답변
            is_correct: 정답 여부
            hint_used: 힌트 사용 여부
            reward_stock: 지급받은 주식명
            reward_amount: 지급받은 주식 수량

        Returns:
            저장 성공 여부
        """
        try:
            db = SqliteDBClient()

            current_time = datetime.now().isoformat()

            query = """
                INSERT INTO quiz_history (
                    request_id, quiz_id, quiz_question, correct_answer, user_answer,
                    is_correct, hint_used, reward_stock, reward_amount,
                    completed_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            params = (
                request_id,
                quiz_id,
                quiz_question,
                correct_answer,
                user_answer,
                is_correct,
                hint_used,
                reward_stock,
                reward_amount,
                current_time,
                current_time,
            )

            db.conn.execute(query, params)
            db.conn.commit()
            db.close()

            logger.info(
                f"퀴즈 결과 저장 완료 - 사용자: {request_id}, 퀴즈: {quiz_id}, 정답: {is_correct}"
            )
            return True

        except Exception as e:
            logger.error(f"퀴즈 결과 저장 중 오류 발생: {e}")
            return False

    @staticmethod
    def get_user_attempted_quiz_ids(request_id: str) -> List[int]:
        """
        특정 사용자가 시도한 퀴즈 ID 목록을 조회합니다.

        Args:
            request_id: 사용자 요청 고유 ID

        Returns:
            시도한 퀴즈 ID 리스트
        """
        try:
            if not request_id:
                logger.debug("request_id가 없어 빈 목록 반환")
                return []

            db = SqliteDBClient()

            query = """
                SELECT DISTINCT quiz_id 
                FROM quiz_history 
                WHERE request_id = ?
                ORDER BY quiz_id
            """

            results, columns = db.fetch_query(query, [request_id])
            db.close()

            attempted_ids = [row[0] for row in results] if results else []

            logger.debug(f"사용자 {request_id} 시도 퀴즈: {attempted_ids}")
            return attempted_ids

        except Exception as e:
            logger.error(f"시도한 퀴즈 ID 조회 중 오류 발생: {e}")
            return []
