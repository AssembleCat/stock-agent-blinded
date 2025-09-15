from dotenv import load_dotenv
from rag.stock_agent.graph.constant import (
    CLASSIFY_QUERY,
    FETCH_STOCK_DATA,
    CONDITIONAL_STOCK_DATA,
    SIGNAL_STOCK_DATA,
    QUIZ_STOCK_DATA,
    QUIZ_GENERATE_RESPONSE,
    GENERATE_RESPONSE,
    PREPROCESS,
    AMBIGUOUS_QUERY,
)
from rag.stock_agent.graph.nodes.classify_query import (
    classify_query,
    classify_query_with_path,
)
from rag.stock_agent.graph.nodes.generate_response import generate_response
from rag.stock_agent.graph.nodes.fetch_stock_data import fetch_stock_data
from rag.stock_agent.graph.nodes.conditional_stock_data import conditional_stock_data
from rag.stock_agent.graph.nodes.signal_stock_data import signal_stock_data
from rag.stock_agent.graph.nodes.quiz_stock_data import quiz_stock_data
from rag.stock_agent.graph.nodes.quiz_generate_response import quiz_generate_response
from rag.stock_agent.graph.nodes.preprocess import preprocess
from rag.stock_agent.graph.nodes.ambiguous_query import (
    clarify_question_node,
    ambiguous_query_with_path,
)
from rag.stock_agent.graph.state import StockAgentState
from langgraph.graph import StateGraph, END


load_dotenv()

graph_builder = StateGraph(state_schema=StockAgentState)

# Graph에 포함될 Node
graph_builder.add_node(PREPROCESS, preprocess)
graph_builder.add_node(CLASSIFY_QUERY, classify_query)
graph_builder.add_node(AMBIGUOUS_QUERY, clarify_question_node)
graph_builder.add_node(FETCH_STOCK_DATA, fetch_stock_data)
graph_builder.add_node(CONDITIONAL_STOCK_DATA, conditional_stock_data)
graph_builder.add_node(SIGNAL_STOCK_DATA, signal_stock_data)
graph_builder.add_node(QUIZ_STOCK_DATA, quiz_stock_data)
graph_builder.add_node(QUIZ_GENERATE_RESPONSE, quiz_generate_response)
graph_builder.add_node(GENERATE_RESPONSE, generate_response)

# Classify Query는 결과에 따라 분기됨.
graph_builder.add_conditional_edges(
    CLASSIFY_QUERY,
    classify_query_with_path,
    {
        "fetch_stock_data": FETCH_STOCK_DATA,
        "conditional_stock_data": CONDITIONAL_STOCK_DATA,
        "signal_stock_data": SIGNAL_STOCK_DATA,
        "quiz_stock_data": QUIZ_STOCK_DATA,
        "ambiguous_query": AMBIGUOUS_QUERY,
    },
)

# Ambiguous Query는 재질의 여부에 따라 분기됨.
graph_builder.add_conditional_edges(
    AMBIGUOUS_QUERY,
    ambiguous_query_with_path,
    {
        "ask_clarification": END,  # 재질의는 바로 종료
        "classify_query": CLASSIFY_QUERY,  # 자체 구체화는 재분류
    },
)

# 최초 진입점
graph_builder.set_entry_point(PREPROCESS)

graph_builder.add_edge(PREPROCESS, CLASSIFY_QUERY)
graph_builder.add_edge(FETCH_STOCK_DATA, GENERATE_RESPONSE)
graph_builder.add_edge(CONDITIONAL_STOCK_DATA, GENERATE_RESPONSE)
graph_builder.add_edge(SIGNAL_STOCK_DATA, GENERATE_RESPONSE)
graph_builder.add_edge(QUIZ_STOCK_DATA, QUIZ_GENERATE_RESPONSE)
graph_builder.add_edge(QUIZ_GENERATE_RESPONSE, END)
graph_builder.add_edge(GENERATE_RESPONSE, END)

app = graph_builder.compile()
app.get_graph().draw_mermaid_png(output_file_path="rag/stock_agent/graph/graph.png")
