import streamlit as st
import re
from datetime import datetime
from dotenv import load_dotenv
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
import base64
import os

st.set_page_config(page_title="물어보연세", page_icon="🦅", layout="wide")
# [API 키 강제 주입 코드]
if "OPENAI_API_KEY" in st.secrets:
    os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
if "TAVILY_API_KEY" in st.secrets:
    os.environ["TAVILY_API_KEY"] = st.secrets["TAVILY_API_KEY"]
# --------------------------------------------------------------------------
# Theme Logic
# --------------------------------------------------------------------------
if "theme" not in st.session_state:
    st.session_state["theme"] = "default"

def get_img_as_base64(file_path):
    if not os.path.exists(file_path):
        return ""
    with open(file_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

def get_theme_css(theme):
    # [1] 사이드바 강제 고정 (무조건 흰색 배경/검은 글씨)
    sidebar_fixed_css = """
    section[data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e0e0e0 !important;
    }
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3, 
    section[data-testid="stSidebar"] p, 
    section[data-testid="stSidebar"] span, 
    section[data-testid="stSidebar"] div, 
    section[data-testid="stSidebar"] label {
        color: #333333 !important;
        text-shadow: none !important;
    }
    section[data-testid="stSidebar"] button {
        background-color: #ffffff !important;
        color: #333333 !important;
        border: 1px solid #ccc !important;
    }
    section[data-testid="stSidebar"] button:hover {
        background-color: #f0f0f0 !important;
        border-color: #999 !important;
    }
    """

    # 버튼 CSS 생성 함수
    def get_btn_css(bg_color, text_color):
        return f"""
        a[data-testid="stLinkButton"] {{
            background-color: {bg_color} !important;
            color: {text_color} !important;
            border: none !important;
            font-weight: bold !important;
            border-radius: 8px !important;
            text-decoration: none !important;
        }}
        a[data-testid="stLinkButton"] * {{
            color: {text_color} !important;
        }}
        a[data-testid="stLinkButton"]:hover {{
            background-color: {bg_color} !important;
            filter: brightness(0.9);
            color: {text_color} !important;
        }}
        """
    
    # [2] 테마별 CSS 설정 (다크 모드 삭제됨)
    if theme == "yonsei":
        # 연세 모드
        img_b64 = get_img_as_base64("8317179807071705.jpg")
        return sidebar_fixed_css + get_btn_css("#003876", "#ffffff") + f"""
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@700;900&display=swap');
        
        .stApp {{
            background-image: url('data:image/jpg;base64,{img_b64}');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        .stApp::before {{
            content: "";
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background-color: rgba(255, 255, 255, 0.85);
            z-index: -1;
        }}
        .stApp, .stText, p, h2, h3, h4, h5, h6, li, span, div {{
            color: #003876 !important;
            font-family: 'Noto Sans KR', sans-serif !important;
            font-weight: 700 !important;
        }}
        .stCaptionContainer, .stCaption, div[data-testid="stCaptionContainer"] p {{
             color: #ffffff !important;
        }}
        div[data-testid="stSpinner"] p {{
             color: #ffffff !important;
        }}
        div[data-testid="stStatusWidget"] div {{
             color: #ffffff !important;
        }}
        h1 {{
            color: #ffffff !important;
            font-family: 'Noto Sans KR', sans-serif !important;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
        }}
        #yonsei-title-prefix {{
            color: #ffffff !important;
        }}
        #love-yonsei-text {{
            color: #FFD700 !important;
        }}
        .answer-box {{
            padding: 1.2rem;
            border-radius: 10px;
            background-color: rgba(248, 249, 250, 0.95);
            border: 1px solid #003876 !important;
            border-left: 5px solid #003876 !important;
            margin-bottom: 1rem;
            font-size: 1.05rem;
            line-height: 1.6;
            color: #003876 !important;
            font-family: 'Noto Sans KR', sans-serif !important;
        }}
        """
        
    else:
        # 기본 모드 (Default)
        return sidebar_fixed_css + get_btn_css("#28a745", "#ffffff") + """
        .answer-box {
            padding: 1.2rem;
            border-radius: 10px;
            background-color: #f8f9fa;
            border-left: 5px solid #003876;
            margin-bottom: 1rem;
            font-size: 1.05rem;
            line-height: 1.6;
            color: #333;
        }
        """

st.markdown(f"<style>{get_theme_css(st.session_state['theme'])}</style>", unsafe_allow_html=True)


def get_clean_keyword(user_input, chat_history):
    load_dotenv()
    llm = ChatOpenAI(
    model="gpt-4o", 
    temperature=0, 
    openai_api_key=st.secrets["OPENAI_API_KEY"]
)
    
    ABBREVIATIONS = """
    [약어 사전]
    - 언기도 -> 연세대학교 언더우드기념도서관
    - 중도 -> 연세대학교 중앙도서관
    - 학관 -> 연세대학교 학생회관
    - 공라 -> 연세대학교 공학원 도서관
    - 국캠/송도 -> 연세대학교 국제캠퍼스
    - 신촌 -> 연세대학교 신촌캠퍼스
    - 복전 -> 연세대학교 복수전공
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", 
         f"""
         너는 검색어 최적화 에이전트다.
         사용자의 질문을 검색 엔진이 처리하기 좋은 키워드로 변환하라.
         
         [규칙]
         1. **약어 풀이:** 사전({ABBREVIATIONS})에 있는 단어는 반드시 공식 명칭으로 변경.
         2. **최신성:** 사용자가 날짜를 생략한 질문은 '최신' 키워드 추가.
         3. **장소 구체화:** '언기도 밑 우체국' 같이 특정 장소 내 시설을 물으면 -> '연세대학교 국제캠퍼스 우체국' 처럼 풀어서 검색어 생성.
         4. 연세대학교 미래캠퍼스에 관한 내용은 배제한다. 
         [출력]
         설명 없이 변환된 검색어만 출력.
         """),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}")
    ])

    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"chat_history": chat_history, "input": user_input})


@st.cache_resource
def get_agent_executor():
    load_dotenv()
    today = datetime.now().strftime("%Y년 %m월 %d일")
    
    search_tool = TavilySearchResults(k=15)
    llm = ChatOpenAI(
    model="gpt-4o", 
    temperature=0, 
    openai_api_key=st.secrets["OPENAI_API_KEY"]
)
    tools = [search_tool]
    
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                f"""
                너는 연세대학교의 모든 정보를 찾아주는 AI 탑색가 '연수리'다. (현재: {today})
                
                너는 질문의 유형을 파악하고 아래의 **행동 로직(Logic Flow)**을 엄격히 따라야 한다.
                
                # [유형별 행동 로직]
                - 연세대학교 미래캠퍼스에 대한 내용은 배제한다. 

                **CASE 1: 전화번호 질문**
                1. `yonsei.ac.kr` 도메인 내에서 1차 검색.(미래캠퍼스, 원주 등에 관한 내용은 배제하라.)
                2. (실패 시) 외부 사이트 및 지도 정보 등에서 2차 검색.공식 사이트가 아니여도 괜찮다((미래캠퍼스, 원주 등에 관한 내용은 배제하라.)
                3. **(그래도 실패 시)** 사용자가 찾는 대상의 **'상위 부서'**를 파악하라.(미래캠퍼스, 원주 등에 관한 내용은 배제하라.)
                4. **결과 제공:** "직통 번호가 없어 상위 부서인 [OOO]의 연락처를 안내해 드립니다"라고 명시하고 번호를 제공.(미래캠퍼스, 원주 등에 관한 내용은 배제하라.)

                **CASE 2: 이메일 질문**
                1. `yonsei.ac.kr` 도메인 내에서 1차 검색.
                2. (실패 시) 외부 사이트 검색.
                3. **(그래도 실패 시)** "죄송합니다. 공개된 이메일 정보를 찾을 수 없습니다."라고 정직하게 답변. (추측 금지)

                **CASE 3: 그 외(학사 정보, 행사, 위치 등)**
                1. 문맥에 따라 문장을 해석하고, 검색어 키워드를 추출한다. 
                2. 키워드에 장소가 포함되어있으면(언기도, 중도, 국제캠 기숙사 등) 무조건 yonsei.ac.kr+해당장소인 페이지(예를 들면, 언기도라는 키워드가 들어감-> 언더우드기념도서관 페이지uml.yonsei.ac.kr, 송도학사 -> yicdorm.yonsei.ac.kr)에서 최우선적으로 탐색하라. 반드시 그래야한다.
                3. 2번에서 정한 사이트의 공지사항을 우선적으로 확인한다. 나오지 않으면 그 사이트의 메인페이지를 제공해라.
                
                # [공통 출력 규칙]
                - 답변의 근거가 된 출처 URL은 답변 맨 마지막에 아래 태그로 붙여라. (본문엔 넣지 말 것)
                - `||SOURCE:https://찾은_URL`
                - 링크가 없으면 답변이 완성되지 않은 것이다. 반드시 찾아라.
                """
            ),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True)


def render_chat_message(full_response):
    md_link_pattern = r'\[([^\]]+)\]\((https?://[^\)]+)\)'
    inline_links = re.findall(md_link_pattern, full_response)
    clean_text = re.sub(md_link_pattern, r'\1', full_response)
    
    source_link_pattern = r'\|\|SOURCE:(https?://[^\s]+)'
    source_links = re.findall(source_link_pattern, clean_text)
    clean_text = re.sub(r'\|\|SOURCE:.*', '', clean_text).strip()

    st.markdown(f"<div class='answer-box'>{clean_text}</div>", unsafe_allow_html=True)
    
    all_links = []
    
    for title, url in inline_links:
        all_links.append((title, url))
        
    for url in source_links:
        if not any(link[1] == url for link in all_links):
            label = "관련 자료"
            if "yonsei.ac.kr" in url: label = "🦅 공식 홈페이지"
            elif "map" in url: label = "📍 지도/위치"
            elif "google" in url and "forms" in url: label = "📝 신청 폼"
            all_links.append((label, url))

    valid_links = []
    for label, url in all_links:
        if any(bad in url for bad in ["login", "auth", "member", "facebook", "instagram", "band.us"]):
            continue
        valid_links.append((label, url))

    if valid_links:
        st.caption("📚 관련 링크 바로가기")
        cols = st.columns(min(len(valid_links), 4))
        for i, (label, url) in enumerate(valid_links[:4]):
            with cols[i]:
                display_label = label[:10] + ".." if len(label) > 10 else label
                st.link_button(display_label, url, use_container_width=True)


def main():
    with st.sidebar:
        st.title("🦅 물어보연세")
        st.info("""
        연세대학교와 관련된 정보를 물어보면 답해드립니다!
        """)
        st.error("질문 답변중 모드를 바꾸지 마세요.")
        
        st.divider()
        st.subheader("화면 스타일 설정")
        # [수정됨] 다크 모드 버튼 삭제
        if st.button("기본 모드", use_container_width=True):
            st.session_state["theme"] = "default"
            st.rerun()
        if st.button("연세 모드", use_container_width=True):
            st.session_state["theme"] = "yonsei"
            st.rerun()
        

    # Title Section
    if st.session_state["theme"] == "yonsei":
        col_title, col_btn = st.columns([3, 1])
        with col_title:
            st.markdown("<h1>🦅 <span id='yonsei-title-prefix' style='font-size: 50%;'>무엇이든</span> 물어보연세</h1>", unsafe_allow_html=True)
        with col_btn:
             st.markdown("""
             <div style="text-align: right; padding-top: 10px;">
                 <a href="https://www.youtube.com/watch?v=cGdOCYiQNyg&list=RDcGdOCYiQNyg&start_radio=1" target="_blank" style="
                    display: inline-block;
                    text-decoration: none;
                    background-color: #003876;
                    border-radius: 8px;
                    border: 2px solid white; 
                    padding: 0.5rem 1rem;
                 ">
                 <span id="love-yonsei-text" style="
                    font-weight: bold;
                    font-family: 'Noto Sans KR', sans-serif;
                 ">나는 연세를 사랑한다</span>
                 </a>
             </div>
             """, unsafe_allow_html=True)
    else:
        st.markdown("<h1>🦅 <span style='font-size: 50%;'>무엇이든</span> 물어보연세</h1>", unsafe_allow_html=True)

    st.divider()

    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "memory" not in st.session_state:
        st.session_state["memory"] = []

    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"], avatar="🦅" if msg["role"] == "assistant" else "👤"):
            if msg["role"] == "assistant":
                render_chat_message(msg["content"])
            else:
                st.write(msg["content"])

    if prompt_input := st.chat_input("질문을 입력하세요..."):
        with st.chat_message("user", avatar="👤"):
            st.write(prompt_input)
        st.session_state["messages"].append({"role": "user", "content": prompt_input})
        
        refined_query = get_clean_keyword(prompt_input, st.session_state["memory"])
        
        agent = get_agent_executor()
        
        with st.chat_message("assistant", avatar="🦅"):
            with st.spinner(f"🦅 '{refined_query}' 정보 확인 중..."):
                try:
                    response = agent.invoke({"input": refined_query})
                    output = response["output"]
                    render_chat_message(output)
                    
                    st.session_state["messages"].append({"role": "assistant", "content": output})
                    st.session_state["memory"].append(HumanMessage(content=prompt_input))
                    st.session_state["memory"].append(AIMessage(content=output))
                except Exception as e:
                    st.error("오류가 발생했습니다.")
                    st.write(e)

if __name__ == "__main__":

    main()

