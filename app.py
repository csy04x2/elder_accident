"""서울 고령 보행자 교통사고 탐색 대시보드 (기존 processed CSV 전용)."""
from pathlib import Path
import json
from html import escape

import folium
import pandas as pd
import plotly.express as px
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

st.set_page_config(page_title="서울 고령 보행자 교통안전", page_icon="🚶", layout="wide")

@st.cache_data(show_spinner=False)
def read_csv(name: str, mtime: float) -> pd.DataFrame:
    return pd.read_csv(DATA / FILES[name], encoding="utf-8-sig")


def load(name):
    path = DATA / FILES[name]
    if not path.exists():
        st.error(f"필수 데이터 파일이 없습니다: {path}")
        st.stop()
    return read_csv(name, path.stat().st_mtime)


def fmt(value, unit="건", digits=0):
    return "자료 없음" if pd.isna(value) else f"{value:,.{digits}f}{unit}"


def wkt_geojson(wkt):
    """WKT POLYGON/MULTIPOLYGON을 지도용 GeoJSON으로 변환. 좌표는 WGS84 경도·위도."""
    from shapely import wkt as shapely_wkt
    from shapely.geometry import mapping
    return mapping(shapely_wkt.loads(wkt))


def plot_map(hs, zones, links):
    joined = hs.merge(links[["다발지역FID", "경계중첩", "최단거리_m"]], on="다발지역FID", how="left", validate="one_to_one")
    centers = joined[["위도", "경도"]].apply(pd.to_numeric, errors="coerce").dropna()
    lat, lon = (centers["위도"].mean(), centers["경도"].mean()) if len(centers) else (37.5665, 126.9780)
    m = folium.Map(location=[lat, lon], zoom_start=12 if len(centers) else 11, tiles="OpenStreetMap")
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
                style_function=lambda feature: {"color": "#2563eb", "weight": 2, "fillColor": "#60a5fa", "fillOpacity": 0.18},
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
            label = "중첩" if overlap else ("비중첩" if known else "판정 미상")
            color = "#dc2626" if overlap else ("#f59e0b" if known else "#64748b")
            name = escape(str(row["지점명"]))
            accident_count = "자료 없음" if pd.isna(row["사고건수"]) else f"{int(row['사고건수']):,}건"
            distance = "자료 없음" if pd.isna(row["최단거리_m"]) else f"{float(row['최단거리_m']):,.1f}m"
            popup = folium.Popup(
                f"<b>사고다발지역 선정 영역</b><br>지점: {name}<br>사고연도: {int(row['사고연도'])}년"
                f"<br>선정지역 집계 사고건수: {accident_count}<br>경계 중첩: {label}"
                f"<br>서울 전체 API 경계까지 최단 직선거리: {distance}",
                max_width=400,
            )
            folium.GeoJson(
                geo,
                style_function=lambda feature, c=color: {"color": c, "weight": 2, "fillColor": c, "fillOpacity": 0.36},
                tooltip=f"{row['지점명']} | {label} | 사고연도 {int(row['사고연도'])}년",
                popup=popup,
            ).add_to(h_layer)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    z_layer.add_to(m)
    h_layer.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    return m, joined


panel = load("panel")
hotspots = load("hotspots")
master = load("master")
zones = load("zones")
links = load("links")
for df in (panel, hotspots, master, zones, links):
    for col in ("사고연도", "지정연도", "경계중첩"):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")

st.title("서울 고령 보행자 교통사고와 노인보호구역")
st.caption("기존 공공데이터 가공 결과에 기반한 탐색 대시보드 · 인과효과를 검증하는 도구가 아닙니다")
page = st.sidebar.radio("화면", ["프로젝트 개요", "지역별 사고 현황", "공간 분석 지도", "지정 전후 탐색"])
years = sorted(panel["사고연도"].dropna().astype(int).unique())
year = st.sidebar.selectbox("사고연도", years, index=len(years)-1)
gu_list = sorted(panel["자치구명"].dropna().unique())
gu = st.sidebar.selectbox("자치구", ["서울 전체"] + gu_list, index=0)
st.sidebar.caption("사고연도는 다발지역 자료ID 연도와 다릅니다. 과거 경계는 현행 API 기록으로 표시합니다.")

