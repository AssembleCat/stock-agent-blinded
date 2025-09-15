import re
import random
from typing import List, Dict, Any, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


def parse_quiz_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Quiz.txt 파일을 파싱하여 퀴즈 데이터 리스트를 반환합니다.

    Args:
        file_path: Quiz.txt 파일 경로

    Returns:
        퀴즈 데이터 딕셔너리 리스트
    """
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        # 문제별로 분할 (숫자. 으로 시작하는 부분을 기준으로)
        quiz_blocks = re.split(r"\n(?=\d+\.)", content.strip())

        quizzes = []
        for block in quiz_blocks:
            if not block.strip():
                continue

            quiz_data = parse_single_quiz(block.strip())
            if quiz_data and validate_quiz_data(quiz_data):
                quizzes.append(quiz_data)
            else:
                logger.warning(f"유효하지 않은 퀴즈 블록 건너뜀: {block[:50]}...")

        logger.info(f"총 {len(quizzes)}개의 유효한 퀴즈를 파싱했습니다.")
        return quizzes

    except FileNotFoundError:
        logger.error(f"퀴즈 파일을 찾을 수 없습니다: {file_path}")
        return []
    except Exception as e:
        logger.error(f"퀴즈 파일 파싱 중 오류 발생: {e}")
        return []


def parse_single_quiz(quiz_block: str) -> Optional[Dict[str, Any]]:
    """
    단일 퀴즈 블록을 파싱하여 구조화된 데이터로 변환합니다.

    Args:
        quiz_block: 퀴즈 텍스트 블록

    Returns:
        퀴즈 데이터 딕셔너리 또는 None
    """
    try:
        lines = [line.strip() for line in quiz_block.split("\n") if line.strip()]

        if len(lines) < 6:  # 최소 필요한 라인 수
            logger.warning("퀴즈 블록의 라인 수가 부족합니다.")
            return None

        # 문제 번호와 질문 추출
        # 첫 번째 줄에서 번호 추출
        first_line = lines[0]
        number_match = re.match(r"(\d+)\.\s*$", first_line)
        if number_match:
            # 번호가 별도 줄에 있는 경우
            quiz_number = int(number_match.group(1))
            if len(lines) > 1 and lines[1].startswith("Q."):
                question = lines[1][2:].strip()  # "Q." 제거 후 질문 추출
            else:
                logger.warning(
                    f"Q.로 시작하는 질문을 찾을 수 없습니다: {lines[1] if len(lines) > 1 else 'N/A'}"
                )
                return None
        else:
            # 번호와 질문이 한 줄에 있는 경우 (기존 로직)
            quiz_number_match = re.match(r"(\d+)\.\s*Q\.\s*(.*)", first_line)
            if not quiz_number_match:
                logger.warning(f"문제 번호와 질문을 추출할 수 없습니다: {first_line}")
                return None
            quiz_number = int(quiz_number_match.group(1))
            question = quiz_number_match.group(2)

        # 선택지 추출 (질문 다음 줄부터 시작)
        options = {}
        option_pattern = r"^[①②③④]\s*(.*)"

        # 질문이 별도 줄에 있는 경우 2번째 줄부터, 한 줄에 있는 경우 1번째 줄부터
        start_line = 2 if number_match else 1

        for line in lines[start_line:]:
            if re.match(option_pattern, line):
                # 유니코드 번호를 일반 번호로 변환
                option_mapping = {"①": "1", "②": "2", "③": "3", "④": "4"}
                for unicode_num, regular_num in option_mapping.items():
                    if line.startswith(unicode_num):
                        option_text = line[1:].strip()
                        options[regular_num] = option_text
                        break

        # 4개의 선택지가 모두 있는지 확인
        if len(options) != 4:
            logger.warning(
                f"퀴즈 {quiz_number}번: 선택지가 4개가 아닙니다. ({len(options)}개)"
            )
            return None

        # 정답 추출
        correct_answer = {}
        background_info = ""

        for i, line in enumerate(lines):
            if line.startswith("정답:"):
                # 정답 라인 파싱
                answer_match = re.match(r"정답:\s*([①②③④])\s*(.*)", line)
                if answer_match:
                    answer_symbol = answer_match.group(1)
                    answer_company = answer_match.group(2)

                    # 유니코드 번호를 일반 번호로 변환
                    symbol_mapping = {"①": "1", "②": "2", "③": "3", "④": "4"}
                    answer_number = symbol_mapping.get(answer_symbol, "1")

                    correct_answer = {
                        "number": answer_number,
                        "company": answer_company,
                        "symbol": answer_symbol,
                    }

                # 배경지식은 정답 다음 줄부터
                if i + 1 < len(lines):
                    background_lines = lines[i + 1 :]
                    background_info = " ".join(
                        [l.strip() for l in background_lines if l.strip()]
                    )
                break

        if not correct_answer:
            logger.warning(f"퀴즈 {quiz_number}번: 정답 정보를 찾을 수 없습니다.")
            return None

        quiz_data = {
            "id": quiz_number,
            "question": question,
            "options": options,
            "correct_answer": correct_answer,
            "background": background_info,
        }

        logger.debug(f"퀴즈 {quiz_number}번 파싱 완료: {question[:30]}...")
        return quiz_data

    except Exception as e:
        logger.error(f"단일 퀴즈 파싱 중 오류 발생: {e}")
        return None


def validate_quiz_data(quiz_data: Dict[str, Any]) -> bool:
    """
    퀴즈 데이터의 유효성을 검증합니다.

    Args:
        quiz_data: 퀴즈 데이터 딕셔너리

    Returns:
        유효성 검증 결과
    """
    try:
        # 필수 필드 확인
        required_fields = ["id", "question", "options", "correct_answer"]
        for field in required_fields:
            if field not in quiz_data:
                logger.error(f"필수 필드 누락: {field}")
                return False

        # ID 유효성 확인
        if not isinstance(quiz_data["id"], int) or quiz_data["id"] <= 0:
            logger.error(f"잘못된 퀴즈 ID: {quiz_data['id']}")
            return False

        # 질문 유효성 확인
        if not quiz_data["question"] or len(quiz_data["question"].strip()) < 10:
            logger.error("질문이 너무 짧거나 비어있습니다.")
            return False

        # 선택지 개수 확인 (정확히 4개)
        options = quiz_data["options"]
        if not isinstance(options, dict) or len(options) != 4:
            logger.error(f"선택지 개수 오류: {len(options)}개 (4개 필요)")
            return False

        # 선택지 번호 확인 (1, 2, 3, 4)
        expected_numbers = {"1", "2", "3", "4"}
        if set(options.keys()) != expected_numbers:
            logger.error(f"선택지 번호 오류: {set(options.keys())} (1,2,3,4 필요)")
            return False

        # 선택지 내용 확인
        for num, option_text in options.items():
            if not option_text or len(option_text.strip()) < 2:
                logger.error(f"선택지 {num}번이 너무 짧거나 비어있습니다.")
                return False

        # 정답 정보 확인
        correct_answer = quiz_data["correct_answer"]
        if not isinstance(correct_answer, dict):
            logger.error("정답 정보가 딕셔너리가 아닙니다.")
            return False

        required_answer_fields = ["number", "company"]
        for field in required_answer_fields:
            if field not in correct_answer:
                logger.error(f"정답 정보 필수 필드 누락: {field}")
                return False

        # 정답 번호가 선택지에 존재하는지 확인
        answer_number = correct_answer["number"]
        if answer_number not in options:
            logger.error(f"정답 번호 {answer_number}가 선택지에 없습니다.")
            return False

        # 정답 회사명이 선택지에 포함되는지 확인
        answer_company = correct_answer["company"]
        correct_option = options[answer_number]
        if answer_company not in correct_option:
            logger.warning(
                f"정답 회사명 '{answer_company}'가 선택지 '{correct_option}'와 일치하지 않습니다."
            )
            # 경고만 하고 통과 (약간의 불일치는 허용)

        return True

    except Exception as e:
        logger.error(f"퀴즈 데이터 검증 중 오류: {e}")
        return False


def get_random_quiz(quizzes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    퀴즈 리스트에서 랜덤하게 하나를 선택합니다.

    Args:
        quizzes: 퀴즈 데이터 리스트

    Returns:
        선택된 퀴즈 데이터 또는 None
    """
    if not quizzes:
        logger.error("선택할 퀴즈가 없습니다.")
        return None

    try:
        selected_quiz = random.choice(quizzes)
        logger.info(f"퀴즈 {selected_quiz.get('id', 'Unknown')}번이 선택되었습니다.")
        return selected_quiz
    except Exception as e:
        logger.error(f"퀴즈 선택 중 오류: {e}")
        return None


