"""서울 고령 보행자 교통사고 탐색 대시보드 (기존 processed CSV 전용)."""
from pathlib import Path
import json
from html import escape

import folium
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from folium.plugins import Fullscreen
from streamlit_folium import st_folium

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "processed"
FILES = {
    "panel": "01_자치구연도_패널.csv",
    "hotspots": "03_다발지역_서울.csv",
    "master": "04_보호구역_마스터.csv",
    "zones": "05_보호구역_경계.csv",
    "links": "06_다발지역_보호구역_연결.csv",
}

# ── 디자인 토큰: 파랑 = 보호구역, 주황 = 사고 ─────────────────────────
INK, MUTED, LINE, GROUND = "#101828", "#475467", "#DDE2EA", "#F3F5F8"
NAVY, BLUE, BLUE_DARK, BLUE_SOFT = "#0F1B2D", "#1D4ED8", "#1E3A8A", "#BFD3FB"
ORANGE, ORANGE_DARK, ORANGE_SOFT, GRAY = "#C2410C", "#9A3412", "#F6A96B", "#667085"
BANDS = [("보호구역과 겹침", BLUE), ("100m 이내", "#FCD9B6"), ("100–300m", ORANGE_SOFT),
         ("300–500m", "#DD6B20"), ("500m 초과", ORANGE_DARK)]
FONT = "'IBM Plex Sans KR', 'Malgun Gothic', system-ui, sans-serif"

st.set_page_config(page_title="서울 고령 보행자 교통안전", page_icon="🚶", layout="wide")

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+KR:wght@400;500;600;700&display=swap');
.stApp, .stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp td, .stApp th,
.stApp button, .stApp input {{ font-family: {FONT}; }}
.stApp {{ background: {GROUND}; color: {INK}; }}
.block-container {{ padding-top: 2.6rem; padding-bottom: 3rem; max-width: 1240px; }}

