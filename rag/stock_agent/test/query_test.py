import pandas as pd
from rag.stock_agent.graph.graph import app
from rag.stock_agent.graph.state import default_stock_agent_state
from utils.logger import get_logger
import os

logger = get_logger(__name__)


def main():
    # test_question 폴더 내의 모든 csv 파일 나열
    test_dir = "test_question"
    files = [f for f in os.listdir(test_dir) if f.endswith(".csv")]
    if not files:
        logger.error("test_question 폴더에 csv 파일이 없습니다.")
        return
    print("테스트할 파일을 선택하세요:")
    for i, fname in enumerate(files):
        print(f"{i+1}. {fname}")
    while True:
        try:
            choice = int(input("번호 입력: "))
            if 1 <= choice <= len(files):
                break
            else:
                print("잘못된 번호입니다. 다시 입력하세요.")
        except ValueError:
            print("숫자를 입력하세요.")
    csv_path = os.path.join(test_dir, files[choice - 1])
    logger.info(f"선택된 파일: {csv_path}")

    df = pd.read_csv(csv_path)

    for idx, row in df.iterrows():
        question = row["question"]
        if pd.isna(question) or str(question).strip() == "":
            logger.info("질문이 nan 또는 공백입니다. 테스트를 종료합니다.")
            df = df.iloc[:idx]
            break
        logger.info(f"질문: {question}")

        state = default_stock_agent_state()
        state["query"] = question
        res = app.invoke(state)

        # res 전체를 state 컬럼에, res["response"]를 answer 컬럼에 저장
        df.at[idx, "state"] = str(res)
        df.at[idx, "answer"] = res["response"]

    df.to_csv(csv_path, index=False)


if __name__ == "__main__":
    main()