def get_unplayed_quiz(
    quizzes: List[Dict[str, Any]], request_id: str = ""
) -> Optional[Dict[str, Any]]:
    """
    사용자가 시도하지 않은 퀴즈 중에서 랜덤하게 하나를 선택합니다.

    Args:
        quizzes: 퀴즈 데이터 리스트
        request_id: 사용자 요청 고유 ID

    Returns:
        선택된 퀴즈 데이터 또는 None
    """
    if not quizzes:
        logger.error("선택할 퀴즈가 없습니다.")
        return None

    try:
        # request_id가 없으면 기존 랜덤 선택
        if not request_id:
            logger.debug("request_id가 없어 랜덤 선택")
            return get_random_quiz(quizzes)

        # 사용자가 시도한 퀴즈 ID 조회
        from rag.stock_agent.graph.tools.quiz.database import QuizDatabase

        attempted_quiz_ids = QuizDatabase.get_user_attempted_quiz_ids(request_id)

        # 시도하지 않은 퀴즈만 필터링
        unplayed_quizzes = [
            quiz for quiz in quizzes if quiz.get("id") not in attempted_quiz_ids
        ]

        if not unplayed_quizzes:
            # 모든 퀴즈를 다 풀었을 경우
            logger.warning(
                f"사용자 {request_id}가 모든 퀴즈를 완료했습니다. 전체 퀴즈에서 랜덤 선택"
            )
            return get_random_quiz(quizzes)

        # 미완료 퀴즈 중에서 랜덤 선택
        selected_quiz = random.choice(unplayed_quizzes)

        logger.info(
            f"사용자 {request_id} - 미완료 퀴즈 {len(unplayed_quizzes)}개 중 "
            f"퀴즈 {selected_quiz.get('id', 'Unknown')}번 선택"
        )

        return selected_quiz

    except Exception as e:
        logger.error(f"미완료 퀴즈 선택 중 오류: {e}")
        # 오류 시 기존 랜덤 선택으로 폴백
        return get_random_quiz(quizzes)
