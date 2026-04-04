import os
import sys
from dotenv import load_dotenv

# 프로젝트 루트를 path에 추가하여 임포트 가능하게 함
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from travel_agent.agents.weather.graph import get_graph

def test_weather():
    load_dotenv()
    
    print("=== Weather Agent Integration Test ===")
    graph = get_graph()
    
    # 테스트 쿼리
    query = "destination=서울 weather=true"
    print(f"Input Query: {query}")
    
    try:
        result = graph.invoke({"query": query})
        print("\n=== Result ===")
        print(result.get("result", "No result returned"))
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    test_weather()