p = panel.loc[(panel["사고연도"] == year) & ((panel["자치구명"] == gu) if gu != "서울 전체" else True)].copy()
h = hotspots.loc[(hotspots["사고연도"] == year) & ((hotspots["자치구명"] == gu) if gu != "서울 전체" else True)].copy()
z = zones.loc[(zones["자치구명"] == gu) if gu != "서울 전체" else slice(None)].copy()

if page == "프로젝트 개요":
    st.subheader("무엇을 확인할 수 있나요?")
    st.write("노인보호구역 지정 이후 사고가 감소했는가, 사고다발지역과 보호구역이 얼마나 겹치는가, 동대문구와 도봉구의 차이가 무엇인가를 탐색합니다.")
    valid = p["고령보행자_사고건수"].notna()
    a, b, c = st.columns(3)
    a.metric(f"{year}년 사고건수 (자료 있는 구)", fmt(p["고령보행자_사고건수"].sum() if valid.any() else float('nan')))
    b.metric("사고건수 자료 확보 자치구", f"{valid.sum()} / {len(p)}개")
    c.metric("사고다발지역 선정 기록", fmt(len(h), "곳"))
    st.info("2022~2025년 자치구별 사고건수는 서울 25개 구 통합 자료를 사용합니다. 연도·지역 필터에 따라 집계 범위가 달라집니다.")
    st.markdown("**주요 발견(기존 분석)**: 2025년 서울 사고다발지역 71곳 중 59곳이 확보된 보호구역 API 경계와 면적 중첩하지 않았습니다. 이 비율은 개별 사고의 보호구역 밖 발생 비율이 아닙니다.")
    st.caption("출처: TAAS 고령 보행자 사고 통계·사고다발지역, 서울시 보호구역 지정 명단, 행정안전부 보호구역 API. 분석 방식과 세부 출처는 README 및 데이터사전.md 참조.")

elif page == "지역별 사고 현황":
    st.subheader(f"{year}년 자치구별 고령 보행자 사고")
    usable = p.dropna(subset=["고령보행자_사고건수"])
    if usable.empty:
        st.warning("선택한 범위에서 사고건수 자료가 없습니다.")
    else:
        metric = st.radio("표시 지표", ["고령보행자_사고건수", "고령인구1만명당_고령보행자사고"], horizontal=True,
                          format_func=lambda x: "사고건수 (건)" if x == "고령보행자_사고건수" else "65세 이상 거주인구 1만 명당 사고 (건)")
        fig = px.bar(usable.sort_values(metric, ascending=False), x="자치구명", y=metric, color="자치구명", text_auto=".1f" if metric != "고령보행자_사고건수" else ".0f")
        fig.update_layout(showlegend=False, xaxis_title="자치구", yaxis_title="건" if metric == "고령보행자_사고건수" else "건/1만 명")
        st.plotly_chart(fig, width="stretch")
    st.subheader("서울 25개 자치구 연도별 고령 보행자 사고 추이")
    st.caption("2022~2025년 사고건수(건). 아래 체크박스로 그래프에 표시할 자치구를 선택하세요. 상단 사고연도 필터는 이 4개년 추이에는 적용되지 않습니다.")
    district_names = sorted(panel["자치구명"].dropna().unique().tolist())
    for district in district_names:
        st.session_state.setdefault(f"trend_{district}", district in ("동대문구", "도봉구"))

    def select_districts(checked):
        for district in district_names:
            st.session_state[f"trend_{district}"] = checked

    all_col, none_col, _ = st.columns([1, 1, 5])
    all_col.button("전체 선택", on_click=select_districts, args=(True,), key="trend_select_all")
    none_col.button("전체 해제", on_click=select_districts, args=(False,), key="trend_select_none")
    check_cols = st.columns(5)
    for i, district in enumerate(district_names):
        with check_cols[i % 5]:
            st.checkbox(district, key=f"trend_{district}")

    selected_districts = [district for district in district_names if st.session_state[f"trend_{district}"]]
    comparison = panel.loc[panel["자치구명"].isin(selected_districts)].dropna(subset=["고령보행자_사고건수"])
    if comparison.empty:
        st.info("표시할 자치구를 하나 이상 선택해 주세요.")
    else:
        fig2 = px.line(comparison.sort_values("사고연도"), x="사고연도", y="고령보행자_사고건수",
                       color="자치구명", markers=True,
                       labels={"사고연도": "사고연도", "고령보행자_사고건수": "사고건수 (건)", "자치구명": "자치구"})
        fig2.update_layout(xaxis=dict(dtick=1), yaxis_title="사고건수 (건)",
                           legend_title_text="자치구", hovermode="x unified")
        st.plotly_chart(fig2, width="stretch")
    st.caption("출처: 01_자치구연도_패널.csv · TAAS 시군구 사고통계. 선택한 자치구만 표시하며 결측값을 0건으로 대체하지 않습니다.")
    st.dataframe(p[["사고연도", "자치구명", "고령인구", "고령보행자_사고건수", "고령인구1만명당_고령보행자사고", "고령보행자_출처"]], hide_index=True, width="stretch")
    st.caption("출처: 01_자치구연도_패널.csv. 사고는 발생 지역 기준이며 고령인구는 거주지 기준입니다. 결측은 0이 아닙니다. 연도·지표별 자료 범위와 출처를 구분해야 합니다.")

