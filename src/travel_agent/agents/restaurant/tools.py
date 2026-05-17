import logging
from typing import List, Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from serpapi import GoogleSearch

from travel_agent.config import OPENAI_API_KEY, OPENAI_MODEL, SERPAPI_API_KEY

logger = logging.getLogger(__name__)

def generate_optimized_search_query(location: str, travel_context: str) -> str:
    """LLM을 사용하여 사용자의 상황과 장소에 최적화된 검색 쿼리를 생성합니다."""
    llm = ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY, temperature=0)
    
    prompt = (
        f"사용자가 '{location}'으로 '{travel_context}' 여행을 계획 중입니다. "
        f"이 상황에 가장 적합한 '분위기와 특징이 뚜렷한' 현지 맛집을 찾기 위한 Google Maps 검색어를 생성하세요.\n"
        f"조건:\n"
        f"1. 단순 맛집이 아닌, '{travel_context}'가 선호할 만한 'vibe', 'atmosphere', 'service' 정보를 유도하는 키워드를 포함하세요.\n"
        f"2. 해외 지역일 경우 영문 검색어를 우선하세요.\n"
        f"3. 검색어만 딱 한 줄로 출력하세요.\n"
        f"예: 'romantic upscale restaurants with sunset view in Da Nang', '서울 부모님 환갑잔치 하기 좋은 프라이빗 룸 식당'"
    )
    
    try:
        response = llm.invoke(prompt)
        return response.content.strip().replace("'", "").replace('"', "")
    except Exception:
        return f"{location} {travel_context} 맛집"

def fetch_restaurant_documents(location: str, travel_context: str) -> List[Document]:
    """LLM이 생성한 동적 쿼리를 사용하여 맛집 정보를 수집합니다."""
    if not SERPAPI_API_KEY:
        return []

    optimized_query = generate_optimized_search_query(location, travel_context)
    logger.info(f"Generated dynamic query: {optimized_query}")

    params = {
        "engine": "google_maps",
        "q": optimized_query,
        "type": "search",
        "hl": "ko",
        "api_key": SERPAPI_API_KEY
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
    except Exception as e:
        logger.error(f"SerpApi 호출 오류: {e}")
        return []

    local_results = results.get("local_results", [])
    documents = []
    
    for res in local_results:
        # 가독성을 위해 평점과 리뷰가 있는 것 위주로 컨텍스트 구성
        content = (
            f"식당명: {res.get('title')}\n"
            f"카테고리: {res.get('type')}\n"
            f"평점: {res.get('rating')} (리뷰 {res.get('reviews')}개)\n"
            f"주소: {res.get('address')}\n"
            f"가격대: {res.get('price')}\n"
            f"특징/설명: {res.get('description')}\n"
            f"실제 고객 리뷰 요약: {' '.join([h.get('review', '') for h in res.get('review_highlights', [])])}"
        )
        documents.append(Document(page_content=content, metadata={"name": res.get("title")}))
    
    return documents

def get_persona_recommendations(location: str, travel_context: str) -> str:
    """데이터와 페르소나 사이의 구체적 연결 고리를 포함한 추천을 생성합니다."""
    logger.warning(f"[RAG DEBUG] location={location!r}  travel_context={travel_context!r}")
    if not OPENAI_API_KEY:
        return "OpenAI API 키가 설정되지 않았습니다."

    docs = fetch_restaurant_documents(location, travel_context)
    if not docs:
        return f"'{location}' 지역에서 '{travel_context}'에 맞는 식당 정보를 찾을 수 없습니다."

    embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY)
    vectorstore = FAISS.from_documents(docs, embeddings)

    # 페르소나 키워드와 가장 관련 깊은 문서 검색
    relevant_docs = vectorstore.similarity_search(travel_context, k=5)
    context_text = "\n\n".join([d.page_content for d in relevant_docs])

    llm = ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY, temperature=0.2)

    prompt = (
        f"당신은 '{location}' 전문 가이드이자 미식 전문가입니다. "
        f"아래의 실제 수집된 식당 데이터와 리뷰를 분석하여 '{travel_context}' 여행객에게 완벽한 식당 3곳을 추천하세요.\n\n"
        f"### 지침:\n"
        f"1. 추천 사유에 반드시 '{travel_context}'라는 단어를 직접 포함하세요. "
        f"예: '이 식당은 {travel_context}에게 ... 한 이유로 강력히 추천합니다.'\n"
        f"2. 단순히 좋은 식당이 아니라, 수집된 리뷰/특징 데이터에서 '{travel_context}'의 상황과 "
        f"연결되는 구체적인 근거(분위기, 서비스, 메뉴 등)를 반드시 언급하세요.\n"
        f"3. 반드시 '{location}' 현지 식당인지 주소로 확인 후 선별하세요.\n"
        f"4. 전문적이고 설득력 있는 말투를 사용하세요.\n\n"
        f"### 수집된 맛집 데이터:\n{context_text}\n\n"
        f"### 답변 형식:\n"
        f"각 식당별로 다음 형식을 따르세요:\n"
        f"- 식당 이름 / 평점\n"
        f"- [{travel_context} 맞춤 추천 사유] (반드시 '{travel_context}'라는 단어를 포함할 것)"
    )

    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as e:
        return f"추천 생성 중 오류 발생: {e}"
