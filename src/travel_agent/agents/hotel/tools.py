import re
from typing import Optional

from serpapi import GoogleSearch

def extract_id_from_link(link: str) -> Optional[str]:
    """호텔 상세 링크 URL에서 고유 Entity ID를 추출합니다."""
    if not link:
        return None
    match = re.search(r'/entity/([^/?]+)', link)
    if match:
        return match.group(1)
    return None

def get_hotel_data_text(api_key: str, location: str, check_in_date: str = "", check_out_date: str = "") -> str:
    """SerpApi를 사용하여 구글 호텔 검색 후, 결과를 보기 좋은 문자열로 포맷팅합니다."""
    if not api_key:
        return (
            "⚠️ **API 키 누락 오류**\n"
            "`SERPAPI_API_KEY` 환경 변수가 설정되지 않아 구글 호텔 검색을 수행할 수 없습니다.\n"
            "SerpApi 가입 후 발급받은 키를 프로젝트의 `.env` 파일에 추가해 주세요."
        )

    # 기본 파라미터 구성
    params = {
        "engine": "google_hotels",
        "q": f"{location} 최고 평점 호텔", # 5성급 대신 '최고 평점' 등으로 유연하게 변경
        "currency": "KRW",
        "gl": "kr",   # 국가 코드
        "hl": "ko",   # 언어 설정
        "api_key": api_key
    }

    import datetime
    
    # 구글 호텔 API는 기본적으로 날짜가 필수 파라미터입니다.
    # 사용자가 제시하지 않았다면 '내일'과 '모레'를 임의 지정합니다.
    if not check_in_date:
        check_in_date = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    if not check_out_date:
        check_out_date = (datetime.date.today() + datetime.timedelta(days=2)).strftime("%Y-%m-%d")

    params["check_in_date"] = check_in_date
    params["check_out_date"] = check_out_date

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
    except Exception as e:
        return f"호텔 검색 중 외부 API 오류가 발생했습니다: {e}"

    hotels = results.get("properties", [])
    if not hotels:
        query_date = f" ({check_in_date} ~ {check_out_date})" if check_in_date else ""
        return f"'{location}' 지역{query_date}의 호텔 검색 결과가 없습니다."

    # 포매팅 시작
    lines = [
        f"### 🏨 '{location}' 추천 호텔 베스트 5",
        ""
    ]

    for idx, hotel in enumerate(hotels[:5], 1): # 가독성을 위해 상위 5개만
        name = hotel.get("name", "이름 없음")
        
        # 가격 정보 추출
        rate_info = hotel.get("rate_per_night", {})
        price = rate_info.get("lowest", "가격 정보 없음")
        
        rating = hotel.get("overall_rating", "평가 없음")
        reviews = hotel.get("reviews", 0)
        
        # 편의시설 추출 (최대 3개 등)
        amenities = hotel.get("amenities", [])
        if amenities:
            amenities_str = ", ".join(amenities[:4])
            if len(amenities) > 4:
                amenities_str += " 등"
        else:
            amenities_str = "정보 없음"
            
        link = hotel.get("link", "#")

        # 마크다운 포맷 조합
        lines.append(f"**{idx}. [{name}]({link})**")
        lines.append(f"- 💰 1박 예상 가격: **{price}**")
        lines.append(f"- ⭐ 평점: **{rating}** ({reviews}개의 리뷰)")
        lines.append(f"- 🛋️ 편의시설: {amenities_str}")
        lines.append("")

    return "\n".join(lines)