elif page == "공간 분석 지도":
    st.subheader(f"{year}년 사고다발지역과 확보된 보호구역 경계")
    st.markdown("🔵 **파랑:** 보호구역 API 경계　 🔴 **빨강:** 중첩 사고다발지역　 🟡 **주황:** 비중첩 사고다발지역　 ⚪ **회색:** 판정 미상")
    if year <= 2020:
        st.warning("2020년 이전 사고다발지역은 이후와 선정 기준이 달라 연도 간 직접 비교에 주의해야 합니다.")
    view, joined = plot_map(h, z, links)
    known = joined["경계중첩"].notna()
    overlapping = int((joined.loc[known, "경계중첩"] == 1).sum())
    nonoverlapping = int((joined.loc[known, "경계중첩"] == 0).sum())
    unknown = int((~known).sum())
    a, b, c, d = st.columns(4)
    a.metric("선정지역", f"{len(joined)}곳")
    b.metric("경계 중첩", f"{overlapping}곳")
    c.metric("비중첩", f"{nonoverlapping}곳")
    d.metric("판정 미상", f"{unknown}곳")
    st.caption("지도 영역을 클릭하면 집계 사고건수·중첩 여부·최근접 보호구역 경계까지의 직선거리가 나옵니다.")
    st_folium(view, width=None, height=550, returned_objects=[])
    st.subheader("자치구별 사고다발지역 공간 중첩 현황")
    st.caption("선택한 사고연도의 사고다발지역 *선정 영역 수(곳)*입니다. 개별 사고건수가 아닙니다.")
    chart_data = joined[["자치구명", "경계중첩"]].copy()
    chart_data["분류"] = chart_data["경계중첩"].map({1: "경계 중첩", 0: "비중첩"}).fillna("판정 미상")
    chart_counts = chart_data.groupby(["자치구명", "분류"], as_index=False).size().rename(columns={"size": "선정지역 수"})
    if chart_counts.empty:
        st.info("선택한 연도와 자치구에는 공식 선정 기준을 충족한 사고다발지역 기록이 없습니다.")
    else:
        chart_order = (chart_counts.groupby("자치구명")["선정지역 수"].sum()
                       .sort_values(ascending=False).index.tolist())
        fig_overlap = px.bar(
            chart_counts, x="자치구명", y="선정지역 수", color="분류",
            category_orders={"자치구명": chart_order,
                             "분류": ["경계 중첩", "비중첩", "판정 미상"]},
            color_discrete_map={"경계 중첩": "#dc2626", "비중첩": "#f59e0b", "판정 미상": "#64748b"},
            labels={"자치구명": "자치구", "선정지역 수": "선정지역 수 (곳)"},
            barmode="stack", text_auto=True,
        )
        fig_overlap.update_layout(xaxis_title="자치구", yaxis_title="선정지역 수 (곳)")
        st.plotly_chart(fig_overlap, width="stretch")
        determined = overlapping + nonoverlapping
        if determined:
            st.caption(f"선택 범위의 판정 가능 지역 {determined}곳 중 비중첩 {nonoverlapping}곳 "
                       f"({nonoverlapping / determined:.1%}). 판정 미상 {unknown}곳은 비율에서 제외했습니다.")
        else:
            st.caption("중첩 판정 가능한 지역이 없어 비중첩 비율을 계산하지 않습니다.")
    st.caption("출처: 03_다발지역_서울.csv · 06_다발지역_보호구역_연결.csv. "
               "현행 API 경계와 비교한 공간 관계로서, 당시 지정 경계 또는 사고 예방 효과를 입증하지 않습니다. "
               "2020년 이전과 이후는 사고다발지역 선정 기준이 달라 연도 간 직접 비교에 주의해야 합니다.")

    st.dataframe(joined[["지점명", "사고연도", "사고건수", "경계중첩", "최단거리_m"]], hide_index=True, width="stretch")
    st.caption("출처: 03·05·06 가공 CSV. 사고다발지역은 개별 사고 지점이 아니라 선정된 영역입니다. 경계는 현행 API 자료로, 공식 지정 시설 전체를 포괄하지 않을 수 있습니다. 최단거리는 선택한 자치구가 아니라 서울 전체 경계를 대상으로 계산하며 보행 경로 거리가 아닙니다. 연도별 선정 기준과 과거 실제 경계는 다를 수 있습니다.")