/* 사이드바 */
[data-testid="stSidebar"] {{ background: {NAVY}; }}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] label {{ color: #E6EAF0; }}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{ color: #9DB0C9; font-size: 12px; font-weight: 600; }}
[data-testid="stSidebar"] [data-baseweb="select"] > div {{ background: #FFFFFF !important; border-color: #FFFFFF !important; min-height: 44px; border-radius: 8px; }}
[data-testid="stSidebar"] [data-baseweb="select"] div {{ color: {INK} !important; }}
/* 화면 메뉴: 모든 행을 같은 높이(44px)로, 라디오 동그라미는 숨김 */
[data-testid="stSidebar"] div[role="radiogroup"] {{ gap: 4px !important; margin: 0 0 12px; }}
[data-testid="stSidebar"] div[role="radiogroup"] > label {{ display: flex !important; align-items: center !important; box-sizing: border-box;
  width: 100%; height: 44px; min-height: 44px; margin: 0 !important; padding: 0 12px !important; border-radius: 8px; cursor: pointer; }}
[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-of-type {{ display: none !important; }}
[data-testid="stSidebar"] div[role="radiogroup"] > label > div:last-child {{ display: flex !important; align-items: center; margin: 0 !important; padding: 0 !important; }}
[data-testid="stSidebar"] div[role="radiogroup"] > label div[data-testid="stMarkdownContainer"] {{ margin: 0 !important; padding: 0 !important; }}
[data-testid="stSidebar"] div[role="radiogroup"] > label p {{ margin: 0 !important; font-size: 15px; line-height: 1.2; }}
[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{ background: #17263C; }}
[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {{ background: #FFFFFF; }}
[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p {{ color: {NAVY} !important; font-weight: 600; }}
.ea-brand {{ margin-bottom: 20px; }}
.ea-brand small {{ display: block; font-size: 12px; font-weight: 600; letter-spacing: .08em; color: #9DB0C9; }}
.ea-brand b {{ display: block; margin-top: 6px; font-size: 19px; line-height: 1.35; color: #FFFFFF; }}
.ea-side-note {{ font-size: 12px; line-height: 1.6; color: #9DB0C9; }}

/* 본문 */
.ea-eyebrow {{ font-size: 13px; font-weight: 600; color: {MUTED}; }}
.ea-title {{ margin: 8px 0 0 !important; padding: 0 !important; font-size: 32px !important; line-height: 1.3; font-weight: 700; letter-spacing: -.01em; color: {INK}; }}
.ea-lead {{ margin: 10px 0 0; max-width: 820px; font-size: 16px; line-height: 1.6; color: #344054; }}
.ea-kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin: 24px 0 8px; }}
.ea-kpi {{ background: #FFFFFF; border: 1px solid {LINE}; border-radius: 12px; padding: 20px; }}
.ea-kpi .l {{ font-size: 13px; font-weight: 600; color: {MUTED}; }}
.ea-kpi .v {{ margin-top: 8px; font-size: 32px; font-weight: 700; line-height: 1.1; color: {INK}; }}
.ea-kpi .v span {{ font-size: 16px; font-weight: 500; color: {MUTED}; }}
.ea-kpi .d {{ margin-top: 8px; font-size: 13px; color: {MUTED}; }}
.ea-kpi .d.up {{ color: #B93815; font-weight: 600; }}
.ea-h2 {{ margin: 0 !important; padding: 0 !important; font-size: 18px !important; line-height: 1.4 !important; font-weight: 700; color: {INK}; }}
.ea-sub {{ margin-top: 4px; font-size: 13px; color: {MUTED}; }}
.ea-src {{ font-size: 12px; color: {MUTED}; }}
.ea-note {{ background: #E9EEF6; border-radius: 12px; padding: 20px 24px; margin-top: 8px; }}
.ea-note b {{ display: block; font-size: 14px; color: {INK}; }}
.ea-note p {{ margin: 6px 0 0; max-width: 880px; font-size: 14px; line-height: 1.6; color: #344054; }}
.ea-legend {{ display: flex; flex-wrap: wrap; gap: 8px 20px; font-size: 13px; color: #344054; }}
.ea-legend span {{ display: inline-flex; align-items: center; gap: 8px; }}
.ea-legend i {{ display: inline-block; width: 14px; height: 14px; box-sizing: border-box; }}
.ea-bands {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-top: 4px; }}
.ea-bands .k {{ display: flex; align-items: center; gap: 8px; font-size: 13px; color: #344054; }}
.ea-bands .k i {{ display: inline-block; width: 12px; height: 12px; border-radius: 3px; border: 1px solid #C9D1DC; box-sizing: border-box; }}
.ea-bands .n {{ font-size: 22px; font-weight: 700; color: {INK}; }}
.ea-bands .n span {{ font-size: 14px; font-weight: 500; color: {MUTED}; }}
.ea-bar {{ display: flex; gap: 2px; height: 36px; border-radius: 6px; overflow: hidden; margin: 14px 0; }}
.ea-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
.ea-table th {{ padding: 8px; font-size: 12px; font-weight: 600; color: {MUTED}; border-bottom: 1px solid {LINE}; text-align: left; }}
.ea-table td {{ padding: 10px 8px; border-bottom: 1px solid #EEF1F5; color: {INK}; }}
.ea-table .r {{ text-align: right; }}
.ea-table .out {{ color: {ORANGE_DARK}; font-weight: 600; }}
.ea-pill {{ display: inline-block; padding: 2px 8px; border-radius: 999px; background: #E0E9FD; color: {BLUE_DARK}; font-size: 12px; font-weight: 600; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ background: #FFFFFF; border-radius: 12px; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ── 데이터 ────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def read_csv(name: str, mtime: float) -> pd.DataFrame:
    return pd.read_csv(DATA / FILES[name], encoding="utf-8-sig")


def load(name):
    path = DATA / FILES[name]
    if not path.exists():
        st.error(f"필수 데이터 파일이 없습니다: {path}")
        st.stop()
    return read_csv(name, path.stat().st_mtime)


def total(df, col):
    """결측을 0으로 바꾸지 않는 합계. 값이 하나도 없으면 NaN."""
    return pd.to_numeric(df[col], errors="coerce").sum(min_count=1) if col in df else float("nan")


def num(value, digits=0):
    return "자료 없음" if pd.isna(value) else f"{value:,.{digits}f}"


# ── 화면 조각 ─────────────────────────────────────────────────────────
def html(text):
    st.markdown(text, unsafe_allow_html=True)


def header(eyebrow, title, lead=None):
    lead_html = f'<p class="ea-lead">{escape(lead)}</p>' if lead else ""
    html(f'<div class="ea-eyebrow">{escape(eyebrow)}</div><h1 class="ea-title">{escape(title)}</h1>{lead_html}')


def kpis(items):
    """items: (라벨, 값, 단위, 보조문구, 증가강조 여부, 값 색상)"""
    cards = []
    for label, value, unit, detail, up, color in items:
        unit_html = f"<span> {escape(unit)}</span>" if value != "자료 없음" else ""
        style = f' style="color:{color}"' if color else ""
        cards.append(f'<div class="ea-kpi"><div class="l">{escape(label)}</div><div class="v"{style}>{escape(value)}{unit_html}</div>'
                     f'<div class="d{" up" if up else ""}">{escape(detail)}</div></div>')
    html(f'<div class="ea-kpis">{"".join(cards)}</div>')


def card_title(title, sub=None):
    sub_html = f'<div class="ea-sub">{escape(sub)}</div>' if sub else ""
    html(f'<h2 class="ea-h2">{escape(title)}</h2>{sub_html}')


def note(title, body):
    html(f'<div class="ea-note"><b>{escape(title)}</b><p>{escape(body)}</p></div>')


def source(text):
    html(f'<div class="ea-src">{escape(text)}</div>')


def change(now, before, unit):
    """전년 대비 문구와 증가 여부."""
    if pd.isna(now) or pd.isna(before):
        return "전년 자료 없음", False
    diff = now - before
    if diff == 0:
        return "전년과 같음", False
    return f"전년 대비 {diff:+,.0f}{unit}", diff > 0


def style(fig, height=320):
    fig.update_layout(height=height, margin=dict(l=8, r=16, t=12, b=8), paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
                      font=dict(family=FONT, size=13, color=INK), hoverlabel=dict(font_family=FONT), title_text="")
    fig.update_xaxes(gridcolor="#E4E8EE", zeroline=False, linecolor=LINE)
    fig.update_yaxes(gridcolor="#E4E8EE", zeroline=False, linecolor=LINE)
    return fig


def ranking_chart(df, metric, highlight, height):
    """자치구 가로 막대. 한 가지 색만 쓰고 선택한 자치구만 진하게."""
    d = df.sort_values(metric, ascending=True)
    colors = [ORANGE_DARK if (highlight and g == highlight) else (ORANGE if not highlight else ORANGE_SOFT) for g in d["자치구명"]]
    digits = 0 if metric == "고령보행자_사고건수" else 1
    fig = go.Figure(go.Bar(x=d[metric], y=d["자치구명"], orientation="h", marker_color=colors,
                           text=[f"{v:,.{digits}f}" for v in d[metric]], textposition="outside", cliponaxis=False,
                           hovertemplate="%{y}: %{x:,." + str(digits) + "f}<extra></extra>"))
    fig.update_xaxes(showticklabels=False, showgrid=False)
    return style(fig, height)


def band_counts(link_rows):
    d = pd.to_numeric(link_rows["최단거리_m"], errors="coerce").dropna()
    return [int((d <= 0).sum()), int(((d > 0) & (d <= 100)).sum()), int(((d > 100) & (d <= 300)).sum()),
            int(((d > 300) & (d <= 500)).sum()), int((d > 500).sum())]


def short_name(row):
    """'제기동 동서시장'처럼 짧은 지점 이름."""
    if pd.notna(row.get("법정동명")) and pd.notna(row.get("부근명")):
        return f"{row['법정동명']} {str(row['부근명']).replace(' 부근', '')}"
    return str(row["지점명"])


def wkt_geojson(wkt):
    """WKT POLYGON/MULTIPOLYGON을 지도용 GeoJSON으로 변환. 좌표는 WGS84 경도·위도."""
    from shapely import wkt as shapely_wkt
    from shapely.geometry import mapping
    return mapping(shapely_wkt.loads(wkt))


def plot_map(hs, zones, links):
    joined = hs.merge(links[["다발지역FID", "경계중첩", "최단거리_m"]], on="다발지역FID", how="left", validate="one_to_one")
    centers = joined[["위도", "경도"]].apply(pd.to_numeric, errors="coerce").dropna()
    lat, lon = (centers["위도"].mean(), centers["경도"].mean()) if len(centers) else (37.5665, 126.9780)
    m = folium.Map(location=[lat, lon], zoom_start=12 if len(centers) else 11, tiles="CartoDB positron")
    Fullscreen().add_to(m)
    z_layer = folium.FeatureGroup(name=f"보호구역 API 경계 ({len(zones)}건)", show=True)
    h_layer = folium.FeatureGroup(name=f"사고다발지역 ({len(joined)}곳)", show=True)
    for _, row in zones.iterrows():
        if pd.isna(row.get("경계WKT")):
            continue
        try:
            geo = wkt_geojson(row["경계WKT"])
            name = escape(str(row["API시설명"]))
            area = escape(str(row["자치구명"]))
            designated = "자료 없음" if pd.isna(row["지정연도"]) else str(int(row["지정연도"])) + "년 (명단 기준)"
            popup = folium.Popup(
                f"<b>노인보호구역 API 경계</b><br>시설: {name}<br>자치구: {area}<br>지정연도: {designated}",
                max_width=340,
            )
            folium.GeoJson(
                geo,
                style_function=lambda feature: {"color": BLUE, "weight": 2, "fillColor": BLUE_SOFT, "fillOpacity": 0.55},
                tooltip=f"보호구역: {row['API시설명']}",
                popup=popup,
            ).add_to(z_layer)
        except (ValueError, TypeError):
            continue
    for _, row in joined.iterrows():
        if pd.isna(row.get("다발지역폴리곤")):
            continue
        try:
            geo = json.loads(row["다발지역폴리곤"])
            known = pd.notna(row["경계중첩"])
            overlap = known and int(row["경계중첩"]) == 1
            label = "겹침" if overlap else ("보호구역 밖" if known else "판정 미상")
            line, fill = (BLUE_DARK, BLUE_DARK) if overlap else ((ORANGE_DARK, ORANGE_SOFT) if known else (GRAY, GRAY))
            name = escape(str(row["지점명"]))
            accident_count = "자료 없음" if pd.isna(row["사고건수"]) else f"{int(row['사고건수']):,}건"
            distance = "자료 없음" if pd.isna(row["최단거리_m"]) else f"{float(row['최단거리_m']):,.1f}m"
            popup = folium.Popup(
                f"<b>사고다발지역 선정 영역</b><br>지점: {name}<br>사고연도: {int(row['사고연도'])}년"
                f"<br>선정지역 집계 사고건수: {accident_count}<br>보호구역 경계: {label}"
                f"<br>서울 전체 API 경계까지 최단 직선거리: {distance}",
                max_width=400,
            )
            folium.GeoJson(
                geo,
                style_function=lambda feature, a=line, b=fill: {"color": a, "weight": 2, "fillColor": b, "fillOpacity": 0.7},
                tooltip=f"{row['지점명']} | {label} | 사고연도 {int(row['사고연도'])}년",
                popup=popup,
            ).add_to(h_layer)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    z_layer.add_to(m)
    h_layer.add_to(m)
    folium.LayerControl(collapsed=True).add_to(m)
    return m, joined


# ── 공통 필터 ─────────────────────────────────────────────────────────
panel = load("panel")
hotspots = load("hotspots")
master = load("master")
zones = load("zones")
links = load("links")
for df in (panel, hotspots, master, zones, links):
    for col in ("사고연도", "지정연도", "경계중첩"):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")

# 자치구 25곳을 색만으로 구분하기는 어려워서 색 + 선 모양 + 표식 모양을 함께 고정 배정한다.
GU_COLORS = ["#C2410C", "#1D4ED8", "#0F766E", "#7C3AED", "#BE185D", "#4D7C0F", "#0369A1", "#B45309", "#111827", "#DC2626",
             "#0891B2", "#A16207", "#6D28D9", "#15803D", "#DB2777", "#475569", "#EA580C", "#2563EB", "#059669", "#9333EA",
             "#9F1239", "#65A30D", "#0E7490", "#CA8A04", "#4338CA"]
GU_DASHES = ["solid", "dash", "dot", "dashdot", "longdash"]
GU_SYMBOLS = ["circle", "square", "diamond", "triangle-up", "x", "star", "triangle-down"]

PAGES = ["개요", "지역별 사고 현황", "공간 분석 지도", "지정 전후 탐색"]
years = sorted(panel["사고연도"].dropna().astype(int).unique())
gu_list = sorted(panel["자치구명"].dropna().unique())
with st.sidebar:
    html(f'<div class="ea-brand"><small>SEOUL · {years[0]}–{years[-1]}</small><b>고령 보행자<br>교통안전</b></div>')
    page = st.radio("화면", PAGES, label_visibility="collapsed")
    year = st.selectbox("사고연도", years, index=len(years) - 1)
    gu = st.selectbox("자치구", ["서울 전체"] + gu_list, index=0)
    html('<div class="ea-side-note">탐색용 대시보드입니다. 보호구역의 사고 예방 효과를 검증하는 도구가 아닙니다.</div>')

scope = "서울 전체" if gu == "서울 전체" else gu
place = "서울" if gu == "서울 전체" else gu           # 문장 안에서 쓰는 이름
in_scope = (lambda df: df if gu == "서울 전체" else df[df["자치구명"] == gu])
year_all = panel[panel["사고연도"] == year]                 # 선택 연도, 25개 구
p = in_scope(year_all).copy()                               # 선택 연도·범위
prev = in_scope(panel[panel["사고연도"] == year - 1])       # 전년·범위
h = in_scope(hotspots[hotspots["사고연도"] == year]).copy()
z = in_scope(zones).copy()

# ── 01 개요 ───────────────────────────────────────────────────────────
if page == "개요":
    acc, dead = total(p, "고령보행자_사고건수"), total(p, "고령보행자_사망자수")
    all_acc, all_dead = total(p, "전체보행자_사고건수"), total(p, "전체보행자_사망자수")
    elderly, people = total(p, "고령인구"), total(p, "총인구")
    rate = acc / elderly * 10000 if pd.notna(acc) and pd.notna(elderly) and elderly > 0 else float("nan")
    prev_acc, prev_dead, prev_elderly = total(prev, "고령보행자_사고건수"), total(prev, "고령보행자_사망자수"), total(prev, "고령인구")
    prev_rate = prev_acc / prev_elderly * 10000 if pd.notna(prev_acc) and pd.notna(prev_elderly) and prev_elderly > 0 else float("nan")
    facilities = total(p, "보호구역_명단시설수")

    if pd.notna(all_dead) and all_dead > 0 and pd.notna(dead):
        title = f"보행 사망자 {all_dead:,.0f}명 중 {dead:,.0f}명이 65세 이상입니다"
    elif pd.notna(acc):
        title = f"{year}년 고령 보행자 사고는 {acc:,.0f}건입니다"
    else:
        title = "선택한 범위에 사고 자료가 없습니다"
    lead = None
    if pd.notna(people) and people > 0 and pd.notna(all_acc) and all_acc > 0 and pd.notna(acc):
        lead = (f"65세 이상은 {place} 인구의 {elderly / people:.1%}인데 보행자 사고의 {acc / all_acc:.1%}를 차지합니다. "
                "노인보호구역이 이들이 다치는 곳을 얼마나 덮고 있는지 살펴봅니다.")
    header(f"{scope} · {year}년 · 사고 발생 지역 기준", title, lead)

    d_acc, up_acc = change(acc, prev_acc, "건")
    d_dead, up_dead = change(dead, prev_dead, "명")
    d_rate = "전년 자료 없음" if pd.isna(prev_rate) else f"{year - 1}년 {prev_rate:,.1f}건"
    kpis([
        ("고령 보행자 사고", num(acc), "건", d_acc, up_acc, None),
        ("고령 보행 사망자", num(dead), "명", d_dead, up_dead, None),
        ("고령인구 1만 명당 사고", num(rate, 1), "건", d_rate, False, None),
        ("노인보호구역", num(facilities), "곳", f"{year}년 말 지정 명단 기준", False, BLUE),
    ])

    left, right = st.columns(2, gap="medium")
    with left, st.container(border=True):
        trend = in_scope(panel).groupby("사고연도", as_index=False)["고령보행자_사고건수"].sum(min_count=1).dropna()
        card_title(f"{place} 고령 보행자 사고 추이", f"사고 건수, {years[0]}–{years[-1]}년")
        if trend.empty:
            st.info("선택한 범위에 연도별 사고건수 자료가 없습니다.")
        else:
            fig = go.Figure(go.Scatter(x=trend["사고연도"], y=trend["고령보행자_사고건수"], mode="lines+markers+text",
                                       text=[f"{v:,.0f}" for v in trend["고령보행자_사고건수"]], textposition="top center",
                                       line=dict(color=ORANGE, width=3), marker=dict(size=10, color="#FFFFFF", line=dict(color=ORANGE, width=3)),
                                       hovertemplate="%{x}년: %{y:,.0f}건<extra></extra>", cliponaxis=False))
            fig.update_xaxes(dtick=1, showgrid=False)
            fig.update_yaxes(rangemode="tozero", tickformat=",")
            st.plotly_chart(style(fig, 330), width="stretch")
        source("출처: 한국도로교통공단 TAAS 시군구별 보행노인 사고 통계")
    with right, st.container(border=True):
        ranked = year_all.dropna(subset=["고령인구1만명당_고령보행자사고"]).sort_values("고령인구1만명당_고령보행자사고", ascending=False)
        if ranked.empty:
            card_title("자치구별 사고율")
            st.info("선택한 연도에 자치구별 사고율 자료가 없습니다.")
        else:
            top, low = ranked.iloc[0], ranked.iloc[-1]
            ratio = top["고령인구1만명당_고령보행자사고"] / low["고령인구1만명당_고령보행자사고"]
            card_title(f"사고율은 {top['자치구명']}가 {low['자치구명']}의 {ratio:.1f}배입니다", f"고령인구 1만 명당 사고 건수, {year}년 상위 10개 구")
            st.plotly_chart(ranking_chart(ranked.head(10), "고령인구1만명당_고령보행자사고", None if gu == "서울 전체" else gu, 330), width="stretch")
        source("사고는 발생 지역, 인구는 거주지 기준입니다. 전체 순위는 ‘지역별 사고 현황’에서 볼 수 있습니다.")

    with st.container(border=True):
        linked = in_scope(links[links["사고연도"] == year])
        counts = band_counts(linked)
        if sum(counts) == 0:
            card_title("사고다발지역과 보호구역")
            st.info("선택한 연도와 자치구에는 공식 선정 기준을 충족한 사고다발지역이 없습니다. 사고가 없었다는 뜻은 아닙니다.")
        else:
            card_title(f"사고다발지역 {sum(counts)}곳 중 보호구역과 겹치는 곳은 {counts[0]}곳입니다",
                       f"{year}년 고령 보행자 사고다발지역에서 가장 가까운 노인보호구역 경계까지의 직선거리")
            segs = "".join(f'<span style="flex:{n} 1 0;background:{c}"></span>' for (_, c), n in zip(BANDS, counts) if n)
            keys = "".join(f'<div><div class="k"><i style="background:{c}"></i>{escape(name)}</div><div class="n">{n}<span> 곳</span></div></div>'
                           for (name, c), n in zip(BANDS, counts))
            html(f'<div class="ea-bar" role="img" aria-label="거리 구간별 사고다발지역 수">{segs}</div><div class="ea-bands">{keys}</div>')

    note("이 수치를 읽을 때",
         "사고다발지역은 공단이 선정한 영역이며 개별 사고 전체가 아닙니다. 보호구역 경계는 현재 API 기록이라 지정 당시 범위와 다를 수 있고, "
         "명단에 있지만 경계 자료가 없는 시설도 있습니다. 겹치지 않는다는 사실이 보호구역의 효과가 없다는 뜻은 아닙니다.")

# ── 02 지역별 사고 현황 ───────────────────────────────────────────────
elif page == "지역별 사고 현황":
    usable = year_all.dropna(subset=["고령보행자_사고건수"])
    if usable.empty:
        header(f"서울 25개 자치구 · {year}년", "선택한 연도에 사고 자료가 없습니다")
    else:
        by_rate = usable.dropna(subset=["고령인구1만명당_고령보행자사고"]).sort_values("고령인구1만명당_고령보행자사고", ascending=False)
        by_count = usable.sort_values("고령보행자_사고건수", ascending=False)
        most = by_count.iloc[0]["자치구명"]
        if by_rate.empty:
            title = f"사고가 가장 많은 곳은 {most}입니다"
        elif by_rate.iloc[0]["자치구명"] == most:
            title = f"사고 건수와 인구 대비 사고율 모두 {most}가 가장 높습니다"
        else:
            title = f"사고가 가장 많은 곳은 {most}, 인구 대비로는 {by_rate.iloc[0]['자치구명']}입니다"
        header(f"서울 25개 자치구 · {year}년 · 사고 발생 지역 기준", title,
               "사고 건수와 고령인구 1만 명당 사고율은 서로 다른 질문에 답합니다. 두 지표의 순위가 어떻게 달라지는지 비교해 보세요.")
        html("<div style='height:16px'></div>")
        with st.container(border=True):
            metric = st.radio("표시 지표", ["고령인구1만명당_고령보행자사고", "고령보행자_사고건수"], horizontal=True,
                              format_func=lambda x: "사고 건수" if x == "고령보행자_사고건수" else "고령인구 1만 명당 사고")
            card_title("자치구별 " + ("고령 보행자 사고 건수" if metric == "고령보행자_사고건수" else "고령인구 1만 명당 사고 건수"),
                       f"{year}년" + ("" if gu == "서울 전체" else f" · {gu} 강조"))
            st.plotly_chart(ranking_chart(usable.dropna(subset=[metric]), metric, None if gu == "서울 전체" else gu, 720), width="stretch")
            source("출처: TAAS 시군구별 보행노인 사고 통계, 서울 열린데이터광장 65세 이상 인구. 사고는 발생 지역, 인구는 거주지 기준입니다.")

    with st.container(border=True):
        card_title("자치구별 연도별 추이", f"고령 보행자 사고 건수, {years[0]}–{years[-1]}년. 사이드바의 사고연도와 무관하게 전체 기간을 보여줍니다.")
        default = [gu] if gu != "서울 전체" else [g for g in ("동대문구", "도봉구") if g in gu_list]
        picked = st.multiselect("비교할 자치구", gu_list, default=default)
        comparison = panel[panel["자치구명"].isin(picked)].dropna(subset=["고령보행자_사고건수"]).sort_values("사고연도")
        if comparison.empty:
            st.info("비교할 자치구를 하나 이상 선택해 주세요.")
        else:
            look = {g: (GU_COLORS[i % len(GU_COLORS)], GU_DASHES[i % len(GU_DASHES)], GU_SYMBOLS[i % len(GU_SYMBOLS)])
                    for i, g in enumerate(gu_list)}
            fig2 = px.line(comparison, x="사고연도", y="고령보행자_사고건수", color="자치구명", line_dash="자치구명", symbol="자치구명",
                           category_orders={"자치구명": [g for g in gu_list if g in picked]},
                           color_discrete_map={g: v[0] for g, v in look.items()},
                           line_dash_map={g: v[1] for g, v in look.items()},
                           symbol_map={g: v[2] for g, v in look.items()},
                           labels={"사고연도": "", "고령보행자_사고건수": "사고 건수", "자치구명": "자치구"})
            fig2.update_traces(line=dict(width=2.5), marker=dict(size=9))
            fig2.update_xaxes(dtick=1, showgrid=False)
            fig2.update_layout(hovermode="closest", legend=dict(orientation="v", x=1.02, y=1, xanchor="left", yanchor="top", title_text=""))
            st.plotly_chart(style(fig2, max(380, 24 * len(picked) + 80)), width="stretch")
        source("자치구마다 색·선 모양·표식 모양이 고정돼 있습니다. 범례를 누르면 해당 구를 숨기거나 다시 볼 수 있습니다. 결측값은 0건으로 바꾸지 않고 비워 둡니다.")

    with st.expander("자료 표 보기"):
        st.dataframe(p[["사고연도", "자치구명", "고령인구", "고령보행자_사고건수", "고령보행자_사망자수",
                        "고령인구1만명당_고령보행자사고", "고령보행자_출처"]], hide_index=True, width="stretch")

# ── 03 공간 분석 지도 ─────────────────────────────────────────────────
elif page == "공간 분석 지도":
    view, joined = plot_map(h, z, links)
    known = joined["경계중첩"].notna()
    overlapping = int((joined.loc[known, "경계중첩"] == 1).sum())
    outside = int((joined.loc[known, "경계중첩"] == 0).sum())
    unknown = int((~known).sum())
    if len(joined) == 0:
        title = f"{place}에는 {year}년 사고다발지역이 없습니다"
    else:
        title = f"{place} 사고다발지역 {len(joined)}곳 중 {outside}곳은 보호구역 밖에 있습니다"
    header(f"{scope} · {year}년 · 사고다발지역 선정 영역 기준", title)
    cards = [("사고다발지역", f"{len(joined)}", "곳", "공단 선정 영역 수", False, None),
             ("보호구역과 겹침", f"{overlapping}", "곳", "경계가 맞닿거나 겹침", False, BLUE),
             ("보호구역 밖", f"{outside}", "곳", "경계와 떨어져 있음", False, "#B93815"),
             ("보호구역 경계 기록", f"{len(z)}", "건", "행안부 API 기준", False, None)]
    if unknown:
        cards.append(("판정 미상", f"{unknown}", "곳", "연결 자료 없음", False, None))
    kpis(cards)
    if year <= 2020:
        st.warning("2020년 이전 사고다발지역은 이후와 선정 기준이 달라 연도 간 직접 비교에 주의해야 합니다.")

    map_col, list_col = st.columns([3, 2], gap="medium")
    with map_col, st.container(border=True):
        html(f'<div class="ea-legend"><span><i style="background:{BLUE_SOFT};border:2px solid {BLUE};border-radius:3px"></i>노인보호구역 경계</span>'
             f'<span><i style="background:{BLUE_DARK};border-radius:50%"></i>겹치는 사고다발지역</span>'
             f'<span><i style="background:{ORANGE_SOFT};border:2px solid {ORANGE_DARK};border-radius:50%"></i>보호구역 밖 사고다발지역</span></div>')
        st_folium(view, width=None, height=540, returned_objects=[])
        source("영역을 누르면 집계 사고 건수와 가장 가까운 보호구역까지의 거리가 나옵니다.")
    with list_col, st.container(border=True):
        card_title("사고다발지역 목록", "집계 사고 건수와 가장 가까운 보호구역까지 직선거리")
        if joined.empty:
            st.info("표시할 사고다발지역이 없습니다. 개별 사고가 없었다는 뜻은 아닙니다.")
        else:
            ordered = joined.sort_values(["사고건수", "최단거리_m"], ascending=[False, True])
            rows = []
            for _, r in ordered.head(12).iterrows():
                if pd.isna(r["경계중첩"]):
                    where = "판정 미상"
                elif int(r["경계중첩"]) == 1:
                    where = '<span class="ea-pill">겹침</span>'
                else:
                    where = f'<span class="out">{float(r["최단거리_m"]):,.0f}m</span>'
                place = escape(short_name(r) if gu != "서울 전체" else f"{r['자치구명']} {short_name(r)}")
                rows.append(f'<tr><td>{place}</td><td class="r"><b>{num(r["사고건수"])}건</b></td><td class="r">{where}</td></tr>')
            html('<table class="ea-table"><thead><tr><th scope="col">지점</th><th scope="col" class="r">사고</th>'
                 f'<th scope="col" class="r">보호구역</th></tr></thead><tbody>{"".join(rows)}</tbody></table>')
            if len(ordered) > 12:
                source(f"사고 건수 상위 12곳입니다. 나머지 {len(ordered) - 12}곳은 아래 표에서 볼 수 있습니다.")

    if gu == "서울 전체" and not joined.empty:
        with st.container(border=True):
            card_title("자치구별 사고다발지역과 보호구역 중첩", f"{year}년 사고다발지역 선정 영역 수. 개별 사고 건수가 아닙니다.")
            chart = joined[["자치구명", "경계중첩"]].copy()
            chart["분류"] = chart["경계중첩"].map({1: "보호구역과 겹침", 0: "보호구역 밖"}).fillna("판정 미상")
            counts = chart.groupby(["자치구명", "분류"], as_index=False).size().rename(columns={"size": "선정지역 수"})
            order = counts.groupby("자치구명")["선정지역 수"].sum().sort_values(ascending=False).index.tolist()
            fig = px.bar(counts, x="자치구명", y="선정지역 수", color="분류", barmode="stack", text_auto=True,
                         category_orders={"자치구명": order, "분류": ["보호구역과 겹침", "보호구역 밖", "판정 미상"]},
                         color_discrete_map={"보호구역과 겹침": BLUE_DARK, "보호구역 밖": ORANGE_SOFT, "판정 미상": GRAY},
                         labels={"자치구명": "", "선정지역 수": "선정지역 수 (곳)", "분류": ""})
            fig.update_layout(legend=dict(orientation="h", y=1.12))
            fig.update_xaxes(showgrid=False)
            st.plotly_chart(style(fig, 360), width="stretch")
            if overlapping + outside:
                source(f"판정 가능한 {overlapping + outside}곳 중 보호구역 밖은 {outside}곳({outside / (overlapping + outside):.1%})입니다.")

    with st.expander("자료 표 보기"):
        st.dataframe(joined[["지점명", "사고연도", "사고건수", "경계중첩", "최단거리_m"]], hide_index=True, width="stretch")
    note("이 지도를 읽을 때",
         "거리는 자치구 경계와 상관없이 서울 전체 보호구역 중 가장 가까운 경계까지의 직선거리이며 보행 경로가 아닙니다. "
         "경계는 현재 API 기록이라 지정 당시 범위와 다를 수 있고 공식 지정 시설 전체를 포괄하지 않을 수 있습니다. "
         "사고다발지역은 개별 사고 지점이 아니라 선정된 영역입니다.")

# ── 04 지정 전후 탐색 ─────────────────────────────────────────────────
else:
    candidates = in_scope(master[(master["명단변동"] == "신규등재") & master["지정연도"].notna()]).copy()
    with_boundary = int((pd.to_numeric(candidates["API경계기록수"], errors="coerce") > 0).sum())
    header(f"{scope} · 지정 전후 탐색", "지정 효과는 아직 판단할 수 없습니다",
           "같은 보호구역의 지정 전과 후 개별 사고 건수를 비교할 자료가 없습니다. 아래는 사고다발지역 선정 기록과 신규 지정 시설을 나란히 놓은 탐색 자료입니다.")
    kpis([
        ("신규 등재 시설", f"{len(candidates)}", "곳", "2023–2025년 명단에 새로 등장", False, BLUE),
        ("경계 자료가 있는 시설", f"{with_boundary}", "곳", "공간 비교가 가능한 곳", False, None),
        ("경계 자료가 없는 시설", f"{len(candidates) - with_boundary}", "곳", "API에 경계 없음", False, None),
    ])

    with st.container(border=True):
        card_title("사고다발지역 선정 기록 추이", "연도별 선정 영역 수. 사고 추세나 지정 효과의 추정치가 아닙니다.")
        counts = in_scope(hotspots).groupby(["사고연도", "선정기준구간"], as_index=False).size()
        if counts.empty:
            st.info("선택한 자치구에는 사고다발지역 선정 기록이 없습니다.")
        else:
            eras = sorted(counts["선정기준구간"].unique())
            fig = px.bar(counts, x="사고연도", y="size", color="선정기준구간",
                         color_discrete_map=dict(zip(eras, [GRAY, ORANGE])),
                         labels={"size": "선정 영역 수 (곳)", "사고연도": "", "선정기준구간": "선정 기준"})
            fig.update_xaxes(dtick=1, showgrid=False)
            fig.update_layout(legend=dict(orientation="h", y=1.12, title_text=""), bargap=0.25)
            st.plotly_chart(style(fig, 360), width="stretch")
        source("회색과 주황은 선정 기준이 다른 구간입니다. 두 구간을 하나의 추세로 이어서 읽으면 안 됩니다.")

    with st.container(border=True):
        card_title("신규 등재 시설", "서울시 연말 지정 명단에 새로 등장한 노인보호구역")
        if candidates.empty:
            st.info("선택한 자치구에는 신규 등재 시설이 없습니다.")
        else:
            st.dataframe(candidates.sort_values(["지정연도", "자치구명"], ascending=[False, True])
                         [["시설명", "자치구명", "지정연도", "최초등재명단", "API경계기록수"]], hide_index=True, width="stretch")

    note("이 자료를 읽을 때",
         "명단에 새로 등장한 연도는 실제 지정 고시일과 다를 수 있고, 지정 당시의 경계도 확인되지 않았습니다. "
         "지정 효과는 개별 사고 자료와 정보공개청구 결과를 확보한 뒤에 판단할 수 있습니다.")

st.divider()
st.caption("데이터 출처와 처리 기준: 저장소 README.md · 데이터사전.md · data/processed/ | 관측된 공간 관계와 사고 감소의 인과효과는 다릅니다.")
