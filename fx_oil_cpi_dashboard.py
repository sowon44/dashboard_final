"""
USD/CNY, USD/JPY, WTI, 국내 소비자물가지수(CPI) 통합 대시보드 (2023.01 ~ 2026.08)
================================================================================
과제 주제: "USD/CNY·USD/JPY 환율, WTI 국제유가, 국내 소비자물가지수(CPI) 추이와
           주요 변동 요인을 한 화면에서 비교 분석"
분석 기간: 2023-01-01 ~ 2026-08-31 (CPI는 2020년 이후 분기 기준 전체 표시)

이 대시보드는 네 가지 핵심 거시지표(USD/CNY, USD/JPY, WTI, 국내 CPI)를
① 상단 KPI 카드, ② 중앙 2x2 시계열 차트, ③ 하단 구매 전략 방향(Action Plan)
구조로 제시합니다.

[수정/설계 원칙]
1. 사실(Fact, 이벤트 자체의 발생/발표)과 해석(Opinion, 그 효과에 대한 시장 해석)을
   분리하여 각각 "발생 사실"과 "시장 해석" 필드로 구분 표시합니다.
2. 정책·시장 효과는 단정적으로 서술하지 않고, "~로 해석되었다", "~기대가 반영되었다"
   등 추정·해석 표현을 사용합니다.
3. 분석 종료일(2026-08-31) 기준 과거 데이터와, CPI처럼 발표 주기상 지연되는 지표는
   "최신 발표 기준" 배지로 명확히 구분 표시합니다.
4. 각 이벤트에는 출처(source) 필드를 추가하되, 공개 뉴스·리서치 보도를
   요약한 참고용 자료임을 명시합니다(원문 확인 권장).
5. Yahoo Finance 'USDCNY=X' 티커는 간헐적으로 스파이크성 오류값을 반환하는 사례가
   보고되어 있어, 직전 구간 롤링 중앙값 대비 통계적으로 비정상적인 종가는 데이터
   이상치로 간주하여 보정합니다. 과거에는 "2025년 이후 7.25~7.35 박스권(완만한
   우상향)"이라는 고정 범위를 가정했으나, 실제로는 2025년 하반기 이후 달러
   약세·위안화 강세 흐름 속에 USD/CNY가 7위안 아래로 내려가 2026년에는 6.7~7.0위안대
   에서 등락하는 추세로 확인되어(관련 보도 다수), 고정 박스권 가정을 폐기하고 추세에
   맞춰 스스로 갱신되는 롤링 기준 방식으로 교체했습니다(자세한 내용은 sanitize_usdcny
   함수 주석 참고).
6. 하단 "구매 전략 방향(Action Plan)" 카드는 각 지표의 현재 수준·변동 방향에
   대한 규칙 기반 요약이며, 개별 기업의 실제 구매 의사결정을 대체하지 않는
   참고용 가이드입니다. 각 카드에는 방향성을 한눈에 보여주는 짧은 태그를 함께
   표시합니다.
7. 하단에는 4대 지표 간 상관관계 분석과, 선행지표(유가·환율)로 후행지표(CPI)를
   가늠해보는 참고용 프레임워크를 추가로 제공합니다. 통계적 상관관계에 기반한
   참고 자료이며 인과관계를 단정하거나 실제 물가를 예측·보증하지 않습니다.

데이터 출처 안내
----------------
- USD/CNY, USD/JPY: Yahoo Finance(yfinance) 실시간/과거 시세
  (USD/CNY = "USDCNY=X", USD/JPY = "USDJPY=X")
- WTI 국제유가: 한국석유공사 PETRONET(국제석유통계 > 국제석유가격 > 일일국제원유가격)
  제공 자료를 바탕으로 정리한 일별 종가(data/wti_prices.csv)
- 국내 소비자물가지수(CPI, 2020=100, 전국): KOSIS(국가데이터처) 소비자물가조사
  분기·연간 지수(data/cpi_kr.csv)

주요 변동 요인 이벤트는 각 시기의 뉴스/리서치 보도를 바탕으로 정리한
참고용 요약이며, 정확한 수치·인과관계는 공식 통계·1차 자료 확인을 권장합니다.

파일 구성
----------------
fx_oil_cpi_dashboard.py       (본 스크립트)
data/wti_prices.csv           (WTI 일별 종가, 2023-01-03 ~ 2026-08-31)
data/cpi_kr.csv                (국내 CPI 분기 지수, 2020-03-31 ~ 2025-12-31)
※ data/ 폴더를 스크립트와 같은 위치에 두고 실행해야 WTI·CPI 패널이 표시됩니다.

실행 방법
----------------
pip install streamlit yfinance plotly pandas numpy
streamlit run fx_oil_cpi_dashboard.py
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from pathlib import Path

# ----------------------------------------------------------------------------
# 기본 설정
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="USD/CNY·USD/JPY·WTI·CPI 통합 대시보드",
    page_icon="💱",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = Path(__file__).resolve().parent / "data"

TICKERS = {"USD/CNY": "USDCNY=X", "USD/JPY": "USDJPY=X"}
CURRENCY_COLORS = {"USD/CNY": "#f59f00", "USD/JPY": "#4dabf7"}
WTI_COLOR = "#e8590c"
CPI_COLOR = "#20c997"

DEFAULT_START = datetime(2023, 1, 1)
DEFAULT_END = datetime(2026, 8, 31)          # 분석 종료일 (고정 데이터 기준일)
ANALYSIS_ASOF_LABEL = "2026-08-31"
CPI_ASOF_LABEL = "2025년 4분기 (최신 발표치, 2026-09-10 조회 기준)"

# 참고용 최신 시세 스냅샷(2026년 8월 기준, 외신·환율 정보 사이트 종합) — 분석용
# 과거 시계열과는 별개로 사이드바 안내 등에 참고치로만 사용한다.
# USD/CNY: 2025년 하반기 이후 달러 약세·위안화 강세 흐름 속에 7위안선이 무너져
#          2026년에는 대체로 6.7~7.0위안대에서 등락 중(과거 가정했던 7.25~7.35
#          박스권과는 반대 방향의 흐름으로 확인됨).
# USD/JPY: BOJ의 반복적 정책금리 인상(2026-06 1.0%, 31년래 최고)에도 불구하고
#          엔 캐리트레이드 등의 영향으로 엔화 약세 압력이 이어지며 2026년 상반기~
#          한여름 기준 160엔대 초중반에서 거래.
REALTIME_REFERENCE = {
    "USD/CNY": 6.78,
    "USD/JPY": 161.5,
}

# 이상치 탐지는 고정된 절대 범위가 아니라, 각 시점 직전 구간의 롤링 중앙값 대비
# 괴리 정도(중앙값 절대편차, MAD 기반)로 판단한다. 특정 연도의 실제 시장 박스권을
# 코드에 하드코딩하면(과거 "2025년 이후 7.25~7.35" 가정처럼) 이후 추세가 바뀔 때
# 정상적인 실제 데이터를 이상치로 오인해 잘못 보정하는 문제가 생길 수 있기 때문이다.
CNY_ROLLING_WINDOW = 20          # 이상치 판단 기준이 되는 롤링 윈도우(거래일)
CNY_OUTLIER_MAD_MULTIPLIER = 6.0  # 롤링 중앙값 대비 이 배수(스케일 조정 MAD 기준) 이상 벗어나면 이상치로 간주

PERIOD_MAP = {
    "전체 (2023.01–2026.08)": "full",
    "최근 1년": "1y",
    "최근 6개월": "6mo",
    "최근 1개월": "1mo",
    "사용자 지정": "custom",
}

# ----------------------------------------------------------------------------
# 주요 변동 요인 이벤트 (조사 기반 요약)
# 각 이벤트는 "fact"(발생 사실)와 "opinion"(시장 해석·기대) 필드를 분리한다.
# bucket: 통화정책 / 무역정책 / 시장심리 / 에너지 4구분 비중 시각화용 카테고리
# source: 참고 출처(요약, 원문 확인 권장)
# ----------------------------------------------------------------------------
EVENTS = [
    # -- USD/JPY 관련 --
    {"date": "2024-03-19", "currency": "USD/JPY", "category": "통화정책", "bucket": "통화정책",
     "title": "BOJ, 마이너스 금리 및 수익률곡선통제(YCC) 종료",
     "fact": "일본은행이 2007년 이후 처음으로 정책금리를 인상하고 YCC를 종료했다.",
     "opinion": "초완화적 통화정책 정상화 착수로, 엔화 약세의 구조적 배경이 변화할 가능성이 제기된 것으로 해석되었다.",
     "source": "일본은행(BOJ) 발표 및 로이터·블룸버그 보도 종합"},
    {"date": "2024-07-03", "currency": "USD/JPY", "category": "시장동향", "bucket": "시장심리",
     "title": "USD/JPY 연중 고점 약 161.6엔 기록",
     "fact": "USD/JPY 환율이 장중 약 161.6엔까지 상승했다.",
     "opinion": "미·일 금리 차 확대와 엔 캐리트레이드 지속 기대가 엔화 약세 요인으로 반영된 것으로 해석되었다.",
     "source": "Yahoo Finance 시세 및 외신 보도 종합"},
    {"date": "2024-07-31", "currency": "USD/JPY", "category": "통화정책", "bucket": "통화정책",
     "title": "BOJ 추가 금리 인상(0.25%)",
     "fact": "일본은행이 정책금리를 추가로 인상했다.",
     "opinion": "미·일 금리차 축소 기대가 확대되며 엔 캐리트레이드 청산 가능성이 부각된 것으로 해석되었다.",
     "source": "일본은행(BOJ) 발표 및 로이터 보도 종합"},
    {"date": "2024-08-05", "currency": "USD/JPY", "category": "시장동향", "bucket": "시장심리",
     "title": "글로벌 증시 급락 · 엔 캐리트레이드 청산 쇼크",
     "fact": "니케이지수 등 글로벌 증시가 급락하고 엔화가 단기간 급격히 강세로 전환했다.",
     "opinion": "BOJ 긴축 우려와 미국 경기둔화 우려가 겹치며 캐리트레이드 청산이 촉발된 것으로 해석되었다.",
     "source": "니혼게이자이·블룸버그 보도 종합"},
    {"date": "2024-09-16", "currency": "USD/JPY", "category": "시장동향", "bucket": "시장심리",
     "title": "USD/JPY 연중 저점 약 139.6엔",
     "fact": "USD/JPY 환율이 장중 약 139.6엔까지 하락했다.",
     "opinion": "BOJ 정책 정상화 기대와 미국 경기 모멘텀 둔화 신호가 겹치며 엔화 강세 압력으로 반영된 것으로 해석되었다.",
     "source": "Yahoo Finance 시세 및 외신 보도 종합"},
    {"date": "2024-11-06", "currency": "공통", "category": "정치/정책", "bucket": "시장심리",
     "title": "미국 대선 결과 발표",
     "fact": "미국 대통령 선거 결과가 발표되었다.",
     "opinion": "관세 확대 및 재정지출 증가 기대가 달러 강세 요인으로 반영된 것으로 해석되었다.",
     "source": "로이터·AP 보도 종합"},
    {"date": "2025-01-24", "currency": "USD/JPY", "category": "통화정책", "bucket": "통화정책",
     "title": "BOJ 기준금리 0.5%로 인상",
     "fact": "일본은행이 기준금리를 0.5%로 인상했다.",
     "opinion": "임금·물가 선순환이 일부 확인되며 추가 정상화 기대가 반영된 것으로 해석되었다.",
     "source": "일본은행(BOJ) 발표 종합"},
    {"date": "2025-12-19", "currency": "USD/JPY", "category": "통화정책", "bucket": "통화정책",
     "title": "BOJ 기준금리 0.75%로 인상",
     "fact": "일본은행이 정책금리를 0.5%에서 0.75%로 인상했다.",
     "opinion": "2026년 춘투 임금 상승 지속 기대와 엔저 압력 지속이 추가 인상의 배경으로 해석되었다.",
     "source": "일본은행(BOJ) 발표 및 리서치 보도 종합"},
    {"date": "2026-06-16", "currency": "USD/JPY", "category": "통화정책", "bucket": "통화정책",
     "title": "BOJ 기준금리 1.0%로 인상 (31년래 최고 수준)",
     "fact": "일본은행이 기준금리를 0.75%에서 1.0%로 인상했다(1995년 이후 약 31년 만의 1%대 진입).",
     "opinion": "정책 정상화가 지속되었으나, 중동發 원자재 가격 상승에 따른 물가 상방 리스크가 부각되며 추가 인상 여력에 대한 시장의 관심이 이어진 것으로 해석되었다. 다만 정책금리 인상에도 불구하고 엔화 약세 압력은 쉽게 해소되지 않았다.",
     "source": "일본은행(BOJ) 발표 종합"},

    # -- USD/CNY 관련 --
    {"date": "2024-09-24", "currency": "USD/CNY", "category": "경기부양", "bucket": "통화정책",
     "title": "중국 정부, 대규모 경기부양 패키지 발표",
     "fact": "중국 정책당국이 지급준비율 및 정책금리 인하, 부동산·증시 지원책을 발표했다.",
     "opinion": "지준율 및 정책금리 인하, 부동산·증시 지원책이 발표되며 중국 경기 회복 기대가 확대된 것으로 해석되었다.",
     "source": "중국인민은행(PBOC) 발표 및 로이터 보도 종합"},
    {"date": "2024-12-11", "currency": "USD/CNY", "category": "통화정책", "bucket": "통화정책",
     "title": "중국 중앙경제공작회의 개최",
     "fact": "중국 중앙경제공작회의가 개최되어 2025년 경제운용 방향이 논의되었다.",
     "opinion": "통화 완화 및 경기 안정 기조가 재확인되었으며, 트럼프발 관세 우려에 대응해 위안화 환율의 변동폭이 확대될 가능성이 있다는 시각이 시장에서 함께 부각된 것으로 해석되었다.",
     "source": "신화통신 발표 및 로이터·블룸버그 보도 종합"},
    {"date": "2025-04-02", "currency": "공통", "category": "무역정책", "bucket": "무역정책",
     "title": "미국, 광범위한 '상호관세' 발표 (이른바 Liberation Day)",
     "fact": "미국 행정부가 다수 교역국을 대상으로 한 관세 인상 조치를 발표했다.",
     "opinion": "미·중 무역갈등 심화 우려로 글로벌 금융시장 변동성 확대가 나타난 것으로 해석되었다.",
     "source": "백악관 발표 및 로이터·블룸버그 보도 종합"},
    {"date": "2025-04-08", "currency": "USD/CNY", "category": "무역정책", "bucket": "무역정책",
     "title": "미·중 관세 갈등 격화 속 PBOC 위안화 고시환율 절하",
     "fact": "PBOC가 위안화 기준환율을 달러당 7.2038위안으로 고시했다.",
     "opinion": "관세 갈등 심화에 대응해 수출 경쟁력 방어 목적의 환율 조정 기대가 반영된 것으로 해석되었다.",
     "source": "블룸버그(2025-04-08) 및 중국인민은행(PBOC) 고시환율 종합"},
]

EVENTS_DF = pd.DataFrame(EVENTS)
EVENTS_DF["date"] = pd.to_datetime(EVENTS_DF["date"])
# 하위 호환: 기존 코드에서 사용하던 통합 설명 컬럼(사실 + 해석)
EVENTS_DF["desc"] = EVENTS_DF["fact"] + " → " + EVENTS_DF["opinion"]

# -- WTI(국제유가) 관련 이벤트 --
# 2026년 초 이란을 둘러싼 미국·이스라엘과의 무력 충돌 확산은 다수 외신에서 광범위하게
# 보도된 사실이며, 한국석유공사 월별 국제유가 통계에서도 WTI 평균가가 2026-01 60.26달러
# → 02월 64.52달러 → 03월 91.00달러로 급등한 뒤, 04월 98.06달러·05월 98.51달러로
# 고공행진을 이어가다 06월 81.79달러로 낮아지는 흐름이 확인된다. 이후 07~08월에는
# 배럴당 77~92달러 사이에서 등락하며 완전히 진정되지는 않은 모습을 보였다.
OIL_EVENTS = [
    {"date": "2026-03-30", "currency": "WTI", "category": "지정학적 리스크", "bucket": "에너지",
     "title": "이란 관련 무력 충돌 확산, WTI 배럴당 100달러 안팎으로 급등",
     "fact": "이란을 둘러싼 미국·이스라엘과의 무력 충돌이 확산되는 가운데, WTI 가격이 **배럴당 100달러 안팎**까지 급등했다(한국석유공사 기준 3월 월평균 91.00달러, 2월 64.52달러 대비 큰 폭 상승).",
     "opinion": "호르무즈 해협을 포함한 원유 공급 차질 우려가 유가 급등의 배경으로 해석되었다.",
     "source": "Axios·로이터 등 외신 보도 및 한국석유공사 유가 통계 종합"},
    {"date": "2026-04-24", "currency": "WTI", "category": "시장동향", "bucket": "시장심리",
     "title": "WTI 100달러 중반대 고점권 형성 이후 점진적 하락 전환",
     "fact": "WTI가 4월(월평균 98.06달러)과 5월(월평균 98.51달러) 두 달 연속 높은 수준에서 고점권을 형성한 뒤, **6월 월평균 81.79달러로 낮아지며 점진적인 하락 전환**이 확인됐다(한국석유공사 기준).",
     "opinion": "지정학적 긴장 완화 기대와 공급 우려 진정 등이 반영되며 유가가 고점 대비 조정된 것으로 해석되었다. 다만 7–8월에도 배럴당 77–92달러 사이에서 등락해, 긴장이 완전히 해소되지는 않은 것으로 보인다.",
     "source": "한국석유공사 유가 통계 및 국내외 에너지 시장 보도 종합"},
]
OIL_EVENTS_DF = pd.DataFrame(OIL_EVENTS)
OIL_EVENTS_DF["date"] = pd.to_datetime(OIL_EVENTS_DF["date"])
OIL_EVENTS_DF["desc"] = OIL_EVENTS_DF["fact"] + " → " + OIL_EVENTS_DF["opinion"]

# -- 국내 CPI 관련 이벤트 (선행지표인 유가·환율의 후행 효과가 실제로 확인된 시점) --
CPI_EVENTS = [
    {"date": "2026-07-02", "currency": "CPI", "category": "물가", "bucket": "물가",
     "title": "6월 소비자물가 3.2%↑, 2년 6개월 만에 최고",
     "fact": "국가데이터처가 발표한 6월 소비자물가지수(2020=100 기준 119.99)가 전년 동월 대비 **3.2% 상승**해, 2023년 12월(3.2%) 이후 **2년 6개월 만에 가장 높은 상승률**을 기록했다(5월 3.1%에 이어 두 달 연속 3%대). 석유류 가격이 전년 동월 대비 **24.7% 급등**하며 전체 물가 상승률을 0.93%포인트 끌어올렸다.",
     "opinion": "**이란전쟁 여파**로 인한 국제유가 급등이 시차를 두고 석유류 가격에 본격 반영되며 물가 상승을 이끈 것으로 해석되었다(선행지표인 유가가 후행지표인 CPI에 반영된 사례). 다만 국가데이터처는 **환율 상승분의 영향은 6월까지는 본격적으로 나타나지 않았다**고 설명해, 환율의 파급 경로는 유가보다 더딘 것으로 나타났다.",
     "source": "국가데이터처 '6월 소비자물가동향' 발표(2026-07-02) 및 뉴시스·YTN·머니투데이 등 보도 종합"},
]
CPI_EVENTS_DF = pd.DataFrame(CPI_EVENTS)
CPI_EVENTS_DF["date"] = pd.to_datetime(CPI_EVENTS_DF["date"])
CPI_EVENTS_DF["desc"] = CPI_EVENTS_DF["fact"] + " → " + CPI_EVENTS_DF["opinion"]

CATEGORY_COLORS = {
    "통화정책": "#4dabf7",
    "무역정책": "#e03131",
    "시장동향": "#f59f00",
    "시장개입": "#be4bdb",
    "경기부양": "#12b886",
    "정치/정책": "#868e96",
    "지정학적 리스크": "#e8590c",
    "물가": "#20c997",
}

BUCKET_COLORS = {
    "통화정책": "#4dabf7",
    "무역정책": "#e03131",
    "시장심리": "#f59f00",
    "에너지": "#e8590c",
    "물가": "#20c997",
}

# ----------------------------------------------------------------------------
# 사이드바 - 사용자 입력
# ----------------------------------------------------------------------------
st.sidebar.title("⚙️ 설정")

theme_mode = st.sidebar.radio("화면 테마", ["다크 모드", "라이트 모드"], index=0)

view_mode = st.sidebar.radio(
    "분석 모드",
    [
        "🌐 4대 지표 통합 대시보드",
        "🔎 개별 통화 심층 분석",
    ],
    index=0,
)

if view_mode.startswith("🔎"):
    focus_currency = st.sidebar.selectbox("통화쌍 선택", list(TICKERS.keys()), index=1)
else:
    focus_currency = None

selected_period_label = st.sidebar.radio("조회 기간", list(PERIOD_MAP.keys()), index=0)
period = PERIOD_MAP[selected_period_label]

custom_start, custom_end = None, None
if period == "custom":
    date_range = st.sidebar.date_input(
        "조회 시작일 – 종료일",
        value=(DEFAULT_START, DEFAULT_END),
        min_value=datetime(2010, 1, 1),
        max_value=datetime.today(),
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        custom_start, custom_end = date_range
    else:
        custom_start, custom_end = DEFAULT_START, DEFAULT_END

st.sidebar.markdown("---")
indicator_mode = st.sidebar.radio("보조지표", ["없음", "이동평균선", "볼린저 밴드"], index=1)
show_ma = indicator_mode == "이동평균선"
show_bollinger = indicator_mode == "볼린저 밴드"
show_rsi = st.sidebar.checkbox("RSI 패널 표시 (개별 분석 모드)", value=True)
show_events_on_chart = st.sidebar.checkbox("차트에 주요 이벤트 표시", value=True)

st.sidebar.markdown("---")
st.sidebar.caption(
    "데이터 출처: Yahoo Finance(USD/CNY·USD/JPY) · 한국석유공사 PETRONET(WTI) · "
    "KOSIS(국내 CPI) · 이벤트: 뉴스·리서치 보도 요약"
)

st.sidebar.markdown("---")
st.sidebar.info(f"📅 FX·WTI 분석 기준일: {ANALYSIS_ASOF_LABEL}")
st.sidebar.info(f"📅 CPI 기준: {CPI_ASOF_LABEL}")

# ----------------------------------------------------------------------------
# 다크모드 / 라이트모드 커스텀 스타일
# ----------------------------------------------------------------------------
if theme_mode == "다크 모드":
    bg_color = "#0e1117"
    card_bg = "#1a1f29"
    text_color = "#f0f2f6"
    accent = "#4dabf7"
    plot_template = "plotly_dark"
    grid_color = "rgba(255,255,255,0.08)"
else:
    bg_color = "#ffffff"
    card_bg = "#f5f7fa"
    text_color = "#1a1f29"
    accent = "#1c7ed6"
    plot_template = "plotly_white"
    grid_color = "rgba(0,0,0,0.08)"

st.markdown(
    f"""
    <style>
    .stApp {{ background-color: {bg_color}; color: {text_color}; }}
    .metric-card {{
        background-color: {card_bg}; padding: 18px; border-radius: 14px;
        border: 1px solid {grid_color}; text-align: center;
    }}
    .metric-card h3 {{ margin: 0; font-size: 13px; opacity: 0.7; font-weight: 500; }}
    .metric-card h1 {{ margin: 6px 0 0 0; font-size: 26px; }}
    .metric-card .sub {{ font-size: 11.5px; opacity: 0.65; margin-top: 4px; }}
    .opinion-box {{
        background-color: {card_bg}; border-left: 6px solid {accent};
        padding: 20px; border-radius: 10px; font-size: 15px; line-height: 1.6;
    }}
    .opinion-box b, .opinion-box strong {{ color: {accent}; }}
    .event-card {{
        background-color: {card_bg}; padding: 14px 18px; border-radius: 10px;
        margin-bottom: 10px; border-left: 5px solid #868e96;
    }}
    .event-date {{ font-size: 12px; opacity: 0.65; }}
    .event-title {{ font-size: 15px; font-weight: 600; margin: 2px 0 4px 0; }}
    .event-fact {{ font-size: 13.5px; opacity: 0.95; line-height: 1.5; margin-bottom: 3px; }}
    .event-opinion {{ font-size: 13.5px; opacity: 0.85; line-height: 1.5; font-style: italic; }}
    .event-fact b, .event-fact strong, .event-opinion b, .event-opinion strong {{
        opacity: 1; color: {accent}; font-style: normal;
    }}
    .event-source {{ font-size: 11.5px; opacity: 0.55; margin-top: 6px; }}
    .tag {{
        display: inline-block; font-size: 11px; padding: 2px 8px;
        border-radius: 999px; color: white; margin-right: 6px; margin-bottom: 4px;
    }}
    .realtime-badge {{
        display:inline-block; background-color:#e03131; color:white; font-size:11px;
        padding:2px 8px; border-radius:999px; margin-left:6px;
    }}
    .asof-badge {{
        display:inline-block; background-color:#495057; color:white; font-size:11px;
        padding:2px 8px; border-radius:999px; margin-left:6px;
    }}
    .action-card {{
        background-color: {card_bg}; border-radius: 14px; padding: 18px;
        border: 1px solid {grid_color}; height: 100%;
    }}
    .action-card h4 {{ margin: 0 0 10px 0; font-size: 15px; }}
    .action-tag {{
        display: inline-block; font-size: 12px; font-weight: 600; color: white;
        padding: 3px 10px; border-radius: 999px;
    }}
    .action-plan-text {{
        font-size: 13px; line-height: 1.55; opacity: 0.9; margin-top: 8px;
    }}
    .action-plan-text b, .action-plan-text strong {{ opacity: 1; color: {accent}; }}
    .corr-card {{
        background-color: {card_bg}; border-radius: 14px; padding: 16px 18px;
        border: 1px solid {grid_color}; margin-bottom: 12px;
    }}
    .corr-card-header {{
        display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;
    }}
    .corr-pair {{ font-size: 15px; font-weight: 700; margin-right: 2px; }}
    .corr-badge {{
        display: inline-block; font-size: 11px; font-weight: 600; color: white;
        padding: 2px 9px; border-radius: 999px; white-space: nowrap;
    }}
    .corr-rval {{
        font-family: "SFMono-Regular", Consolas, monospace; font-size: 13px;
        font-weight: 700; opacity: 0.85; margin-left: auto;
    }}
    .corr-headline {{ font-size: 14px; font-weight: 600; margin-bottom: 4px; }}
    .corr-detail {{ font-size: 13px; line-height: 1.55; opacity: 0.85; }}
    .corr-detail b, .corr-detail strong {{ opacity: 1; color: {accent}; }}
    .corr-caution {{
        margin-top: 9px; padding: 8px 12px; border-radius: 8px;
        background-color: rgba(247,103,7,0.12); border-left: 4px solid #f76707;
        font-size: 12.5px; line-height: 1.5;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# 데이터 수집 / 지표 계산
# ----------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def fetch_fx_data(ticker_symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    """yfinance로 환율 데이터를 가져온다. 지표 계산용 90일 버퍼를 앞으로 확보한다."""
    fetch_start = pd.to_datetime(start) - timedelta(days=90)
    fetch_end = pd.to_datetime(end) + timedelta(days=1)

    df = yf.download(
        ticker_symbol,
        start=fetch_start.strftime("%Y-%m-%d"),
        end=fetch_end.strftime("%Y-%m-%d"),
        interval="1d",
        progress=False,
        auto_adjust=True,
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(subset=["Close"])


def sanitize_usdcny(df: pd.DataFrame) -> pd.DataFrame:
    """USDCNY=X 티커의 스파이크성 오류값을 추세 적응형(롤링 MAD 기반) 방식으로 보정한다.

    Yahoo Finance의 'USDCNY=X' 티커는 간헐적으로 스파이크성 오류값(비정상적으로
    튀는 단발성 종가)을 반환하는 사례가 보고되어 있다. 과거 버전에서는 "2025년 이후
    7.25~7.35 박스권"이라는 고정 범위를 벗어나면 이상치로 간주했으나, 실제로는
    2025년 하반기 이후 달러 약세·위안화 강세 흐름 속에 USD/CNY가 7위안 아래로
    내려가 2026년에는 6.7~7.0위안대에서 등락했다(관련 보도 다수). 즉 실제 정상
    데이터가 가정했던 박스권 밖에 있었던 것이며, 고정 범위 방식은 이런 정상적인
    추세 이동을 이상치로 오인해 잘못 지워버릴 위험이 있다.

    이를 개선해, 각 시점 직전 CNY_ROLLING_WINDOW 거래일의 롤링 중앙값(median)과
    중앙값절대편차(MAD)를 함께 계산하고, 그 중앙값에서 CNY_OUTLIER_MAD_MULTIPLIER배
    이상 벗어난 종가만 이상치로 보정한다. 이 방식은 특정 연도의 실제 시세 구간을
    코드에 하드코딩하지 않으므로, 환율이 어느 방향으로 추세 이동하더라도(위안화
    강세든 약세든) 그 추세 자체는 보존하면서 순간적인 스파이크성 오류값만 걸러낸다.
    """
    if df.empty:
        return df
    df = df.copy()
    close = df["Close"]
    rolling_median = close.rolling(window=CNY_ROLLING_WINDOW, min_periods=5, center=False).median()
    abs_dev = (close - rolling_median).abs()
    rolling_mad = abs_dev.rolling(window=CNY_ROLLING_WINDOW, min_periods=5, center=False).median()
    # MAD가 0이거나 초기 구간처럼 계산 불가한 경우엔 이상치 판정을 생략한다(오탐 방지).
    scaled_mad = rolling_mad * 1.4826  # 정규분포 가정 하 표준편차에 상응하는 스케일 보정
    threshold = scaled_mad * CNY_OUTLIER_MAD_MULTIPLIER
    is_outlier = (
        rolling_median.notna() & threshold.notna() & (threshold > 0) &
        (abs_dev > threshold)
    )
    if is_outlier.any():
        df.loc[is_outlier, "Close"] = np.nan
        df["Close"] = df["Close"].ffill().bfill()
    return df


@st.cache_data(show_spinner=False)
def load_wti_data() -> pd.DataFrame:
    """한국석유공사 PETRONET 자료를 정리한 로컬 CSV(data/wti_prices.csv)를 읽는다."""
    path = DATA_DIR / "wti_prices.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.set_index("date").sort_index()
    df = df.rename(columns={"wti": "Close"})
    return df


@st.cache_data(show_spinner=False)
def load_cpi_data() -> pd.DataFrame:
    """KOSIS 국내 소비자물가지수 분기 자료를 정리한 로컬 CSV(data/cpi_kr.csv)를 읽는다."""
    path = DATA_DIR / "cpi_kr.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["date"])
    df = df.set_index("date").sort_index()
    return df


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["MA20"] = df["Close"].rolling(window=20).mean()
    df["MA50"] = df["Close"].rolling(window=50).mean()

    df["BB_Mid"] = df["Close"].rolling(window=20).mean()
    bb_std = df["Close"].rolling(window=20).std()
    df["BB_Upper"] = df["BB_Mid"] + 2 * bb_std
    df["BB_Lower"] = df["BB_Mid"] - 2 * bb_std

    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))
    return df


def trim_to_range(df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    start_ts, end_ts = pd.to_datetime(start), pd.to_datetime(end)
    return df[(df.index >= start_ts) & (df.index <= end_ts)]


def resolve_date_range(period_key: str, c_start, c_end):
    """선택된 기간 라벨을 실제 (start, end) 날짜로 변환한다."""
    if period_key == "full":
        return DEFAULT_START, DEFAULT_END
    if period_key == "custom":
        return c_start, c_end
    days_map = {"1mo": 30, "6mo": 182, "1y": 365}
    end = min(datetime.today(), DEFAULT_END)
    start = end - timedelta(days=days_map.get(period_key, 365))
    return start, end


def generate_ai_opinion(latest: pd.Series, currency_label: str) -> str:
    """통계 지표만을 근거로 한 자동 요약이며, 정책 인과관계에 대한 단정적 판단이 아니다."""
    rsi = latest.get("RSI", np.nan)
    close = latest.get("Close", np.nan)
    bb_upper = latest.get("BB_Upper", np.nan)
    bb_lower = latest.get("BB_Lower", np.nan)

    signals = []
    if pd.notna(rsi):
        if rsi >= 70:
            signals.append(("과매수", f"RSI {rsi:.1f} (70 이상)"))
        elif rsi <= 30:
            signals.append(("과매도", f"RSI {rsi:.1f} (30 이하)"))
        else:
            signals.append(("정상", f"RSI {rsi:.1f} (30–70 구간)"))

    if pd.notna(bb_upper) and pd.notna(bb_lower) and pd.notna(close):
        if close >= bb_upper:
            signals.append(("과매수", "종가가 볼린저 상단 밴드 상회"))
        elif close <= bb_lower:
            signals.append(("과매도", "종가가 볼린저 하단 밴드 하회"))
        else:
            signals.append(("정상", "종가가 볼린저 밴드 내부"))

    statuses = [s[0] for s in signals]
    if statuses.count("과매수") >= 1 and statuses.count("과매도") == 0:
        final, color = ("과매수 (고점 경계)" if statuses.count("과매수") >= 2 else "과매수 가능성으로 해석됨"), "🔴"
    elif statuses.count("과매도") >= 1 and statuses.count("과매수") == 0:
        final, color = ("과매도 (저점 경계)" if statuses.count("과매도") >= 2 else "과매도 가능성으로 해석됨"), "🟢"
    else:
        final, color = "정상 범위로 해석됨", "🟡"

    detail = " · ".join([f"{label}({reason})" for label, reason in signals])
    return f"{color} **{currency_label}: {final}** — {detail} (※ 통계 지표 기반 참고용 해석)"


def render_event_list(events_subset: pd.DataFrame):
    if events_subset.empty:
        st.info("해당 조건에 부합하는 이벤트가 없습니다.")
        return
    for _, row in events_subset.sort_values("date").iterrows():
        color = CATEGORY_COLORS.get(row["category"], "#868e96")
        st.markdown(
            f'<div class="event-card" style="border-left-color:{color};">'
            f'<span class="event-date">{row["date"].strftime("%Y-%m-%d")} · {row["currency"]}</span>'
            f'<span class="tag" style="background-color:{color};">{row["category"]}</span>'
            f'<span class="tag" style="background-color:{BUCKET_COLORS.get(row["bucket"], "#868e96")};">{row["bucket"]}</span>'
            f'<div class="event-title">{row["title"]}</div>'
            f'<div class="event-fact">📌 <b>사실</b>: {row["fact"]}</div>'
            f'<div class="event-opinion">💬 <b>시장 해석</b>: {row["opinion"]}</div>'
            f'<div class="event-source">출처(참고용): {row["source"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def render_kpi_card(icon_label: str, value: float, baseline_value: float,
                     baseline_label: str, value_fmt: str = "{:.4f}",
                     extra_caption: str | None = None):
    """일별(전일) 등락이 아니라, 조회 기간 내 '기준점(첫 시점)' 대비 누적 변동을 보여준다.

    baseline_label에는 기준점이 되는 날짜/분기(예: '2023-01-02 기준')를 포함한다.
    """
    change = value - baseline_value
    pct = (change / baseline_value) * 100 if baseline_value else 0
    arrow = "▲" if change >= 0 else "▼"
    color = "#e03131" if change >= 0 else "#1c7ed6"
    extra_html = f'<div class="sub">{extra_caption}</div>' if extra_caption else ""
    html = (
        f'<div class="metric-card">'
        f'<h3>{icon_label}</h3>'
        f'<h1>{value_fmt.format(value)}</h1>'
        f'<div class="sub" style="color:{color}; font-weight:600;">'
        f'{arrow} {baseline_label} 대비 {abs(change):.4f} ({pct:+.2f}%)</div>'
        f'{extra_html}'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# 구매 전략 방향(Action Plan) 규칙 기반 매핑
# ※ 아래 로직은 각 지표의 현재 수준·변동 방향에 대한 단순 규칙 기반 요약이며,
#   개별 기업의 실제 구매 의사결정을 대체하지 않는 참고용 가이드입니다.
# ※ 기준값(threshold) 검증: 2026년 실제 관측 범위와 대조해 아래 값을 그대로 유지했다.
#   - USD/CNY 7.25: 2025년 하반기 이후 실제 시세(6.7~7.0위안대)는 이 기준보다 낮아,
#     현재는 대부분 '위안화 강세' 분기 쪽으로 판정되는 것이 맞다(설계 원칙 5번 참고).
#   - USD/JPY 150: 2026년 상반기~한여름 실제 시세(155~162엔대)는 이 기준을 웃돌아,
#     '엔저' 분기 판정이 실제 흐름과 부합한다.
#   - WTI 90: 이란 사태 이후 2026년 6~8월 실제 관측치(월평균 81.79달러, 일별로는
#     77~92달러 사이 등락)를 볼 때, 90달러는 '고유가 국면'과 '진정 국면'을 가르는
#     경계값으로 여전히 합리적이다.
# ----------------------------------------------------------------------------
def usdcny_action(level: float, pct_change: float) -> tuple[str, str, str]:
    """(태그, 태그색상, 설명텍스트)를 반환한다."""
    if level >= 7.25:
        return (
            "분할매입 검토",
            "#e03131",
            "현재 위안화가 약세(고환율) 구간에 있어, 중국산 원부자재는 분할 매입·선구매를 "
            "검토할 수 있는 시점입니다. 다만 변동폭 확대 가능성에 대비해 환헤지 비중을 함께 점검합니다.",
        )
    return (
        "헤지 비중 확대",
        "#1c7ed6",
        "위안화가 상대적 강세 구간에 있어 구매단가 상승 부담이 커질 수 있으므로, "
        "환헤지 비중 확대와 대체 소싱처 검토를 함께 진행합니다.",
    )


def usdjpy_action(level: float, pct_change: float) -> tuple[str, str, str]:
    if level >= 150:
        return (
            "계약 시점 앞당기기",
            "#e03131",
            "엔저 구간이 이어지고 있어 일본산 설비·부품은 구매 경쟁력이 높은 편입니다. "
            "계약 시점을 앞당기되, BOJ 정책 전환 시 엔화 변동성 확대에 대비해 헤지 비율을 함께 점검합니다.",
        )
    return (
        "헤지 비율 조정",
        "#1c7ed6",
        "엔화가 상대적 강세 구간으로 전환되고 있어, 일본산 설비·부품 수입원가 상승 가능성에 대비한 "
        "헤지 비율 조정을 검토합니다.",
    )


def wti_action(level: float, pct_change: float) -> tuple[str, str, str]:
    if level >= 90:
        return (
            "장기계약 비중 확대",
            "#e03131",
            "고유가 국면으로, 연료·물류 비용 급등에 대비해 장기계약 비중 확대, 유가 연동 조항 점검, "
            "대체 운송·에너지 소싱 방안을 함께 검토합니다.",
        )
    return (
        "헤지 비중 사전 점검",
        "#1c7ed6",
        "유가가 상대적으로 안정된 구간이므로, 향후 변동성 확대에 대비한 장기계약·헤지 비중을 "
        "미리 점검해 두는 것이 유리합니다.",
    )


def cpi_action(yoy_pct: float, qoq_pct: float) -> tuple[str, str, str]:
    if yoy_pct >= 3:
        return (
            "에스컬레이션 조항 점검",
            "#e03131",
            "물가 상승 압력이 확대되는 국면으로, 인건비·원자재 단가 상승분을 반영한 예산 재검토와 "
            "장기 공급계약의 물가연동(에스컬레이션) 조항 점검이 필요합니다.",
        )
    return (
        "장기계약 조항 사전 반영",
        "#1c7ed6",
        "물가 상승세가 완만한 편이나, 장기 공급계약에는 물가연동(에스컬레이션) 조항을 "
        "미리 반영해 두는 것을 권장합니다.",
    )


def render_action_card(icon_title: str, action: tuple[str, str, str]):
    """action은 (태그, 태그색상, 설명텍스트) 튜플이다."""
    tag, tag_color, action_text = action
    html = (
        f'<div class="action-card">'
        f'<h4>{icon_title}</h4>'
        f'<span class="action-tag" style="background-color:{tag_color};">{tag}</span>'
        f'<div class="action-plan-text"><b>구매 전략 방향</b><br>{action_text}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def build_integrated_chart(cny_df, jpy_df, wti_df, cpi_df, fx_events, oil_events,
                            show_events, plot_template, bg_color, text_color, grid_color,
                            cpi_events=None):
    """2x2 시계열 그리드. 각 패널의 Y축을 0 기준이 아닌 해당 지표의 실제 값
    범위에 맞춰 설정해 지표별 변동 트렌드가 잘 드러나도록 한다."""
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("USD/CNY", "USD/JPY", "WTI 원유 ($/배럴)", "국내 소비자물가지수 (2020=100, 분기)"),
        vertical_spacing=0.14, horizontal_spacing=0.08,
    )

    panels = [
        (1, 1, cny_df, CURRENCY_COLORS["USD/CNY"],
         fx_events[fx_events["currency"].isin(["USD/CNY", "공통"])] if fx_events is not None else None),
        (1, 2, jpy_df, CURRENCY_COLORS["USD/JPY"],
         fx_events[fx_events["currency"].isin(["USD/JPY", "공통"])] if fx_events is not None else None),
        (2, 1, wti_df, WTI_COLOR, oil_events),
    ]
    for row, col, df, color, ev in panels:
        if df is None or df.empty:
            continue
        fig.add_trace(
            go.Scatter(x=df.index, y=df["Close"], line=dict(color=color, width=2), showlegend=False),
            row=row, col=col,
        )
        lo, hi = float(df["Close"].min()), float(df["Close"].max())
        pad = (hi - lo) * 0.08 if hi > lo else max(hi * 0.02, 0.5)
        fig.update_yaxes(range=[lo - pad, hi + pad], gridcolor=grid_color, row=row, col=col)
        # x축 범위를 데이터 자체의 실제 구간으로 고정한다. 그렇지 않으면 아래에서 그리는
        # 이벤트 vline(점선)이 데이터 범위 밖 날짜를 가리킬 때 Plotly가 축 범위를 그
        # 날짜까지 억지로 늘려서, 그래프 대부분이 빈 공간이 되어버리는 문제가 생길 수 있다.
        fig.update_xaxes(range=[df.index.min(), df.index.max()], gridcolor=grid_color, row=row, col=col)
        if show_events and ev is not None and not ev.empty:
            ev_in_range = ev[(ev["date"] >= df.index.min()) & (ev["date"] <= df.index.max())]
            for _, e in ev_in_range.iterrows():
                fig.add_vline(
                    x=e["date"].timestamp() * 1000, line_width=1, line_dash="dash",
                    line_color=CATEGORY_COLORS.get(e.get("category"), "#868e96"),
                    opacity=0.6, row=row, col=col,
                )

    if cpi_df is not None and not cpi_df.empty:
        fig.add_trace(
            go.Scatter(x=cpi_df.index, y=cpi_df["cpi"], line=dict(color=CPI_COLOR, width=2.4),
                       mode="lines+markers", showlegend=False),
            row=2, col=2,
        )
        lo, hi = float(cpi_df["cpi"].min()), float(cpi_df["cpi"].max())
        pad = (hi - lo) * 0.08 if hi > lo else 1.0
        fig.update_yaxes(range=[lo - pad, hi + pad], gridcolor=grid_color, row=2, col=2)
        # CPI 이벤트는 실제 발표일 기준으로 기록되지만, CPI 데이터 자체는 최신 분기까지만
        # 존재한다(사이드바의 'CPI 기준' 배지 참고). 데이터 범위를 벗어난 이벤트 날짜로 인해
        # x축이 늘어나 그래프 대부분이 빈 공간으로 보이는 것을 막기 위해, x축 범위를 CPI
        # 데이터 자체의 구간으로 고정하고, 그 구간을 벗어나는 이벤트는 이 패널에는 표시하지
        # 않는다(하단 '주요 변동 요인 타임라인'과 '사실 검토'에는 그대로 표시된다).
        fig.update_xaxes(range=[cpi_df.index.min(), cpi_df.index.max()], gridcolor=grid_color, row=2, col=2)
        if show_events and cpi_events is not None and not cpi_events.empty:
            cpi_ev_in_range = cpi_events[
                (cpi_events["date"] >= cpi_df.index.min()) & (cpi_events["date"] <= cpi_df.index.max())
            ]
            for _, e in cpi_ev_in_range.iterrows():
                fig.add_vline(
                    x=e["date"].timestamp() * 1000, line_width=1, line_dash="dash",
                    line_color=CATEGORY_COLORS.get(e.get("category"), "#868e96"),
                    opacity=0.6, row=2, col=2,
                )

    fig.update_layout(
        template=plot_template, height=680, showlegend=False,
        plot_bgcolor=bg_color, paper_bgcolor=bg_color, font=dict(color=text_color),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    return fig


# ----------------------------------------------------------------------------
# 상관관계 분석 & 선행지표→후행지표 예측 프레임워크
# ----------------------------------------------------------------------------
def _to_quarterly(series: pd.Series) -> pd.Series:
    """일별 시계열을 분기 평균으로 변환한다(CPI가 분기 지표이므로 주기를 맞춘다)."""
    if series is None or series.empty:
        return pd.Series(dtype=float)
    s = series.copy()
    s.index = s.index.to_period("Q")
    return s.groupby(level=0).mean()


def build_quarterly_panel(cny_df: pd.DataFrame, jpy_df: pd.DataFrame,
                           wti_df: pd.DataFrame, cpi_df: pd.DataFrame) -> pd.DataFrame:
    """USD/CNY·USD/JPY·WTI(분기 평균)와 CPI(분기 지수)를 하나의 분기 패널로 합친다."""
    data = {}
    if cny_df is not None and not cny_df.empty:
        data["USD/CNY"] = _to_quarterly(cny_df["Close"])
    if jpy_df is not None and not jpy_df.empty:
        data["USD/JPY"] = _to_quarterly(jpy_df["Close"])
    if wti_df is not None and not wti_df.empty:
        data["WTI"] = _to_quarterly(wti_df["Close"])
    if cpi_df is not None and not cpi_df.empty:
        s = cpi_df["cpi"].copy()
        s.index = s.index.to_period("Q")
        data["CPI"] = s.groupby(level=0).mean()
    if not data:
        return pd.DataFrame()
    panel = pd.DataFrame(data).sort_index()
    return panel


def render_normalized_index_chart(panel: pd.DataFrame, plot_template, bg_color, text_color, grid_color):
    """4대 지표를 공통 구간의 첫 분기를 100으로 정규화해 한 차트에 겹쳐 보여준다.
    아래 상관관계 해설에서 말하는 '같은 방향/반대 방향' 움직임을 숫자 없이도 한눈에
    확인할 수 있게 하기 위한 시각 보조 자료다(상관계수 표/히트맵을 대체)."""
    cols = [c for c in ["USD/CNY", "USD/JPY", "WTI", "CPI"] if c in panel.columns]
    common = panel[cols].dropna()
    if common.empty or len(common) < 2:
        return None
    indexed = common.div(common.iloc[0]) * 100

    color_map = {
        "USD/CNY": CURRENCY_COLORS.get("USD/CNY", "#f59f00"),
        "USD/JPY": CURRENCY_COLORS.get("USD/JPY", "#4dabf7"),
        "WTI": WTI_COLOR,
        "CPI": CPI_COLOR,
    }
    fig = go.Figure()
    for col in cols:
        fig.add_trace(go.Scatter(
            x=[str(p) for p in indexed.index], y=indexed[col],
            mode="lines+markers", name=col,
            line=dict(color=color_map.get(col), width=2.2),
        ))
    fig.update_layout(
        template=plot_template, height=340,
        title="4대 지표 정규화 추이 (공통 구간 첫 분기 = 100)",
        xaxis_title="분기", yaxis_title="지수 (첫 분기 = 100)",
        plot_bgcolor=bg_color, paper_bgcolor=bg_color, font=dict(color=text_color),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    fig.update_xaxes(gridcolor=grid_color)
    fig.update_yaxes(gridcolor=grid_color)
    return fig


def _pair_interpretation(a: str, b: str, r: float) -> str:
    """지표 쌍의 실제 상관계수 부호(같은 방향/반대 방향)에 맞춰 모순 없는 해석 문장을 만든다.
    고정된 한 방향 서술을 쓰면(예: 'r이 음수인데 양(+)의 경로만 설명') 통계치와 해설이
    어긋날 수 있으므로, 부호별로 분기해 서술한다."""
    pair = frozenset([a, b])
    same_dir = r >= 0

    if pair == frozenset(["WTI", "CPI"]):
        if same_dir:
            return (
                "국제유가와 국내 물가가 같은 방향으로 움직이는 전형적인 관계로 나타났습니다. "
                "유가 상승이 **원자재·물류·에너지 수입 비용 상승**을 통해 시차를 두고 물가에 반영되는 "
                "경로가 통계적으로도 뒷받침됩니다."
            )
        return (
            "이번 조회 기간에는 유가와 국내 물가가 반대 방향으로 나타났습니다. 유가 상승분이 "
            "아직 CPI에 본격 반영되기 전이거나(**시차 효과**), 유가가 하락하는 구간과 다른 요인(환율, "
            "서비스 물가 등)에 의한 물가 상승 구간이 겹쳤을 가능성을 시사합니다. 아래 '유가/환율을 "
            "통해 CPI 예측 프레임워크'의 시차별 분석을 함께 참고하는 것이 좋습니다."
        )

    if pair == frozenset(["USD/JPY", "CPI"]):
        if same_dir:
            base = "엔화 약세(USD/JPY 상승)와 국내 물가 상승이 같은 방향으로 나타났습니다."
        else:
            base = "엔화 약세(USD/JPY 상승) 국면에서 오히려 국내 물가는 낮아지는 방향으로 나타났습니다."
        return (
            base + " 엔화는 일본산 설비·부품의 원화 환산 구매비용에 영향을 줄 수 있지만, 국내 "
            "소비자물가 전반에 미치는 직접적 파급 경로는 유가에 비해 **간접적인 편**입니다."
        )

    if pair == frozenset(["USD/CNY", "CPI"]):
        if same_dir:
            base = (
                "위안화 약세(USD/CNY 상승)와 국내 물가 상승이 같은 방향으로 나타나, 위안화 하나만으로는 "
                "설명하기 어려운 다른 원가 상승 요인(유가, 원/달러 환율 등)이 함께 작용했을 가능성을 "
                "보여줍니다."
            )
        else:
            base = (
                "위안화 강세(USD/CNY 하락)일 때 국내 물가는 낮아지는 방향으로 나타나, 이론상 예상되는 "
                "경로(위안화 강세 → 수입단가 하락 → 물가 하방)와 방향이 일치합니다."
            )
        return base + " 다만 유가·국내 수요 등 다른 요인의 영향력이 더 커서, 위안화 단독의 설명력은 **제한적인 편**입니다."

    if pair == frozenset(["USD/CNY", "WTI"]):
        if same_dir:
            return (
                "중국은 **원유 순수입국**이어서 유가 상승이 무역수지 부담을 통해 위안화 약세(USD/CNY 상승) "
                "요인으로 작용하는 전형적인 경로가 확인됩니다."
            )
        return (
            "중국은 원유 순수입국이어서 유가 상승이 위안화 약세 요인으로 작용할 수 있는데, 이번 "
            "기간에는 반대로 유가가 오를 때 위안화가 강세(USD/CNY 하락)를 보였습니다. 최근 **미 "
            "달러화 전반의 약세 흐름**이 유가-위안화 관계보다 더 크게 작용했을 가능성을 시사합니다."
        )

    if pair == frozenset(["USD/JPY", "WTI"]):
        if same_dir:
            return (
                "국제유가 상승과 엔화 약세가 함께 진행되는 모습입니다. 통상 유가 급등은 위험회피 "
                "심리를 자극해 엔화 강세 요인으로 작용하는 경우가 많지만, 최근에는 **BOJ의 완만한 "
                "정책 정상화 속도**와 엔 캐리트레이드 지속으로 유가 상승이 엔화 강세로 충분히 전이되지 "
                "못한 것으로 해석됩니다."
            )
        return (
            "국제유가가 오를 때 엔화가 강세(USD/JPY 하락)를 보이는, 통상적인 **위험회피·안전자산 선호** "
            "경로에 부합하는 모습입니다."
        )

    if pair == frozenset(["USD/CNY", "USD/JPY"]):
        if same_dir:
            return (
                "두 통화 모두 미 달러화 지수(DXY)의 전반적인 흐름에 함께 연동되는 경향이 있습니다. "
                "실제로 2025년 상반기 달러화가 전반적으로 약세를 보이는 국면에서 위안화와 엔화가 "
                "동반 강세를 나타낸 사례가 있어, **'공통의 달러 요인'**이 두 환율을 함께 움직이는 배경으로 "
                "해석됩니다."
            )
        return (
            "두 통화 모두 평소 미 달러화 지수(DXY) 흐름에 함께 연동되는 경향이 있는데, 이번 조회 "
            "기간에는 반대 방향으로 나타났습니다. 이는 중국 경기부양책이나 BOJ 정책금리 인상 속도 "
            "차이처럼 통화별 고유 요인이 공통의 달러 요인보다 더 크게 작용했을 가능성을 시사합니다."
        )

    return ""


def render_correlation_section(panel: pd.DataFrame, plot_template, bg_color, text_color, grid_color):
    """4대 지표 간 상관관계를 표/히트맵이 아니라, 실제 경제적 영향 경로를 바탕으로 말로 해석해 보여준다."""
    st.subheader("🔗 지표 간 상관관계 분석")
    st.caption(
        "USD/CNY·USD/JPY·WTI는 분기 평균으로, CPI는 분기 지수로 환산해 동일 주기에서 "
        "상관관계를 계산한 뒤, 실제 어떤 경로로 서로 영향을 주고받는지를 중심으로 해설합니다. "
        "상관관계는 인과관계를 의미하지 않으며, 참고용 해석입니다."
    )
    valid_cols = [c for c in ["USD/CNY", "USD/JPY", "WTI", "CPI"] if c in panel.columns]
    usable = panel[valid_cols].dropna(how="all")
    if len(valid_cols) < 2 or len(usable.dropna()) < 4:
        st.info("상관관계를 해석하기에 공통 구간의 데이터가 충분하지 않습니다.")
        return None

    # 상관계수 표/히트맵 대신, 정규화 추이 차트로 아래 해설의 '동행/역행' 움직임을 시각화한다.
    trend_fig = render_normalized_index_chart(panel, plot_template, bg_color, text_color, grid_color)
    if trend_fig is not None:
        st.plotly_chart(trend_fig, width="stretch")
        st.caption(
            "위 차트는 4대 지표가 공통으로 겹치는 분기 구간을 첫 분기=100 기준으로 정규화한 것입니다. "
            "CPI는 최신 발표 분기(사이드바 'CPI 기준' 배지 참고)까지만 존재해, WTI·환율 데이터의 "
            "전체 조회 기간보다 겹치는 구간이 더 짧게 표시될 수 있습니다."
        )

    corr = usable.corr()

    # 직접적 인과 경로보다 공통 추세·간접 경로에 더 의존하는 조합 — 상관계수가 높게 나와도
    # '허위상관(spurious correlation)' 가능성을 함께 짚어준다.
    INDIRECT_PAIRS = {
        frozenset(["USD/JPY", "CPI"]), frozenset(["USD/CNY", "CPI"]),
        frozenset(["USD/JPY", "WTI"]), frozenset(["USD/CNY", "USD/JPY"]),
        frozenset(["USD/CNY", "WTI"]),
    }

    pairs = []
    for i, a in enumerate(corr.columns):
        for b in corr.columns[i + 1:]:
            val = corr.loc[a, b]
            if pd.notna(val):
                pairs.append((a, b, val))
    if not pairs:
        st.info("해석할 수 있는 지표 조합이 없습니다.")
        return corr

    pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    for a, b, val in pairs:
        direction = "같은 방향으로" if val >= 0 else "반대 방향으로"
        strength_label = "매우 강함" if abs(val) >= 0.7 else ("중간" if abs(val) >= 0.4 else "약함")
        strength_color = "#1864ab" if abs(val) >= 0.7 else ("#4dabf7" if abs(val) >= 0.4 else "#adb5bd")
        direction_label = "같은 방향" if val >= 0 else "반대 방향"
        direction_color = "#12b886" if val >= 0 else "#e8590c"
        note = _pair_interpretation(a, b, val)

        caution_html = ""
        if abs(val) >= 0.6 and frozenset([a, b]) in INDIRECT_PAIRS:
            caution_html = (
                '<div class="corr-caution">⚠️ 두 지표 모두 조회 기간 내내 뚜렷한 <b>추세(trend)</b>를 '
                '보이는 시계열이라, 직접적인 인과 경로가 약하더라도 우연히 높은 상관계수가 나타나는 '
                '<b>허위상관</b>일 가능성에 유의해야 합니다.</div>'
            )

        st.markdown(
            f'<div class="corr-card">'
            f'<div class="corr-card-header">'
            f'<span class="corr-pair">{a} ↔ {b}</span>'
            f'<span class="corr-badge" style="background-color:{strength_color};">{strength_label}</span>'
            f'<span class="corr-badge" style="background-color:{direction_color};">{direction_label}</span>'
            f'<span class="corr-rval">r = {val:+.2f}</span>'
            f'</div>'
            f'<div class="corr-headline">{strength_label} 강도로 {direction} 움직이는 관계로 나타납니다.</div>'
            f'<div class="corr-detail">{note}</div>'
            f'{caution_html}'
            f'</div>',
            unsafe_allow_html=True,
        )
    return corr


def compute_lead_lag_corr(panel: pd.DataFrame, leading_col: str, lagging_col: str = "CPI",
                           max_lag: int = 3) -> pd.DataFrame:
    """leading_col의 분기별 등락률이 lagging_col의 등락률에 몇 분기 뒤에 가장 강하게
    반영되는지(선행-후행 관계)를 시차별 상관계수로 계산한다."""
    if leading_col not in panel.columns or lagging_col not in panel.columns:
        return pd.DataFrame(columns=["lag", "corr", "n"])
    base = panel[[leading_col, lagging_col]].dropna()
    leading_chg = base[leading_col].pct_change()
    lagging_chg = base[lagging_col].pct_change()
    rows = []
    for lag in range(0, max_lag + 1):
        shifted = leading_chg.shift(lag)
        aligned = pd.concat([shifted, lagging_chg], axis=1).dropna()
        if len(aligned) >= 4:
            corr_val = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
        else:
            corr_val = np.nan
        rows.append({"lag": lag, "corr": corr_val, "n": len(aligned)})
    return pd.DataFrame(rows)


def render_leading_lagging_section(panel: pd.DataFrame, plot_template, bg_color, text_color, grid_color,
                                    oil_events: pd.DataFrame | None = None,
                                    cpi_events: pd.DataFrame | None = None):
    """선행지표(유가·환율) → 후행지표(CPI) 예측 프레임워크: 단일 지표 관찰을 넘어,
    시차별 상관관계로 '몇 분기 뒤에 CPI에 반영되는 경향이 있는지'를 참고 지표로 제시하고,
    이를 뒷받침하는 실제 사실과 해석을 함께 검토한다.

    막대그래프에는 모든 시차의 상관계수를 있는 그대로 보여주되(투명성), 아래 글로 풀어
    쓰는 해석 문장에는 '유가·환율이 오르면(원가 상승 요인) CPI도 함께 오른다'는 이론적으로
    타당한 방향(양(+)의 상관)과 어느 정도 강도(|r| ≥ 0.3)를 충족하는 지표만 포함한다.
    이론적 방향과 어긋나는(음의 상관) 결과는 예측 신호로 쓰기에 부적합하므로 해석에서 제외한다.
    """
    st.subheader("🔮 선행지표(유가/환율)을 통한 CPI 예측 프레임워크")
    st.caption(
        "WTI·USD/CNY·USD/JPY의 분기 등락률이 몇 분기 뒤 국내 CPI 등락률과 가장 강하게 "
        "연관되는지를 시차별 상관계수로 살펴봅니다. 통계적 상관관계에 기반한 참고 자료이며, "
        "실제 물가 인과관계를 단정하거나 미래 수치를 보증하지 않습니다."
    )
    if "CPI" not in panel.columns:
        st.info("CPI 데이터가 없어 선행-후행 분석을 수행할 수 없습니다.")
        return

    leading_candidates = [c for c in ["WTI", "USD/CNY", "USD/JPY"] if c in panel.columns]
    if not leading_candidates:
        st.info("선행지표로 사용할 WTI/환율 데이터가 없습니다.")
        return

    # 이론적으로 타당한 방향: 유가 상승·위안화 약세(USD/CNY↑)·엔화 약세(USD/JPY↑) 모두
    # 원자재·수입 비용 상승을 통해 CPI를 밀어올리는 방향(양(+)의 상관)이 예상된다.
    MIN_INTERPRETABLE_CORR = 0.3

    lag_fig = go.Figure()
    all_best_lags = {}
    for col in leading_candidates:
        lag_df = compute_lead_lag_corr(panel, col, "CPI", max_lag=3)
        if lag_df["corr"].notna().any():
            lag_fig.add_trace(go.Bar(x=lag_df["lag"], y=lag_df["corr"], name=col))
            best_row = lag_df.loc[lag_df["corr"].abs().idxmax()]
            all_best_lags[col] = (int(best_row["lag"]), float(best_row["corr"]))

    lag_fig.update_layout(
        template=plot_template, height=360, barmode="group",
        title="시차(분기)별 CPI 등락률과의 상관계수",
        xaxis_title="선행 시차(분기)", yaxis_title="상관계수",
        plot_bgcolor=bg_color, paper_bgcolor=bg_color, font=dict(color=text_color),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    lag_fig.update_yaxes(gridcolor=grid_color, range=[-1, 1])
    lag_fig.update_xaxes(gridcolor=grid_color, dtick=1)
    st.plotly_chart(lag_fig, width="stretch")
    st.caption("위 그래프는 모든 시차의 상관계수를 있는 그대로 보여줍니다(방향과 무관하게 투명하게 표시).")

    # 해석 문장에는 이론적 방향(양(+))과 부합하고 강도가 일정 수준(|r|≥0.3) 이상인 지표만 포함한다.
    qualifying = {
        col: (lag, corr_val) for col, (lag, corr_val) in all_best_lags.items()
        if corr_val >= MIN_INTERPRETABLE_CORR
    }
    excluded = [col for col in all_best_lags if col not in qualifying]

    if qualifying:
        for col, (lag, corr_val) in qualifying.items():
            lag_desc = "동시점 (0분기)" if lag == 0 else f"약 {lag}분기 후행"
            strength_color = "#1864ab" if abs(corr_val) >= 0.7 else "#4dabf7"
            st.markdown(
                f'<div class="corr-card">'
                f'<div class="corr-card-header">'
                f'<span class="corr-pair">{col} → CPI</span>'
                f'<span class="corr-badge" style="background-color:{strength_color};">{lag_desc}</span>'
                f'<span class="corr-badge" style="background-color:#12b886;">예상 방향과 일치</span>'
                f'<span class="corr-rval">r = {corr_val:+.2f}</span>'
                f'</div>'
                f'<div class="corr-detail">원가 상승 → 물가 상승이라는 <b>예상 방향</b>대로 CPI 등락률과 연관되는 모습입니다.</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("이번 조회 기간에는 이론적으로 예상되는 방향(원가 상승 → 물가 상승)과 부합하면서 "
                "충분히 강한 선행 신호가 확인되지 않았습니다.")

    if excluded:
        st.caption(
            "※ " + ", ".join(excluded) + "는 이번 조회 기간에는 예상 방향과 어긋나거나(반대 방향) "
            "상관관계가 약해(|r| < 0.3) 예측 신호로 해석하지 않고 제외했습니다. 위 그래프에는 "
            "참고용으로 그대로 남겨두었습니다."
        )

    if qualifying:
        # 최근 1~2분기 모멘텀은 해석에 채택된(이론적 방향과 부합하는) 지표만으로 계산한다.
        momentum_signals = []
        for col in qualifying:
            series = panel[col].dropna()
            if len(series) >= 3 and series.iloc[-3]:
                recent_chg = (series.iloc[-1] - series.iloc[-3]) / series.iloc[-3] * 100
                momentum_signals.append(recent_chg)
        if momentum_signals:
            avg_momentum = float(np.mean(momentum_signals))
            if avg_momentum >= 3:
                signal_label, signal_color = "물가 상방 압력 우세 (참고)", "#e03131"
            elif avg_momentum <= -3:
                signal_label, signal_color = "물가 하방 안정 우세 (참고)", "#1c7ed6"
            else:
                signal_label, signal_color = "혼조 / 뚜렷한 방향성 부재 (참고)", "#868e96"
            st.markdown(
                f'<span class="action-tag" style="background-color:{signal_color};">{signal_label}</span> '
                f'<span style="font-size:13px; opacity:0.8;">이론적 방향과 부합한 선행지표 '
                f'({", ".join(qualifying.keys())})의 최근 2분기 평균 변동률 {avg_momentum:+.2f}%를 '
                f'단순 평균한 규칙 기반 신호이며, 공식 물가 전망이 아닙니다.</span>',
                unsafe_allow_html=True,
            )

    # --- 사실 검토 및 해석: 위 통계적 프레임워크를 뒷받침하는 실제 사례를 팩트체크한다 ---
    st.markdown("")
    st.markdown("**📌 사실 검토** — 선행-후행 관계를 뒷받침하는 실제 사례")
    fact_rows = []
    if oil_events is not None and not oil_events.empty:
        fact_rows.extend(oil_events.sort_values("date").to_dict("records"))
    if cpi_events is not None and not cpi_events.empty:
        fact_rows.extend(cpi_events.sort_values("date").to_dict("records"))
    if fact_rows:
        fact_rows.sort(key=lambda r: r["date"])
        fact_lines = [f"- {r['date']:%Y-%m-%d} · **{r['title']}**: {r['fact']}" for r in fact_rows]
        st.markdown("\n".join(fact_lines))
    else:
        st.caption("현재 조회 기간에는 참고할 만한 사례가 포함되어 있지 않습니다.")

    st.markdown("**💬 해석** — 위 사실을 종합한 시장 해석")
    if fact_rows:
        opinion_lines = [f"- {r['opinion']}" for r in fact_rows if r.get("opinion")]
        st.markdown("\n".join(opinion_lines))
        st.caption(
            "종합하면, 2026년 1분기 이란전쟁발 지정학적 리스크로 촉발된 유가 급등이 약 1분기 안팎의 "
            "시차를 두고 석유류 가격 급등(6월 기준 전년 동월 대비 +24.7%)을 통해 국내 물가 상승률 "
            "확대(6월 3.2%, 2년 6개월래 최고)로 이어진 흐름이 확인됩니다. 다만 국가데이터처는 환율 "
            "상승분의 영향은 6월까지 본격적으로 나타나지 않았다고 밝혀, 유가 경로에 비해 환율 경로의 "
            "파급은 더 더딘 것으로 나타났습니다. 이는 하나의 사례에 기반한 정성적 해석이며, 표본 기간이 "
            "짧아 통계적 일반화에는 한계가 있습니다. 위 시차별 상관계수 분석에서 이론적 방향과 어긋난 "
            "지표가 있었다면, 이는 이 하나의 사례만으로 일반적인 법칙을 단정할 수 없다는 근거로도 함께 "
            "읽을 수 있습니다."
        )
    else:
        st.caption("현재 조회 기간에는 해석할 수 있는 사례가 포함되어 있지 않습니다.")


# ----------------------------------------------------------------------------
# 메인 화면
# ----------------------------------------------------------------------------
st.title("💱 USD/CNY · USD/JPY · WTI · 국내 CPI 통합 대시보드")
st.caption(
    "분석 기간: 2023-01-01 – 2026-08-31 (CPI는 2020년 이후 분기 기준 전체 표시) | "
    "통화정책·무역정책·시장심리·에너지 이벤트 기반 변동 요인 분석"
)
st.markdown(
    f'<span class="asof-badge">📅 FX·WTI 데이터 기준일: {ANALYSIS_ASOF_LABEL}</span>'
    f'<span class="asof-badge">📅 CPI: {CPI_ASOF_LABEL}</span>',
    unsafe_allow_html=True,
)

start_date, end_date = resolve_date_range(period, custom_start, custom_end)

with st.spinner("데이터를 불러오는 중입니다..."):
    try:
        data = {}
        for label, tkr in TICKERS.items():
            raw = fetch_fx_data(tkr, start_date, end_date)
            if raw.empty:
                st.warning(f"{label} 데이터를 가져오지 못했습니다.")
                continue
            if label == "USD/CNY":
                raw = sanitize_usdcny(raw)
            full = compute_indicators(raw)
            data[label] = trim_to_range(full, start_date, end_date)
    except Exception as e:
        st.error(f"환율 데이터 수집 중 오류가 발생했습니다: {e}")
        st.stop()

    wti_raw = load_wti_data()
    if wti_raw.empty:
        st.warning(
            "WTI 데이터 파일(data/wti_prices.csv)을 찾을 수 없습니다. "
            "스크립트와 같은 위치에 data/ 폴더를 두고 실행해 주세요."
        )
        wti_data = pd.DataFrame()
    else:
        wti_full = compute_indicators(wti_raw)
        wti_data = trim_to_range(wti_full, start_date, end_date)

    cpi_data = load_cpi_data()
    if cpi_data.empty:
        st.warning(
            "CPI 데이터 파일(data/cpi_kr.csv)을 찾을 수 없습니다. "
            "스크립트와 같은 위치에 data/ 폴더를 두고 실행해 주세요."
        )

if not data:
    st.error("표시할 환율 데이터가 없습니다.")
    st.stop()

events_in_range = EVENTS_DF[
    (EVENTS_DF["date"] >= pd.to_datetime(start_date)) & (EVENTS_DF["date"] <= pd.to_datetime(end_date))
]
oil_events_in_range = OIL_EVENTS_DF[
    (OIL_EVENTS_DF["date"] >= pd.to_datetime(start_date)) & (OIL_EVENTS_DF["date"] <= pd.to_datetime(end_date))
]
# CPI는 분기 지표 특성상 항상 2020년 이후 전체 구간을 표시하므로(설계 원칙 3번 참고),
# CPI 이벤트는 조회 기간 필터와 무관하게 항상 포함한다.
cpi_events_in_range = CPI_EVENTS_DF

# ============================================================================
# 모드 0: 4대 지표 통합 대시보드 (신규)
# ============================================================================
if view_mode.startswith("🌐"):

    cny_df = data.get("USD/CNY", pd.DataFrame())
    jpy_df = data.get("USD/JPY", pd.DataFrame())

    # --- 상단 KPI 카드 (4개) --------------------------------------------------
    st.subheader("📌 핵심 지표 KPI")
    kpi_cols = st.columns(4)

    with kpi_cols[0]:
        if not cny_df.empty:
            latest, base = cny_df.iloc[-1], cny_df.iloc[0]
            label = f"기준일 {base.name:%Y-%m-%d}"
            render_kpi_card("💴 USD/CNY", latest["Close"], base["Close"], label)
        else:
            st.info("USD/CNY 데이터 없음")

    with kpi_cols[1]:
        if not jpy_df.empty:
            latest, base = jpy_df.iloc[-1], jpy_df.iloc[0]
            label = f"기준일 {base.name:%Y-%m-%d}"
            render_kpi_card("💴 USD/JPY", latest["Close"], base["Close"], label, value_fmt="{:.2f}")
        else:
            st.info("USD/JPY 데이터 없음")

    with kpi_cols[2]:
        if not wti_data.empty:
            latest, base = wti_data.iloc[-1], wti_data.iloc[0]
            label = f"기준일 {base.name:%Y-%m-%d}"
            render_kpi_card("🛢️ WTI ($/배럴)", latest["Close"], base["Close"], label, value_fmt="{:.2f}")
        else:
            st.info("WTI 데이터 없음")

    with kpi_cols[3]:
        if not cpi_data.empty:
            latest_cpi = cpi_data.iloc[-1]
            base_cpi = cpi_data.iloc[0]
            yoy_pct = None
            if len(cpi_data) > 4:
                prev_year_q = cpi_data.iloc[-5]
                yoy_pct = (latest_cpi["cpi"] - prev_year_q["cpi"]) / prev_year_q["cpi"] * 100
            extra = f"{prev_year_q['quarter_label']} 대비(YoY) {yoy_pct:+.2f}%" if yoy_pct is not None else None
            label = f"기준분기 {base_cpi['quarter_label']}"
            render_kpi_card("📈 국내 CPI (2020=100)", latest_cpi["cpi"], base_cpi["cpi"], label,
                             value_fmt="{:.2f}", extra_caption=extra)
        else:
            st.info("CPI 데이터 없음")

    st.markdown("")

    # --- 중앙 2x2 시계열 차트 --------------------------------------------------
    st.subheader("📊 지표별 시계열 트렌드")
    integrated_fig = build_integrated_chart(
        cny_df, jpy_df, wti_data, cpi_data, events_in_range, oil_events_in_range,
        show_events_on_chart, plot_template, bg_color, text_color, grid_color,
        cpi_events=cpi_events_in_range,
    )
    st.plotly_chart(integrated_fig, width="stretch")

    st.markdown("")
    st.markdown("---")

    # --- 상관관계 분석 & 선행-후행 예측 프레임워크 ------------------------------
    quarterly_panel = build_quarterly_panel(cny_df, jpy_df, wti_data, cpi_data)
    if not quarterly_panel.empty:
        render_correlation_section(quarterly_panel, plot_template, bg_color, text_color, grid_color)
        st.markdown("")
        render_leading_lagging_section(
            quarterly_panel, plot_template, bg_color, text_color, grid_color,
            oil_events=oil_events_in_range, cpi_events=cpi_events_in_range,
        )
    else:
        st.info("상관관계 및 선행-후행 분석을 위한 데이터가 부족합니다.")

    st.markdown("")
    st.markdown("---")

    # --- 하단: 구매 전략 방향(Action Plan) --------------------------------------
    st.subheader("🧭 구매 전략 방향(Action Plan)")
    st.caption("각 지표의 현재 수준·변동 방향에 대한 규칙 기반 요약이며, 개별 기업의 실제 구매 의사결정을 대체하지 않는 참고용 가이드입니다.")
    action_cols = st.columns(4)

    with action_cols[0]:
        if not cny_df.empty:
            latest, base = cny_df.iloc[-1], cny_df.iloc[0]
            pct = (latest["Close"] - base["Close"]) / base["Close"] * 100 if base["Close"] else 0
            render_action_card("💴 USD/CNY", usdcny_action(latest["Close"], pct))

    with action_cols[1]:
        if not jpy_df.empty:
            latest, base = jpy_df.iloc[-1], jpy_df.iloc[0]
            pct = (latest["Close"] - base["Close"]) / base["Close"] * 100 if base["Close"] else 0
            render_action_card("💴 USD/JPY", usdjpy_action(latest["Close"], pct))

    with action_cols[2]:
        if not wti_data.empty:
            latest, base = wti_data.iloc[-1], wti_data.iloc[0]
            pct = (latest["Close"] - base["Close"]) / base["Close"] * 100 if base["Close"] else 0
            render_action_card("🛢️ WTI", wti_action(latest["Close"], pct))

    with action_cols[3]:
        if not cpi_data.empty:
            latest_cpi = cpi_data.iloc[-1]
            base_cpi = cpi_data.iloc[0]
            qoq_pct = (latest_cpi["cpi"] - base_cpi["cpi"]) / base_cpi["cpi"] * 100 if base_cpi["cpi"] else 0
            yoy_pct = 0.0
            if len(cpi_data) > 4:
                prev_year_q = cpi_data.iloc[-5]
                yoy_pct = (latest_cpi["cpi"] - prev_year_q["cpi"]) / prev_year_q["cpi"] * 100
            render_action_card("📈 국내 CPI", cpi_action(yoy_pct, qoq_pct))

    st.markdown("")
    st.markdown("---")
    st.subheader("📌 주요 변동 요인 타임라인")
    combined_events = pd.concat(
        [events_in_range, oil_events_in_range, cpi_events_in_range], ignore_index=True
    )
    render_event_list(combined_events)

# ============================================================================
# 공통(모드 1·2 전용): USD/CNY vs USD/JPY 비교표
# ============================================================================
else:
    # ========================================================================
    # 개별 통화 심층 분석
    # ========================================================================
    label = focus_currency
    df = data.get(label)
    if df is None or df.empty:
        st.error("데이터가 없습니다.")
        st.stop()

    latest = df.iloc[-1]
    base = df.iloc[0]
    change = latest["Close"] - base["Close"]
    pct_change = (change / base["Close"]) * 100 if base["Close"] else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f'<div class="metric-card"><h3>{df.index[-1]:%Y-%m-%d} 환율</h3>'
            f'<h1>{latest["Close"]:.4f}</h1></div>',
            unsafe_allow_html=True,
        )
    with col2:
        arrow = "▲" if change >= 0 else "▼"
        color = "#e03131" if change >= 0 else "#1c7ed6"
        st.markdown(
            f'<div class="metric-card"><h3>기준일 {base.name:%Y-%m-%d} 대비</h3>'
            f'<h1 style="color:{color};">{arrow} {abs(change):.4f} ({pct_change:+.2f}%)</h1></div>',
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f'<div class="metric-card"><h3>MA20 / MA50 ({df.index[-1]:%Y-%m-%d} 기준)</h3>'
            f'<h1 style="font-size:20px;">{latest["MA20"]:.4f} / {latest["MA50"]:.4f}</h1></div>',
            unsafe_allow_html=True,
        )

    st.markdown("")
    st.markdown(f'<div class="opinion-box">{generate_ai_opinion(latest, label)}</div>', unsafe_allow_html=True)
    st.markdown("")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="환율 (종가)",
                              line=dict(color=accent, width=2)))
    if show_ma:
        fig.add_trace(go.Scatter(x=df.index, y=df["MA20"], name="MA20",
                                  line=dict(color="#f59f00", width=1.4, dash="dot")))
        fig.add_trace(go.Scatter(x=df.index, y=df["MA50"], name="MA50",
                                  line=dict(color="#e64980", width=1.4, dash="dot")))
    if show_bollinger:
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_Upper"], name="볼린저 상단",
                                  line=dict(color="rgba(150,150,150,0.5)", width=1)))
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_Lower"], name="볼린저 하단",
                                  line=dict(color="rgba(150,150,150,0.5)", width=1),
                                  fill="tonexty", fillcolor="rgba(150,150,150,0.12)"))

    currency_events = events_in_range[events_in_range["currency"].isin([label, "공통"])]
    if show_events_on_chart:
        for _, ev in currency_events.iterrows():
            fig.add_vline(
                x=ev["date"].timestamp() * 1000, line_width=1, line_dash="dash",
                line_color=CATEGORY_COLORS.get(ev["category"], "#868e96"), opacity=0.6,
            )

    fig.update_layout(
        template=plot_template,
        title=f"{label} 환율 추세 ({df.index.min():%Y-%m-%d} ~ {df.index.max():%Y-%m-%d})",
        xaxis_title="날짜", yaxis_title="환율", height=520, hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=60, b=10),
        plot_bgcolor=bg_color, paper_bgcolor=bg_color, font=dict(color=text_color),
    )
    fig.update_xaxes(gridcolor=grid_color)
    fig.update_yaxes(gridcolor=grid_color)
    st.plotly_chart(fig, width="stretch")

    if show_rsi:
        rsi_fig = go.Figure()
        rsi_fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI",
                                      line=dict(color=accent, width=1.6)))
        rsi_fig.add_hline(y=70, line_dash="dash", line_color="#e03131",
                           annotation_text="과매수 (70)", annotation_position="top left")
        rsi_fig.add_hline(y=30, line_dash="dash", line_color="#2f9e44",
                           annotation_text="과매도 (30)", annotation_position="bottom left")
        rsi_fig.update_layout(
            template=plot_template, title="RSI (14일)", height=260,
            margin=dict(l=10, r=10, t=50, b=10),
            plot_bgcolor=bg_color, paper_bgcolor=bg_color, font=dict(color=text_color),
            yaxis=dict(range=[0, 100]),
        )
        rsi_fig.update_xaxes(gridcolor=grid_color)
        rsi_fig.update_yaxes(gridcolor=grid_color)
        st.plotly_chart(rsi_fig, width="stretch")

    st.markdown("")
    st.subheader(f"📌 {label} 주요 변동 요인 타임라인")
    render_event_list(currency_events)

    with st.expander("📄 원본 데이터 테이블 보기"):
        display_df = df[["Close", "MA20", "MA50", "BB_Upper", "BB_Lower", "RSI"]].copy()
        display_df = display_df.sort_index(ascending=False)
        st.dataframe(display_df.style.format("{:.4f}"), width="stretch")

st.markdown("---")
st.caption(
    "⚠️ 데이터 출처: Yahoo Finance(USD/CNY·USD/JPY) · 한국석유공사 PETRONET(WTI) · "
    "KOSIS(국내 CPI) / 변동 요인: 뉴스·리서치 보도 요약 (참고용, 투자 자문 아님)"
)