else:
    st.subheader("보호구역 지정 전후 탐색 — 사고 감소 효과 분석 불가")
    st.warning("현재 CSV만으로 동일 보호구역 지정 전후 개별 사고건수의 변화를 검증할 수 없습니다. 아래는 사고다발지역 **선정 기록 수**의 탐색적 비교입니다.")
    candidates = master.loc[(master["명단변동"] == "신규등재") & master["지정연도"].notna()].copy()
    if gu != "서울 전체":
        candidates = candidates[candidates["자치구명"] == gu]
    st.metric("선택 범위 신규 등재 시설", f"{len(candidates)}곳")
    st.dataframe(candidates[["시설명", "자치구명", "지정연도", "최초등재명단", "API경계기록수"]], hide_index=True, width="stretch")
    st.subheader("사고다발지역 선정 기록 추이 (효과 추정 아님)")
    counts = hotspots.loc[(hotspots["자치구명"] == gu) if gu != "서울 전체" else slice(None)].groupby(["사고연도", "선정기준구간"], as_index=False).size()
    fig = px.bar(counts, x="사고연도", y="size", color="선정기준구간", barmode="group", labels={"size":"선정 지역 수 (곳)", "사고연도":"사고연도"})
    st.plotly_chart(fig, width="stretch")
    st.caption("출처: 03·04 가공 CSV. A/B 선정 기준의 단절 때문에 두 구간을 하나의 사고 추세로 해석할 수 없습니다. 신규 명단 등재연도는 실제 지정 고시일이 아니며, 당시 경계도 확인되지 않았습니다. 개별 사고 자료와 정보공개청구 결과 확보 후 지정 효과 판단이 가능합니다.")

st.divider()
st.caption("데이터 출처 및 처리 기준: 저장소 README.md · 데이터사전.md · data/processed/ | 관측된 공간 관계와 사고 감소의 인과효과는 다릅니다.")
