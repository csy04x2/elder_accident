"""서울 고령 보행자 교통사고 탐색 대시보드 (기존 processed CSV 전용)."""
from pathlib import Path
import json
from base64 import b64encode
from math import ceil, floor, log10
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
BOUNDARY = DATA / "08_서울_자치구_경계.geojson"
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
[data-testid="stSidebar"] div[role="radiogroup"] label {{ display: flex !important; align-items: center !important; box-sizing: border-box;
  width: 100%; height: 44px; min-height: 44px; margin: 0 !important; padding: 0 12px !important; border-radius: 8px; cursor: pointer; }}
[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-of-type {{ display: none !important; }}
[data-testid="stSidebar"] div[role="radiogroup"] label > div:last-child {{ display: flex !important; align-items: center; margin: 0 !important; padding: 0 !important; }}
[data-testid="stSidebar"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] {{ margin: 0 !important; padding: 0 !important; }}
[data-testid="stSidebar"] div[role="radiogroup"] label p {{ margin: 0 !important; font-size: 15px; line-height: 1.2; }}
[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{ background: #17263C; }}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{ background: #FFFFFF; }}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {{ color: {NAVY} !important; font-weight: 600; }}
.ea-brand {{ margin-bottom: 20px; }}
.ea-brand small {{ display: block; font-size: 12px; font-weight: 600; letter-spacing: .08em; color: #9DB0C9; }}
.ea-brand b {{ display: block; margin-top: 6px; font-size: 19px; line-height: 1.35; color: #FFFFFF; }}
.ea-side-note {{ font-size: 12px; line-height: 1.6; color: #9DB0C9; }}

/* 본문 */
.ea-eyebrow {{ font-size: 13px; font-weight: 600; color: {MUTED}; }}
.ea-title {{ margin: 8px 0 0 !important; padding: 0 !important; font-size: 32px !important; line-height: 1.3; font-weight: 700; letter-spacing: -.01em; color: {INK}; }}
.ea-kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin: 24px 0 8px; }}
.ea-kpi {{ background: #FFFFFF; border: 1px solid {LINE}; border-radius: 12px; padding: 20px; }}
.ea-kpi .l {{ font-size: 13px; font-weight: 600; color: {MUTED}; }}
.ea-kpi .v {{ margin-top: 8px; font-size: 32px; font-weight: 700; line-height: 1.1; color: {INK}; }}
.ea-kpi .v span {{ font-size: 16px; font-weight: 500; color: {MUTED}; }}
.ea-kpi .d {{ margin-top: 8px; font-size: 13px; color: {MUTED}; }}
.ea-kpi .d.up {{ color: #B93815; font-weight: 600; }}
.ea-lead {{ margin: 10px 0 0; max-width: 820px; font-size: 16px; line-height: 1.6; color: #344054; }}
.ea-h2 {{ margin: 0 !important; padding: 0 !important; font-size: 18px !important; line-height: 1.4 !important; font-weight: 700; color: {INK}; }}
.ea-sub {{ margin-top: 4px; font-size: 13px; color: {MUTED}; }}
.ea-src {{ font-size: 12px; color: {MUTED}; }}
.ea-note {{ background: #E9EEF6; border-radius: 12px; padding: 20px 24px; margin-top: 8px; }}
.ea-note b {{ display: block; font-size: 14px; color: {INK}; }}
.ea-note p {{ margin: 6px 0 0; max-width: 880px; font-size: 14px; line-height: 1.6; color: #344054; }}
.ea-legend {{ display: flex; flex-wrap: wrap; gap: 8px 20px; font-size: 13px; color: #344054; }}
.ea-legend span {{ display: inline-flex; align-items: center; gap: 8px; }}
.ea-legend i {{ display: inline-block; width: 14px; height: 14px; box-sizing: border-box; }}
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


DISTRICT_METRICS = {
    "65세 이상 거주인구": ("고령인구", "명", 0),
    "고령 생활인구": ("고령생활인구_연평균", "명", 0),
    "고령 보행자 사고 건수": ("고령보행자_사고건수", "건", 0),
    "고령인구 1만 명당 사고 건수": ("고령인구1만명당_고령보행자사고", "건", 1),
    "고령 보행 사망자": ("고령보행자_사망자수", "명", 0),
    "노인보호구역": ("보호구역_명단시설수", "곳", 0),
    "고령 보행자 사고다발지역": ("다발지역_수", "곳", 0),
    "보호구역 경계와 겹치는 사고다발지역": ("다발지역_보호구역중첩수", "곳", 0),
}


def district_ranking(frame, label, focus):
    column, unit, digits = DISTRICT_METRICS[label]
    ranked = frame.assign(value=pd.to_numeric(frame[column], errors="coerce"))
    ranked = ranked.sort_values(["value", "자치구명"], ascending=[False, True], na_position="last")
    maximum = ranked["value"].max()
    scale = maximum if pd.notna(maximum) and maximum > 0 else 1
    rows = []
    for district, value in ranked[["자치구명", "value"]].itertuples(index=False, name=None):
        value_text = "자료 없음" if pd.isna(value) else f"{num(value, digits)}{unit}"
        width = 0 if pd.isna(value) else value / scale * 100
        accent = " district-highlight" if district in {"동대문구", "도봉구", focus} else ""
        rows.append(
            f'<tr class="{accent}"><th scope="row">{escape(district)}</th>'
            f'<td class="district-value">{value_text}</td>'
            f'<td class="district-track" aria-hidden="true"><div class="district-bar" style="width:{width:.4f}%"></div></td>'
            f'<td class="district-end" aria-hidden="true">{value_text}</td></tr>'
        )
    html(
        '<style>'
        '.district-table{width:100%;table-layout:fixed;border-collapse:collapse;font-size:13px}'
        '.district-table th,.district-table td{border:0;padding:3px 5px;line-height:1.4}'
        '.district-table thead th{font-size:12px;color:#475467;text-align:left;font-weight:500}'
        '.district-table tbody th{text-align:left;font-weight:500;white-space:nowrap}'
        '.district-table .district-value,.district-table .district-end{text-align:right;white-space:nowrap}'
        '.district-table .district-value{color:#475467}'
        '.district-table .district-bar{height:14px;border-radius:0 4px 4px 0;background:#9eb1c7;'
        'transform-origin:left;animation:district-fill .65s ease-out both}'
        '.district-table .district-highlight th,.district-table .district-highlight .district-end{font-weight:750}'
        '.district-table .district-highlight .district-bar{background:#2467b2}'
        '@keyframes district-fill{from{transform:scaleX(0)}to{transform:scaleX(1)}}'
        '@media(prefers-reduced-motion:reduce){.district-table .district-bar{animation:none}}'
        '</style>'
        '<table class="district-table" aria-label="서울 자치구 지표 순위">'
        '<colgroup><col style="width:64px"><col style="width:88px"><col><col style="width:88px"></colgroup>'
        '<thead><tr><th scope="col">자치구</th><th scope="col" class="district-value">수치</th>'
        f'<th scope="col" colspan="2">{escape(label)}</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'
    )


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


@st.cache_data(show_spinner=False)
def load_boundaries(mtime: float) -> dict:
    """자치구·서울 외곽선. {이름: [[경도, 위도], ...]} (출처: 통계청 SGIS, 가공 vuski/admdongkor, CC BY 4.0)"""
    with open(BOUNDARY, encoding="utf-8") as fh:
        return {f["properties"]["자치구명"]: f["geometry"]["coordinates"][0] for f in json.load(fh)["features"]}


def boundaries():
    """경계 파일이 없으면 빈 dict — 지도는 가림막 없이 그대로 나온다."""
    try:
        return load_boundaries(BOUNDARY.stat().st_mtime)
    except (OSError, KeyError, ValueError):
        return {}


def add_seoul_frame(m, focus):
    """서울 바깥을 단색으로 가리고, 서울·자치구 외곽선을 그린 뒤 선택 범위에 화면을 맞춘다."""
    rings = boundaries()
    seoul = rings.get("서울 전체")
    if not seoul:
        return
    world = [[-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]]
    folium.GeoJson({"type": "Polygon", "coordinates": [world, seoul]}, control=False,
                   style_function=lambda feature: {"stroke": False, "fillColor": GROUND, "fillOpacity": 1}).add_to(m)
    districts = {"type": "MultiLineString", "coordinates": [r for name, r in rings.items() if name != "서울 전체"]}
    folium.GeoJson(districts, control=False,
                   style_function=lambda feature: {"color": "#667085", "weight": 1, "opacity": 0.7, "fill": False}).add_to(m)
    folium.GeoJson({"type": "LineString", "coordinates": seoul}, control=False,
                   style_function=lambda feature: {"color": NAVY, "weight": 2.5, "fill": False}).add_to(m)
    target = rings.get(focus, seoul)
    if focus in rings and focus != "서울 전체":
        folium.GeoJson({"type": "LineString", "coordinates": target}, control=False,
                       style_function=lambda feature: {"color": NAVY, "weight": 4, "fill": False}).add_to(m)
    lons, lats = [c[0] for c in target], [c[1] for c in target]
    m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])


def plot_map(hs, zones, links, focus="서울 전체"):
    joined = hs.merge(links[["다발지역FID", "경계중첩", "최단거리_m"]], on="다발지역FID", how="left", validate="one_to_one")
    centers = joined[["위도", "경도"]].apply(pd.to_numeric, errors="coerce").dropna()
    lat, lon = (centers["위도"].mean(), centers["경도"].mean()) if len(centers) else (37.5665, 126.9780)
    m = folium.Map(location=[lat, lon], zoom_start=12 if len(centers) else 11, tiles="OpenStreetMap", min_zoom=10)
    Fullscreen().add_to(m)
    add_seoul_frame(m, focus)
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



OVERVIEW_CSS = """
.ea-overview{--navy:#081323;--panel:#0e1e34;--line:#25405e;--white:#edf6ff;--muted:#a9bed5;--blue:#81cfff;--aqua:#8ceee6}
.ea-overview *{box-sizing:border-box}
[data-testid="stMain"]:has(.ea-overview) {
  background: radial-gradient(ellipse at 72% 0%, #1b4870 0%, transparent 54%), #081323;
}
[data-testid="stMain"]:has(.ea-overview) .block-container {
  max-width: none;
  padding: 3.5rem clamp(16px, 3vw, 52px) 1rem;
}
[data-testid="stHeader"]:has(~ [data-testid="stMain"] .ea-overview),
[data-testid="stAppViewContainer"]:has(.ea-overview) [data-testid="stHeader"] {
  background: transparent;
  color: #edf6ff;
}
.ea-overview { container-type: inline-size; color: var(--white); font-family: "Pretendard", "Malgun Gothic", system-ui, sans-serif; }
.ea-overview h1 { color: var(--white); padding: 0; }
.ea-overview h2 { padding: 0; }
.ea-overview .chart { max-height: 330px; }
.ea-overview header{height:76px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);gap:18px}
.ea-overview .brand{font-size:15px;font-weight:750;display:flex;align-items:center;gap:12px}
.ea-overview .logo{width:25px;height:25px;border:1px solid #5186b0;border-radius:7px;background:linear-gradient(125deg,transparent 48%,var(--blue) 49%,var(--blue) 54%,transparent 55%);position:relative}
.ea-overview .logo:after{content:"";position:absolute;top:8px;left:8px;width:6px;height:6px;background:var(--aqua);border-radius:100%;box-shadow:0 0 10px var(--aqua)}
.ea-overview .period{font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}
.ea-overview .hero{position:relative;isolation:isolate;padding:51px 0 31px;overflow:hidden}
.ea-overview .hero svg{position:absolute;z-index:-1;right:-35px;bottom:-19px;width:min(55%,630px);opacity:.62;pointer-events:none}
.ea-overview .eyebrow{color:var(--blue);font-size:13px;font-weight:700;margin:0 0 12px}
.ea-overview h1{font-size:clamp(30px,5vw,60px);letter-spacing:-.065em;line-height:1.13;margin:0}
.ea-overview .lede{font-size:clamp(16px,2.25vw,22px);margin:13px 0 0;color:#c5d9ee;letter-spacing:-.025em}
.ea-overview .lede strong{color:var(--aqua)}
.ea-overview .metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.ea-overview .metric{min-width:0;border:1px solid #30516c;border-radius:12px;padding:16px 17px 14px;background:radial-gradient(circle at 90% 0%,#163652,transparent 80%),#0c1c30;animation:arrive .55s both;animation-delay:calc(var(--i)*125ms)}
.ea-overview .metric h2{font-size:13px;line-height:1.35;margin:0 0 11px;color:#d5e8f8}
.ea-overview .display{padding:5px 9px 6px;background:radial-gradient(circle,#5ba1cd2b .7px,transparent 1.2px) 0 0/5px 5px,#07121e;border:1px solid #233f54;border-radius:6px;white-space:nowrap}
.ea-overview .number{font:700 clamp(27px,4vw,48px)/1.1 "Courier New",monospace;letter-spacing:-.08em;color:var(--aqua);text-shadow:0 0 14px #62ffe875;font-variant-numeric:tabular-nums}
.ea-overview .unit{font-size:13px;margin-left:8px;color:#c8e6ef}
.ea-overview .metric p{margin:9px 0 0;font-size:12px;color:var(--muted)}
.ea-overview .controls{display:flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:10px;color:var(--muted);font-size:12px;margin:10px 0 19px}
.ea-overview button{font:inherit;color:#d9efff;background:#132943;border:1px solid #395875;border-radius:6px;padding:4px 9px;cursor:pointer}
.ea-overview button:focus-visible{outline:2px solid var(--aqua);outline-offset:3px}
.ea-overview .scan{animation:scan .65s ease-out}
.ea-overview .charts{display:grid;grid-template-columns:1.07fr 1fr;gap:14px}
.ea-overview .panel{background:linear-gradient(155deg,#122641,#0b192b 85%);border:1px solid var(--line);border-radius:15px;padding:19px 20px 16px;min-width:0}
.ea-overview .panel h2{font-size:20px;letter-spacing:-.045em;margin:0}
.ea-overview .sub,.ea-overview .note{color:var(--muted);font-size:12px;line-height:1.55;margin:5px 0 0}
.ea-overview .chart{display:block;width:100%;height:auto;margin:5px 0}
.ea-overview .chart text{fill:#b9cee4;font-size:13px;font-family:inherit}
.ea-overview .chart .value{fill:#e6f5ff;font-weight:750;font-size:15px}
.ea-overview .grid{stroke:#2b425b;stroke-dasharray:4 5}
.ea-overview .trend{stroke:#83d7ff;stroke-width:3.6;fill:none;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:1;stroke-dashoffset:1;animation:draw 2s .38s ease-out forwards}
.ea-overview .point{animation:arrive .35s both;animation-delay:var(--delay)}
.ea-overview .note strong{color:#d7edff}
.ea-overview footer{border-top:1px solid var(--line);color:var(--muted);font-size:12px;line-height:1.65;margin-top:19px;padding:11px 0 20px}
@keyframes arrive{from{opacity:0;transform:translateY(7px)}to{opacity:1;transform:translateY(0)}}
@keyframes draw{to{stroke-dashoffset:0}}
@keyframes scan{25%{box-shadow:inset 0 0 16px #6fffe449}100%{box-shadow:none}}
@container (max-width:780px){.ea-overview .charts{grid-template-columns:1fr}.ea-overview .hero{padding-top:32px}.ea-overview .metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.ea-overview .number{font-size:37px}}
@container (max-width:360px){.ea-overview .metric{padding:10px}.ea-overview .panel{padding:12px}.ea-overview .brand{font-size:12px}}
@media(prefers-reduced-motion:reduce){.ea-overview *,.ea-overview *:before,.ea-overview *:after{animation-duration:0s!important;animation-delay:0s!important}.ea-overview .trend{stroke-dashoffset:0}}

.ea-overview header { height: 58px; }
.ea-overview .hero { padding-top: 34px; }
.ea-overview .chart-empty { min-height: 160px; display: grid; align-items: center; color: var(--muted); }
"""
OVERVIEW_SCRIPT = """
(() => {
const report = document.querySelector('.ea-overview');
if (!report || report.dataset.animated) return;
report.dataset.animated = 'true';

// Streamlit sanitizes inline SVG. Decode the server-generated artwork and mount it as SVG.
for (const slot of report.querySelectorAll('[data-overview-svg]')) {
  const bytes = Uint8Array.from(atob(slot.dataset.overviewSvg), character => character.charCodeAt(0));
  const markup = new TextDecoder().decode(bytes);
  const svg = new DOMParser().parseFromString(markup, 'image/svg+xml').documentElement;
  if (svg.namespaceURI === 'http://www.w3.org/2000/svg' && svg.localName === 'svg') {
    slot.replaceWith(svg);
  }
}
const numbers = [...report.querySelectorAll('.number')];
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const format = new Intl.NumberFormat('ko-KR');
const toggle = report.querySelector('#toggle');
let timer;
let frame;

function showTotals() {
  cancelAnimationFrame(frame);
  for (const number of numbers) {
    number.textContent = format.format(Number(number.dataset.value));
  }
}

function animateNumbers() {
  if (!report.isConnected) {
    clearInterval(timer);
    return;
  }
  if (document.hidden || reducedMotion.matches) return;
  cancelAnimationFrame(frame);
  const start = performance.now();
  for (const number of numbers) number.textContent = '0';

  function draw(now) {
    let counting = false;
    for (const [index, number] of numbers.entries()) {
      const elapsed = now - start - index * 125;
      const fraction = Math.max(0, Math.min(1, elapsed / 950));
      const value = Number(number.dataset.value);
      number.textContent = format.format(Math.round(value * (1 - (1 - fraction) ** 3)));
      counting ||= fraction < 1;
    }
    if (counting) frame = requestAnimationFrame(draw);
  }

  frame = requestAnimationFrame(draw);
}

function setRefresh(enabled) {
  clearInterval(timer);
  timer = enabled ? setInterval(animateNumbers, 5000) : undefined;
  if (!enabled) showTotals();
  toggle.textContent = enabled ? '효과 일시정지' : '효과 재개';
}

toggle.addEventListener('click', () => {
  const enabled = timer === undefined;
  setRefresh(enabled);
  if (enabled) animateNumbers();
});
toggle.hidden = reducedMotion.matches;
animateNumbers();
setRefresh(!reducedMotion.matches);
})();
"""
OVERVIEW_FLOW = """
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 205" aria-hidden="true">
    <defs><linearGradient id="flow"><stop stop-color="#70bffa" stop-opacity="0"/><stop offset="1" stop-color="#70bffa" stop-opacity=".66"/></linearGradient></defs>
    <g fill="none" stroke="url(#flow)">
      <path d="M0 178C180 176 200 117 331 102S478 119 640 13"/>
      <path d="M0 185C180 183 200 124 331 109S478 126 640 22"/>
      <path d="M0 193C180 191 200 132 331 117S478 134 640 31"/>
      <path d="M0 202C180 200 200 141 331 126S478 143 640 42"/>
    </g>
    <circle cx="331" cy="102" r="3" fill="#86f1e5"/><circle cx="524" cy="78" r="3" fill="#86f1e5"/>
  </svg>
"""
OVERVIEW_DISTANCE = """<svg xmlns="http://www.w3.org/2000/svg" class="chart" viewBox="0 0 480 211" role="img" aria-label="__DISTANCE_LABEL__">
      <defs><linearGradient id="ruler"><stop stop-color="#8ceee6"/><stop offset="1" stop-color="#6fa1fb"/></linearGradient></defs>
      <path d="M30 112H447l-8-5m8 5l-8 5" fill="none" stroke="url(#ruler)" stroke-width="2"/>
      <path d="M30 104v16M100 104v16M240 104v16M380 104v16" stroke="#98b9da"/>
      <g text-anchor="middle"><text x="30" y="139">0m</text><text x="100" y="139">100m</text><text x="240" y="139">300m</text><text x="380" y="139">500m</text></g>
      <g text-anchor="middle">
        <g class="point" style="--delay:.55s"><circle cx="30" cy="112" r="6" fill="#8ceee6"/><text class="value" x="30" y="88">__BAND_0__곳</text><text x="30" y="68">겹침</text></g>
        <g class="point" style="--delay:.69s"><circle cx="65" cy="112" r="4" fill="#89dfff"/><text class="value" x="73" y="173">__BAND_1__곳</text><text x="73" y="192">100m 이내</text></g>
        <g class="point" style="--delay:.83s"><circle cx="170" cy="112" r="5" fill="#89dfff"/><text class="value" x="170" y="88">__BAND_2__곳</text><text x="170" y="68">100–300m</text></g>
        <g class="point" style="--delay:.97s"><circle cx="310" cy="112" r="5" fill="#8bb9ff"/><text class="value" x="310" y="88">__BAND_3__곳</text><text x="310" y="68">300–500m</text></g>
        <g class="point" style="--delay:1.11s"><circle cx="421" cy="112" r="5" fill="#8bb9ff"/><text class="value" x="421" y="173">__BAND_4__곳</text><text x="421" y="192">500m 초과</text></g>
      </g>
    </svg>
    """


def overview_trend(trend):
    """Draw from the first available year, using a zero-based scale."""
    if trend.empty:
        return '<p class="chart-empty">선택 범위에 연도별 사고 자료가 없습니다.</p>'

    records = list(trend.itertuples(index=False, name=None))
    maximum = max(value for _, value in records)
    target = max(1, maximum / 4)
    magnitude = 10 ** floor(log10(target))
    step = ceil(target / magnitude) * magnitude
    ceiling = step * 4
    ticks = []
    for index in range(5):
        y = 180 - index * 34
        ticks.append(
            f'<path class="grid" d="M56 {y}H452"/>'
            f'<text x="48" y="{y + 4}" text-anchor="end">{index * step:,}</text>'
        )

    coordinates = []
    markers = []
    labels = []
    for index, (record_year, value) in enumerate(records):
        x = 76 + 354 * index / max(len(records) - 1, 1)
        y = 180 - value / ceiling * 136
        coordinates.append(f"{x:.2f} {y:.2f}")
        markers.append(
            f'<g class="point" style="--delay:{.38 + index * 1.9 / max(len(records) - 1, 1):.2f}s">'
            f'<circle cx="{x}" cy="{y}" r="4" fill="#8ceee6"/>'
            f'<text class="value" x="{x}" y="{y - 12}">{value:,.0f}</text></g>'
            f'<text x="{x}" y="201">{record_year:.0f}</text>'
        )
        labels.append(f"{record_year:.0f}년 {value:,.0f}건")

    path = "M" + "L".join(coordinates)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" class="chart" viewBox="0 0 480 211" role="img" aria-label="{escape(", ".join(labels))}">'
        f'{"".join(ticks)}<path class="trend" pathLength="1" d="{path}"/>'
        f'<g text-anchor="middle">{"".join(markers)}</g></svg>'
    )


def overview_svg_slot(markup):
    """Carry trusted, server-generated SVG through Streamlit's HTML sanitizer."""
    encoded = b64encode(markup.strip().encode("utf-8")).decode("ascii")
    return f'<div data-overview-svg="{encoded}"></div>'


def overview_page(scope, year, all_dead, dead, metrics, trend, counts, hotspot_total):
    cards = []
    for index, (label, value, unit, detail) in enumerate(metrics):
        value_text = num(value)
        if pd.isna(value):
            value_html = '<span>자료 없음</span>'
        else:
            value_html = (
                f'<span class="number" data-value="{int(value)}" aria-hidden="true">{value_text}</span>'
                f'<span class="unit" aria-hidden="true">{escape(unit)}</span>'
            )
        accessible_value = value_text if pd.isna(value) else value_text + unit
        cards.append(
            f'<article class="metric" style="--i:{index}"><h2>{escape(label)}</h2>'
            f'<div class="display" role="group" aria-label="{escape(accessible_value)}">{value_html}</div>'
            f'<p>{escape(detail)}</p></article>'
        )

    summary = ""
    if pd.notna(all_dead) and all_dead > 0 and pd.notna(dead):
        summary = f'<p class="lede">보행 사망자 {num(all_dead)}명 중 <strong>65세 이상 {num(dead)}명</strong></p>'

    if sum(counts):
        distance = OVERVIEW_DISTANCE.replace(
            "__DISTANCE_LABEL__",
            escape(", ".join(f"{label} {count}곳" for (label, _), count in zip(BANDS, counts))),
        )
        for index, count in enumerate(counts):
            distance = distance.replace(f"__BAND_{index}__", str(count))
    else:
        message = (
            "선택 범위의 보호구역 경계 거리 자료가 없습니다."
            if hotspot_total else "선택 범위에 선정된 사고다발지역이 없습니다."
        )
        distance = f'<p class="chart-empty">{message}</p>'

    trend_chart = overview_trend(trend)
    if not trend.empty:
        trend_chart = overview_svg_slot(trend_chart)
    if sum(counts):
        distance = overview_svg_slot(distance)

    st.html(
        f"""<style>{OVERVIEW_CSS}</style>
<div class="ea-overview" lang="ko">
<header><div class="brand"><span class="logo" aria-hidden="true"></span> 서울 보행안전 리포트</div>
<span class="period">{year}년 · 사고 발생 지역 기준</span></header>
<div>
<section class="hero" aria-labelledby="headline">{overview_svg_slot(OVERVIEW_FLOW)}
<p class="eyebrow">개요 · {escape(scope)}</p>
<h1 id="headline">고령 보행자 교통안전</h1>{summary}</section>
<section class="metrics" aria-label="주요 지표">{"".join(cards)}</section>
<div class="controls"><span>{year}년 집계 · 5초 간격 숫자 다시 세기</span>
<button id="toggle" type="button">효과 일시정지</button></div>
<section class="charts" aria-label="사고 추이와 보호구역 거리">
<article class="panel"><h2>고령 보행자 사고 추이</h2>
<p class="sub">사고 건수 · {years[0]}–{years[-1]}년 · {escape(scope)}</p>
{trend_chart}
<p class="note">한국도로교통공단 TAAS · 사고 발생 지역 기준</p></article>
<article class="panel"><h2>사고다발지역과 보호구역 거리</h2>
<p class="sub">가장 가까운 확보 보호구역 경계까지 직선거리 · 거리 자료 {sum(counts)}곳</p>
{distance}
<p class="note"><strong>점은 거리 구간별 집계</strong> · 확보한 보호구역 경계 기준 잠정값</p></article>
</section></div>
<footer>자료 · 한국도로교통공단 TAAS, 서울시 지정 명단, 팀 공간 분석<br>
사고다발지역은 공단이 선정한 영역입니다. 일부 지정 시설의 경계 자료가 빠져 있으며, 확보한 경계가 지정 당시 범위와 다를 수 있습니다.</footer>
</div><script>{OVERVIEW_SCRIPT}</script>""",
        unsafe_allow_javascript=True,
    )


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
    acc = total(p, "고령보행자_사고건수")
    dead = total(p, "고령보행자_사망자수")
    all_dead = total(p, "전체보행자_사망자수")
    prev_acc = total(prev, "고령보행자_사고건수")
    prev_dead = total(prev, "고령보행자_사망자수")
    facilities = total(p, "보호구역_명단시설수")
    hotspot_total = h["다발지역FID"].nunique()
    trend = (
        in_scope(panel).groupby("사고연도", as_index=False)["고령보행자_사고건수"]
        .sum(min_count=1).dropna()
    )
    linked = in_scope(links[links["사고연도"] == year])
    metrics = [
        ("고령 보행자 사고", acc, "건", change(acc, prev_acc, "건")[0]),
        ("고령 보행 사망자", dead, "명", change(dead, prev_dead, "명")[0]),
        (f"{year}년 고령 보행자 사고다발지역", hotspot_total, "곳", "TAAS 선정 지역"),
        ("노인보호구역", facilities, "곳", f"{year}년 말 지정 명단 기준"),
    ]
    overview_page(scope, year, all_dead, dead, metrics, trend, band_counts(linked), hotspot_total)

# ── 02 지역별 사고 현황 ───────────────────────────────────────────────
elif page == "지역별 사고 현황":
    header(f"서울 25개 자치구 · {year}년", "지역별 사고 현황")
    with st.container(border=True):
        title_column, control_column = st.columns([2, 3], vertical_alignment="center")
        with title_column:
            card_title("25개 자치구 비교")
        with control_column:
            label = st.selectbox("비교 지표", list(DISTRICT_METRICS), label_visibility="collapsed")
        district_ranking(year_all, label, gu)
        source(f"{year}년 기준 · 큰 값부터 표시 · 동대문구와 도봉구 강조")
        source("자료: 한국도로교통공단 TAAS, 서울 열린데이터광장, 서울시 지정 명단, 팀 공간 분석")

    with st.container(border=True):
        card_title("자치구별 연도별 추이", f"{years[0]}–{years[-1]}년. 사이드바의 사고연도와 무관하게 전체 기간을 보여줍니다.")
        trend_metric = st.radio("추이 지표", ["고령보행자_사고건수", "고령인구1만명당_고령보행자사고"],
                                format_func=lambda v: "사고건수 (건)" if v == "고령보행자_사고건수" else "고령인구 1만 명당 사고율 (건)",
                                horizontal=True, key="district_trend_metric")
        default = [gu] if gu != "서울 전체" else [g for g in ("동대문구", "도봉구") if g in gu_list]
        picked = st.multiselect("비교할 자치구", gu_list, default=default)
        comparison = panel[panel["자치구명"].isin(picked)].dropna(subset=[trend_metric]).sort_values("사고연도")
        if comparison.empty:
            st.info("비교할 자치구를 하나 이상 선택해 주세요.")
        else:
            look = {g: (GU_COLORS[i % len(GU_COLORS)], GU_DASHES[i % len(GU_DASHES)], GU_SYMBOLS[i % len(GU_SYMBOLS)])
                    for i, g in enumerate(gu_list)}
            fig2 = px.line(comparison, x="사고연도", y=trend_metric, color="자치구명", line_dash="자치구명", symbol="자치구명",
                           category_orders={"자치구명": [g for g in gu_list if g in picked]},
                           color_discrete_map={g: v[0] for g, v in look.items()},
                           line_dash_map={g: v[1] for g, v in look.items()},
                           symbol_map={g: v[2] for g, v in look.items()},
                           labels={"사고연도": "", trend_metric: "사고 건수 (건)" if trend_metric == "고령보행자_사고건수" else "고령인구 1만 명당 사고율 (건)", "자치구명": "자치구"})
            fig2.update_traces(line=dict(width=2.5), marker=dict(size=9))
            fig2.update_xaxes(dtick=1, showgrid=False)
            fig2.update_layout(hovermode="closest", legend=dict(orientation="v", x=1.02, y=1, xanchor="left", yanchor="top", title_text=""))
            st.plotly_chart(style(fig2, max(380, 24 * len(picked) + 80)), width="stretch")
        source("자치구마다 색·선 모양·표식 모양이 고정돼 있습니다. 범례를 누르면 해당 구를 숨기거나 다시 볼 수 있습니다. 결측값은 0건으로 바꾸지 않고 비워 둡니다.")

    with st.container(border=True):
        card_title("사고율 격차·순위 변화", f"{year}년 서울 전체 고령인구 1만 명당 사고율과 자치구별 격차")
        rate_rows = year_all.dropna(subset=["고령보행자_사고건수", "고령인구"]).copy()
        population = total(rate_rows, "고령인구")
        seoul_rate = total(rate_rows, "고령보행자_사고건수") / population * 10000 if pd.notna(population) and population > 0 else float("nan")
        rate_rows["사고율"] = rate_rows["고령보행자_사고건수"] / rate_rows["고령인구"].where(rate_rows["고령인구"] > 0) * 10000
        rate_rows = rate_rows.dropna(subset=["사고율"])
        rate_rows["순위"] = rate_rows["사고율"].rank(method="min", ascending=False).astype(int)
        prev_rows = panel[panel["사고연도"] == year - 1].dropna(subset=["고령보행자_사고건수", "고령인구"]).copy()
        prev_rows["전년사고율"] = prev_rows["고령보행자_사고건수"] / prev_rows["고령인구"].where(prev_rows["고령인구"] > 0) * 10000
        prev_rows["전년순위"] = prev_rows["전년사고율"].rank(method="min", ascending=False)
        rate_rows = rate_rows.merge(prev_rows[["자치구명", "전년사고율", "전년순위", "고령보행자_사고건수"]].rename(
            columns={"고령보행자_사고건수": "전년사고건수"}), on="자치구명", how="left", validate="one_to_one")
        rate_rows["서울 대비 격차"] = rate_rows["사고율"] - seoul_rate
        rate_rows["순위 변화(상승+)"] = rate_rows["전년순위"] - rate_rows["순위"]
        rate_rows["사고 증감(건)"] = rate_rows["고령보행자_사고건수"] - rate_rows["전년사고건수"]
        rate_rows["사고 증감률(%)"] = (rate_rows["사고 증감(건)"] / rate_rows["전년사고건수"].where(rate_rows["전년사고건수"] != 0) * 100)
        if pd.notna(seoul_rate) and not rate_rows.empty:
            source(f"서울 전체 사고율: {seoul_rate:.2f}건/1만 명 = 서울 전체 고령 보행자 사고건수 ÷ 서울 전체 65세 이상 거주인구 × 10,000 (자치구 단순 평균 아님)")
            plot_rates = rate_rows.sort_values("서울 대비 격차")
            bars = go.Figure(go.Bar(x=plot_rates["서울 대비 격차"], y=plot_rates["자치구명"], orientation="h",
                                    marker_color=[ORANGE_DARK if g == gu else (ORANGE if v >= 0 else BLUE_SOFT)
                                                  for g, v in zip(plot_rates["자치구명"], plot_rates["서울 대비 격차"])],
                                    hovertemplate="%{y}: 서울 대비 %{x:+.2f}건/1만 명<extra></extra>"))
            bars.add_vline(x=0, line_color=GRAY, line_width=1)
            st.plotly_chart(style(bars, 650), width="stretch")
            view_rates = rate_rows.sort_values("순위")[["자치구명", "순위", "전년순위", "순위 변화(상승+)", "사고율", "서울 대비 격차", "사고 증감(건)", "사고 증감률(%)"]]
            st.dataframe(view_rates, hide_index=True, width="stretch",
                         column_config={"사고율": st.column_config.NumberColumn(format="%.2f"),
                                        "서울 대비 격차": st.column_config.NumberColumn(format="%+.2f"),
                                        "사고 증감률(%)": st.column_config.NumberColumn(format="%+.1f")})
        else:
            st.info("서울 전체 사고율 또는 지역별 사고율을 계산할 자료가 없습니다.")
        source("순위·증감은 전년과 비교합니다. 2022년은 전년 자료가 없어 표시하지 않습니다. 거주 인구는 실제 보행량이 아닙니다.")

    with st.container(border=True):
        card_title("동대문구·도봉구와 서울 전체 비교", "두 지역은 탐색 사례이며 서울 전체 분석을 대체하지 않습니다.")
        case = panel[panel["자치구명"].isin(["동대문구", "도봉구"])][["사고연도", "자치구명", "고령보행자_사고건수", "고령인구1만명당_고령보행자사고"]].copy()
        baseline = panel.groupby("사고연도", as_index=False)[["고령보행자_사고건수", "고령인구"]].sum(min_count=1)
        baseline["고령인구1만명당_고령보행자사고"] = (baseline["고령보행자_사고건수"] / baseline["고령인구"] * 10000)
        baseline["자치구명"] = "서울 전체"
        case = pd.concat([case, baseline[["사고연도", "자치구명", "고령보행자_사고건수", "고령인구1만명당_고령보행자사고"]]], ignore_index=True)
        case_metric = st.radio("비교 지표", ["고령보행자_사고건수", "고령인구1만명당_고령보행자사고"], horizontal=True,
                               format_func=lambda v: "사고건수 (건)" if v == "고령보행자_사고건수" else "고령인구 1만 명당 사고율 (건)", key="case_metric")
        fig_case = px.line(case.dropna(subset=[case_metric]), x="사고연도", y=case_metric, color="자치구명", markers=True,
                           color_discrete_map={"서울 전체": NAVY, "동대문구": ORANGE, "도봉구": BLUE},
                           category_orders={"자치구명": ["서울 전체", "동대문구", "도봉구"]},
                           labels={"사고연도": "연도", case_metric: "사고건수 (건)" if case_metric == "고령보행자_사고건수" else "사고율 (건/1만 명)"})
        fig_case.update_xaxes(dtick=1)
        st.plotly_chart(style(fig_case, 330), width="stretch")
        source("사고건수는 서울 전체와 두 구의 규모가 달라 수치가 크게 벌어집니다. 사고율 비교에는 지역별 고령인구 차이가 반영됩니다.")

    with st.expander("자료 표 보기"):
        st.dataframe(p[["사고연도", "자치구명", "고령인구", "고령보행자_사고건수", "고령보행자_사망자수",
                        "고령인구1만명당_고령보행자사고", "고령보행자_출처"]], hide_index=True, width="stretch")

# ── 03 공간 분석 지도 ─────────────────────────────────────────────────
elif page == "공간 분석 지도":
    view, joined = plot_map(h, z, links, gu)
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

    with st.container(border=True):
        html(f'<div class="ea-legend"><span><i style="background:{BLUE_SOFT};border:2px solid {BLUE};border-radius:3px"></i>노인보호구역 경계</span>'
             f'<span><i style="background:{BLUE_DARK};border-radius:50%"></i>겹치는 사고다발지역</span>'
             f'<span><i style="background:{ORANGE_SOFT};border:2px solid {ORANGE_DARK};border-radius:50%"></i>보호구역 밖 사고다발지역</span></div>')
        st_folium(view, width=None, height=640, returned_objects=[])
        source("영역을 누르면 집계 사고 건수와 가장 가까운 보호구역까지의 거리가 나옵니다. 행정경계: 통계청 SGIS, 가공 vuski/admdongkor (CC BY 4.0)")
    with st.container(border=True):
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
                spot = escape(short_name(r) if gu != "서울 전체" else f"{r['자치구명']} {short_name(r)}")
                rows.append(f'<tr><td>{spot}</td><td class="r"><b>{num(r["사고건수"])}건</b></td><td class="r">{where}</td></tr>')
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

    with st.container(border=True):
        card_title("자치구 사고 수준과 보호구역 공간 관계", f"{year}년 자치구별 사고율과 사고다발지역의 API 경계 중첩 여부 (정책 효과 추정 아님)")
        linked_year = links[links["사고연도"] == year].dropna(subset=["경계중첩"]).copy()
        linked_year["비중첩"] = (linked_year["경계중첩"] == 0).astype(int)
        areas = linked_year.groupby("자치구명").agg(판정가능_선정지역수=("비중첩", "size"), 비중첩_선정지역수=("비중첩", "sum")).reset_index()
        areas["비중첩비율_%"] = areas["비중첩_선정지역수"] / areas["판정가능_선정지역수"] * 100
        rates = year_all[["자치구명", "고령보행자_사고건수", "고령인구1만명당_고령보행자사고", "보호구역_명단시설수"]]
        joined_rates = rates.merge(areas, on="자치구명", how="left", validate="one_to_one")
        if gu != "서울 전체":
            joined_rates = joined_rates[joined_rates["자치구명"] == gu]
        available = joined_rates.dropna(subset=["고령인구1만명당_고령보행자사고", "비중첩비율_%"])
        if available.empty:
            st.info("선택한 자치구·연도에는 중첩 판정 가능한 사고다발지역이 없어 공간 비교를 표시하지 않습니다.")
        elif gu == "서울 전체":
            # 사고율 순위와 비중첩 선정 영역의 분자/분모를 한 행에 표시한다.
            # 비중첩 비율은 구 전체 사고건수의 비율이나 보호 효과가 아니다.
            ranked = joined_rates.dropna(subset=["고령인구1만명당_고령보행자사고"]).copy()
            ranked = ranked.sort_values("고령인구1만명당_고령보행자사고")
            max_rate = ranked["고령인구1만명당_고령보행자사고"].max()
            note_x = max_rate * 1.20
            fig_spatial = go.Figure(go.Bar(
                x=ranked["고령인구1만명당_고령보행자사고"],
                y=ranked["자치구명"], orientation="h",
                marker_color=ORANGE, width=0.65,
                text=ranked["고령인구1만명당_고령보행자사고"].map(lambda v: f"{v:.1f}"),
                textposition="outside", cliponaxis=False,
                hovertemplate="%{y}<br>고령인구 1만 명당 사고: %{x:.2f}건<extra></extra>",
            ))
            for _, item in ranked.iterrows():
                count = item["판정가능_선정지역수"]
                outside_count = item["비중첩_선정지역수"]
                detail = (f"{int(outside_count)}/{int(count)}곳"
                          if pd.notna(count) and count > 0 else "선정 영역 없음")
                fig_spatial.add_annotation(
                    x=note_x, y=item["자치구명"], text=detail,
                    xanchor="left", showarrow=False,
                    font=dict(size=12, color=MUTED),
                )
            fig_spatial.update_xaxes(
                title="고령인구 1만 명당 사고 (건)",
                range=[0, max_rate * 1.85], showgrid=False,
            )
            fig_spatial.update_yaxes(title=None, automargin=True)
            st.caption("막대: 자치구 전체 사고율 · 오른쪽: 보호구역 API 경계와 비중첩인 사고다발지역 수 / 중첩 판정 가능 선정지역 수")
            st.plotly_chart(style(fig_spatial, max(340, 30 * len(ranked) + 100)), width="stretch")
        st.dataframe(joined_rates[["자치구명", "고령보행자_사고건수", "고령인구1만명당_고령보행자사고",
                                  "보호구역_명단시설수", "판정가능_선정지역수", "비중첩_선정지역수", "비중첩비율_%"]],
                     hide_index=True, width="stretch")
        source("사고건수·사고율은 자치구 전체, 중첩 비율은 사고다발지역 '선정 영역' 중 판정 가능한 곳의 비율입니다. "
               "선정 영역이 없는 자치구는 0%로 처리하지 않습니다. 현행 API 경계와의 공간 비교는 정책 공백 탐색용이며 보호 효과를 뜻하지 않습니다.")

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

if page != "개요":
    st.divider()
    st.caption("데이터 출처와 처리 기준: 저장소 README.md · 데이터사전.md · data/processed/ | 관측된 공간 관계와 사고 감소의 인과효과는 다릅니다.")
