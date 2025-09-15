from dotenv import load_dotenv
from utils.logger import get_logger
from rag.stock_agent.graph.graph import app
from rag.stock_agent.graph.state import default_stock_agent_state

logger = get_logger(__name__)

load_dotenv()

if __name__ == "__main__":
    logger.info("--STOCK AGENT START--")

    state = default_stock_agent_state()

    # 테스트 쿼리들
    test_queries = ["패션플랫폼이 2024-06-01부터 2025-06-30까지 데드크로스 또는 골든크로스가 몇번 발생했어?"]

    for i, test_query in enumerate(test_queries, 1):
        logger.info(f"\n=== 테스트 {i}: {test_query} ===")

        state = default_stock_agent_state()  # 상태 초기화
        state["query"] = test_query

        try:
            # 그래프 실행
            logger.info("--그래프 실행 시작--")
            result = app.invoke(state)

            logger.info("--실행 결과--")
            print("=" * 60)
            print(f"질문: {test_query}")
            print(f"응답: {result.get('response', '응답 없음')}")
            print(f"카테고리: {result.get('query_category', '카테고리 없음')}")
            print("=" * 60)

        except Exception as e:
            logger.error(f"실행 중 오류 발생: {e}")
            import traceback

            traceback.print_exc()
