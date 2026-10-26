import streamlit as st
import pandas as pd
import numpy as np
import base64
import os
import json
import re
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
import math
import uuid
import urllib.request
import urllib.error
from catboost import CatBoostRegressor


# 로컬 .env 파일이 존재할 경우 환경변수로 자동 로드
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as _f:
        for _line in _f:
            if "=" in _line and not _line.strip().startswith("#"):
                _k, _v = _line.strip().split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# --------------------------------------------------------------------------
# 페이지 기본 설정 및 스타일
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="HostMate",
    page_icon="🏠",
    layout="wide"
)

@st.cache_data
def get_base64_encoded_image(target_path):
    with open(target_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def set_dashboard_background(image_name="nyc_background.jpg"):
    base_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else '.'
    candidates = [
        image_name,
        os.path.join(base_dir, image_name),
        "nyc_background.png",
        os.path.join(base_dir, "nyc_background.png"),
        "nyc_background.jpeg",
        os.path.join(base_dir, "nyc_background.jpeg")
    ]
    
    target_path = None
    for p in candidates:
        if os.path.exists(p):
            target_path = p
            break
            
    if target_path is None:
        print(f"⚠️ [HostMate] 배경 이미지({image_name})를 찾을 수 없습니다. 경로를 확인해 주세요.")
        return

    mime = "image/png" if target_path.lower().endswith(".png") else "image/jpeg"
    encoded_img = get_base64_encoded_image(target_path)

    bg_css = f"""
        <style>
            [data-testid="stAppViewContainer"] {{
                background: linear-gradient(rgba(18, 19, 26, 0.75), rgba(15, 16, 22, 0.80)),
                            url("data:{mime};base64,{encoded_img}") !important;
                background-size: cover !important;
                background-position: center bottom !important;
                background-attachment: fixed !important;
            }}
            [data-testid="stHeader"], [data-testid="stMain"], .stApp {{
                background: transparent !important;
            }}
        </style>
    """
    st.markdown(bg_css, unsafe_allow_html=True)

set_dashboard_background("nyc_background.jpg")

st.markdown("""
<style>
    /* 전역 타이포그래피 및 구분선 */
    h1, h2, h3, p, ul, li { margin: 0; padding: 0; font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif; }
    div[data-testid="stMarkdownContainer"] > hr { margin-top: 0.8rem !important; margin-bottom: 1.5rem !important; border-color: rgba(255,255,255,0.12); }

    /* 상단 Stepper (진행 상태 바) */
    .stepper-wrap {
        display: flex; justify-content: space-between; align-items: center;
        background: rgba(30, 32, 42, 0.85); border: 1px solid rgba(255,255,255,0.1);
        padding: 14px 28px; border-radius: 14px; margin-bottom: 24px;
    }
    .step-item { display: flex; align-items: center; gap: 10px; font-size: 15px; font-weight: 600; color: #777A8B; }
    .step-item.active { color: #FFFFFF; font-weight: 800; }
    .step-item.done { color: #38EF7D; }
    .step-badge {
        width: 26px; height: 26px; border-radius: 50%; display: inline-flex;
        align-items: center; justify-content: center; font-size: 13px; font-weight: 800;
        background: #2E303E; color: #888;
    }
    .step-item.active .step-badge { background: linear-gradient(135deg, #FF385C 0%, #E31C5F 100%); color: white; box-shadow: 0 0 12px rgba(255,56,92,0.5); }
    .step-item.done .step-badge { background: rgba(56, 239, 125, 0.2); color: #38EF7D; border: 1px solid #38EF7D; }

    /* 공통 버튼 스타일 (전역 오염 방지) */
    div.stButton > button {
        height: 48px; border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.15); background: #262837; color: #FFFFFF;
        transition: all 0.2s ease;
    }
    /* 일반(이동/확정 등) 버튼 내부 텍스트: 글자 크기 17px & 볼드(800) */
    div.stButton > button p {
        font-size: 16px !important;
        font-weight: 700 !important;
        letter-spacing: -0.2px;
    }
    div.stButton > button:hover { border-color: #FF385C; color: #FFFFFF; transform: translateY(-1px); }
    div.stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #FF385C 0%, #D90B38 100%) !important;
        border: none !important; color: white !important;
        box-shadow: 0 6px 20px rgba(255, 56, 92, 0.35) !important;
    }
    div.stButton > button[kind="primary"]:hover {
        box-shadow: 0 8px 25px rgba(255, 56, 92, 0.55) !important; transform: scale(1.01);
    }

    /* 가이드 박스 */
    .guide-box {
        background: linear-gradient(135deg, #1E2030 0%, #27293D 100%);
        padding: 18px 22px; border-left: 5px solid #FF385C; border-radius: 12px;
        margin-bottom: 22px; box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .guide-text { color: #FFFFFF; font-size: 16.5px; font-weight: 600; display: flex; align-items: center; gap: 10px; }

    /* 결과 페이지 KPI 카드 */
    .kpi-card {
        background: linear-gradient(145deg, #222433 0%, #191A24 100%);
        border: 1px solid rgba(255,255,255,0.12); border-radius: 18px; padding: 24px;
        height: 100%; position: relative; overflow: hidden;
    }
    .kpi-card.primary-kpi {
        background: radial-gradient(circle at top right, rgba(255, 56, 92, 0.22), transparent 60%),
                    linear-gradient(145deg, #261E2B 0%, #191A24 100%);
        border: 1.5px solid #FF385C;
    }
    .kpi-label { font-size: 14px; font-weight: 600; color: #A0A4B8; margin-bottom: 8px; }
    .kpi-value { font-size: 40px; font-weight: 800; color: #FFFFFF; letter-spacing: -1px; line-height: 1.1; }
    .kpi-sub { font-size: 13.5px; color: #B8BCCF; margin-top: 12px; line-height: 1.5; }

    /* 사이드바 스타일 */
    .sidebar-label { font-size: 13px; font-weight: 700; color: #8E92A4; margin-bottom: 6px; margin-top: 16px; text-transform: uppercase; }
    .sidebar-box {
        background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 10px; padding: 10px 14px; color: #FFFFFF; font-size: 14.5px; font-weight: 600;
    }

    /* 랜딩 페이지 상용 SaaS 스타일 추가 */
    .top-brand-bar {
        display: flex; justify-content: space-between; align-items: center;
        padding: 8px 4px 20px 4px; border-bottom: 1px solid rgba(255,255,255,0.08); margin-bottom: 28px;
    }
    .brand-logo { font-size: 28px; font-weight: 800; color: #FFFFFF; letter-spacing: -0.5px; display: flex; align-items: center; gap: 10px; }
    .brand-dot { width: 12px; height: 12px; border-radius: 50%; background: #FF385C; box-shadow: 0 0 12px #FF385C; }
    .status-pill {
        background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.12);
        color: #B0B3C5; padding: 6px 14px; border-radius: 999px; font-size: 13px; font-weight: 600;
    }

    /* 시세 프리미엄 배지 */
    .premium-badge {
        background: rgba(56, 239, 125, 0.14);
        border: 1px solid rgba(56, 239, 125, 0.4);
        color: #38EF7D;
        padding: 5px 12px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 800;
        letter-spacing: -0.2px;
        box-shadow: 0 0 12px rgba(56, 239, 125, 0.2);
    }

    /* 좌측 메인 히어로 박스 (좌측 정렬) */
    .saas-hero-left {
        background: radial-gradient(circle at 10% 15%, rgba(255, 56, 92, 0.18), transparent 55%),
                    linear-gradient(145deg, #1E202B 0%, #14151D 100%);
        border: 1px solid rgba(255,255,255,0.1); border-radius: 24px;
        padding: 44px 40px; height: 100%; text-align: left;
        box-shadow: 0 20px 40px rgba(0,0,0,0.4);
    }
    .eyebrow-tag {
        display: inline-block; background: rgba(255, 56, 92, 0.14); color: #FF6B81;
        border: 1px solid rgba(255, 56, 92, 0.35); padding: 5px 14px; border-radius: 999px;
        font-size: 13px; font-weight: 700; margin-bottom: 18px;
    }
    .saas-title { font-size: 38px; font-weight: 800; color: #FFFFFF; line-height: 1.25; letter-spacing: -1px; margin-bottom: 16px; }
    .saas-desc { font-size: 16px; color: #A0A4B8; line-height: 1.65; margin-bottom: 24px; }
    .check-list { display: flex; gap: 18px; flex-wrap: wrap; padding-top: 18px; border-top: 1px solid rgba(255,255,255,0.08); font-size: 13.5px; color: #D0D3E2; font-weight: 600; }

    /* 우측 실시간 리포트 프리뷰 위젯 */
    div[data-testid="stColumn"]:has(.saas-preview-card) > div[data-testid="stVerticalBlock"],
    div[data-testid="stColumn"]:has(.saas-preview-card) .stElementContainer,
    div[data-testid="stColumn"]:has(.saas-preview-card) div[data-testid="stMarkdownContainer"] {
        height: 100% !important;
        display: flex !important;
        flex-direction: column !important;
    }
    .saas-preview-card {
        background: linear-gradient(160deg, #242636 0%, #181924 100%);
        border: 1px solid rgba(255,255,255,0.14); border-radius: 24px;
        padding: 28px 28px; height: 100%; box-sizing: border-box;
        box-shadow: 0 20px 40px rgba(0,0,0,0.4);
        display: flex; flex-direction: column; justify-content: space-between;
    }
    .preview-top { display: flex; justify-content: space-between; align-items: center; padding-bottom: 14px; margin-bottom: 16px; border-bottom: 1px solid rgba(255,255,255,0.08); }
    .live-badge { background: rgba(56, 239, 125, 0.15); color: #38EF7D; border: 1px solid rgba(56, 239, 125, 0.35); padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
    .preview-main-box { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 18px; margin-bottom: 14px; }
    .preview-row { display: flex; justify-content: space-between; padding: 9px 0; border-bottom: 1px dashed rgba(255,255,255,0.08); font-size: 14px; color: #CCCCCC; }

    .bento-feature-wrap {
        display: flex; flex-direction: column; gap: 12px; height: 100%; justify-content: space-between;
    }
    .bento-feature-item {
        background: linear-gradient(145deg, #1E202B 0%, #161722 100%);
        border: 1px solid rgba(255,255,255,0.08); border-radius: 16px;
        padding: 18px 22px; transition: all 0.25s ease; text-align: left;
    }
    .bento-feature-item:hover {
        border-color: #FF385C; transform: translateX(4px); box-shadow: 0 8px 20px rgba(255,56,92,0.12);
    }
    .bento-feature-step {
        font-size: 11px; font-weight: 800; color: #FF5A79; letter-spacing: 1px; margin-bottom: 4px; display: block;
    }
    .bento-feature-title { font-size: 16px; font-weight: 700; color: #FFFFFF; margin-bottom: 4px; }
    .bento-feature-text { font-size: 13.5px; color: #9EA3B8; line-height: 1.5; margin: 0; }

    /* 섹션 디바이더 헤더 */
    .saas-section-header {
        margin-top: 36px; margin-bottom: 22px; text-align: left;
        padding-top: 26px; border-top: 1px solid rgba(255,255,255,0.08);
    }
    .saas-section-badge {
        display: inline-block; background: rgba(96, 165, 250, 0.12); color: #60A5FA;
        border: 1px solid rgba(96, 165, 250, 0.3); padding: 4px 12px; border-radius: 999px;
        font-size: 12px; font-weight: 700; margin-bottom: 10px;
    }
    .saas-section-title { font-size: 24px; font-weight: 800; color: #FFFFFF; letter-spacing: -0.5px; margin-bottom: 6px; }
    .saas-section-desc { font-size: 14.5px; color: #8E92A8; margin: 0; }

    /* [3개 시세 박스] 좌측 'AI 추천 1박 적정 요금' 박스와 100% 동일한 연한 다크톤 */
    .stat-pill-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
        margin-top: 14px;
        margin-bottom: 14px;
    }
    .stat-pill {
        background: #252838 !important; /* 좌측 .preview-main-box와 100% 동일한 연한 솔리드 다크 */
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 14px !important;
        padding: 14px 8px !important;
        text-align: center !important;
        box-shadow: none !important;
    }
    .stat-pill-label { 
        font-size: 12px; 
        color: #8E92A8; 
        margin-bottom: 5px; 
        font-weight: 600; 
    }
    .stat-pill-val { 
        font-size: 17.5px; 
        font-weight: 800; 
    }

    /* [우측 겉박스] 좌측 카드와 100% 동일한 어두운 불투명 카드 (다중 안전 셀렉터) */
    .st-key-landing_action_card,
    div[class*="st-key-landing_action_card"],
    div[data-testid*="stColumn"]:nth-of-type(2) div[data-testid*="stVerticalBlock"]:has(button[key*="btn_landing_"]) {
        background: linear-gradient(160deg, #242636 0%, #181924 100%) !important;
        background-color: #1E202B !important; /* 배경 투과 원천 차단 */
        border: 1px solid rgba(255, 255, 255, 0.14) !important;
        border-radius: 24px !important;
        padding: 26px 24px !important;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.45) !important;
    }
    .st-key-landing_action_card > div {
        background: transparent !important;
        border: none !important;
    }

    /* 자치구 선택 버튼 탭 */
    div[class*="st-key-btn_landing_"] div.stButton > button,
    div[class*="st-key-quick_boro_"] div.stButton > button {
        height: 44px !important;
        border-radius: 10px !important;
        padding: 0 4px !important;
    }
    /* 자치구 버튼 기본(미선택) 글자 크기 확대(16.5px) 및 일반 굵기(500) */
    div[class*="st-key-btn_landing_"] div.stButton > button p,
    div[class*="st-key-quick_boro_"] div.stButton > button p {
        font-size: 16px !important;
        font-weight: 500 !important;
    }
    /* 자치구 버튼 선택되었을 때(primary) 글자 볼드(800) 처리 */
    div[class*="st-key-btn_landing_"] div.stButton > button[kind="primary"] p,
    div[class*="st-key-quick_boro_"] div.stButton > button[kind="primary"] p {
        font-size: 16px !important;
        font-weight: 700 !important;
    }

    /* [우측 하단 3줄 브리핑 행] 좌측 미리보기 리스트와 동일한 레이아웃 */
    .action-info-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 9.5px 0;
        border-bottom: 1px dashed rgba(255, 255, 255, 0.08);
        font-size: 13.5px;
        color: #CCCCCC;
    }

    /* 메인 섹션 헤더 (운영 방식 선택 / 세부 운영 조건 설정) */
    .section-main-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-top: 10px;
        margin-bottom: 14px;
    }
    .section-main-title {
        font-size: 20px !important;
        font-weight: 800 !important;
        color: #FFFFFF !important;
        letter-spacing: -0.3px;
    }

    /* 하위 위젯 라벨 크기 강화 (최소 숙박일 수 / 숙소 공간 유형) */
    div[data-testid="stSlider"] label p,
    div[data-testid="stSelectbox"] label p,
    div[data-testid="stNumberInput"] label p {
        font-size: 15.5px !important;
        font-weight: 700 !important;
        color: #F1F3F9 !important;
        margin-bottom: 6px !important;
    }

    /* 인라인 호버 툴팁 배지 & 팝업 */
    .inline-tooltip-wrap {
        position: relative;
        display: inline-flex;
        align-items: center;
    }
    .policy-hover-badge {
        background: rgba(255, 56, 92, 0.12);
        color: #FF6B81;
        border: 1px solid rgba(255, 56, 92, 0.35);
        padding: 5px 12px;
        border-radius: 999px;
        font-size: 12.5px;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.2s ease;
        display: inline-flex;
        align-items: center;
        gap: 5px;
    }
    .policy-hover-badge:hover {
        background: rgba(255, 56, 92, 0.22);
        border-color: #FF385C;
        color: #FFFFFF;
        box-shadow: 0 0 14px rgba(255, 56, 92, 0.35);
    }
    .policy-popup-card {
        visibility: hidden;
        opacity: 0;
        position: absolute;
        top: calc(100% + 10px);
        left: 0;
        width: 480px;
        max-width: 90vw;
        background: #181A24;
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 14px;
        padding: 16px 18px;
        box-shadow: 0 16px 36px rgba(0, 0, 0, 0.7);
        z-index: 99999;
        transition: all 0.2s ease-in-out;
        pointer-events: none;
    }
    .inline-tooltip-wrap:hover .policy-popup-card {
        visibility: visible;
        opacity: 1;
        transform: translateY(0);
        pointer-events: auto;
    }
    .popup-title {
        font-size: 13px;
        font-weight: 800;
        color: #A0A4B8;
        margin-bottom: 10px;
        padding-bottom: 6px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        display: flex;
        justify-content: space-between;
    }
    .popup-row {
        font-size: 13.5px;
        line-height: 1.6;
        margin-bottom: 6px;
    }
    .popup-row:last-child {
        margin-bottom: 0;
    }

    .tip-hover-badge {
        background: rgba(255, 255, 255, 0.07);
        color: #D1D5DB;
        border: 1px solid rgba(255, 255, 255, 0.2);
        padding: 3px 10px;               
        border-radius: 999px;            
        font-size: 11.5px;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.2s ease;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        user-select: none;
    }
    .tip-hover-badge:hover {
        background: rgba(255, 184, 0, 0.16);
        border-color: #FFB800;
        color: #FFB800;
        box-shadow: 0 0 12px rgba(255, 184, 0, 0.35);
    }
    .tip-popup-card {
        visibility: hidden;
        opacity: 0;
        position: absolute;
        bottom: calc(100% + 8px);
        top: auto;
        right: 0;
        left: auto;
        width: max-content;          
        max-width: 380px;               
        background: #181A24;
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 10px;
        padding: 8px 13px; 
        box-shadow: 0 14px 32px rgba(0, 0, 0, 0.75);
        z-index: 99999;
        transition: all 0.2s ease-in-out;
        pointer-events: none;
        font-size: 13px;
        color: #FFFFFF;
        line-height: 1.5;
        text-align: left;
        white-space: normal;
        word-break: keep-all;
    }
    .inline-tooltip-wrap:hover .tip-popup-card {
        visibility: visible;
        opacity: 1;
        pointer-events: auto;
    }

    @keyframes fadeOutWarning {
        0%   { opacity: 1; max-height: 80px; transform: translateY(0); }
        80%  { opacity: 1; max-height: 80px; transform: translateY(0); }
        95%  { opacity: 0; max-height: 80px; transform: translateY(-4px); }
        100% { opacity: 0; max-height: 0; padding: 0; margin: 0; border: none; visibility: hidden; }
    }
    .fade-warning-card {
        overflow: hidden;
        animation: fadeOutWarning 5s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------
# 내장 레퍼런스 DB 
# -------------------------------------

# 공통 기준 좌표 및 자치구 중심점 정의
TIMES_SQUARE_COORDS = [40.7580, -73.9855]

BOROUGH_CENTERS = {
    "Manhattan": [40.7580, -73.9855],
    "Brooklyn": [40.6782, -73.9442],
    "Queens": [40.7282, -73.7949],
    "Bronx": [40.8448, -73.8648],
    "Staten Island": [40.5795, -74.1502]
}

# 4대 편의시설 카테고리 정의
AMENITY_GROUPS = {
    "💎 프리미엄 편의시설": {
        "col": "luxury_amenities_cnt",
        "items": {
            "elevator": "엘리베이터",
            "gym": "헬스장",
            "building_staff": "도어맨 / 빌딩 스태프",
            "view": "스카이라인 뷰",
            "patio_balcony": "테라스 / 발코니",
        },
    },
    "🍳 실생활 편의시설": {
        "col": "living_amenities_cnt",
        "items": {
            "kitchen": "주방/취사 시설",
            "washer": "실내 세탁기",
            "dryer": "실내 건조기",
            "dishwasher": "식기세척기",
            "refrigerator": "대형 냉장고",
        },
    },
    "💼 서비스 편의시설": {
        "col": "service_amenities_cnt",
        "items": {
            "workspace": "전용 업무 공간(책상·의자)",
            "self_checkin": "셀프 체크인",
            "coffee_maker": "커피 메이커",
            "pets_allowed": "반려동물 동반 가능",
            "iron": "다리미",
        },
    },
    "🧴 필수 편의시설": {
        "col": "essential_amenities_cnt",
        "items": {
            "air_conditioning": "에어컨",
            "heating": "난방 시설",
            "wifi": "초고속 무선 인터넷 (WIFI)",
            "tv": "TV",
            "hair_dryer": "헤어드라이어",
        },
    },
}

# ---------------------------------
# 데이터 및 모델 로드 함수
# ---------------------------------
@st.cache_data
def load_location_data():
    return pd.read_csv('location.csv')

@st.cache_data
def load_market_summary():
    for fname in ['market_summary.json']:
        try:
            with open(fname, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            continue
    return {"borough_room_medians": {}, "hood_room_medians": {}, "citywide_room_medians": {}} # 안전 리턴 추가

loc_df = load_location_data()
market_data = load_market_summary()
BOROUGH_ROOM_MEDIANS = market_data.get("borough_room_medians", {})

@st.cache_data
def load_real_neighborhood_geojson():
    """로컬의 Inside Airbnb 세부 동네 GeoJSON 파일을 최우선 로드"""
    for path in ["neighbourhoods.geojson", "neighborhoods.geojson"]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                continue
    return None

def _point_in_ring(lon, lat, ring):
    """점이 다각형(ring) 내부에 있는지 판별 (Ray-Casting 알고리즘)"""
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        if ((y1 > lat) != (y2 > lat)) and (lon < (x2 - x1) * (lat - y1) / (y2 - y1 + 1e-12) + x1):
            inside = not inside
    return inside

def _point_in_geometry(lon, lat, geom):
    """점이 GeoJSON Polygon 또는 MultiPolygon 내부에 있는지 확인"""
    g_type = geom.get("type")
    coords = geom.get("coordinates", [])
    if g_type == "Polygon" and coords:
        return _point_in_ring(lon, lat, coords[0])
    elif g_type == "MultiPolygon":
        for poly in coords:
            if poly and _point_in_ring(lon, lat, poly[0]):
                return True
    return False

def _norm_name(s):
    """특수문자, 공백, 대소문자를 모두 제거하여 이름 매칭 확률을 극대화"""
    return re.sub(r'[^a-z0-9]', '', str(s).lower())

@st.cache_data
def get_real_hood_geojson_for_borough(borough_name, _hoods_df, _raw_hood_geojson):
    if not _raw_hood_geojson or _hoods_df.empty or not borough_name:
        return None

    # 1. location.csv의 동네 이름을 정규화 키로 매핑
    csv_hood_exact = {str(r['neighbourhood']).strip().lower(): str(r['neighbourhood']).strip() for _, r in _hoods_df.iterrows()}
    csv_hood_norm = {_norm_name(r['neighbourhood']): str(r['neighbourhood']).strip() for _, r in _hoods_df.iterrows()}
    csv_pts = [(float(r['mean_lon']), float(r['mean_lat']), str(r['neighbourhood']).strip()) for _, r in _hoods_df.iterrows()]

    matched_features = []
    target_boro_norm = _norm_name(borough_name)

    for feat in _raw_hood_geojson.get("features", []):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        if not geom:
            continue

        f_boro = props.get("neighbourhood_group") or props.get("borough") or props.get("BoroName") or ""
        if f_boro and _norm_name(f_boro) != target_boro_norm:
            continue

        raw_h_name = (props.get("neighbourhood") or props.get("neighborhood") or props.get("NTAName") or props.get("name") or "").strip()
        
        # 1차: 정확히 일치 또는 특수문자 제거 후 일치 확인
        std_name = csv_hood_exact.get(raw_h_name.lower()) or csv_hood_norm.get(_norm_name(raw_h_name))

        # 2차: 이름에 Park 등이 겹치지 않을 때만 폴리곤 내부 좌표(Point-in-Polygon)로 매칭
        if not std_name and "park" not in raw_h_name.lower() and "cemetery" not in raw_h_name.lower():
            for pt_lon, pt_lat, cand_name in csv_pts:
                if _point_in_geometry(pt_lon, pt_lat, geom):
                    std_name = cand_name
                    break

        if std_name:
            matched_features.append({
                "type": "Feature",
                "properties": {"std_hood_name": std_name, "raw_name": raw_h_name},
                "geometry": geom
            })

    return {"type": "FeatureCollection", "features": matched_features} if matched_features else None

def build_inverted_mask_geojson(features_list):
    """
    전달받은 Feature 리스트(폴리곤들)만 밝게 뚫어주고,
    나머지 모든 구역은 어둡게 덮는 반전(Inverted) 마스크 GeoJSON 생성
    """
    world_outer = [[-180.0, -85.0], [180.0, -85.0], [180.0, 85.0], [-180.0, 85.0], [-180.0, -85.0]]
    mask_holes = []
    for feat in features_list:
        geom = feat.get("geometry", {})
        g_type = geom.get("type")
        g_coords = geom.get("coordinates", [])
        if g_type == "Polygon" and g_coords:
            mask_holes.append(g_coords[0])
        elif g_type == "MultiPolygon":
            for poly in g_coords:
                if poly:
                    mask_holes.append(poly[0])
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [world_outer] + mask_holes},
            "properties": {}
        }]
    }

def get_neighborhood_center(hood_name, borough_name):
    """location.csv의 mean_lat, mean_lon에서 동네 중심 좌표를 즉시 조회"""
    row = loc_df[(loc_df['borough'] == borough_name) & (loc_df['neighbourhood'] == hood_name)]
    if not row.empty:
        return [float(row['mean_lat'].iloc[0]), float(row['mean_lon'].iloc[0])]
    return BOROUGH_CENTERS.get(borough_name, TIMES_SQUARE_COORDS)

@st.cache_data(show_spinner=False, ttl=3600, max_entries=100)
def get_address_from_coords(lat, lon, hood_name="", borough_name=""):
    # 캐시 적중률 향상 및 미세 떨림 방지를 위해 소수점 4자리로 통일
    lat, lon = round(lat, 4), round(lon, 4)
    try:
        geolocator = Nominatim(user_agent="hostmate_nyc_airbnb_app_v2", timeout=1.5)
        location = geolocator.reverse((lat, lon), language="en")
        if location and location.address:
            return location.address
    except Exception:
        pass
    return f"{hood_name}, {borough_name}, New York, NY ({lat:.4f}, {lon:.4f})"

def calculate_haversine_distance(lat1, lon1):
    """맨해튼 타임스퀘어 기준 하버사인 직선거리(km) 산출"""
    lat2, lon2 = TIMES_SQUARE_COORDS
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)

def build_features_dict():
    """세션 상태로부터 예측 모델 입력 피처 딕셔너리를 생성"""
    counts_by_cat = {}
    for grp_info in AMENITY_GROUPS.values():
        col_name = grp_info["col"]
        counts_by_cat[col_name] = sum(
            1 for k in grp_info["items"].keys() if st.session_state.selected_amenities.get(k, False)
        )

    dist_val = st.session_state.distance_to_ts
    if dist_val is None and st.session_state.pin_lat and st.session_state.pin_lon:
        dist_val = calculate_haversine_distance(st.session_state.pin_lat, st.session_state.pin_lon)

    accom = int(st.session_state.accommodates)
    bedrooms = float(st.session_state.bedrooms)
    beds = float(st.session_state.beds)
    baths = float(st.session_state.bathrooms)

    return {
        'neighbourhood_group_cleansed': st.session_state.selected_borough,
        'neighbourhood_cleansed': st.session_state.selected_hood,
        'latitude': st.session_state.pin_lat,
        'longitude': st.session_state.pin_lon,
        'dist_from_center(km)': dist_val,
        'room_type': st.session_state.room_type,
        'accommodates': accom,
        'bedrooms': bedrooms,
        'beds': beds,
        'bathrooms_cleansed': baths,
        'minimum_nights_cleansed': min(
            30, max(1, int(st.session_state.min_nights))
        ),
        'luxury_amenities_cnt': counts_by_cat.get('luxury_amenities_cnt', 0),
        'service_amenities_cnt': counts_by_cat.get('service_amenities_cnt', 0),
        'living_amenities_cnt': counts_by_cat.get('living_amenities_cnt', 0),
        'essential_amenities_cnt': counts_by_cat.get(
            'essential_amenities_cnt', 0
        ),
        'beds_per_room': beds / (bedrooms + 1.0),
        'beds_per_guest': beds / max(1, accom),
        'bathroom_ratio_cleansed': baths / max(1, accom),
    }

@st.cache_resource
def load_model():
    model = CatBoostRegressor()
    try:
        model.load_model('airbnb_price_model.cbm') # 학습된 모델 불러오기
        return model
    except Exception:
        return None

# [수정 후] predict_price_usd() 함수 상단
def predict_price_usd(model, feature_dict):
  """CatBoost 모델 추론 후 지수 역변환을 거쳐 달러($) 가격 반환 (오류 시 EDA 수식 폴백)"""
  ordered_cols = [
      'neighbourhood_group_cleansed',
      'neighbourhood_cleansed',
      'latitude',
      'longitude',
      'dist_from_center(km)',
      'room_type',
      'accommodates',
      'bedrooms',
      'beds',
      'bathrooms_cleansed',
      'minimum_nights_cleansed',
      'luxury_amenities_cnt',
      'service_amenities_cnt',
      'living_amenities_cnt',
      'essential_amenities_cnt',
      'beds_per_room',
      'beds_per_guest',
      'bathroom_ratio_cleansed',
  ]
  if model is not None:
    try:
      f_copy = feature_dict.copy()
      # 시뮬레이션에서 인원/침대/욕실 변경 시에도 파생변수 3종이 자동 동기화되도록 계산
      accom = max(1, int(f_copy.get('accommodates', 1)))
      bedrooms = float(f_copy.get('bedrooms', 1.0))
      beds = float(f_copy.get('beds', 1.0))
      baths = float(f_copy.get('bathrooms_cleansed', 1.0))

      f_copy['beds_per_room'] = beds / (bedrooms + 1.0)
      f_copy['beds_per_guest'] = beds / accom
      f_copy['bathroom_ratio_cleansed'] = baths / accom

      df_in = pd.DataFrame([{col: f_copy.get(col, 0) for col in ordered_cols}])
      log_pred = model.predict(df_in)
      val = float(np.expm1(log_pred)[0])
      if not math.isnan(val) and not math.isinf(val):
        return max(25.0, round(val, 2))
    except Exception as e:
      print(f'⚠️ [HostMate] CatBoost 추론 폴백 전환: {e}')

    # 모델 파일 미존재 또는 미학습 범주 에러 시 EDA 기반 정밀 추정치 반환
    boro_key = feature_dict.get('neighbourhood_group_cleansed')
    room_key = feature_dict.get('room_type')
    base = BOROUGH_ROOM_MEDIANS.get(boro_key, {}).get(room_key)
    if base is None or (isinstance(base, float) and math.isnan(base)):
        base = market_data.get('citywide_room_medians', {}).get(room_key, 120.0)
    dist_km = feature_dict.get('dist_from_center(km)') or 0.0
    dist_factor = max(0.65, 1.15 - 0.03 * float(dist_km))
    scale_factor = 1.0 + max(0, int(feature_dict.get('accommodates', 1)) - 2) * 0.12 + max(0, float(feature_dict.get('bedrooms', 1)) - 1) * 0.15
    amen_bonus = (
        (int(feature_dict.get('service_amenities_cnt', 0)) * 8.5)
        + (int(feature_dict.get('luxury_amenities_cnt', 0)) * 14.0)
        + (int(feature_dict.get('living_amenities_cnt', 0)) * 10.0)
    )
    stay_discount = 0.82 if int(feature_dict.get('minimum_nights_cleansed', 3)) >= 30 else 1.0
    return round((base * dist_factor * scale_factor + amen_bonus) * stay_discount, 2)

nyc_hood_geojson = load_real_neighborhood_geojson()

# -----------------------------------
# 단일 Draft Token 기반 상태 저장소
# -----------------------------------

@st.cache_resource
def get_draft_store():
    """서버 인메모리에 세션 상태를 보관하는 Draft 저장소"""
    return {}

draft_store = get_draft_store()

# 기본 세션 값 정의 (누락 없이 전 변수 정의)
defaults = {
    'draft_token': None,
    'page': 'landing',
    'selected_landing_boro': 'Manhattan',
    'selected_borough': None,
    'selected_hood': "선택해주세요",
    'pin_lat': None,
    'pin_lon': None,
    'pin_address': None,
    'distance_to_ts': None,
    'final_features': None,
    'input_step': 0,
    'boro_zoom': None,   
    'boro_center': None,
    'init_boro_zoom': None,
    'init_boro_center': None,
    'detail_zoom': 15,      
    'detail_center': None,
    'init_detail_zoom': None, 
    'init_detail_center': None,
    'pin_reset_cnt': 0,
    'accommodates': 1,
    'bedrooms': 1,
    'beds': 1,
    'bathrooms': 1.0,
    'selected_amenities': {},
    'stay_category': "단기 숙박 (30일 미만)",
    'min_nights': 3,
    'room_type': "Private room",
    'show_acc_warning': False,
    'acc_warn_nonce': 0,
    'show_room_warning': False,
    'room_warn_nonce': 0,
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v.copy() if isinstance(v, dict) else v

# 최초 접속 및 F5 새로고침 시에만 서버 저장소에서 복원
if 'draft_restored' not in st.session_state:
    url_token = st.query_params.get("s")
    if url_token and url_token in draft_store:
        saved_state = draft_store[url_token]
        for k, v in saved_state.items():
            st.session_state[k] = v
        st.session_state['draft_token'] = url_token
        st.session_state['step2_input_acc'] = st.session_state.get('accommodates', 1)
        st.session_state['step2_input_bed'] = st.session_state.get('bedrooms', 1)
        st.session_state['step2_input_bds'] = st.session_state.get('beds', 1)
        st.session_state['step2_input_bath'] = st.session_state.get('bathrooms', 1.0)

        # 뷰포트 초기값 동기화 (F5 새로고침 시 저장된 최신 줌/중심점을 지도 초기값에 1회 반영)
        if st.session_state.init_boro_zoom is None and st.session_state.boro_zoom is not None:
            st.session_state.init_boro_zoom = st.session_state.boro_zoom
        if st.session_state.init_boro_center is None and st.session_state.boro_center is not None:
            st.session_state.init_boro_center = st.session_state.boro_center
        if st.session_state.init_detail_zoom is None:
            st.session_state.init_detail_zoom = st.session_state.detail_zoom if st.session_state.detail_zoom is not None else 15
        if st.session_state.init_detail_center is None and st.session_state.detail_center is not None:
            st.session_state.init_detail_center = st.session_state.detail_center

    else:
        if not st.session_state.get('draft_token'):
            st.session_state['draft_token'] = uuid.uuid4().hex[:6]
    st.session_state['draft_restored'] = True

def sync_url_params():
    """
    URL에는 오직 단일 토큰(?s=xxxxxx) 딱 1개만 유지하고,
    init_* 변수는 제외하여 새로고침(F5) 시 항상 최신 줌/위치가 복원되도록 보장
    """
    token = st.session_state.get('draft_token')
    if not token:
        token = uuid.uuid4().hex[:6]
        st.session_state['draft_token'] = token

    state_to_save = {
        'page': st.session_state.page,
        'selected_landing_boro': st.session_state.get('selected_landing_boro', 'Manhattan'),
        'input_step': st.session_state.input_step,
        'selected_borough': st.session_state.selected_borough,
        'selected_hood': st.session_state.selected_hood,
        'pin_lat': st.session_state.pin_lat,
        'pin_lon': st.session_state.pin_lon,
        'pin_address': st.session_state.pin_address,
        'distance_to_ts': st.session_state.distance_to_ts,
        # 1단계 자치구 지도 최신 뷰포트만 저장 (init_* 저장 제외)
        'boro_zoom': st.session_state.get('boro_zoom'),
        'boro_center': st.session_state.get('boro_center'),
        # 2단계 세부 동네 지도 최신 뷰포트만 저장 (init_* 저장 제외)
        'detail_zoom': st.session_state.get('detail_zoom', 15),
        'detail_center': st.session_state.get('detail_center'),
        # 스펙 정보
        'accommodates': st.session_state.accommodates,
        'bedrooms': st.session_state.bedrooms,
        'beds': st.session_state.beds,
        'bathrooms': st.session_state.bathrooms,
        'selected_amenities': st.session_state.selected_amenities,
        'stay_category': st.session_state.stay_category,
        'min_nights': st.session_state.min_nights,
        'room_type': st.session_state.room_type,
    }
    draft_store[token] = state_to_save

    if dict(st.query_params) != {"s": token}:
        st.query_params.clear()
        st.query_params["s"] = token

# ---------------------------------
# 상단 프로그래스 바 렌더링 함수
# ---------------------------------

def render_stepper(current_stage):
    steps = [
        (1, "위치 및 동네 선택"),
        (2, "숙소 정보 입력"),
        (3, "입력 정보 확인"),
        (4, "가격 예측 & 컨설팅")
    ]
    html = '<div class="stepper-wrap">'
    for idx, label in steps:
        if idx < current_stage:
            cls, icon = "done", "✓"
        elif idx == current_stage:
            cls, icon = "active", str(idx)
        else:
            cls, icon = "", str(idx)
        html += f'<div class="step-item {cls}"><span class="step-badge">{icon}</span><span>{label}</span></div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# --------------------------------------------------------------------------
# 좌측 사이드바 요약 패널
# --------------------------------------------------------------------------
if st.session_state.page in ['borough_map', 'detail_step', 'prediction_page']:
    with st.sidebar:
        st.markdown("# 🏠 HostMate")
        st.write("---")

        b_disp = st.session_state.selected_borough or "미선택"
        h_disp = st.session_state.selected_hood if st.session_state.selected_hood != "선택해주세요" else "미선택"

        st.markdown('<div class="sidebar-label">📍 숙소 위치</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sidebar-box">자치구 : {b_disp}<br>세부 동네 : {h_disp}<br></div>', unsafe_allow_html=True)

        if st.session_state.selected_hood != "선택해주세요":
            addr_disp = st.session_state.pin_address if st.session_state.pin_address else "미선택"
            st.markdown('<div class="sidebar-label">🗺️ 상세 주소</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="sidebar-box" style="font-size:13px; line-height:1.45;">{addr_disp}</div>', unsafe_allow_html=True)

        # Step 2(스펙 입력) 이상으로 넘어왔을 때부터 '운영 정책 및 룸타입' 표시
        show_policy_in_sidebar = (
            st.session_state.page == 'detail_step'
            and st.session_state.input_step >= 1
        ) or (st.session_state.page == 'prediction_page')
        if show_policy_in_sidebar:
          st.markdown(
              '<div class="sidebar-label">💡 호스팅 정책 및 룸타입</div>',
              unsafe_allow_html=True,
          )
          stay_txt = (
              f"단기 ({st.session_state.min_nights}박 이상)"
              if "단기" in st.session_state.stay_category
              else "장기 (30박 이상)"
          )

          # 룸타입 한글 변환
          sidebar_room_labels = {
              "Entire home/apt": "집 전체",
              "Private room": "개인실",
              "Shared room": "다인실",
              "Hotel room": "호텔 / 부티크 숙소",
          }
          r_kr_name = sidebar_room_labels.get(
              st.session_state.room_type, st.session_state.room_type
          )

          st.markdown(
              f'<div class="sidebar-box">{r_kr_name}<br><span'
              f' style="color:#38EF7D; font-size:13px;">{stay_txt}</span></div>',
              unsafe_allow_html=True,
          )

        # Step 3(최종 확인) 이상으로 넘어왔을 때부터 '수용 규모 및 공간 구성' & '보유 편의시설' 표시
        show_spec_in_sidebar = (st.session_state.page == 'detail_step' and st.session_state.input_step >= 2) or (st.session_state.page == 'prediction_page')
        if show_spec_in_sidebar:
            st.markdown('<div class="sidebar-label">🏢 수용 규모 및 공간 구성</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="sidebar-box">인원 {int(st.session_state.accommodates)}명 | 침실 {int(st.session_state.bedrooms)}개<br>'
                f'침대 {int(st.session_state.beds)}개 | 욕실 {float(st.session_state.bathrooms)}개</div>',
                unsafe_allow_html=True
            )

            st.markdown('<div class="sidebar-label">✨ 보유 편의시설</div>', unsafe_allow_html=True)
            amen_html_parts = []
            for idx_g, (grp_title, grp_info) in enumerate(AMENITY_GROUPS.items()):
                selected_labels = [
                    label for k_eng, label in grp_info["items"].items()
                    if st.session_state.selected_amenities.get(k_eng, False)
                ]
                margin_b = "0px" if idx_g == len(AMENITY_GROUPS) - 1 else "12px"
                # 카테고리 헤더 바로 아래에 연한 구분선(border-bottom) 추가
                header_html = (
                    f'<div style="font-size:13px; font-weight:800; color:#FFFFFF; '
                    f'padding-bottom:4px; margin-bottom:5px; '
                    f'border-bottom:1px solid rgba(255, 255, 255, 0.12);">{grp_title}</div>'
                )
                if selected_labels:
                    items_str = ", ".join(selected_labels)
                    amen_html_parts.append(
                        f'<div style="margin-bottom:{margin_b};">'
                        f'{header_html}'
                        f'<div style="font-size:12.5px; color:#38EF7D; font-weight:600; line-height:1.4;">{items_str}</div>'
                        f'</div>'
                    )
                else:
                    amen_html_parts.append(
                        f'<div style="margin-bottom:{margin_b};">'
                        f'{header_html}'
                        f'<div style="font-size:12px; color:#777A8B; font-weight:500;">선택 없음</div>'
                        f'</div>'
                    )
            st.markdown(f'<div class="sidebar-box">{"".join(amen_html_parts)}</div>', unsafe_allow_html=True)

        st.write("---")
        if st.button("🔄 처음으로 돌아가기", width='stretch'):
            curr_token = st.session_state.get('draft_token') or st.query_params.get("s")
            if curr_token and curr_token in draft_store:
                del draft_store[curr_token]
            
            st.query_params.clear()
            
            # 모든 세션 및 위젯 키 완전 파기
            for k in list(st.session_state.keys()):
                del st.session_state[k]
                
            # 딕셔너리 깊은 복사로 초기 기본값 재설정
            for k, v in defaults.items():
                st.session_state[k] = v.copy() if isinstance(v, dict) else v
            st.session_state.page = 'landing'
            st.rerun()

# =========================
# [PAGE 1] 랜딩 페이지
# =========================
if st.session_state.page == 'landing':

    st.markdown("""
    <div class="top-brand-bar">
        <div class="brand-logo"><span class="brand-dot"></span>HostMate NYC</div>
        <div style="display:flex; gap:10px;">
            <span class="status-pill">🗽 뉴욕 단기 임대 규정(Local Law 18) 반영</span>
            <span class="status-pill">📊 뉴욕 5대 자치구 실거래 시세 기반</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    hero_l, hero_r = st.columns([5.8, 4.2], gap="large")

    with hero_l:
        st.markdown("""
        <div class="saas-hero-left">
            <div class="eyebrow-tag">✨ NYC 에어비앤비 호스트 전용 솔루션</div>
            <div class="saas-title">
                내 <span style="color: #FF385C;">뉴욕 숙소</span>,<br>
                <span class="highlight">1박에 얼마를 받아야</span> 가장 유리할까요?
            </div>
            <p class="saas-desc">
                감으로 설정한 요금은 공실이나 수익 손실로 이어집니다.<br>
                주변 숙소들의 실제 예약 시세와 타임스퀘어 접근성, 그리고 뉴욕시 임대 규정까지 고려해
                <b>내 숙소의 적정 요금과 월 예상 수익</b>을 계산해 드립니다.
            </p>
            <div class="check-list">
                <span>✓ 동네별 실거래 시세 비교</span>
                <span>✓ 단기 vs 장기 숙박 수익 비교</span>
                <span>✓ 요금을 올릴 수 있는 인기 옵션 추천</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with hero_r:
        st.markdown("""
        <div class="bento-feature-wrap">
            <div class="bento-feature-item">
                <span class="bento-feature-step">01 · LOCATION & MARKET</span>
                <div class="bento-feature-title">클릭 몇 번으로 끝나는 내 숙소 요금 분석</div>
                <p class="bento-feature-text">복잡한 주소나 서류 입력 없이 위치와 기본 조건만 가볍게 클릭하세요. 주변 실거래 시세와 내 숙소의 요금 적정가를 즉시 완성합니다.</p>
            </div>
            <div class="bento-feature-item">
                <span class="bento-feature-step">02 · SHORT VS LONG TERM</span>
                <div class="bento-feature-title">단기 숙박 vs 한 달 살기 수익 비교</div>
                <p class="bento-feature-text">뉴욕시 단기 임대 규정(Local Law 18)에 맞춰 '개인실 단기 운영'과 '집 전체 30일 이상 장기 임대' 중 어느 쪽이 월 수익에 유리한지 비교합니다.</p>
            </div>
            <div class="bento-feature-item">
                <span class="bento-feature-step">03 · AMENITY UPGRADE</span>
                <div class="bento-feature-title">숙박료를 높이는 맞춤 옵션 추천</div>
                <p class="bento-feature-text">큰 공사 없이도 커피머신, 셀프 체크인, 세탁기 등 게스트 선호 옵션을 추가했을 때 상승하는 예상 수익을 제안합니다.</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("""
    <div class="saas-section-header">
        <div class="saas-section-title">내 숙소 요금 계산 시작하기</div>
        <p class="saas-section-desc">
            우측에서 자치구를 선택하고 시작하여 예시와 같은 <b>맞춤 분석 리포트</b>를 받아 보세요.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col_preview, col_action = st.columns([4.8, 5.2], gap="large")

    with col_preview:
        st.markdown("""
        <div class="saas-preview-card">
            <div class="preview-top">
                <div>
                    <span class="saas-section-badge" style="margin-bottom:4px;">📊 리포트 예시</span>
                    <div style="font-size:16.5px; color:#FFFFFF; font-weight:800; margin-top:4px;">Brooklyn · Williamsburg 개인실</div>
                </div>
                <span class="live-badge" title="해당 지역 월평균 가동률 60% 이상 인기 상권">🔥 예약 수요 높음</span>
            </div>
            <div class="preview-main-box">
                <div style="font-size:12.5px; color:#A0A4B8; margin-bottom:4px;">AI 추천 1박 적정 요금</div>
                <div style="display:flex; align-items:center; justify-content:space-between;">
                    <span style="font-size:34px; font-weight:800; color:#FFFFFF;">$ 118.00 <span style="font-size:14px; font-weight:500; color:#888;">/ 박</span></span>
                    <!-- [수정 4] 눈에 확 들어오는 트렌디한 네온 알약 배지 -->
                    <span class="premium-badge">동네 시세 대비 +18% ▲</span>
                </div>
                <div style="font-size:12px; color:#8E92A8; margin-top:6px;">권장 요금 설정 범위: $104 ~ $132 / 박</div>
            </div>
            <div class="preview-row">
                <span>📅 단기 운영 시 월 예상 매출</span>
                <b style="color:#FFFFFF;">$ 1,950 / 월</b>
            </div>
            <div class="preview-row">
                <span>🏠 장기 전환 시 월 예상 매출</span>
                <b style="color:#38EF7D;">$ 4,350 / 월</b>
            </div>
            <div class="preview-row" style="border-bottom:none; padding-bottom:0;">
                <span>✨ 커피머신·셀프체크인 추가 효과</span>
                <b style="color:#FF6B81;">+ $16 / 박 상승 ▲</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_action:
        with st.container(border=True, key="landing_action_card"):
            st.markdown("""
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
                    <span style="font-size:20px; font-weight:800; color:#FFFFFF;">📍 숙소가 위치한 자치구 선택</span>
                    <span style="font-size:12px; color:#FF5A79; font-weight:700; background:rgba(255,90,121,0.12); padding:3px 8px; border-radius:6px;">실거래 시세 연동</span>
                </div>
            """, unsafe_allow_html=True)

            # 시스템 내부 기준 키는 항상 영문 유지
            if 'selected_landing_boro' not in st.session_state or st.session_state.selected_landing_boro not in ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]:
                st.session_state.selected_landing_boro = "Manhattan"

            # 영문 키와 화면 표기용 한글 라벨 1:1 매핑
            boro_options = [
                ("Manhattan", "맨해튼"),
                ("Brooklyn", "브루클린"),
                ("Queens", "퀸즈"),
                ("Bronx", "브롱크스"),
                ("Staten Island", "스태튼")
            ]

            b_cols = st.columns(5)
            for i, (b_eng, b_kr) in enumerate(boro_options):
                with b_cols[i]:
                    is_active = (st.session_state.selected_landing_boro == b_eng)
                    btn_type = "primary" if is_active else "secondary"

                    if st.button(b_kr, key=f"btn_landing_{b_eng}", type=btn_type, width='stretch'):
                        st.session_state.selected_landing_boro = b_eng
                        sync_url_params()
                        st.rerun()

            # 선택된 영문 키를 기준으로 시세 데이터 정상 조회
            curr_boro_eng = st.session_state.selected_landing_boro
            curr_boro_kr = dict(boro_options).get(curr_boro_eng, "맨해튼")

            b_med = BOROUGH_ROOM_MEDIANS.get(curr_boro_eng, {})
            entire_val = b_med.get('Entire home/apt', 160.0)
            priv_val = b_med.get('Private room', 85.0)
            month_val = entire_val * 30

            boro_insights = {
                "Manhattan": {
                    "target": "비즈니스 출장객, 한 달 살기 여행객, 유학생",
                    "strategy": "집 전체 30일 이상 장기 임대 운영 적극 권장"
                },
                "Brooklyn": {
                    "target": "2030 감성 여행자, 단기 관광객 (예약 수요 1위)",
                    "strategy": "호스트 거주형 개인실 단기 감성 숙박 권장"
                },
                "Queens": {
                    "target": "공항 환승객, 가성비 여행객, 맨해튼 통근족",
                    "strategy": "공항 연계 단기 운영 및 통근형 장기 임대 병행"
                },
                "Bronx": {
                    "target": "MLB 야구 관람객, 가족 및 소그룹 방문객",
                    "strategy": "넓은 공간 대비 합리적 요금 및 가족 타겟팅"
                },
                "Staten Island": {
                    "target": "렌터카 이용 가족 여행객, 휴양 목적 장기 체류객",
                    "strategy": "단독 주택 규모 및 무료 주차 편의성 강조"
                }
            }
            insight = boro_insights.get(curr_boro_eng, boro_insights["Manhattan"])

            st.markdown(f"""
                <div class="stat-pill-grid">
                    <div class="stat-pill">
                        <div class="stat-pill-label">집 전체 시세</div>
                        <div class="stat-pill-val" style="color:#FF5A79;">${entire_val:.0f} <span style="font-size:12px; color:#888;">/박</span></div>
                    </div>
                    <div class="stat-pill">
                        <div class="stat-pill-label">개인실 시세</div>
                        <div class="stat-pill-val" style="color:#38EF7D;">${priv_val:.0f} <span style="font-size:12px; color:#888;">/박</span></div>
                    </div>
                    <div class="stat-pill">
                        <div class="stat-pill-label">장기(30일+) 임대 시세</div>
                        <div class="stat-pill-val" style="color:#60A5FA;">${month_val:,.0f} <span style="font-size:12px; color:#888;">/월</span></div>
                    </div>
                </div>
                <div class="action-info-row">
                    <span>👥 주요 선호 게스트 층</span>
                    <b style="color:#38EF7D;">{insight['target']}</b>
                </div>
                <div class="action-info-row">
                    <span>💡 권장 호스팅 정책</span>
                    <b style="color:#FF6B81;">{insight['strategy']}</b>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
            _, pred_btn_col, _ = st.columns([0.8, 3.4, 0.8])
            with pred_btn_col:
                if st.button(f"✨ {curr_boro_kr}의 내 숙소 가격 예측하기", key="btn_landing_predict", type="primary", width='stretch'):
                    st.session_state.selected_borough = curr_boro_eng
                    st.session_state.selected_hood = "선택해주세요" 
                    st.session_state.pin_lat = None                  
                    st.session_state.pin_lon = None
                    st.session_state.pin_address = None
                    st.session_state.distance_to_ts = None
                    st.session_state.boro_zoom = None
                    st.session_state.boro_center = None
                    st.session_state.init_boro_zoom = None     
                    st.session_state.init_boro_center = None   
                    st.session_state.detail_zoom = 15
                    st.session_state.detail_center = None
                    st.session_state.init_detail_zoom = 15     
                    st.session_state.init_detail_center = None
                    st.session_state.input_step = 0
                    st.session_state.stay_category = "단기 숙박 (30일 미만)"
                    st.session_state.min_nights = 3
                    st.session_state.room_type = "Private room"
                    st.session_state.accommodates = 1
                    st.session_state.bedrooms = 1
                    st.session_state.beds = 1
                    st.session_state.bathrooms = 1.0
                    st.session_state.step2_input_acc = 1
                    st.session_state.step2_input_bed = 1
                    st.session_state.step2_input_bds = 1
                    st.session_state.step2_input_bath = 1.0
                    st.session_state.selected_amenities = {}
                    st.session_state.show_acc_warning = False
                    st.session_state.page = 'borough_map'
                    sync_url_params()
                    st.rerun()

# =============================================
# [PAGE 2] 위치 및 세부 동네 선택 페이지
# =============================================
elif st.session_state.page == 'borough_map':
    render_stepper(1)

    # 1단계(자치구) 및 2단계(세부 동네) 지도 고정 높이(px)
    STAGE1_MAP_HEIGHT = 950  
    STAGE2_MAP_HEIGHT = 950

    borough_data = {
        "Manhattan": {"color": "#60A5FA", "kr": "맨해튼", "center": [40.7831, -73.9650], "zoom": 12},
        "Brooklyn": {"color": "#F472B6", "kr": "브루클린", "center": [40.6500, -73.9500], "zoom": 12},
        "Queens": {"color": "#34D399", "kr": "퀸즈", "center": [40.7282, -73.7949], "zoom": 11},
        "Bronx": {"color": "#A78BFA", "kr": "브롱크스", "center": [40.8500, -73.8648], "zoom": 13},
        "Staten Island": {"color": "#FBBF24", "kr": "스태튼 아일랜드", "center": [40.5795, -74.1502], "zoom": 12}
    }

    if not st.session_state.selected_borough or st.session_state.selected_borough not in borough_data:
        st.session_state.selected_borough = "Manhattan"
    b_name = st.session_state.selected_borough
    is_hood_selected = (st.session_state.selected_hood != "선택해주세요")

    if not is_hood_selected:
        st.markdown("##### 🗺️ 숙소가 위치한 세부 동네 선택")
    else:
        st.markdown("##### 🗺️ 숙소가 위치한 상세 주소 선택")

    # 상단 자치구 퀵 선택 버튼 바
    b_cols = st.columns(5)
    for idx, (b_eng, b_meta) in enumerate(borough_data.items()):
        with b_cols[idx]:
            is_sel = (st.session_state.selected_borough == b_eng)
            btn_type = "primary" if is_sel else "secondary"
            if st.button(b_meta['kr'], key=f"quick_boro_{b_eng}", type=btn_type, width='stretch'):
                st.session_state.selected_borough = b_eng
                st.session_state.selected_hood = "선택해주세요"
                st.session_state.pin_lat = None
                st.session_state.pin_lon = None
                st.session_state.pin_address = None
                st.session_state.distance_to_ts = None
                st.session_state.boro_zoom = None
                st.session_state.boro_center = None
                st.session_state.init_boro_zoom = None     
                st.session_state.init_boro_center = None   
                st.session_state.detail_zoom = 15
                st.session_state.detail_center = None
                st.session_state.init_detail_zoom = 15     
                st.session_state.init_detail_center = None 
                sync_url_params()
                st.rerun()

    st.write("")
    hoods_in_boro = loc_df[loc_df['borough'] == b_name].dropna(subset=['neighbourhood', 'mean_lat', 'mean_lon']) if b_name else pd.DataFrame()
    hood_polygons = get_real_hood_geojson_for_borough(b_name, hoods_in_boro, nyc_hood_geojson)

    borough_details = {
        "Manhattan": {
            "location": "뉴욕의 심장부 (금융·상업·관광 중심지)",
            "features": [
                "타임스퀘어, 센트럴파크 등 핵심 랜드마크 밀집",
                "집 전체 평균 시세 $182/박으로 뉴욕 최고 수익 권역",
                "단기 임대 규정 이후 30일 이상 장기·출장 수요 집중"
            ],
            "target": "비즈니스 출장객, 한 달 살기, 장기 유학생",
            "strategy": "집 전체 장기 임대 운영 권장"
        },
        "Brooklyn": {
            "location": "맨해튼 동쪽 (브루클린 브리지 인접)",
            "features": [
                "트렌디한 감성의 붉은 벽돌 주택과 로컬 카페·맛집 밀집",
                "맨해튼 접근성이 뛰어나 단기 여행객 유입 급증",
                "개인실·다인실의 단기 예약 수익성이 매우 높음"
            ],
            "target": "2030 젊은 여행객, 감성 여행자, 단기 투숙객",
            "strategy": "개인실, 다인실 단기 운영 권장"
        },
        "Queens": {
            "location": "브루클린 북쪽, 맨해튼 동쪽",
            "features": [
                "JFK 공항과 라과디아 공항이 모두 위치한 교통 요충지",
                "다양한 글로벌 미식 상권과 합리적인 숙박 시세 형성",
                "강변은 맨해튼 통근이 편리해 장기 수요 풍부"
            ],
            "target": "공항 환승객, 실속형 여행객, 장기 유학생",
            "strategy": "단기 개인실 또는 집 전체 장기 임대 운영 권장"
        },
        "Bronx": {
            "location": "맨해튼 북쪽",
            "features": [
                "양키 스타디움, 브롱크스 동물원 등 방문 목적지 보유",
                "시세는 합리적이나 Riverdale 등 고급 주택가 존재",
                "가성비를 중시하는 실속형 게스트 수요 꾸준"
            ],
            "target": "MLB 야구 팬, 가성비 여행객, 가족 단위 방문객",
            "strategy": "일반 주거지 vs 고급 주택가에 맞춘 요금 설정"
        },
        "Staten Island": {
            "location": "맨해튼 남단 (페리 이동 권역)",
            "features": [
                "도심보다 한적한 교외 주택가 분위기 및 넓은 공간",
                "무료 페리로 자유의 여신상을 조망하며 이동 가능",
                "주차가 용이하고 가족 단위 단독 공간 대여에 유리"
            ],
            "target": "렌터카 이용 가족 여행객, 휴양 목적 체류객",
            "strategy": "다인 수용 규모 및 주차·생활 편의시설 강조 전략"
        }
    }

    info = borough_details.get(b_name, borough_details["Manhattan"])
    feat_html = "".join([f"<li style='margin-bottom:6px;'>{f}</li>" for f in info["features"]])

    # ---------------------------------------------------
    # [1단계] 자치구 내 세부 동네 바운더리 구획 지도
    # ---------------------------------------------------
    if not is_hood_selected:
        b_meta = borough_data.get(b_name, {"center": [40.7831, -73.9650], "zoom": 12, "kr": b_name})
        base_center = b_meta.get("center", [40.7831, -73.9650])
        default_adjusted_center = [base_center[0], base_center[1] + 0.012]

        center_lv1 = st.session_state.init_boro_center if st.session_state.get("init_boro_center") else default_adjusted_center
        zoom_lv1 = st.session_state.init_boro_zoom if st.session_state.get("init_boro_zoom") else b_meta.get("zoom", 12)

        m1 = folium.Map(
            location=center_lv1,
            zoom_start=zoom_lv1,
            tiles="OpenStreetMap"
        )

        if hood_polygons:
            folium.GeoJson(
                hood_polygons,
                style_function=lambda f: {
                    'fillColor': '#FF385C',
                    'color': '#FFFFFF',
                    'weight': 2.0,
                    'opacity': 0.9,
                    'fillOpacity': 0.08
                },
                highlight_function=lambda f: {
                    'fillColor': '#38EF7D',
                    'color': '#38EF7D',
                    'weight': 3.5,
                    'opacity': 1.0,
                    'fillOpacity': 0.38
                }
            ).add_to(m1)

            folium.map.CustomPane("mask_pane", z_index=450).add_to(m1)
            inverted_geojson = build_inverted_mask_geojson(hood_polygons.get("features", []))
            folium.GeoJson(
                inverted_geojson,
                pane="mask_pane",
                interactive=False,
                style_function=lambda f: {
                    'fillColor': '#11131A',
                    'fillOpacity': 0.82,
                    'color': '#FFFFFF',
                    'weight': 1.5,
                    'opacity': 0.6
                }
            ).add_to(m1)

        if not hoods_in_boro.empty:
            for _, h_row in hoods_in_boro.iterrows():
                h_name = h_row['neighbourhood']
                h_lat, h_lon = float(h_row['mean_lat']), float(h_row['mean_lon'])
                safe_name = h_name.replace('"', '&quot;')

                folium.Marker(
                    [h_lat, h_lon],
                    icon=folium.DivIcon(
                        icon_size=(130, 22),
                        icon_anchor=(65, 11),
                        html=f'''<div class="hood-label-txt" data-hood="{safe_name}">{h_name}</div>'''
                    )
                ).add_to(m1)

        # 동네 라벨 호버 전용 스크립트 (충돌하던 100vh 강제 코드 완전 제거)
        hover_stage1_html = '''
        <style>
            .hood-label-txt {
                font-size: 11.5px;
                font-weight: 800;
                color: #FFFFFF;
                text-shadow: -1.5px -1.5px 0 #000, 1.5px -1.5px 0 #000, -1.5px 1.5px 0 #000, 1.5px 1.5px 0 #000, 0 0 6px rgba(0,0,0,0.95);
                text-align: center;
                white-space: nowrap;
                pointer-events: none;
                transition: all 0.15s ease;
                letter-spacing: -0.2px;
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            }
            .hood-label-txt.active-hood-txt {
                color: #38EF7D !important;
                transform: scale(1.25) !important;
                text-shadow: -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000, 0 0 14px rgba(56,239,125,0.9) !important;
            }
        </style>
        <script>
            setTimeout(function() {
                for (var k in window) {
                    if (k.startsWith("map_") && window[k] && window[k].eachLayer) {
                        var mapObj = window[k];
                        mapObj.eachLayer(function(layer) {
                            if (layer.feature && layer.feature.properties && layer.feature.properties.std_hood_name) {
                                var hName = layer.feature.properties.std_hood_name;
                                layer.on("mouseover", function() {
                                    var els = document.querySelectorAll('.hood-label-txt');
                                    els.forEach(function(el) {
                                        if (el.getAttribute('data-hood') === hName) el.classList.add('active-hood-txt');
                                    });
                                });
                                layer.on("mouseout", function() {
                                    var els = document.querySelectorAll('.hood-label-txt');
                                    els.forEach(function(el) {
                                        if (el.getAttribute('data-hood') === hName) el.classList.remove('active-hood-txt');
                                    });
                                });
                            }
                        });
                        break;
                    }
                }
            }, 250);
        </script>
        '''
        m1.get_root().html.add_child(folium.Element(hover_stage1_html))

        floating_guide_center_html = '''
        <div style="
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 9999;
            background: rgba(20, 22, 32, 0.90);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 999px;
            padding: 9px 26px;
            color: #FFFFFF;
            font-size: 14px;
            font-weight: 700;
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.6);
            display: flex;
            align-items: center;
            gap: 8px;
            pointer-events: none;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            white-space: nowrap;
        ">
            <span style="font-size:18px;">💡</span> 지도에서 숙소가 위치한 세부 동네 구역을 클릭하세요.
        </div>
        '''
        m1.get_root().html.add_child(folium.Element(floating_guide_center_html))

        floating_card_html = f'''
        <div id="floating-briefing" style="
            position: fixed;
            top: 20px;
            right: 25px;
            width: 350px;
            max-width: 85%;
            z-index: 9999;
            background: rgba(20, 22, 32, 0.90);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 18px;
            box-shadow: 0 16px 36px rgba(0, 0, 0, 0.6);
            color: #FFFFFF;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            pointer-events: auto;
        ">
            <div style="padding:14px 18px; border-bottom:1px solid rgba(255,255,255,0.12); display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:15px; font-weight:800; color:#FFFFFF;">📊 {borough_data[b_name]['kr']} 특징 및 추천</span>
            </div>
            <div style="padding:16px 18px; font-size:13px; max-height:360px; overflow-y:auto;">
                <div style="margin-bottom:12px;">
                    <span style="background:rgba(255,255,255,0.08); padding:2px 6px; border-radius:4px; font-size:11.5px; font-weight:700; color:#BBB;">📍 입지 특성</span>
                    <ul style="color:#D0D3E2; font-size:12.5px; line-height:1.5; margin-top:4px; padding-left:16px;">
                        <li style="margin-bottom:6px;">{info['location']}</li>
                    </ul>
                </div>
                <div style="margin-bottom:12px;">
                    <span style="background:rgba(255,255,255,0.08); padding:2px 6px; border-radius:4px; font-size:11.5px; font-weight:700; color:#BBB;">📈 지역 숙박 트렌드</span>
                    <ul style="color:#D0D3E2; font-size:12.5px; line-height:1.5; margin-top:4px; padding-left:16px;">{feat_html}</ul>
                </div>
                <div>
                    <span style="background:rgba(255,56,92,0.2); padding:2px 6px; border-radius:4px; font-size:11.5px; font-weight:700; color:#FF5A79;">🎯 주요 게스트 & 추천 운영</span>
                    <ul style="color:#D0D3E2; font-size:12.5px; line-height:1.5; margin-top:4px; padding-left:16px;">
                        <li style="margin-bottom:6px;">게스트 : {info['target']}</li>
                        <li style="margin-bottom:2px;">추천 : <b style="color:#38EF7D;">{info['strategy']}</b></li>
                    </ul>
                </div>
            </div>
        </div>
        '''
        m1.get_root().html.add_child(folium.Element(floating_card_html))

        map_data1 = st_folium(
            m1,
            height=STAGE1_MAP_HEIGHT,
            width='stretch',
            key=f"map_stage1_fullscreen_{b_name}",
            returned_objects=["last_active_drawing", "zoom", "center"]
        )

        if map_data1:
            m1_changed = False
            if map_data1.get("zoom") is not None:
                new_z1 = int(map_data1["zoom"])
                if new_z1 != st.session_state.get("boro_zoom"):
                    st.session_state.boro_zoom = new_z1
                    m1_changed = True
            if map_data1.get("center"):
                c1 = map_data1["center"]
                new_c1 = [round(c1["lat"], 5), round(c1["lng"], 5)]
                if new_c1 != st.session_state.get("boro_center"):
                    st.session_state.boro_center = new_c1
                    m1_changed = True
            if m1_changed:
                sync_url_params()

        if map_data1 and map_data1.get("last_active_drawing"):
            props = map_data1["last_active_drawing"].get("properties", {})
            clicked_hood = props.get("std_hood_name")
            if clicked_hood and clicked_hood in hoods_in_boro['neighbourhood'].values:
                if map_data1.get("zoom") is not None:
                    st.session_state.boro_zoom = int(map_data1["zoom"])
                    st.session_state.init_boro_zoom = int(map_data1["zoom"])
                if map_data1.get("center"):
                    c1 = map_data1["center"]
                    st.session_state.boro_center = [round(c1["lat"], 5), round(c1["lng"], 5)]
                    st.session_state.init_boro_center = st.session_state.boro_center

                st.session_state.selected_hood = clicked_hood
                st.session_state.pin_lat = None
                st.session_state.pin_lon = None
                st.session_state.distance_to_ts = None
                st.session_state.pin_address = None
                st.session_state.detail_center = None
                st.session_state.init_detail_center = None
                st.session_state.detail_zoom = 15
                st.session_state.init_detail_zoom = 15
                sync_url_params()
                st.rerun()

    # ----------------------------------------------------------------------
    # [2단계] 선택된 세부 동네의 상세 줌인 지도
    # ----------------------------------------------------------------------
    else:
        h_name = st.session_state.selected_hood

        if st.session_state.get("init_detail_center"):
            center_loc = st.session_state.init_detail_center
        elif st.session_state.pin_lat is not None and st.session_state.pin_lon is not None:
            center_loc = [st.session_state.pin_lat, st.session_state.pin_lon]
        else:
            center_loc = get_neighborhood_center(h_name, b_name)

        zoom_lv2 = st.session_state.init_detail_zoom if st.session_state.get("init_detail_zoom") else 15

        m2 = folium.Map(
            location=center_loc,
            zoom_start=zoom_lv2,
            tiles="OpenStreetMap"
        )

        if hood_polygons:
            selected_hood_feats = [
                feat for feat in hood_polygons.get("features", [])
                if feat.get("properties", {}).get("std_hood_name") == h_name
            ]
            if selected_hood_feats:
                folium.map.CustomPane("mask_pane_stage2", z_index=450).add_to(m2)
                inv_mask_stage2 = build_inverted_mask_geojson(selected_hood_feats)
                folium.GeoJson(
                    inv_mask_stage2,
                    pane="mask_pane_stage2",
                    interactive=False,
                    style_function=lambda f: {
                        'fillColor': '#11131A',
                        'fillOpacity': 0.82,
                        'color': '#11131A',
                        'weight': 0
                    }
                ).add_to(m2)

                folium.GeoJson(
                    {"type": "FeatureCollection", "features": selected_hood_feats},
                    pane="mask_pane_stage2",
                    interactive=False,
                    style_function=lambda f: {
                        'fillColor': 'transparent',
                        'color': '#FFFFFF',
                        'weight': 2.5,
                        'opacity': 0.95
                    }
                ).add_to(m2)

        floating_guide2_center_html = f'''
        <div style="
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 9999;
            background: rgba(20, 22, 32, 0.90);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 999px;
            padding: 9px 26px;
            color: #FFFFFF;
            font-size: 14px;
            font-weight: 700;
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.6);
            display: flex;
            align-items: center;
            gap: 8px;
            pointer-events: none;
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            white-space: nowrap;
        ">
            <span>📍</span> <b>{h_name}</b> 상세 지도에서 실제 숙소 위치를 클릭하세요.
        </div>
        '''
        m2.get_root().html.add_child(folium.Element(floating_guide2_center_html))

        has_pin = (st.session_state.pin_lat is not None and st.session_state.pin_lon is not None)
        if has_pin:
            folium.Marker(
                [st.session_state.pin_lat, st.session_state.pin_lon],
                icon=folium.Icon(color="red", icon="home")
            ).add_to(m2)

        map_data2 = st_folium(
            m2,
            height=STAGE2_MAP_HEIGHT,
            width='stretch',
            key=f"map_stage2_detail_{b_name}_{st.session_state.selected_hood}_{st.session_state.pin_reset_cnt}",
            returned_objects=["last_clicked", "zoom", "center"]
        )

        if map_data2:
            m2_changed = False
            if map_data2.get("zoom") is not None:
                new_z2 = int(map_data2["zoom"])
                if new_z2 != st.session_state.get("detail_zoom"):
                    st.session_state.detail_zoom = new_z2
                    m2_changed = True
            if map_data2.get("center"):
                c2 = map_data2["center"]
                new_c2 = [round(c2["lat"], 5), round(c2["lng"], 5)]
                if new_c2 != st.session_state.get("detail_center"):
                    st.session_state.detail_center = new_c2
                    m2_changed = True
            if m2_changed:
                sync_url_params()

        if map_data2 and map_data2.get("last_clicked"):
            clk = map_data2["last_clicked"]
            new_lat = round(float(clk["lat"]), 5)
            new_lon = round(float(clk["lng"]), 5)
            if new_lat != st.session_state.pin_lat or new_lon != st.session_state.pin_lon:
                st.session_state.pin_lat = new_lat
                st.session_state.pin_lon = new_lon
                if map_data2.get("zoom") is not None:
                    st.session_state.detail_zoom = int(map_data2["zoom"])
                
                # 핀을 찍었을 때 핀의 위치가 지도의 정중앙으로 오도록 중심점 갱신
                st.session_state.detail_center = [new_lat, new_lon]
                st.session_state.init_detail_center = [new_lat, new_lon]
                st.session_state.init_detail_zoom = st.session_state.detail_zoom

                st.session_state.distance_to_ts = calculate_haversine_distance(new_lat, new_lon)
                st.session_state.pin_address = get_address_from_coords(
                    new_lat, new_lon, st.session_state.selected_hood, b_name
                )
                sync_url_params()
                st.rerun()

        st.markdown("""
        <style>
            /* 핀이 찍혔을 때 나타나는 하단 중앙 확인/취소 바 */
            div[class*="st-key-floating_pin_bar"] {
                margin-top: -150px !important;           
                transform: translateY(-70px) !important;
                height: fit-content !important;
                flex: 0 0 auto !important;
                margin-bottom: 0px !important;
                position: relative !important;
                z-index: 999 !important;
                background: rgba(20, 22, 32, 0.94) !important;
                backdrop-filter: blur(16px) !important;
                -webkit-backdrop-filter: blur(16px) !important;
                border: 1px solid rgba(255, 255, 255, 0.18) !important;
                border-radius: 18px !important;
                padding: 18px 24px !important;
                max-width: 700px !important;
                margin-left: auto !important;
                margin-right: auto !important;
                box-shadow: 0 18px 40px rgba(0, 0, 0, 0.75) !important;
            }
            
            /* [수정] 지도 좌측 하단 세부 동네 다시 선택 버튼 컨테이너 */
            div[class*="st-key-floating_back_only"] {
                margin-top: -108px !important;   /* -75px에서 -108px로 조정하여 지도 바닥에서 35~40px 띄움 */
                margin-bottom: 0px !important;
                margin-left: 28px !important;    /* 좌측 여백을 28px로 주어 안정감 확보 */
                position: relative !important;
                z-index: 999 !important;
                max-width: 250px !important;
            }
            
            /* 좌측 하단 버튼 전용 플로팅 글래스모피즘 스타일 */
            div[class*="st-key-floating_back_only"] div.stButton > button {
                height: 44px !important;
                font-size: 14.5px !important;
                font-weight: 700 !important;
                border-radius: 12px !important;
                background: rgba(24, 26, 36, 0.92) !important;
                backdrop-filter: blur(12px) !important;
                -webkit-backdrop-filter: blur(12px) !important;
                border: 1px solid rgba(255, 255, 255, 0.22) !important;
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.65) !important;
                color: #FFFFFF !important;
                transition: all 0.2s ease !important;
            }
            div[class*="st-key-floating_back_only"] div.stButton > button:hover {
                background: rgba(35, 38, 52, 0.98) !important;
                border-color: #FF385C !important;
                transform: translateY(-2px) !important;
                box-shadow: 0 12px 28px rgba(0, 0, 0, 0.8) !important;
            }

            /* 핀 확인 바 내부 버튼 높이 */
            div[class*="st-key-floating_pin_bar"] div.stButton > button {
                height: 44px !important;
                font-size: 14.5px !important;
                border-radius: 10px !important;
            }
        </style>
        """, unsafe_allow_html=True)

        if has_pin:
            with st.container(key="floating_pin_bar"):
                st.markdown(f"""
                    <div style="text-align:center; margin-bottom:14px;">
                        <div style="font-size:17.5px; font-weight:800; color:#38EF7D; margin-bottom:5px;">
                            📍 위치 확인
                        </div>
                        <div style="font-size:15px; color:#E2E4F0; line-height:1.45; word-break:break-word; white-space:normal;">
                            <b>주소 :</b> {st.session_state.pin_address}
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                b_col1, b_col2 = st.columns(2, gap="small")
                with b_col1:
                    if st.button("취소", key="btn_cancel_pin", width='stretch'):
                        if not st.session_state.get("detail_center") and st.session_state.pin_lat:
                            st.session_state.detail_center = [st.session_state.pin_lat, st.session_state.pin_lon]
                            
                        st.session_state.pin_lat = None
                        st.session_state.pin_lon = None
                        st.session_state.pin_address = None
                        st.session_state.distance_to_ts = None
                        
                        st.session_state.init_detail_center = st.session_state.detail_center
                        st.session_state.init_detail_zoom = st.session_state.detail_zoom
                        st.session_state.pin_reset_cnt += 1
                        sync_url_params()
                        st.rerun()
                with b_col2:
                    if st.button("확인", key="btn_confirm_pin", type="primary", width='stretch'):
                        st.session_state.init_detail_center = st.session_state.detail_center
                        st.session_state.init_detail_zoom = st.session_state.detail_zoom
                        st.session_state.page = 'detail_step'
                        st.session_state.input_step = 0
                        sync_url_params()
                        st.rerun()
        else:
            with st.container(key="floating_back_only"):
                if st.button("⬅️ 세부 동네 다시 선택", key="btn_reselect_hood_nopin", width='stretch'):
                    st.session_state.selected_hood = "선택해주세요"
                    st.session_state.pin_lat = None
                    st.session_state.pin_lon = None
                    st.session_state.pin_address = None
                    st.session_state.distance_to_ts = None   
                    st.session_state.detail_center = None
                    st.session_state.detail_zoom = 15
                    st.session_state.init_detail_zoom = 15     
                    st.session_state.init_detail_center = None 
                    sync_url_params()
                    st.rerun()

# ================================================
# [PAGE 3] 숙소 상세 스펙 & 운영 정책 입력 페이지
# ================================================
elif st.session_state.page == 'detail_step':
    st.markdown("""
    <style>
        div[class*="st-key-step1_card"],
        div[class*="st-key-step2_card_"],
        div[data-testid="stExpander"] {
            background: rgba(24, 26, 38, 0.4) !important;
            backdrop-filter: blur(12px) !important;
            -webkit-backdrop-filter: blur(12px) !important;
            border: 1px solid rgba(255, 255, 255, 0.14) !important;
            border-radius: 16px !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # Stepper 연동 : Step 1, 2는 '2. 숙소 정보 입력', Step 3은 '3. 최종 확인'
    current_stepper_stage = 2 if st.session_state.input_step in [0, 1] else 3
    render_stepper(current_stepper_stage)

    # ----------------------------------------------------------------------
    # [Step 1] 숙소의 룸타입 및 운영 정책 입력
    # ----------------------------------------------------------------------
    if st.session_state.input_step == 0:
        st.markdown("""
            <div class="guide-box">
                <div class="guide-text">
                    <span style="font-size:20px;">💡</span>
                    <div>
                        <div style="font-size:16.5px; font-weight:800; color:#FFFFFF;">Step 1. 호스팅 정책 및 룸타입 설정을 설정해 주세요.</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        with st.container(border=True, key="step1_card"):
            # 항목 헤더 + 호버 툴팁 가이드 배지
            is_short = "단기" in st.session_state.stay_category
            
            st.markdown("""
                <div class="section-main-header">
                    <span class="section-main-title">🎯 호스팅 정책</span>
                    <div class="inline-tooltip-wrap">
                        <span class="policy-hover-badge">
                            🗽 뉴욕시 단기 임대 규정(Local Law 18) 가이드
                        </span>
                        <div class="policy-popup-card">
                            <div class="popup-title">
                                <span>🗽 뉴욕시 단기 임대 규정(Local Law 18) 가이드</span>
                                <span>2023년 9월 시행</span>
                            </div>
                            <div class="popup-row">
                                <span style="color:#FF5A79; font-weight:800;">⚡ 단기 숙박 (30일 미만)</span>
                                <span style="color:#FFFFFF;"> : ① 호스트 실거주 필수 / ② 유료 게스트 최대 2인 이하</span>
                            </div>
                            <div class="popup-row">
                                <span style="color:#38EF7D; font-weight:800;">📅 장기 숙박 (30일 이상)</span>
                                <span style="color:#FFFFFF;"> : ① 임대 규제 전면 면제 / ② 게스트 인원 제한 없음</span>
                            </div>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            # 운영 방식 라디오 버튼
            stay_opts = ["단기 숙박 (30일 미만)", "장기 숙박 (30일 이상)"]
            s_idx = 0 if is_short else 1
            chosen_stay = st.radio(
                "운영 방식", 
                stay_opts, 
                index=s_idx, 
                horizontal=True,
                label_visibility="collapsed"
            )

            # 운영 방식 변경 시 동적 상태 업데이트
            if ("단기" in chosen_stay) != is_short:
                st.session_state.stay_category = "단기 숙박 (30일 미만)" if "단기" in chosen_stay else "장기 숙박 (30일 이상)"
                if "장기" in chosen_stay:
                    st.session_state.min_nights = 30
                    st.session_state.room_type = "Entire home/apt"
                else:
                    if st.session_state.min_nights >= 30:
                        st.session_state.min_nights = 3
                    if st.session_state.room_type == "Entire home/apt":
                        st.session_state.room_type = "Private room"
                    if st.session_state.accommodates > 2:
                        st.session_state.accommodates = 2
                        st.session_state.step2_input_acc = 2
                sync_url_params()
                st.rerun()

            st.write("")
            st.markdown("<hr style='margin:14px 0 20px 0; border-color:rgba(255,255,255,0.08);'>", unsafe_allow_html=True)

            # 세부 운영 조건 설정 헤더
            st.markdown("""
                <div class="section-main-header">
                    <span class="section-main-title">🏠 세부 운영 조건</span>
                </div>
            """, unsafe_allow_html=True)
            
            col_p1, col_p2 = st.columns(2, gap="medium")
            
            with col_p1:
                if "단기" in st.session_state.stay_category:
                    val_n = min(29, max(1, int(st.session_state.min_nights)))
                    
                    st.markdown("""
                        <div style="display:flex; justify-content:space-between; align-items:center; width:100%; margin-bottom:6px;">
                            <span style="font-size:15.5px; font-weight:700; color:#F1F3F9;">📅 최소 숙박일 수 설정 (박)</span>
                            <div class="inline-tooltip-wrap">
                                <span class="tip-hover-badge">💡 Tip</span>
                                <div class="tip-popup-card">
                                    단기 예약의 경우 <b>2~3박 설정</b>이 공실률을 줄이고 예약 회전율을 높이는 데 가장 효과적입니다.
                                </div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    st.session_state.min_nights = st.slider(
                        "최소 숙박일 수 설정", 
                        1, 29, val_n,
                        label_visibility="collapsed"
                    )
                    avail_rooms = ["Private room", "Shared room", "Hotel room"]
                else:
                    st.session_state.min_nights = 30
                    st.markdown("""
                        <div style="background:rgba(56,239,125,0.08); border:1px solid rgba(56,239,125,0.3); border-radius:10px; padding:12px 14px; margin-top:6px;">
                            <div style="color:#38EF7D; font-size:14.5px; font-weight:800; margin-bottom:2px;">✅ 최소 숙박 30박 고정 (장기 임대 기준)</div>
                            <div style="color:#A0A4B8; font-size:12.5px;">뉴욕시 단기 임대 규정(Local Law 18)가 전면 면제되어 집 전체 대여 및 다인 수용이 합법입니다.</div>
                        </div>
                    """, unsafe_allow_html=True)
                    avail_rooms = ["Entire home/apt", "Private room", "Shared room", "Hotel room"]

            with col_p2:
                room_labels = {
                    "Entire home/apt": "집 전체",
                    "Private room": "개인실",
                    "Shared room": "다인실",
                    "Hotel room": "호텔 / 부티크 숙소",
                }

                curr_r = st.session_state.room_type
                r_idx = avail_rooms.index(curr_r) if curr_r in avail_rooms else 0

                # 라벨 + 💡 Tip 호버 배지
                st.markdown("""
                    <div style="display:flex; justify-content:space-between; align-items:center; width:100%; margin-bottom:6px;">
                        <span style="font-size:15.5px; font-weight:700; color:#F1F3F9;">🚪 숙소 공간 유형</span>
                        <div class="inline-tooltip-wrap">
                            <span class="tip-hover-badge">💡 Tip</span>
                            <div class="tip-popup-card">
                                숙소 유형은 가격 형성에 가장 결정적인 <b>핵심 변수</b>입니다.
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                selected_display = st.selectbox(
                    "숙소 공간 유형",
                    avail_rooms,
                    index=r_idx,
                    format_func=lambda x: room_labels.get(x, x),
                    label_visibility="collapsed"
                )

                st.session_state.room_type = selected_display
                sync_url_params()

        st.write("")
        c_l, _, c_r = st.columns([0.9, 3.2, 0.9])
        with c_l:
            if st.button("⬅️ 상세 주소 다시 선택", width='stretch'):
                st.session_state.init_detail_center = st.session_state.detail_center
                st.session_state.init_detail_zoom = st.session_state.detail_zoom
                st.session_state.page = 'borough_map'
                sync_url_params()
                st.rerun()

        with c_r:
            if st.button("다음", type="primary", width='stretch'):
                st.session_state.show_acc_warning = False
                st.session_state.show_room_warning = False
                st.session_state.input_step = 1
                sync_url_params()
                st.rerun()

    # ----------------------------------------------------------------------
    # [Step 2] 숙소의 스펙 정보 입력 (규모 · 구조 · 편의시설)
    # ----------------------------------------------------------------------
    elif st.session_state.input_step == 1:
        st.session_state.step2_input_acc = int(st.session_state.accommodates)
        st.session_state.step2_input_bed = int(st.session_state.bedrooms)
        st.session_state.step2_input_bds = int(st.session_state.beds)
        st.session_state.step2_input_bath = float(st.session_state.bathrooms)

        st.markdown("""
            <div class="guide-box">
                <div class="guide-text">
                    <span style="font-size:20px;">💡</span>
                    <div>
                        <div style="font-size:16.5px; font-weight:800; color:#FFFFFF;">Step 2. 숙소의 스펙 정보를 입력해 주세요.</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # 숙소 규모 섹션
        with st.container(border=True, key="step2_card_spec"):
            st.markdown("""
                <div class="section-main-header" style="justify-content: flex-start; gap: 10px; margin-bottom: 14px;">
                    <span class="section-main-title">🏢 수용 규모 및 공간 구성</span>
                    <div class="inline-tooltip-wrap">
                        <span class="tip-hover-badge">💡 Tip</span>
                        <div class="tip-popup-card" style="left: 0; right: auto;">
                            수용 인원, 침실, 침대 및 욕실 수는 숙박 요금을 결정하는 <b>핵심 요소</b>입니다.
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            # 안전하게 세션값 조회 (AttributeError 원천 방지)
            curr_stay_cat = st.session_state.get('stay_category', "단기 숙박 (30일 미만)")
            is_short_stay = "단기" in curr_stay_cat

            c1, c2, c3, c4 = st.columns(4)

            # [단기 2인 초과 감지 및 5초 리셋 콜백]
            def handle_acc_change():
                val = st.session_state.get('step2_input_acc', 1)
                is_short = "단기" in st.session_state.get('stay_category', '')
                if is_short and val > 2:
                    st.session_state.step2_input_acc = 2
                    st.session_state.accommodates = 2
                    st.session_state.show_acc_warning = True
                    st.session_state.acc_warn_nonce = st.session_state.get('acc_warn_nonce', 0) + 1
                else:
                    st.session_state.accommodates = val
                    if val <= 2:
                        st.session_state.show_acc_warning = False
                sync_url_params()

            # 최대 수용 인원
            with c1:
                st.number_input(
                    "👥 최대 수용 인원 (명)", 
                    min_value=1, 
                    max_value=20, 
                    key="step2_input_acc",
                    on_change=handle_acc_change
                )

                # 단기에서 2인을 초과하려 할 때 5초간 노출 (연타 시 nonce 갱신으로 시간 재충전)
                if is_short_stay and st.session_state.get('show_acc_warning', False):
                    nonce = st.session_state.get('acc_warn_nonce', 0)
                    st.markdown(f"""
                        <div key="warn_{nonce}" class="fade-warning-card" style="
                            background: rgba(239, 68, 68, 0.12);
                            border: 1px solid rgba(239, 68, 68, 0.4);
                            border-left: 4px solid #EF4444;
                            border-radius: 8px;
                            padding: 8px 12px;
                            margin-top: 10px;
                            margin-bottom: 12px;
                            font-size: 13px;
                            color: #F87171;
                            font-weight: 700;
                            line-height: 1.4;
                            word-break: keep-all;
                        ">
                            🚫 <b>뉴욕시 단기 임대 규정(Local Law 18)</b> : 단기 숙박은 최대 2인까지만 가능합니다.
                        </div>
                    """, unsafe_allow_html=True)

            def handle_step2_spec_change():
                st.session_state.bedrooms = int(st.session_state.get('step2_input_bed', 1))
                st.session_state.beds = int(st.session_state.get('step2_input_bds', 1))
                st.session_state.bathrooms = float(st.session_state.get('step2_input_bath', 1.0))
                sync_url_params()

            # [2] 침실 수
            with c2:
                st.number_input(
                    "🚪 침실 수 (개)", min_value=0, max_value=15, 
                    key="step2_input_bed",
                    on_change=handle_step2_spec_change
                )

            # [3] 침대 수
            with c3:
                st.number_input(
                    "🛏️ 침대 수 (개)", min_value=1, max_value=25, 
                    key="step2_input_bds",
                    on_change=handle_step2_spec_change
                )

            # [4] 욕실 수
            with c4:
                st.number_input(
                    "🚿 욕실 수 (개)", min_value=0.5, max_value=15.0, 
                    step=0.5, key="step2_input_bath",
                    on_change=handle_step2_spec_change
                )

                bath_ratio = st.session_state.bathrooms / max(1, st.session_state.accommodates)
                if bath_ratio > 2.0:
                    st.markdown(f"""
                        <div style="
                            background: rgba(245, 158, 11, 0.10);
                            border: 1px solid rgba(245, 158, 11, 0.35);
                            border-left: 4px solid #F59E0B;
                            border-radius: 8px;
                            padding: 8px 12px;
                            margin-top: 10px;
                            margin-bottom: 12px;
                            font-size: 13.5px;
                            color: #FBBF24;
                            font-weight: 600;
                            line-height: 1.4;
                            word-break: keep-all;
                        ">
                            ⚠️ <b>욕실 수 확인 ({bath_ratio:.1f}개/인)</b> : 게스트 전용 화장실 개수인지 확인해 주세요.
                        </div>
                    """, unsafe_allow_html=True)

        st.write("")

        # 3. 편의시설 선택 섹션 (18.5px 헤더 + 우측 끝 💡 Tip 배지 + 15.5px 부헤더)
        with st.container(border=True, key="step2_card_amen"):
            st.markdown("""
                <div class="section-main-header" style="justify-content: flex-start; gap: 10px; margin-bottom: 14px;">
                    <span class="section-main-title">✨ 보유 편의시설</span>
                    <div class="inline-tooltip-wrap">
                        <span class="tip-hover-badge">💡 Tip</span>
                        <div class="tip-popup-card" style="left: 0; right: auto;">
                            게스트가 검색할 때 중요하게 작용하는 <b>핵심 편의시설</b>입니다.
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            for grp_title, grp_info in AMENITY_GROUPS.items():
                st.markdown(f'<div style="font-size:15.5px; font-weight:700; color:#F1F3F9; margin-top:6px; margin-bottom:10px;">{grp_title}</div>', unsafe_allow_html=True)
                
                items_dict = grp_info["items"]
                cols = st.columns(3)
                for idx, (k_eng, k_label) in enumerate(items_dict.items()):
                    with cols[idx % 3]:
                        curr_bool = st.session_state.selected_amenities.get(k_eng, False)
                        st.session_state.selected_amenities[k_eng] = st.checkbox(
                            k_label, value=curr_bool, key=f"amen_{k_eng}"
                        )
                st.markdown("<hr style='margin:12px 0; border-color:rgba(255,255,255,0.06);'>", unsafe_allow_html=True)
            sync_url_params()

        st.write("")
        c_l, _, c_r = st.columns([0.9, 3.2, 0.9])
        with c_l:
            if st.button("⬅️ 이전", width='stretch'):
                st.session_state.input_step = 0
                sync_url_params()
                st.rerun()
        with c_r:
            if st.button("다음", type="primary", width='stretch'):
                st.session_state.confirm_acc = int(st.session_state.accommodates)
                st.session_state.confirm_bed = int(st.session_state.bedrooms)
                st.session_state.confirm_bds = int(st.session_state.beds)
                st.session_state.confirm_bath = float(st.session_state.bathrooms)
                st.session_state.show_acc_warning = False
                st.session_state.input_step = 2
                sync_url_params()
                st.rerun()

    # ----------------------------------------------------------------------
    # [Step 3] 입력 정보 확인 및 즉시 수정
    # ----------------------------------------------------------------------
    elif st.session_state.input_step == 2:
        # [핵심] 3개 카드가 모두 펼쳐져도 하단 버튼이 한눈에 보이도록 전체 레이아웃을 위로 당김
        st.markdown("""
        <style>
            .block-container {
                padding-top: 2.0rem !important;
                padding-bottom: 1.5rem !important;
            }
            .stepper-wrap {
                padding: 10px 24px !important;
                margin-bottom: 12px !important;
            }
            .guide-box {
                padding: 13px 20px !important;
                margin-bottom: 12px !important;
            }
            div[data-testid="stExpander"] {
                margin-bottom: 10px !important;
            }
            div[data-testid="stExpanderDetails"] {
                padding-top: 8px !important;
                padding-bottom: 12px !important;
            }
        </style>
        """, unsafe_allow_html=True)

        # Step 1, 2와 100% 동일한 폰트 및 구조의 가이드 카드
        st.markdown("""
            <div class="guide-box">
                <div class="guide-text">
                    <span style="font-size:20px;">🔍</span>
                    <div>
                        <div style="font-size:16.5px; font-weight:800; color:#FFFFFF;">Step 3. 입력 정보를 확인해 주세요.</div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Step 3 진입 시 세션값과 동기화
        st.session_state.confirm_acc = int(st.session_state.accommodates)
        st.session_state.confirm_bed = int(st.session_state.bedrooms)
        st.session_state.confirm_bds = int(st.session_state.beds)
        st.session_state.confirm_bath = float(st.session_state.bathrooms)

        # [사이드바 즉시 연동용 콜백 함수들]
        def handle_confirm_min_n():
            st.session_state.min_nights = int(st.session_state.confirm_min_n)
            sync_url_params()

        def handle_confirm_room_type():
            st.session_state.room_type = st.session_state.confirm_room_type
            st.session_state.show_room_warning = False
            sync_url_params()

        def handle_confirm_acc_change():
            val = st.session_state.get('confirm_acc', 1)
            is_short = "단기" in st.session_state.get('stay_category', '')
            if is_short and val > 2:
                st.session_state.confirm_acc = 2
                st.session_state.accommodates = 2
                st.session_state.step2_input_acc = 2
                st.session_state.show_acc_warning = True
                st.session_state.acc_warn_nonce = st.session_state.get('acc_warn_nonce', 0) + 1
            else:
                st.session_state.accommodates = val
                st.session_state.step2_input_acc = val
                if val <= 2:
                    st.session_state.show_acc_warning = False
            sync_url_params()

        def handle_confirm_spec_change():
            st.session_state.bedrooms = int(st.session_state.get('confirm_bed', 1))
            st.session_state.beds = int(st.session_state.get('confirm_bds', 1))
            st.session_state.bathrooms = float(st.session_state.get('confirm_bath', 1.0))
            st.session_state.step2_input_bed = st.session_state.bedrooms
            st.session_state.step2_input_bds = st.session_state.beds
            st.session_state.step2_input_bath = st.session_state.bathrooms
            sync_url_params()

        def handle_confirm_amen_change(amen_key):
            st.session_state.selected_amenities[amen_key] = st.session_state.get(f"confirm_amen_{amen_key}", False)
            sync_url_params()

        # 1. 호스팅 정책 및 룸타입 설정 카드
        with st.expander("💡 **호스팅 정책 및 룸타입**", expanded=True):
            is_short_confirm = "단기" in st.session_state.stay_category
            stay_opts = ["단기 숙박 (30일 미만)", "장기 숙박 (30일 이상)"]
            s_idx = 0 if is_short_confirm else 1
            chosen_stay = st.radio(
                "운영 방식",
                stay_opts,
                index=s_idx,
                horizontal=True,
                label_visibility="collapsed",
                key="confirm_stay_cat"
            )

            if ("단기" in chosen_stay) != is_short_confirm:
                st.session_state.stay_category = "단기 숙박 (30일 미만)" if "단기" in chosen_stay else "장기 숙박 (30일 이상)"
                if "장기" in chosen_stay:
                    st.session_state.min_nights = 30
                    # 단기 -> 장기 전환 시에는 기존에 선택한 숙소 공간 유형을 그대로 유지
                    st.session_state.confirm_room_type = st.session_state.room_type
                    st.session_state.show_acc_warning = False
                    st.session_state.show_room_warning = False
                else:
                    if st.session_state.min_nights >= 30:
                        st.session_state.min_nights = 3
                        st.session_state.confirm_min_n = 3

                    # 장기 -> 단기 전환 시: '집 전체'였을 때만 '개인실'로 바꾸고 5초 경고창 활성화
                    if st.session_state.room_type == "Entire home/apt":
                        st.session_state.room_type = "Private room"
                        st.session_state.confirm_room_type = "Private room"
                        st.session_state.show_room_warning = True
                        st.session_state.room_warn_nonce = st.session_state.get('room_warn_nonce', 0) + 1
                    else:
                        # 개인실, 다인실, 호텔 등은 리셋하지 않고 그대로 유지
                        st.session_state.confirm_room_type = st.session_state.room_type
                        st.session_state.show_room_warning = False

                    # 수용 인원이 2인을 초과한 상태였다면 2인으로 맞추면서 인원 경고창도 함께 표시
                    if st.session_state.accommodates > 2:
                        st.session_state.accommodates = 2
                        st.session_state.step2_input_acc = 2
                        st.session_state.confirm_acc = 2
                        st.session_state.show_acc_warning = True
                        st.session_state.acc_warn_nonce = st.session_state.get('acc_warn_nonce', 0) + 1
                sync_url_params()
                st.rerun()

            st.markdown("<hr style='margin:10px 0 14px 0; border-color:rgba(255,255,255,0.08);'>", unsafe_allow_html=True)

            col_p1, col_p2 = st.columns(2, gap="medium")
            with col_p1:
                if "단기" in st.session_state.stay_category:
                    val_n = min(29, max(1, int(st.session_state.min_nights)))
                    st.markdown("""
                        <div style="display:flex; justify-content:space-between; align-items:center; width:100%; margin-bottom:6px;">
                            <span style="font-size:15.5px; font-weight:700; color:#F1F3F9;">📅 최소 숙박일 수 설정 (박)</span>
                            <div class="inline-tooltip-wrap">
                                <span class="tip-hover-badge">💡 Tip</span>
                                <div class="tip-popup-card">
                                    단기 예약의 경우 <b>2~3박 설정</b>이 공실률을 줄이고 예약 회전율을 높이는 데 가장 효과적입니다.
                                </div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    st.slider(
                        "최소 숙박일 수 설정",
                        1, 29, val_n,
                        label_visibility="collapsed",
                        key="confirm_min_n",
                        on_change=handle_confirm_min_n
                    )
                    avail_rooms = ["Private room", "Shared room", "Hotel room"]
                else:
                    st.session_state.min_nights = 30
                    st.markdown("""
                        <div style="background:rgba(56,239,125,0.08); border:1px solid rgba(56,239,125,0.3); border-radius:10px; padding:12px 14px; margin-top:6px;">
                            <div style="color:#38EF7D; font-size:14.5px; font-weight:800; margin-bottom:2px;">✅ 최소 숙박 30박 고정 (장기 임대 기준)</div>
                            <div style="color:#A0A4B8; font-size:12.5px;">뉴욕시 단기 임대 규정(Local Law 18)가 전면 면제되어 집 전체 대여 및 다인 수용이 합법입니다.</div>
                        </div>
                    """, unsafe_allow_html=True)
                    avail_rooms = ["Entire home/apt", "Private room", "Shared room", "Hotel room"]

            with col_p2:
                room_labels = {
                    "Entire home/apt": "집 전체",
                    "Private room": "개인실",
                    "Shared room": "다인실",
                    "Hotel room": "호텔 / 부티크 숙소",
                }
                curr_r = st.session_state.room_type
                r_idx = avail_rooms.index(curr_r) if curr_r in avail_rooms else 0

                st.markdown("""
                    <div style="display:flex; justify-content:space-between; align-items:center; width:100%; margin-bottom:6px;">
                        <span style="font-size:15.5px; font-weight:700; color:#F1F3F9;">🚪 숙소 공간 유형</span>
                        <div class="inline-tooltip-wrap">
                            <span class="tip-hover-badge">💡 Tip</span>
                            <div class="tip-popup-card">
                                숙소 유형은 가격 형성에 가장 결정적인 <b>핵심 변수</b>입니다.
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                st.selectbox(
                    "숙소 공간 유형",
                    avail_rooms,
                    index=r_idx,
                    format_func=lambda x: room_labels.get(x, x),
                    label_visibility="collapsed",
                    key="confirm_room_type",
                    on_change=handle_confirm_room_type
                )

                # 장기(집 전체) -> 단기 전환 시 5초간 노출 후 사라지는 경고창
                if is_short_confirm and st.session_state.get('show_room_warning', False):
                    r_nonce = st.session_state.get('room_warn_nonce', 0)
                    st.markdown(f"""
                        <div key="warn_room_{r_nonce}" class="fade-warning-card" style="
                            background: rgba(239, 68, 68, 0.12);
                            border: 1px solid rgba(239, 68, 68, 0.4);
                            border-left: 4px solid #EF4444;
                            border-radius: 8px;
                            padding: 8px 12px;
                            margin-top: 10px;
                            margin-bottom: 4px;
                            font-size: 13px;
                            color: #F87171;
                            font-weight: 700;
                            line-height: 1.4;
                            word-break: keep-all;
                        ">
                            🚫 <b>뉴욕시 단기 임대 규정(Local Law 18)</b> : 단기 숙박은 집 전체 임대가 제한되어 <b>개인실</b>로 자동 변경되었습니다.
                        </div>
                    """, unsafe_allow_html=True)

        # 2. 수용 규모 및 공간 구성 카드
        with st.expander("🏢 **수용 규모 및 공간 구성**", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.number_input(
                    "👥 최대 수용 인원 (명)",
                    min_value=1,
                    max_value=20,
                    key="confirm_acc",
                    on_change=handle_confirm_acc_change
                )
                if is_short_confirm and st.session_state.get('show_acc_warning', False):
                    nonce = st.session_state.get('acc_warn_nonce', 0)
                    st.markdown(f"""
                        <div key="warn_confirm_{nonce}" class="fade-warning-card" style="
                            background: rgba(239, 68, 68, 0.12);
                            border: 1px solid rgba(239, 68, 68, 0.4);
                            border-left: 4px solid #EF4444;
                            border-radius: 8px;
                            padding: 8px 12px;
                            margin-top: 10px;
                            margin-bottom: 12px;
                            font-size: 13px;
                            color: #F87171;
                            font-weight: 700;
                            line-height: 1.4;
                            word-break: keep-all;
                        ">
                            🚫 <b>뉴욕시 단기 임대 규정(Local Law 18)</b> : 단기 숙박은 최대 2인까지만 가능합니다.
                        </div>
                    """, unsafe_allow_html=True)

            with c2:
                st.number_input(
                    "🚪 침실 수 (개)",
                    min_value=0,
                    max_value=15,
                    key="confirm_bed",
                    on_change=handle_confirm_spec_change
                )
            with c3:
                st.number_input(
                    "🛏️ 침대 수 (개)",
                    min_value=1,
                    max_value=25,
                    key="confirm_bds",
                    on_change=handle_confirm_spec_change
                )
            with c4:
                st.number_input(
                    "🚿 욕실 수 (개)",
                    min_value=0.5,
                    max_value=15.0,
                    step=0.5,
                    key="confirm_bath",
                    on_change=handle_confirm_spec_change
                )
                bath_ratio = st.session_state.bathrooms / max(1, st.session_state.accommodates)
                if bath_ratio > 2.0:
                    st.markdown(f"""
                        <div style="
                            background: rgba(245, 158, 11, 0.10);
                            border: 1px solid rgba(245, 158, 11, 0.35);
                            border-left: 4px solid #F59E0B;
                            border-radius: 8px;
                            padding: 8px 12px;
                            margin-top: 10px;
                            margin-bottom: 12px;
                            font-size: 13.5px;
                            color: #FBBF24;
                            font-weight: 600;
                            line-height: 1.4;
                            word-break: keep-all;
                        ">
                            ⚠️ <b>욕실 수 확인 ({bath_ratio:.1f}개/인)</b> : 게스트 전용 화장실 개수인지 확인해 주세요.
                        </div>
                    """, unsafe_allow_html=True)

        # 3. 보유 편의시설 선택 카드
        with st.expander("✨ **보유 편의시설**", expanded=True):
            for idx_g, (grp_title, grp_info) in enumerate(AMENITY_GROUPS.items()):
                st.markdown(f'<div style="font-size:15px; font-weight:700; color:#F1F3F9; margin-top:2px; margin-bottom:6px;">{grp_title}</div>', unsafe_allow_html=True)
                items_dict = grp_info["items"]
                cols = st.columns(3)
                for idx, (k_eng, k_label) in enumerate(items_dict.items()):
                    with cols[idx % 3]:
                        curr_bool = st.session_state.selected_amenities.get(k_eng, False)
                        st.checkbox(
                            k_label,
                            value=curr_bool,
                            key=f"confirm_amen_{k_eng}",
                            on_change=handle_confirm_amen_change,
                            args=(k_eng,)
                        )
                if idx_g < len(AMENITY_GROUPS) - 1:
                    st.markdown("<hr style='margin:6px 0; border-color:rgba(255,255,255,0.06);'>", unsafe_allow_html=True)

        c_l, _, c_r = st.columns([0.9, 3.2, 0.9])
        with c_l:
            if st.button("⬅️ 이전", width='stretch'):
                st.session_state.step2_input_acc = int(st.session_state.accommodates)
                st.session_state.step2_input_bed = int(st.session_state.bedrooms)
                st.session_state.step2_input_bds = int(st.session_state.beds)
                st.session_state.step2_input_bath = float(st.session_state.bathrooms)
                st.session_state.show_acc_warning = False
                st.session_state.input_step = 1
                sync_url_params()
                st.rerun()
        with c_r:
            if st.button("확정", type="primary", width='stretch'):
                st.session_state.final_features = build_features_dict()
                st.session_state.page = 'prediction_page'
                sync_url_params()
                st.rerun()

# ===========
# AI 설정
# ===========

# [수정 후] 약 952~971번째 줄 교체
def _format_bullets_to_html(text):
  """LLM의 불규칙한 마크다운/리스트/문자열 응답을 일관된 <ul class='hm-list'><li><b>소제목</b> : 내용</li></ul> 구조로 강제 변환"""
  if not text:
    return ""

  # LLM이 문자열 대신 JSON 배열로 반환한 경우 문자열로 병합
  if isinstance(text, list):
    text = "\n".join(str(item) for item in text)

  raw_str = str(text)
  # 마크다운 볼드를 HTML <b>텍스트</b>로 변환 및 불필요한 마크다운 기호(#, `) 제거
  raw_str = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", raw_str)
  raw_str = re.sub(r"`([^`]*)`", r"\1", raw_str)

  lines = [
      line.strip() for line in re.split(r"<br\s*/?>|\n", raw_str) if line.strip()
  ]
  html_out = ['<ul class="hm-list">']

  for line in lines:
    # 앞머리의 •, -, *, ▪, 1., 2), ① 등 모든 종류의 불릿/번호 기호 제거
    clean_item = re.sub(
        r"^(?:[•\-\*▪▸▶➢]|[\d]+[\.\)]|[①-⑩])\s*", "", line
    ).strip()
    clean_item = re.sub(r"^#+\s*", "", clean_item).strip()
    if not clean_item:
      continue

    # '소제목 : 내용' 구조에서 소제목에 <b> 태그가 없으면 자동으로 <b>소제목</b> : 내용 형태로 통일
    if ":" in clean_item and not clean_item.startswith("<b>"):
      parts = clean_item.split(":", 1)
      if len(parts[0].strip()) <= 28:
        clean_item = f"<b>{parts[0].strip()}</b> : {parts[1].strip()}"

    html_out.append(f"<li>{clean_item}</li>")

  html_out.append("</ul>")
  return "".join(html_out)


@st.cache_data(show_spinner=False, ttl=3600)
def _call_ollama_consulting_api(prompt_text, api_key):
    """Ollama Cloud의 gemma4:31b-cloud 모델을 호출하고 JSON을 안전하게 파싱하는 함수"""
    clean_key = str(api_key).strip().strip('"').strip("'")
    if not clean_key:
        raise ValueError("유효하지 않은 Ollama API Key입니다.")

    url = "https://ollama.com/api/chat"
    system_msg = (
        "You are an elite NYC Airbnb Superhost & Revenue Consultant. "
        "Respond ONLY with a valid JSON object without markdown code blocks. "
        "Use <br> and <b> for HTML formatting inside JSON string values."
    )

    candidate_models = ["gemma4:31b-cloud", "gemma4:31b"]
    last_err = None

    for model_name in candidate_models:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt_text},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.2},
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {clean_key}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) HostMateNYC/1.0"
            },
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                raw_txt = res_data.get("message", {}).get("content", "").strip()

                # 추론(<think>...</think>) 블록 및 마크다운 코드블록 제거 후 순수 JSON 추출
                raw_txt = re.sub(r'<think>.*?</think>', '', raw_txt, flags=re.DOTALL).strip()
                json_match = re.search(r'\{.*\}', raw_txt, re.DOTALL)
                if not json_match:
                    raise ValueError(f"JSON 객체를 찾을 수 없습니다: {raw_txt[:100]}")

                parsed = json.loads(json_match.group(0), strict=False)
                required_keys = (
                    "priority_item_advice", "location_policy_strategy", "space_comfort_diagnosis",
                    "listing_title_kr", "listing_title_en", "listing_desc_en", "listing_desc_kr", "highlight_tags"
                )
                if all(k in parsed for k in required_keys):
                    parsed["engine"] = "HostMate AI Engine"
                    return parsed
                raise ValueError(f"필수 JSON 키 누락: {list(parsed.keys())}")
        except urllib.error.HTTPError as he:
            err_msg = he.read().decode("utf-8", errors="ignore")
            last_err = f"Ollama HTTP {he.code} ({model_name}): {err_msg}"
            continue
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"Ollama Cloud API 호출 실패: {last_err}")

def generate_ai_host_consulting(
    boro, hood, rtype_kr, stay_cat, min_n, dist_km,
    accom, bedrooms, beds, baths,
    pred_price, main_bench, diff_pct,
    price_short, rev_short, price_long, rev_long, breakeven_nights,
    gain_svc, gain_all, roi_calc_days, selected_amen_str, missing_svc_str,
    bench_name="동종 표준가", rtype="Private room"
):
    prompt = f"""당신은 뉴욕 에어비앤비 수익화 및 Local Law 18 전문 수석 컨설턴트이자 카피라이터입니다.
                 아래 호스트의 숙소 스펙과 AI 시뮬레이션 데이터를 종합적으로 해석하여, 이 숙소만의 특색이 살아있는 맞춤형 컨설팅 리포트와 리스팅 초안을 자유롭고 깊이 있게 작성해 주세요.
                 
                 [⚠️ 절대 지켜야 할 팩트 가드레일 (할루시네이션 방지)]
                 뉴욕 Local Law 18 기준: 30일 미만 단기 숙박은 '호스트 실거주(동거) 필수 및 게스트 최대 2인 이하'만 합법이며, 30일 이상 장기 숙박은 규제가 전면 면제됩니다. 호스트가 설정한 최소 숙박일({min_n}박)은 개인 운영 설정일 뿐 법적 의무가 아니므로 '최소 {min_n}박 법적 규정을 지켜야 한다'고 잘못 서술하지 마세요.
                 수치 정확성: 아래 제공된 예측 요금(${pred_price:,.2f}), 기준가(${main_bench:,.2f}), 월 매출, 수익 상승폭 숫자를 임의로 변경하지 마세요.
                 허위 옵션 기재 금지: 숙소 디스크립션 작성 시 현재 보유 편의시설({selected_amen_str})에 없는 시설을 이미 갖춘 것처럼 꾸며내지 마세요.
                 
                 [숙소 종합 데이터]
                 위치 및 상권 : 뉴욕 {boro} - {hood} (타임스퀘어 도심에서 직선 {dist_km}km)
                 운영 방식 및 유형 : {stay_cat} / {rtype_kr} (호스트 설정 최소 {min_n}박)
                 물리적 공간 스펙 : 최대 수용 {accom}명, 침실 {bedrooms:.0f}개, 침대 {beds:.0f}개, 욕실 {baths}개
                 AI 가격 진단 : 적정가 ${pred_price:,.2f}/박 ({bench_name} ${main_bench:,.2f} 대비 {diff_pct:+.1f}%)
                 단기 vs 장기 시뮬레이션 : 단기(월 17박 기준) 월 ${rev_short:,.0f} vs 장기(30박 기준) 월 ${rev_long:,.0f} (손익분기점 {breakeven_nights}박)
                 현재 보유 편의시설 : {selected_amen_str}
                 우선 확충 추천 시설 : {missing_svc_str} (2개 추가 시 +${gain_svc:,.2f}/박, 풀패키지 업그레이드 시 +${gain_all:,.2f}/박 상승)
                 
                 [⚠️ 출력 양식 엄수 규칙 (위반 금지)]
                 1. 반드시 아래 JSON 키 구조를 정확히 지키는 단일 JSON 객체로만 응답하세요.
                 2. 모든 JSON 값은 배열(List)이 아닌 단일 문자열(String)이어야 합니다 (단, highlight_tags만 문자열 배열).
                 3. 마크다운 기호(**, #, *, - 등)를 절대 사용하지 마세요. 강조는 오직 HTML <b>태그</b>만 사용하고 줄바꿈은 <br>만 사용하세요.
                 4. 각 컨설팅 항목(priority_item_advice, location_policy_strategy, space_comfort_diagnosis)의 모든 문장은 반드시 '• <b>핵심 소제목</b> : 상세 분석 내용<br>' 형식으로 통일하여 작성하세요.

                 {{"priority_item_advice": "• <b>우선 도입 추천</b> : 현재 미보유 시설({missing_svc_str}) 중 최우선 도입 아이템과 이유<br>• <b>기대 수익 분석</b> : 2개 추가 시 월 +${gain_svc*roi_calc_days:,.0f}, 풀패키지 시 월 +${gain_all*roi_calc_days:,.0f} 상승 효과 분석 (총 2~3개 불릿 문자열)",
                    "location_policy_strategy": "• <b>상권 입지 분석</b> : {boro} {hood} 상권 및 도심 접근성({dist_km}km) 진단<br>• <b>법규 및 운영 전략</b> : Local Law 18 및 단기/장기 수익 비교 기반 최적 운영법<br>• <b>타겟 게스트 및 요금</b> : 추천 타겟층 및 가격 포지셔닝 전략 (총 3~4개 불릿 문자열)",
                    "space_comfort_diagnosis": "• <b>공간 쾌적도 진단</b> : {accom}명 대비 침실({bedrooms:.0f})·침대({beds:.0f})·욕실({baths}) 비율 평가<br>• <b>홈스테이징 연출</b> : 공간 매력도를 높이는 인테리어·사진 연출 팁<br>• <b>리뷰 고평점 전략</b> : 체감 만족도 극대화 포인트 (총 3~4개 불릿 문자열)",
                    "listing_title_kr": "숙소의 입지({hood})와 공간 매력을 살린 한국어 리스팅 제목 (40자 내외, 단일 문자열)",
                    "listing_title_en": "실제 에어비앤비에 등록할 영문 리스팅 제목 (50자 내외, 단일 문자열)",
                    "highlight_tags": ["이모지 포함 핵심 매력 태그 1 (15자 이내)", "핵심 매력 태그 2", "핵심 매력 태그 3"],
                    "listing_desc_kr": "숙소의 위치 장점, 공간 분위기, 추천 게스트층을 담은 자연스러운 한국어 숙소 소개글 (4~5문장, 단일 문자열)",
                    "listing_desc_en": "실제 에어비앤비 About this space에 바로 복사해 쓸 수 있는 영문 숙소 소개글 (4~5문장, 단일 문자열)"
                }}"""

    # OLLAMA_API_KEY 탐색
    ollama_key = os.environ.get("OLLAMA_API_KEY", "")
    try:
        if not ollama_key and "OLLAMA_API_KEY" in st.secrets:
            ollama_key = st.secrets["OLLAMA_API_KEY"]
    except Exception:
        pass

    if ollama_key:
        try:
            return _call_ollama_consulting_api(prompt, ollama_key)
        except Exception as e:
            print(f"⚠️ [HostMate] Ollama Cloud API 호출 실패 (내장 엔진 폴백 전환): {e}")

    if gain_svc > 0:
        priority_fb = (
            f"• <b>최우선 도입 편의시설</b> : 현재 미보유하신 <b>{missing_svc_str}</b> 옵션을 우선 확충하시는 것을 권장합니다.<br>"
            f"• <b>투자 대비 기대 수익</b> : 1박당 <b>+${gain_svc:,.2f}</b>(월 {roi_calc_days}박 기준 <b>+${gain_svc*roi_calc_days:,.0f}</b>) 상승이 예측되며, 풀패키지 보강 시 월 최대 <b>+${gain_all*roi_calc_days:,.0f}</b>의 추가 수익 여력이 존재합니다."
        )
    else:
        priority_fb = (
            f"• <b>핵심 서비스 옵션 완비</b> : 주요 서비스 편의시설을 이미 훌륭하게 갖추고 계십니다.<br>"
            f"• <b>하이엔드 수익 방어</b> : 미보유 실생활·프리미엄 옵션을 추가 보강하면 월 <b>+${gain_all*roi_calc_days:,.0f}</b> 수준의 상위권 요금 방어가 가능합니다."
        )

    loc_fb = (
        f"• <b>상권 및 입지 진단</b> : <b>{boro}({hood})</b> 권역은 타임스퀘어 도심에서 <b>{dist_km}km</b> 거리에 위치해 대중교통 접근성과 로컬 주거 감성을 동시에 갖춘 인기 상권입니다.<br>"
        f"• <b>Local Law 18 준수 전략</b> : 30일 미만 단기 운영 시에는 호스트 실거주 및 최대 2인 제한을 준수해야 하며, 30일 이상 장기 임대 시에는 규제가 전면 면제됩니다.<br>"
        f"• <b>핵심 타겟 게스트</b> : 도심 출퇴근이 필요한 비즈니스 출장자, 한 달 살기 여행객 및 실속형 커플·솔로 투숙객을 타겟팅하세요.<br>"
        f"• <b>최적 운영 포지셔닝</b> : 월 <b>${rev_long:,.0f}</b>의 안정적 매출을 만드는 <b>30박 이상 장기 임대</b>가 단기 운영(월 <b>${rev_short:,.0f}</b>, 손익분기 <b>{breakeven_nights}박</b>) 대비 운영 효율과 수익 면에서 유리합니다."
    )

    people_per_bed = accom / max(1.0, beds)
    bath_per_person = baths / max(1, accom)
    space_status = "다소 타이트한 구성이므로 보조 침구 확충이 권장됩니다." if (people_per_bed > 2.0 or bath_per_person < 0.35) else "1인당 수면 및 욕실 여유도가 매우 쾌적한 황금 비율입니다."

    space_fb = (
        f"• <b>공간 쾌적도 진단</b> : 최대 수용 <b>{accom}명</b> 대비 침실 <b>{bedrooms:.0f}개</b> · 침대 <b>{beds:.0f}개</b> · 욕실 <b>{baths}개</b>로, {space_status}<br>"
        f"• <b>공간 연출 및 동선</b> : 첫 번째 대표 사진에 채광과 침구류 청결도가 돋보이도록 따뜻한 색온도(3000K) 스탠드 조명과 러그를 배치하세요.<br>"
        f"• <b>체감 만족도 보강</b> : <b>{missing_svc_str}</b> 등 선호도 높은 실용 아이템을 우선 비치하여 검색 필터 노출 빈도를 높이세요.<br>"
        f"• <b>리뷰 관리 포인트</b> : 인근 지하철역 도보 이동 시간과 주변 로컬 카페·마트 지도를 체크인 가이드로 제공하면 위치 평점을 크게 끌어올릴 수 있습니다."
    )

    return {
        "priority_item_advice": priority_fb,
        "location_policy_strategy": loc_fb,
        "space_comfort_diagnosis": space_fb,
        "listing_title_kr": f"맨해튼 도심까지 {dist_km}km! 감각적이고 조용한 {hood} {rtype_kr}",
        "listing_title_en": f"Stylish {hood} {rtype} | {dist_km}km to Midtown",
        "highlight_tags": [f"🚇 타임스퀘어 {dist_km}km 접근성", f"🏠 {hood} 핵심 로컬 상권", f"✨ {accom}인 맞춤 쾌적 공간"],
        "listing_desc_en": (
            f"Welcome to your peaceful retreat in the heart of {hood}, {boro}! "
            f"Located just {dist_km}km from Times Square, this bright and thoughtfully designed {rtype.lower()} offers the perfect blend of local NYC charm and easy transit access. "
            f"Featuring {bedrooms:.0f} bedroom(s), {beds:.0f} comfortable bed(s), and {baths} clean bathroom(s), it is ideal for solo travelers, couples, or remote workers looking for a restful stay."
        ),
        "listing_desc_kr": (
            f"{boro}의 매력적인 로컬 동네, {hood}에 위치한 아늑하고 감각적인 숙소에 오신 것을 환영합니다! "
            f"타임스퀘어 도심에서 단 {dist_km}km 거리에 위치해 맨해튼 주요 명소로 빠르게 이동하면서도 조용하고 안전한 휴식을 누리실 수 있습니다. "
            f"침실 {bedrooms:.0f}개, 편안한 침대 {beds:.0f}개, 욕실 {baths}개를 갖추고 있어 출장자나 여행객 모두에게 내 집처럼 편안한 뉴욕 체류 경험을 선사합니다."
        ),
        "engine": "HostMate AI Engine"
    }


# ==========================================================================
# [PAGE 4] 최종 가격 예측 & AI 호스트 컨설팅 리포트
# ==========================================================================
if st.session_state.page == 'prediction_page':
    render_stepper(4)

    if not st.session_state.selected_borough or not st.session_state.pin_lat:
        st.session_state.page = 'landing'
        sync_url_params()
        st.rerun()

    st.session_state.final_features = build_features_dict()

    # [리포트 전용 스타일: 투명도 조절 가이드 및 하단 여백 붙음 방지(box-sizing: border-box) 적용]
    st.markdown("""
    <style>
        .block-container {
            padding-top: 1.8rem !important;
            padding-bottom: 1.5rem !important;
        }
        .stepper-wrap {
            padding: 10px 24px !important;
            margin-bottom: 14px !important;
        }
        /* 최상단 메인 리포트 헤더 & 하단 구분선 */
        .report-main-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 14px;
            margin-bottom: 20px;
            border-bottom: 1.5px solid rgba(255, 255, 255, 0.15);
        }
        .report-main-title {
            font-size: 26px;
            font-weight: 800;
            color: #FFFFFF;
            letter-spacing: -0.6px;
        }
        /* 자치구 브리핑 카드와 100% 동일한 글머리 기호 스타일 */
        ul.hm-list {
            color: #D0D3E2;
            font-size: 13px;
            line-height: 1.55;
            margin-top: 4px !important;
            margin-bottom: 0 !important;
            padding-left: 18px !important;
            list-style-type: disc !important;
        }
        ul.hm-list li {
            margin-bottom: 5px !important;
        }
        ul.hm-list li:last-child {
            margin-bottom: 0 !important;
        }
        /* [항목 2 & 3] 구역별 겉을 감싸는 반투명 그룹 컨테이너
           - 투명도 조절: rgba(20, 22, 34, 0.60) 에서 0.60 숫자를 조절하세요 (0.0~1.0)
           - 하단 여백 확보: padding을 상하좌우 24px로 균일하게 부여 */
        div[class*="st-key-sim_group_container"],
        div[class*="st-key-bottom_group_container"] {
            background: rgba(20, 22, 34, 0.4) !important;
            backdrop-filter: blur(14px) !important;
            -webkit-backdrop-filter: blur(14px) !important;
            border: 1px solid rgba(255, 255, 255, 0.14) !important;
            border-radius: 22px !important;
            padding: 24px 24px 26px 24px !important;
            box-shadow: 0 16px 36px rgba(0, 0, 0, 0.40) !important;
            margin-bottom: 20px !important;
            box-sizing: border-box !important;
        }
        .kpi-card {
            overflow: visible !important;
            padding: 18px 22px !important;
            box-sizing: border-box !important;
        }
        .kpi-value {
            font-size: 34px !important;
        }
        .kpi-sub {
            margin-top: 8px !important;
            font-size: 13px !important;
        }
        /* [항목 3 핵심 해결] box-sizing: border-box를 지정하여 height: 100% 카드가 아래로 삐져나오지 않도록 방지 */
        .report-section-card {
            background: linear-gradient(160deg, rgba(34, 36, 52, 0.90) 0%, rgba(23, 24, 34, 0.90) 100%);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 18px;
            padding: 18px 22px;
            height: 100%;
            box-sizing: border-box !important;
            box-shadow: 0 10px 24px rgba(0, 0, 0, 0.3);
        }
        .report-card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .report-card-title {
            font-size: 16.5px;
            font-weight: 800;
            color: #FFFFFF;
            letter-spacing: -0.3px;
            margin-bottom: 2px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .report-card-sub {
            font-size: 12.5px;
            color: #9EA3B8;
            line-height: 1.35;
        }
        div[class*="st-key-net_profit_card"] {
            background: linear-gradient(160deg, rgba(34, 36, 52, 0.90) 0%, rgba(23, 24, 34, 0.90) 100%) !important;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
            border-radius: 18px !important;
            margin-top: 20px !important;                 
            padding: 24px 28px 28px 28px !important;    
            box-shadow: 0 10px 24px rgba(0, 0, 0, 0.3) !important;
            box-sizing: border-box !important;
        }
        .formula-tooltip-wrap {
            position: relative;
            display: inline-flex;
            align-items: center;
        }
        .formula-badge {
            background: rgba(255, 255, 255, 0.08);
            color: #B0B5C9;
            border: 1px solid rgba(255, 255, 255, 0.18);
            padding: 2px 8px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 700;
            cursor: help;
            transition: all 0.2s ease;
            white-space: nowrap;
        }
        .formula-badge:hover {
            background: rgba(96, 165, 250, 0.2);
            color: #60A5FA;
            border-color: #60A5FA;
        }
        .formula-popup {
            visibility: hidden;
            opacity: 0;
            position: absolute;
            top: calc(100% + 8px);
            right: 0;
            width: 390px;
            background: #141620;
            border: 1px solid rgba(96, 165, 250, 0.45);
            border-radius: 12px;
            padding: 14px 16px;
            box-shadow: 0 16px 36px rgba(0, 0, 0, 0.85);
            z-index: 999999;
            transition: all 0.18s ease-in-out;
            pointer-events: none;
            font-size: 12.5px;
            color: #D8DCE8;
            line-height: 1.55;
            text-align: left;
            font-weight: 400;
        }
        .formula-Popup-left { right: auto !important; left: 0 !important; }
        .formula-tooltip-wrap:hover .formula-popup { visibility: visible; opacity: 1; }
        .formula-popup-head {
            font-size: 13px;
            font-weight: 800;
            color: #60A5FA;
            margin-bottom: 6px;
            padding-bottom: 5px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        .saas-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            margin-top: 6px;
            margin-bottom: 12px;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.1);
            background: rgba(18, 19, 28, 0.7);
        }
        .saas-table th {
            background: rgba(255, 255, 255, 0.05);
            color: #A0A4B8;
            font-size: 12px;
            font-weight: 700;
            text-align: left;
            padding: 9px 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .saas-table td {
            padding: 10px 12px;
            font-size: 13px;
            color: #E2E4F0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.06);
            vertical-align: middle;
        }
        .saas-table tr:last-child td { border-bottom: none; }
        .saas-table tr.highlight-row td { background: rgba(56, 239, 125, 0.06); }
        .insight-banner {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.09);
            border-left: 4px solid #38EF7D;
            border-radius: 12px;
            padding: 12px 16px;
            margin-top: 6px;
        }
        .insight-banner.blue-accent { border-left-color: #60A5FA; }
        .insight-banner-title {
            font-size: 13.5px;
            font-weight: 800;
            color: #FFFFFF;
            margin-bottom: 4px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .ai-badge-pill {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(255, 56, 92, 0.14);
            border: 1px solid rgba(255, 56, 92, 0.4);
            color: #FF6B81;
            padding: 5px 14px;
            border-radius: 999px;
            font-size: 12.5px;
            font-weight: 800;
        }
        .stay-curve-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            margin-top: 8px;
        }
        .stay-curve-box {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 10px 14px;
            text-align: center;
        }
        .copy-box {
            background: rgba(15, 16, 24, 0.75);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 12px 15px;
            font-size: 13px;
            color: #E2E4F0;
            line-height: 1.6;
            margin-top: 6px;
        }
        .tag-pill {
            display: inline-block;
            background: rgba(56, 239, 125, 0.1);
            border: 1px solid rgba(56, 239, 125, 0.3);
            color: #38EF7D;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 11.5px;
            font-weight: 700;
            margin-right: 6px;
            margin-bottom: 4px;
        }
        .consult-sub-header {
            background: rgba(255, 255, 255, 0.05);
            border-left: 4px solid #60A5FA;
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 800;
            color: #FFFFFF;
            margin-bottom: 10px;
        }
        .consult-sub-header.green-bar {
            border-left-color: #38EF7D;
        }
    </style>
    """, unsafe_allow_html=True)

    model = load_model()
    f_row = st.session_state.final_features

    # CatBoost AI 적정 예측가 (파인튜닝 모델 실제 MAPE 27.8% 반영)
    MODEL_MAPE = 0.2699
    predicted_price = predict_price_usd(model, f_row)
    low_bound = round(predicted_price * (1 - MODEL_MAPE), 0)
    high_bound = round(predicted_price * (1 + MODEL_MAPE), 0)

    boro = f_row['neighbourhood_group_cleansed']
    hood = f_row['neighbourhood_cleansed']
    rtype = f_row['room_type']
    min_n = int(f_row['minimum_nights_cleansed'])
    dist_km = f_row.get('dist_from_center(km)') or calculate_haversine_distance(st.session_state.pin_lat, st.session_state.pin_lon)

    room_kr_map = {
        "Entire home/apt": "집 전체",
        "Private room": "개인실",
        "Shared room": "다인실",
        "Hotel room": "호텔 / 부티크 숙소",
    }
    rtype_kr = room_kr_map.get(rtype, rtype)

    # 동종 경쟁군 동적 3단계 슬라이딩 티어 및 요인 분해 산출
    hood_center_coords = get_neighborhood_center(hood, boro)
    hood_center_dist = calculate_haversine_distance(
        hood_center_coords[0], hood_center_coords[1]
    )

    comp_base = f_row.copy()
    comp_base['latitude'] = hood_center_coords[0]
    comp_base['longitude'] = hood_center_coords[1]
    comp_base['dist_from_center(km)'] = hood_center_dist

    # 기본형 : 동네 중심 좌표 + 필수 편의시설만 갖춘 숙소 (필수 3, 생활 0, 서비스 0, 프리미엄 0)
    feat_basic = {
        **comp_base,
        'essential_amenities_cnt': 3,
        'living_amenities_cnt': 0,
        'service_amenities_cnt': 0,
        'luxury_amenities_cnt': 0,
    }
    p_basic = predict_price_usd(model, feat_basic)

    # 표준 : 동네 중심 좌표 + 동네 평균 편의시설을 갖춘 숙소 (필수 4, 생활 2, 서비스 2, 프리미엄 0)
    feat_std = {
        **comp_base,
        'essential_amenities_cnt': 4,
        'living_amenities_cnt': 2,
        'service_amenities_cnt': 2,
        'luxury_amenities_cnt': 0,
    }
    p_std = predict_price_usd(model, feat_std)

    # 풀옵션 : 동네 중심 좌표 + 전 카테고리 풀옵션을 갖춘 숙소 (필수 5, 생활 5, 서비스 5, 프리미엄 5)
    feat_high = {
        **comp_base,
        'essential_amenities_cnt': 5,
        'living_amenities_cnt': 5,
        'service_amenities_cnt': 5,
        'luxury_amenities_cnt': 5,
    }
    p_high = predict_price_usd(model, feat_high)
  
    feat_min = {
          **comp_base,
          'essential_amenities_cnt': 0,
          'living_amenities_cnt': 0,
          'service_amenities_cnt': 0,
          'luxury_amenities_cnt': 0,
      }
    p_raw_min = predict_price_usd(model, feat_min)
    p_min = round(
        min(
            p_raw_min,
            p_basic - max(5.0, (p_std - p_basic)),
            predicted_price * 0.94,
        ),
        2,
    )

    # [동적 구간 판별] 기본형 미달 vs 일반(기본형~풀옵션) vs 풀옵션 초과(프라임)
    if predicted_price < p_basic:
      # [모드 1 : 엔트리 구간] 최소형 ── 기본형(중앙 기준) ── 표준
      feat_pin_basic = {
          **f_row,
          'essential_amenities_cnt': 3,
          'living_amenities_cnt': 0,
          'service_amenities_cnt': 0,
          'luxury_amenities_cnt': 0,
      }
      p_pin_bench = predict_price_usd(model, feat_pin_basic)

      active_bench_name = '동종 기본가'
      active_bench_price = p_basic
      bar_left_label, bar_mid_label, bar_right_label = (
          f'최소형(${p_min:,.0f})',
          f'기본형(${p_basic:,.0f})',
          f'표준(${p_std:,.0f})',
      )
      bar_left_val, bar_mid_val, bar_right_val = p_min, p_basic, p_std

    elif predicted_price <= p_high:
      # [모드 2 : 스탠다드 구간] 기본형 ── 표준(중앙 기준) ── 풀옵션
      feat_pin_std = {
          **f_row,
          'essential_amenities_cnt': 4,
          'living_amenities_cnt': 2,
          'service_amenities_cnt': 2,
          'luxury_amenities_cnt': 0,
      }
      p_pin_bench = predict_price_usd(model, feat_pin_std)

      active_bench_name = '동종 표준가'      
      active_bench_price = p_std
      bar_left_label, bar_mid_label, bar_right_label = (
          f'기본형(${p_basic:,.0f})',
          f'표준(${p_std:,.0f})',
          f'풀옵션(${p_high:,.0f})',
      )
      bar_left_val, bar_mid_val, bar_right_val = p_basic, p_std, p_high

    else:
      # [모드 3 : 프라임 구간 (풀옵션 돌파)] 표준 ── 풀옵션(중앙 기준) ── 프라임 상한
      p_prime = round(
          max(
              p_high + max(10.0, (p_high - p_std) * 0.6), predicted_price * 1.06
          ),
          2,
      )

      feat_pin_high = {
          **f_row,
          'essential_amenities_cnt': 5,
          'living_amenities_cnt': 5,
          'service_amenities_cnt': 5,
          'luxury_amenities_cnt': 5,
      }
      p_pin_bench = predict_price_usd(model, feat_pin_high)

      active_bench_name = '동종 풀옵션가'
      active_bench_price = p_high
      bar_left_label, bar_mid_label, bar_right_label = (
          f'표준(${p_std:,.0f})',
          f'풀옵션(${p_high:,.0f})',
          f'프라임(${p_prime:,.0f})',
      )
      bar_left_val, bar_mid_val, bar_right_val = p_std, p_high, p_prime

    # 선택된 기준점 대비 입지 효과 & 편의시설 효과 정밀 분해
    loc_alpha = round(p_pin_bench - active_bench_price, 2)
    amen_alpha = round(predicted_price - p_pin_bench, 2)
    spec_diff_pct = (
        (predicted_price - active_bench_price) / active_bench_price
    ) * 100

    # 3. [항목 9: 가동률 기준 전면 통일] 단기 월 17박(가동률 57%) / 장기 월 30박(1개월 계약)
    SHORT_TERM_STD_DAYS = 17  # Inside Airbnb & AirDNA NYC 연평균 가동률(약 57%) 월 환산 정수 기준
    if min_n >= 30:
        expected_days = 30
        occ_label = "장기 30일(1개월 계약) 기준"
        range_sub_label = f"1개월 계약 매출 <b>${predicted_price*30:,.0f}</b> (호스트 수수료 3% 차감 후 <b>${predicted_price*30*0.97:,.0f}</b>)"
    else:
        expected_days = SHORT_TERM_STD_DAYS
        occ_label = f"NYC 단기 평균 가동률 57%(월 {SHORT_TERM_STD_DAYS}박) 기준"
        range_sub_label = f"비수기(10박) <b>${predicted_price*10:,.0f}</b> ~ 성수기(24박) <b>${predicted_price*24:,.0f}</b>"
    monthly_rev = round(predicted_price * expected_days, 0)

    # 최소 숙박일 수(1박 / 3박 / 7박 / 30박)별 CatBoost 실제 예측 단가 변화
    stay_curve_prices = {}
    for test_n in [1, 3, 7, 30]:
        tmp_f = f_row.copy()
        tmp_f['minimum_nights_cleansed'] = test_n
        stay_curve_prices[test_n] = predict_price_usd(model, tmp_f)

    # 시뮬레이션 1 : 호스트 입력 스펙 기반 단기 vs 장기(30일+) 비교
    is_currently_short = min_n < 30

    # 단기 시나리오 구성
    sim_short_feat = f_row.copy()
    if is_currently_short:
      # 현재 단기 선택 시 : 호스트 입력값 100% 그대로 유지 (상단 KPI와 일치)
      price_short = predicted_price
    else:
      # 현재 장기 선택 시 -> 단기(기본 3박)로 전환 가정
      sim_short_feat['minimum_nights_cleansed'] = 3
      if rtype == 'Entire home/apt':
        # 집 전체는 단기 임대 불가(Local Law 18) -> 개인실·최대 2인으로 합법 전환 비교
        sim_short_feat['room_type'] = 'Private room'
        sim_short_feat['accommodates'] = min(2, int(f_row['accommodates']))
      elif rtype in ['Private room', 'Shared room']:
        sim_short_feat['accommodates'] = min(2, int(f_row['accommodates']))
      price_short = predict_price_usd(model, sim_short_feat)

    sim_short_rtype_kr = room_kr_map.get(
        sim_short_feat['room_type'], sim_short_feat['room_type']
    )
    sim_short_accom = int(sim_short_feat['accommodates'])
    sim_short_min_n = int(sim_short_feat['minimum_nights_cleansed'])
    rev_short_avg = price_short * SHORT_TERM_STD_DAYS

    # 단기 규정 라벨 (호텔/부티크는 상업 숙박이므로 호스트 동거 면제)
    if sim_short_feat['room_type'] == 'Hotel room':
      short_law_badge = '<span style="color:#60A5FA; font-size:12px; font-weight:700;">상업 숙박 (규제 면제)</span>'
    else:
      short_law_badge = '<span style="color:#FF6B81; font-size:12px; font-weight:700;">호스트 동거·2인 이하</span>'

    # (장기(30박+) 시나리오 구성
    sim_long_feat = f_row.copy()
    sim_long_feat['minimum_nights_cleansed'] = 30
    if not is_currently_short:
      # 현재 장기 선택 시 : 호스트 입력값 100% 그대로 유지 (상단 KPI와 일치)
      price_long_entire = predicted_price
    else:
      # 현재 단기 선택 시 -> 동일 룸타입·동일 인원 그대로 30박 장기 전환 시뮬레이션
      price_long_entire = predict_price_usd(model, sim_long_feat)

    sim_long_rtype_kr = room_kr_map.get(
        sim_long_feat['room_type'], sim_long_feat['room_type']
    )
    sim_long_accom = int(sim_long_feat['accommodates'])
    rev_long_entire = price_long_entire * 30
    breakeven_nights = round(rev_long_entire / max(1, price_short), 1)

    # 시뮬레이션 2: 편의시설 업그레이드 ROI
    curr_svc_cnt = int(f_row.get('service_amenities_cnt', 0))
    curr_liv_cnt = int(f_row.get('living_amenities_cnt', 0))
    curr_lux_cnt = int(f_row.get('luxury_amenities_cnt', 0))
    curr_ess_cnt = int(f_row.get('essential_amenities_cnt', 0))

    sim_svc = f_row.copy()
    if curr_svc_cnt < 5:
        sim_svc['service_amenities_cnt'] = min(5, curr_svc_cnt + 2)
        step1_upgrade_label = f"🛠️ 서비스 편의시설 +2개 ({curr_svc_cnt}➔{sim_svc['service_amenities_cnt']}개)"
    elif curr_liv_cnt < 5:
        sim_svc['living_amenities_cnt'] = min(5, curr_liv_cnt + 2)
        step1_upgrade_label = f"🍳 실생활 편의시설 +2개 ({curr_liv_cnt}➔{sim_svc['living_amenities_cnt']}개)"
    else:
        sim_svc['luxury_amenities_cnt'] = min(5, curr_lux_cnt + 1)
        step1_upgrade_label = f"💎 프리미엄 편의시설 +1개 ({curr_lux_cnt}➔{sim_svc['luxury_amenities_cnt']}개)"

    price_plus_svc = predict_price_usd(model, sim_svc)
    gain_svc = max(0.0, round(price_plus_svc - predicted_price, 2))

    sim_lux = f_row.copy()
    sim_lux['service_amenities_cnt'] = min(5, curr_svc_cnt + 2)
    sim_lux['living_amenities_cnt'] = min(5, curr_liv_cnt + 2)
    sim_lux['luxury_amenities_cnt'] = min(5, curr_lux_cnt + 1)
    price_plus_all = predict_price_usd(model, sim_lux)
    gain_all = max(0.0, round(price_plus_all - predicted_price, 2))

    all_selected_labels = []
    missing_candidates = []
    for grp_title, grp_info in AMENITY_GROUPS.items():
        for k_eng, label in grp_info["items"].items():
            if st.session_state.selected_amenities.get(k_eng, False):
                all_selected_labels.append(label)
            else:
                missing_candidates.append(label)
    selected_amen_str = ", ".join(all_selected_labels) if all_selected_labels else "선택된 편의시설 없음"

    missing_service = [
        label for k, label in AMENITY_GROUPS["💼 서비스 편의시설"]["items"].items()
        if not st.session_state.selected_amenities.get(k, False)
    ]
    rec_list = missing_service[:3] if missing_service else missing_candidates[:3]
    rec_items_str = ", ".join(rec_list) if rec_list else "전 카테고리 핵심 옵션 구비 완료"

    with st.spinner("🤖 입력하신 숙소 정보를 토대로 리포트를 작성하고 있습니다."):
        ai_report = generate_ai_host_consulting(
            boro=boro,
            hood=hood,
            rtype_kr=rtype_kr,
            stay_cat=st.session_state.stay_category,
            min_n=min_n,
            dist_km=dist_km,
            accom=int(f_row['accommodates']),
            bedrooms=float(f_row['bedrooms']),
            beds=float(f_row['beds']),
            baths=float(f_row['bathrooms_cleansed']),
            pred_price=predicted_price,
            main_bench=active_bench_price,
            diff_pct=spec_diff_pct,
            price_short=price_short,
            rev_short=rev_short_avg,
            price_long=price_long_entire,
            rev_long=rev_long_entire,
            breakeven_nights=breakeven_nights,
            gain_svc=gain_svc,
            gain_all=gain_all,
            roi_calc_days=expected_days,
            selected_amen_str=selected_amen_str,
            missing_svc_str=rec_items_str,
            bench_name=active_bench_name,
            rtype=rtype
        )

    # ----------------------------------------------------------------------
    # [섹션 1] 확대된 메인 리포트 헤더(구분선 포함) & 3대 핵심 KPI 카드
    # ----------------------------------------------------------------------
    st.markdown("""
        <div class="report-main-header">
            <div class="report-main-title">
                📝 내 숙소 맞춤 리포트
            </div>
            <span class="ai-badge-pill">✨ HostMate AI Engine 분석 완료</span>
        </div>
    """, unsafe_allow_html=True)

    k1, k2, k3 = st.columns(3, gap="medium")

    with k1:
        st.markdown(f"""
            <div class="kpi-card primary-kpi">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span class="kpi-label" style="margin-bottom:0;">✨ 추천 1박 적정 요금 ({rtype_kr})</span>
                    <div class="formula-tooltip-wrap">
                        <span class="formula-badge">ⓘ 산출 근거</span>
                        <div class="formula-popup formula-Popup-left">
                            <div class="formula-popup-head">📐 가격 예측 공식</div>
                            <ul class="hm-list">
                                <li><b>모델</b> : NYC 실거래 매물을 학습·파인튜닝한 CatBoost</li>
                                <li><b>투입 변수</b> : 자치구, 세부 동네, 위경도 좌표, 타임스퀘어 직선거리, 룸타입, 수용인원·침실·침대·욕실 수, 최소 숙박일, 4대 편의시설 카테고리별 개수</li>
                                <li><b>권장 구간(±26.99%)</b> : 파인튜닝 모델의 검증 평균오차율(<b>MAPE 26.99%</b>)을 반영한 가격 범위(<b>${low_bound:,.0f} ~ ${high_bound:,.0f}</b>)</li>
                            </ul>
                        </div>
                    </div>
                </div>
                <div class="kpi-value">$ {predicted_price:,.2f} <span style="font-size:15px; font-weight:500; color:#AAA;">/ 1박</span></div>
                <div class="kpi-sub">
                    <ul class="hm-list">
                        <li>권장 요금 설정 구간 : <b>${low_bound:,.0f} ~ ${high_bound:,.0f} / 1박</b></li>
                        <li>타임스퀘어까지 거리 : <b>{dist_km} km</b> 반영</li>
                    </ul>
                </div>
            </div>
        """, unsafe_allow_html=True)

    with k2:
      # 구간별 맞춤형 포지셔닝 타이틀 및 배지 컬러 결정
      if predicted_price < p_basic:
        if spec_diff_pct >= -5.0:
          pos_str = f"{spec_diff_pct:+.1f}% 기본형 근접"
          badge_color = "#FBBF24"  # 앰버 옐로우
        else:
          pos_str = f"{spec_diff_pct:+.1f}% 옵션 보강 권장"
          badge_color = "#FB923C"  # 오렌지 코랄
      elif predicted_price <= p_high:
        if spec_diff_pct >= 15.0:
          pos_str = f"+{spec_diff_pct:.1f}% 하이엔드 프리미엄"
          badge_color = "#38EF7D"  # 네온 그린
        elif spec_diff_pct >= 5.0:
          pos_str = f"+{spec_diff_pct:.1f}% 동종 시세 상회"
          badge_color = "#34D399"  # 에메랄드 민트
        elif spec_diff_pct >= -5.0:
          pos_str = f"{spec_diff_pct:+.1f}% 표준 시세권"
          badge_color = "#60A5FA"  # 스카이 블루
        else:
          pos_str = f"{spec_diff_pct:+.1f}% 실속형 가격권"
          badge_color = "#FBBF24"  # 앰버 옐로우
      else:
        pos_str = f"+{spec_diff_pct:.1f}% 프라임 입지 특급"
        badge_color = "#38EF7D"  # 네온 그린

      # 동적 기준 게이지 위치 계산
      if predicted_price <= bar_mid_val:
        left_span = max(1.0, bar_mid_val - bar_left_val)
        ratio = (predicted_price - bar_left_val) / left_span
        gauge_pos = int(50 * ratio)
      else:
        right_span = max(1.0, bar_right_val - bar_mid_val)
        ratio = (predicted_price - bar_mid_val) / right_span
        gauge_pos = int(50 + 50 * ratio)
      gauge_pos = min(96, max(6, gauge_pos))

      st.markdown(
          f"""
            <div class="kpi-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span class="kpi-label" style="margin-bottom:0;">📊 {hood} 동종 경쟁군 비교</span>
                    <div class="formula-tooltip-wrap">
                        <span class="formula-badge">ⓘ 비교 조건</span>
                        <div class="formula-popup">
                            <div class="formula-popup-head">📊 동종 경쟁군 비교 조건</div>
                            <ul class="hm-list">
                                <li><b>동일 체급 고정</b> : 내 숙소와 자치구·동네·룸타입({rtype_kr})·인원({ int(f_row['accommodates']) }명)·침실({ int(f_row['bedrooms']) })·침대({ int(f_row['beds']) })·욕실({ f_row['bathrooms_cleansed'] })·최소숙박({min_n}박)을 100% 동일하게 고정</li>
                                <li><b>최소형 (${p_min:,.0f})</b> : 동네 중심 좌표 + 편의시설 미구비 숙소 (필수 0 · 생활 0 · 서비스 0 · 프리미엄 0)</li>
                                <li><b>기본형 (${p_basic:,.0f})</b> : 동네 중심 좌표 + 필수 편의시설만 갖춘 숙소 (필수 3 · 생활 0 · 서비스 0 · 프리미엄 0)</li>
                                <li><b>표준 (${p_std:,.0f})</b> : 동네 중심 좌표 + 동네 평균 편의시설을 갖춘 숙소 (필수 4 · 생활 2 · 서비스 2 · 프리미엄 0)</li>
                                <li><b>풀옵션 (${p_high:,.0f})</b> : 동네 중심 좌표 + 전 옵션을 모두 갖춘 숙소 (필수 5 · 생활 5 · 서비스 5 · 프리미엄 5)</li>
                                <li><b>동적 스케일 전환</b> : 내 예측가가 기본형 미만이면 <b>기본형</b>을, 일반 구간이면 <b>표준</b>을, 풀옵션 초과 시 <b>풀옵션</b>을 중앙 기준점으로 자동 전환합니다.</li>
                            </ul>
                            <div class="formula-popup-head" style="margin-top:10px;">🔍 요인 분석 (내 숙소 vs {active_bench_name})</div>
                            <ul class="hm-list">
                                <li><b>세부 입지 효과 ({loc_alpha:+.2f}$)</b> : 동네 중심점 대비 내가 찍은 핀 위치(도심 거리 {dist_km}km 등)가 만든 가격 차이</li>
                                <li><b>편의시설 효과 ({amen_alpha:+.2f}$)</b> : {active_bench_name} 옵션 대비 내가 선택한 보유 편의시설(필수 {curr_ess_cnt}·생활 {curr_liv_cnt}·서비스 {curr_svc_cnt}·프리미엄 {curr_lux_cnt})이 만든 가격 차이</li>
                            </ul>
                        </div>
                    </div>
                </div>
                <div class="kpi-value" style="color:{badge_color}; font-size:31px;">{pos_str}</div>
                <div style="margin-top:8px; margin-bottom:4px;">
                    <div style="display:flex; justify-content:space-between; font-size:11px; color:#8E92A8; margin-bottom:3px;">
                        <span>{bar_left_label}</span>
                        <span style="color:#FFFFFF; font-weight:700;">📍 {bar_mid_label}</span>
                        <span>{bar_right_label}</span>
                    </div>
                    <div style="width:100%; height:7px; background:rgba(255,255,255,0.08); border-radius:999px; position:relative;">
                        <div style="width:{gauge_pos}%; height:100%; background:linear-gradient(90deg, #60A5FA 0%, {badge_color} 100%); border-radius:999px;"></div>
                    </div>
                </div>
                <div class="kpi-sub" style="margin-top:6px;">
                        ① {active_bench_name} : <b>${active_bench_price:,.2f}/박</b>,  ② 요인 분석 : 입지 <b>{loc_alpha:+.2f}$</b> / 편의시설 <b>{amen_alpha:+.2f}$</b>
                </div>
            </div>
        """,
          unsafe_allow_html=True,
      )

    with k3:
        st.markdown(f"""
            <div class="kpi-card">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span class="kpi-label" style="margin-bottom:0;">💰 월간 예상 총 수익</span>
                    <div class="formula-tooltip-wrap">
                        <span class="formula-badge">ⓘ 산출 근거</span>
                        <div class="formula-popup">
                            <div class="formula-popup-head">💰 월 예상 매출 산출 공식</div>
                            <ul class="hm-list">
                                <li><b>단기 숙박(30박 미만)</b> : 뉴욕시 단기 숙소 연평균 객실 가동률 통계치인 <b>약 57% (월 17박)</b> 적용</li>
                                <li><b>장기 숙박(30박 이상)</b> : 1개월(30박) 단일 계약 기준 적용</li>
                                <li><b>계절 변동폭</b> : 비수기(월 10박) ~ 성수기(월 24박)</li>
                            </ul>
                        </div>
                    </div>
                </div>
                <div class="kpi-value">$ {monthly_rev:,.0f} <span style="font-size:15px; font-weight:500; color:#AAA;">/ 월</span></div>
                <div class="kpi-sub">
                    <ul class="hm-list">
                        <li>산출 기준 : <b>{occ_label}</b></li>
                        <li>{range_sub_label}</li>
                    </ul>
                </div>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)

    # ----------------------------------------------------------------------
    # 최소 숙박일 수 단가 변화 + 단기 vs 장기 & 어메니티 업그레이드 효과 분석
    # ----------------------------------------------------------------------
    with st.container(key="sim_group_container"):
        st.markdown(f"""
            <div class="report-section-card" style="padding: 14px 20px; margin-bottom: 16px; height: auto;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                    <div style="font-size:15.5px; font-weight:800; color:#FFFFFF;">
                        📉 최소 숙박일 수 설정에 따른 적정 단가
                    </div>
                    <div class="formula-tooltip-wrap">
                        <span class="formula-badge">ⓘ 산출 근거</span>
                        <div class="formula-popup">
                            <div class="formula-popup-head">📉 최소 숙박일수 민감도</div>
                            <ul class="hm-list">
                                <li>설정하신 숙소 조건에서 <b>최소 숙박일 수</b>만 1박, 3박, 7박, 30박으로 변경하여 HostMate AI Engine이 추론한 결과입니다.</li>
                            </ul>
                        </div>
                    </div>
                </div>
                <div class="stay-curve-grid">
                    <div class="stay-curve-box">
                        <div style="font-size:11.5px; color:#9EA3B8; font-weight:600;">⚡ 최소 1박 (초단기 회전)</div>
                        <div style="font-size:18px; font-weight:800; color:#FFFFFF; margin-top:2px;">${stay_curve_prices[1]:,.2f} <span style="font-size:11.5px; color:#888;">/박</span></div>
                    </div>
                    <div class="stay-curve-box">
                        <div style="font-size:11.5px; color:#38EF7D; font-weight:700;">🔥 최소 3박 (단기 표준)</div>
                        <div style="font-size:18px; font-weight:800; color:#38EF7D; margin-top:2px;">${stay_curve_prices[3]:,.2f} <span style="font-size:11.5px; color:#888;">/박</span></div>
                    </div>
                    <div class="stay-curve-box">
                        <div style="font-size:11.5px; color:#60A5FA; font-weight:700;">🧳 최소 7박 (주간 체류)</div>
                        <div style="font-size:18px; font-weight:800; color:#60A5FA; margin-top:2px;">${stay_curve_prices[7]:,.2f} <span style="font-size:11.5px; color:#888;">/박</span></div>
                    </div>
                    <div class="stay-curve-box">
                        <div style="font-size:11.5px; color:#FBBF24; font-weight:700;">🏠 최소 30박 (동일 룸타입 장기)</div>
                        <div style="font-size:18px; font-weight:800; color:#FBBF24; margin-top:2px;">${stay_curve_prices[30]:,.2f} <span style="font-size:11.5px; color:#888;">/박</span></div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        col_sim1, col_sim2 = st.columns(2, gap="medium")

        with col_sim1:
          short_row_cls = "highlight-row" if min_n < 30 else ""
          long_row_cls = "highlight-row" if min_n >= 30 else ""
          short_tag = " (현재 설정)" if min_n < 30 else " (전환 시)"
          long_tag = " (현재 설정)" if min_n >= 30 else " (전환 시)"

          if breakeven_nights > 30:
            breakeven_li_html = (
                f"<li><b>단기 {sim_short_rtype_kr}(${price_short:,.1f}/박)</b>"
                " 운영으로 장기 수익을 넘기려면 산술적으로 월"
                f" <b>{breakeven_nights}박 이상</b> 예약이 차야 하는데, 이는 한"
                " 달(30일)을 초과하여 <b>단기 운영으로는 장기 수익을 넘기"
                f" 어렵기 때문에</b> {sim_long_rtype_kr} 장기(30일+) 운영을"
                " 권장합니다.</li>"
            )
          else:
            breakeven_li_html = (
                f"<li><b>단기 {sim_short_rtype_kr}(${price_short:,.1f}/박)</b>"
                " 운영으로 장기 운영 수익을 넘기려면 한 달 최소"
                f" <b>{breakeven_nights}박 이상</b>(월 가동률"
                f" {(breakeven_nights/30)*100:.0f}% 이상) 예약이 차야"
                " 합니다.</li>"
            )

          st.markdown(
              f"""
                <div class="report-section-card">
                    <div class="report-card-header">
                        <div>
                            <div class="report-card-title">
                                <span>🔄 단기 vs 장기(30일+) 수익 비교</span>
                                <div class="formula-tooltip-wrap">
                                    <span class="formula-badge">ⓘ 산출 근거</span>
                                    <div class="formula-popup formula-Popup-left">
                                        <div class="formula-popup-head">🔄 단기 - 장기 전환 시뮬레이션</div>
                                        <ul class="hm-list">
                                            <li><b>단기 시나리오</b> : 호스트님의 숙소 조건에서 단기 운영 규정(<code style="color:#FF6B81;">room_type='{sim_short_feat['room_type']}', accommodates={sim_short_accom}, min_nights={sim_short_min_n}</code>) 적용 후 CatBoost 추론(<b>${price_short:,.2f}</b> × {SHORT_TERM_STD_DAYS}일)</li>
                                            <li><b>장기 시나리오</b> : 동일 숙소를 30박 이상 장기 임대로 운영 시(<code style="color:#38EF7D;">room_type='{sim_long_feat['room_type']}', accommodates={sim_long_accom}, min_nights=30</code>) CatBoost 추론(<b>${price_long_entire:,.2f}</b> × 30일)</li>
                                            <li><b>손익분기점({breakeven_nights}박)</b> : 장기 월매출(${rev_long_entire:,.0f}) ÷ 단기 1박요금(${price_short:,.2f})</li>
                                        </ul>
                                    </div>
                                </div>
                            </div>
                            <div class="report-card-sub">입력하신 숙소 조건을 기준으로 단기 운영(월 {SHORT_TERM_STD_DAYS}박 평균)과 장기 임대(30박) 수익성 비교</div>
                        </div>
                        <span class="live-badge">손익분기 {breakeven_nights}박</span>
                    </div>
                    <table class="saas-table">
                        <thead>
                            <tr>
                                <th>운영 시나리오</th>
                                <th>1박 요금</th>
                                <th>기준 가동 일수</th>
                                <th>월 예상 매출</th>
                                <th>뉴욕시 규정</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr class="{short_row_cls}">
                                <td><b>단기 운영{short_tag}</b> ({sim_short_rtype_kr}·{sim_short_accom}인, {sim_short_min_n}박+)</td>
                                <td>${price_short:,.2f}</td>
                                <td>월 {SHORT_TERM_STD_DAYS}일 (57%)</td>
                                <td style="font-weight:800; color:#FFFFFF;">${rev_short_avg:,.0f} / 월</td>
                                <td>{short_law_badge}</td>
                            </tr>
                            <tr class="{long_row_cls}">
                                <td><b>장기 운영{long_tag}</b> ({sim_long_rtype_kr}·{sim_long_accom}인, 30박+)</td>
                                <td>${price_long_entire:,.2f}</td>
                                <td>월 30일 (장기 계약)</td>
                                <td style="font-weight:800; color:#38EF7D;">${rev_long_entire:,.0f} / 월</td>
                                <td><span style="color:#38EF7D; font-size:12px; font-weight:700;">30일+ 규제 면제</span></td>
                            </tr>
                        </tbody>
                    </table>
                    <div class="insight-banner blue-accent">
                        <div class="insight-banner-title">💡 단기 vs 장기 손익분기점 진단</div>
                        <ul class="hm-list">
                            <li><b>{sim_long_rtype_kr} 30일 이상 장기 임대</b> 시 1회 계약으로 <b>월 ${rev_long_entire:,.0f}</b>(1박당 ${price_long_entire:,.1f})의 안정적인 매출 확보가 가능합니다.</li>
                            {breakeven_li_html}
                        </ul>
                    </div>
                </div>
            """,
              unsafe_allow_html=True,
          )

        with col_sim2:
            priority_advice_html = _format_bullets_to_html(ai_report.get('priority_item_advice', ''))
            st.markdown(f"""
                <div class="report-section-card">
                    <div class="report-card-header">
                        <div>
                            <div class="report-card-title">
                                <span>✨ 어메니티 업그레이드 효과 분석</span>
                                <div class="formula-tooltip-wrap">
                                    <span class="formula-badge">ⓘ 산출 근거</span>
                                    <div class="formula-popup">
                                        <div class="formula-popup-head">✨ 어매니티 업그레이드 효과 추론</div>
                                        <ul class="hm-list">
                                            <li>다른 모든 조건을 고정한 상태에서 <b>편의시설 카운트 변수만 증가시켜 나온 실제 예측가 차액</b></li>
                                            <li>현재 보유 개수 : 서비스({curr_svc_cnt}/5), 실생활({curr_liv_cnt}/5), 프리미엄({curr_lux_cnt}/5)</li>
                                            <li>월 추가 수익은 <b>월 {expected_days}박 가동 기준</b>(<code style="color:#38EF7D;">1박 요금 상승폭 × {expected_days}일</code>)으로 산출</li>
                                        </ul>
                                    </div>
                                </div>
                            </div>
                            <div class="report-card-sub">편의시설을 보강했을 때 기대되는 1박 요금 상승폭과 월 추가 수익 분석</div>
                        </div>
                        <span class="premium-badge" style="font-size:12px; padding:4px 10px;">최대 +${gain_all*expected_days:,.0f} / 월 ▲</span>
                    </div>
                    <table class="saas-table">
                        <thead>
                            <tr>
                                <th>옵션 업그레이드 단계</th>
                                <th>1박 요금</th>
                                <th>1박 요금 상승폭</th>
                                <th>월 추가 수익</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>현재 옵션</td>
                                <td>${predicted_price:,.2f}</td>
                                <td style="color:#777A8B;">-</td>
                                <td style="color:#777A8B;">-</td>
                            </tr>
                            <tr class="highlight-row">
                                <td><b>{step1_upgrade_label}</b></td>
                                <td>${price_plus_svc:,.2f}</td>
                                <td style="color:#38EF7D; font-weight:700;">+${gain_svc:,.2f} / 박</td>
                                <td style="color:#38EF7D; font-weight:800;">+${gain_svc * expected_days:,.0f} / 월</td>
                            </tr>
                            <tr>
                                <td><b>💎 서비스(+2) · 실생활(+2) · 프리미엄(+1)</b></td>
                                <td>${price_plus_all:,.2f}</td>
                                <td style="color:#60A5FA; font-weight:700;">+${gain_all:,.2f} / 박</td>
                                <td style="color:#60A5FA; font-weight:800;">+${gain_all * expected_days:,.0f} / 월</td>
                            </tr>
                        </tbody>
                    </table>
                    <div class="insight-banner">
                        <div class="insight-banner-title">🚀 우선 도입 추천 편의시설 : {rec_items_str}</div>
                        {priority_advice_html}
                    </div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='margin-top: 18px;'></div>", unsafe_allow_html=True)

        # 순수익 계산기
        with st.container(border=True, key="net_profit_card"):
            st.markdown("""
                <div style="font-size:17px; font-weight:800; color:#FFFFFF; margin-bottom:4px;">
                    🧮 월 순수익 계산기
                </div>
                <div style="font-size:12.5px; color:#9EA3B8; margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.08);">
                    희망 1박 요금, 월 예상 예약 일수, 월 고정 지출을 직접 조절하여 Airbnb 수수료(3%) 및 비용을 제외한 실제 순수익을 계산해 보세요.
                </div>
            """, unsafe_allow_html=True)

            calc_c1, calc_c2, calc_c3 = st.columns(3, gap="medium")
            with calc_c1:
                custom_nightly = st.number_input(
                    "💵 희망 1박 요금 설정 ($)",
                    min_value=20.0,
                    max_value=2000.0,
                    value=float(round(predicted_price, 0)),
                    step=5.0,
                    key="sim_calc_price"
                )
            with calc_c2:
                default_occ_days = 30 if min_n >= 30 else SHORT_TERM_STD_DAYS
                custom_days = st.slider(
                    "📅 월 예상 예약 일수 (박/월)",
                    min_value=1,
                    max_value=30,
                    value=default_occ_days,
                    key="sim_calc_days"
                )
            with calc_c3:
                default_expense = round(predicted_price * default_occ_days * 0.35, -1)
                custom_expense = st.number_input(
                    "🏠 월 고정 지출 (공과금, 소모품비 등, $)",
                    min_value=0.0,
                    max_value=20000.0,
                    value=float(default_expense),
                    step=50.0,
                    key="sim_calc_expense"
                )

            gross_m = custom_nightly * custom_days
            airbnb_fee_m = round(gross_m * 0.03, 0)
            net_profit_m = gross_m - airbnb_fee_m - custom_expense
            net_profit_y = net_profit_m * 12
            margin_pct = (net_profit_m / gross_m * 100) if gross_m > 0 else 0.0
            net_color = "#38EF7D" if net_profit_m >= 0 else "#EF4444"

            st.markdown(f"""
                <div style="display:grid; grid-template-columns: repeat(4, 1fr); gap:16px; margin: 12px 6px 8px 6px; padding-top:16px; border-top:1px solid rgba(255,255,255,0.08);">
                    <div class="stay-curve-box" style="padding: 14px 16px;">
                        <div style="font-size:12px; color:#9EA3B8;">총 예약 매출 (월 {custom_days}박)</div>
                        <div style="font-size:21px; font-weight:800; color:#FFFFFF; margin-top:4px;">$ {gross_m:,.0f}</div>
                    </div>
                    <div class="stay-curve-box" style="padding: 14px 16px;">
                        <div style="font-size:12px; color:#9EA3B8;">플랫폼 수수료(3%) + 고정 지출</div>
                        <div style="font-size:21px; font-weight:800; color:#FF6B81; margin-top:4px;">- $ {airbnb_fee_m + custom_expense:,.0f}</div>
                    </div>
                    <div class="stay-curve-box" style="padding: 14px 16px; border-color:{net_color}; background:rgba(56,239,125,0.06);">
                        <div style="font-size:12px; color:{net_color}; font-weight:700;">💎 월 예상 순수익 (순이익률 {margin_pct:.1f}%)</div>
                        <div style="font-size:23px; font-weight:800; color:{net_color}; margin-top:4px;">$ {net_profit_m:,.0f} <span style="font-size:12px;">/ 월</span></div>
                    </div>
                    <div class="stay-curve-box" style="padding: 14px 16px;">
                        <div style="font-size:12px; color:#60A5FA; font-weight:700;">📈 연간 누적 기대 순수익 (12개월)</div>
                        <div style="font-size:21px; font-weight:800; color:#60A5FA; margin-top:4px;">$ {net_profit_y:,.0f} <span style="font-size:12px;">/ 년</span></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)


    # ----------------------------------------------------------------------
    # [그룹 2] 반투명 박스: 상단 2열(좌: AI 종합 리포트 / 우: AI 리스팅 추천) + 하단 1줄 전체(월 순수익 시뮬레이터)
    # ----------------------------------------------------------------------
    with st.container(key="bottom_group_container"):
        bot_left, bot_right = st.columns([1, 1], gap="medium")

        # [좌측 컬럼] AI 호스트 맞춤 운영 & 포지셔닝 종합 리포트
        with bot_left:
            loc_strategy_html = _format_bullets_to_html(ai_report.get('location_policy_strategy', ''))
            space_diag_html = _format_bullets_to_html(ai_report.get('space_comfort_diagnosis', ''))

            st.markdown(f"""
                <div class="report-section-card">
                    <div class="report-card-header" style="margin-bottom:14px;">
                        <div>
                            <div class="report-card-title" style="font-size:17.5px;">📋 운영 & 포지셔닝 종합 리포트</div>
                            <div class="report-card-sub">상권 입지·뉴욕시 단기 임대 규정(Local Law 18)·공간 구성을 종합한 맞춤형 호스팅 전략입니다.</div>
                        </div>
                    </div>
                    <div class="consult-sub-header">
                        🗽 지역 상권 & 뉴욕시 단기 임대 규정(Local Law 18) 맞춤 전략
                    </div>
                    <div style="margin-bottom: 16px; padding-left: 4px;">
                        {loc_strategy_html}
                    </div>
                    <hr style="border-color: rgba(255,255,255,0.08); margin: 14px 0;">
                    <div class="consult-sub-header green-bar">
                        📐 공간 구성 및 투숙 쾌적도 정밀 진단
                    </div>
                    <div style="padding-left: 4px;">
                        {space_diag_html}
                    </div>
                </div>
            """, unsafe_allow_html=True)

        # [우측 컬럼] AI 에어비앤비 리스팅 제목(한국어 전용) & 숙소 소개글 추천
        with bot_right:
            tags_list = ai_report.get("highlight_tags", [f"🚇 도심 {dist_km}km", f"🏠 {hood} 감성 숙소", f"✨ {rtype_kr}"])
            tags_html = "".join([f'<span class="tag-pill">{t}</span>' for t in tags_list])

            st.markdown(f"""
                <div class="report-section-card">
                    <div class="report-card-header" style="margin-bottom:12px;">
                        <div>
                            <div class="report-card-title" style="font-size:17.5px;">✍️ Airbnb 리스팅 제목 & 디스크립션 초안</div>
                            <div class="report-card-sub">게스트의 클릭과 예약 전환을 유도하는 맞춤형 카피라이팅 초안입니다.</div>
                        </div>
                        <span class="ai-badge-pill">📋 참고용</span>
                    </div>
                    <div style="margin-bottom:12px;">
                        {tags_html}
                    </div>
                    <div style="background:rgba(255,56,92,0.08); border:1px solid rgba(255,56,92,0.3); border-radius:12px; padding:12px 16px; margin-bottom:14px;">
                        <div style="font-size:11.5px; font-weight:800; color:#FF6B81; margin-bottom:4px;">📌 추천 리스팅 제목 (한글 / 영문)</div>
                        <div style="font-size:16px; font-weight:800; color:#FFFFFF; margin-bottom:3px;">"{ai_report.get('listing_title_kr', '')}"</div>
                        <div style="font-size:13px; font-weight:600; color:#D0D3E2;">"{ai_report.get('listing_title_en', '')}"</div>
                    </div>
                    <div style="margin-bottom:12px;">
                        <div style="font-size:12.5px; font-weight:800; color:#38EF7D;">🇰🇷 숙소 디스크립션</div>
                        <div class="copy-box">{ai_report.get('listing_desc_kr', '')}</div>
                    </div>
                    <div>
                        <div style="font-size:12.5px; font-weight:800; color:#60A5FA;">🇺🇸 Accommodation Description</div>
                        <div class="copy-box">{ai_report.get('listing_desc_en', '')}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='margin-top: 16px;'></div>", unsafe_allow_html=True)

    boro_kr_map = {
        "Manhattan": "맨해튼",
        "Brooklyn": "브루클린",
        "Queens": "퀸즈",
        "Bronx": "브롱크스",
        "Staten Island": "스태튼 아일랜드"
    }
    selected_boro_kr = boro_kr_map.get(st.session_state.selected_borough, st.session_state.selected_borough)

    b_col1, _, b_col2 = st.columns([0.9, 3.2, 0.9])
    with b_col1:
        if st.button("⬅️ 숙소 조건 수정하기", key="btn_report_edit", width='stretch'):
            st.session_state.page = 'detail_step'
            st.session_state.input_step = 2
            sync_url_params()
            st.rerun()
    with b_col2:
        # 다른 숙소 확인하기 클릭 시: 자치구만 유지하고 1단계(세부 동네 선택 지도)로 완전 초기화
        if st.button(f"{selected_boro_kr} 내 다른 숙소 확인하기", key="btn_report_other", type="primary", width='stretch'):
            st.session_state.selected_hood = "선택해주세요"
            st.session_state.pin_lat = None
            st.session_state.pin_lon = None
            st.session_state.pin_address = None
            st.session_state.distance_to_ts = None
            st.session_state.final_features = None
            st.session_state.boro_zoom = None
            st.session_state.boro_center = None
            st.session_state.init_boro_zoom = None
            st.session_state.init_boro_center = None
            st.session_state.detail_zoom = 15
            st.session_state.detail_center = None
            st.session_state.init_detail_zoom = 15
            st.session_state.init_detail_center = None
            st.session_state.input_step = 0
            st.session_state.stay_category = "단기 숙박 (30일 미만)"
            st.session_state.min_nights = 3
            st.session_state.room_type = "Private room"
            st.session_state.accommodates = 1
            st.session_state.bedrooms = 1
            st.session_state.beds = 1
            st.session_state.bathrooms = 1.0
            st.session_state.selected_amenities = {}
            st.session_state.show_acc_warning = False
            for w_key in ["confirm_acc", "confirm_bed", "confirm_bds", "confirm_bath", "sim_calc_price", "sim_calc_days", "sim_calc_expense"]:
                if w_key in st.session_state:
                    del st.session_state[w_key]
            st.session_state.page = 'borough_map'
            sync_url_params()
            st.rerun()
