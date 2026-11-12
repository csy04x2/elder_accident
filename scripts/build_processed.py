"""elder_accident 원본(data/raw) → 정리 테이블(data/processed) 생성 스크립트
사용: python build_processed.py <원본폴더> <출력폴더>
필요 패키지: pandas, numpy, openpyxl, matplotlib (shapely·pyproj 불필요)
"""
import sys, os, re, glob, json, zipfile, difflib, warnings
import numpy as np, pandas as pd
from matplotlib.path import Path
warnings.filterwarnings('ignore')
RAW, OUT = sys.argv[1].rstrip('/') + '/', sys.argv[2].rstrip('/') + '/'
os.makedirs(OUT, exist_ok=True)
save = lambda df, name: (df.to_csv(OUT + name, index=False, encoding='utf-8-sig'), print(f'  저장 {name}: {df.shape}'))

# ───────── 공통 키: 자치구코드 ─────────
api = pd.read_csv(RAW + '서울_노인보호구역_API.csv')
GU = dict(api[['SGG_NM', 'SGG_CD']].drop_duplicates().values)          # 자치구명 → 코드
GU_R = {v: k for k, v in GU.items()}
assert len(GU) == 25

# ───────── 02 사고 상세 (동대문·도봉) ─────────
det = pd.concat([pd.read_excel(f).assign(원본파일=os.path.basename(f)) for f in sorted(glob.glob(RAW + '*고령보행자사고상세.xlsx'))], ignore_index=True)
ym = det['발생년월'].str.extract(r'(\d{4})년 (\d{1,2})월').astype(int)
det.insert(1, '사고연도', ym[0]); det.insert(2, '사고월', ym[1])
det['자치구명'] = det['시군구'].str.replace('서울특별시 ', ''); det['자치구코드'] = det['자치구명'].map(GU)
for c in ['사고유형', '도로형태']:
    sp = det[c].str.split(' - ', n=1, expand=True); det[c + '_대분류'] = sp[0]; det[c + '_소분류'] = sp[1]
det['부상자수'] = det[['중상자수', '경상자수', '부상신고자수']].sum(axis=1)
det = det.drop(columns=['발생년월', '시군구'])
front = ['구분번호', '사고연도', '사고월', '자치구코드', '자치구명']
det = det[front + [c for c in det.columns if c not in front]].sort_values(['사고연도', '사고월', '구분번호'])
save(det, '02_사고상세_동대문도봉.csv')

# ───────── 03 다발지역 (서울) ─────────
hs = pd.read_csv(RAW + '2012-2025_전국_고령보행자사고다발지역.csv', encoding='cp949')
hs = hs[hs['시도시군구명'].str.startswith('서울')].copy()
hs['자료ID연도'] = hs['사고다발지id'] // 1000
hs['사고연도'] = hs['자료ID연도'] - 1                                   # ID연도 = 사고연도 + 1 (2025년 엑셀 71곳 = ID 2026 행과 일치)
hs['자치구코드'] = hs['법정동코드'] // 100000; hs['자치구명'] = hs['자치구코드'].map(GU_R)
p = hs['지점명'].str.extract(r'^서울\S* \S+ (.+?)\((.+)\)$'); hs['법정동명'] = p[0]; hs['부근명'] = p[1]
hs['선정기준구간'] = np.where(hs['자료ID연도'] <= 2021, 'A(ID2021이전·최소2건)', 'B(ID2022이후·최소5건)')
hs = hs.rename(columns={'사고다발지fid': '다발지역FID', '사고다발지id': '다발지역ID'})
hs = hs[['다발지역FID', '다발지역ID', '자료ID연도', '사고연도', '선정기준구간', '자치구코드', '자치구명', '법정동코드', '법정동명', '부근명', '지점명',
         '사고건수', '사상자수', '사망자수', '중상자수', '경상자수', '부상신고자수', '경도', '위도', '다발지역폴리곤']].sort_values(['사고연도', '자치구코드', '다발지역FID'])
assert hs['자치구명'].notna().all()
save(hs, '03_다발지역_서울.csv')

# ───────── 04 보호구역 마스터 (서울시 지정현황 명단 4개년) ─────────
def read_list(path):
    zf = zipfile.ZipFile(path); xml = ''.join(zf.read(n).decode('utf-8') for n in sorted(zf.namelist()) if 'section' in n)
    tbs = [[[''.join(re.findall(r'<hp:t[^>]*>([^<]*)</hp:t>', c)).strip() for c in re.findall(r'<hp:tc[ >].*?</hp:tc>', r, flags=re.S)]
            for r in re.findall(r'<hp:tr[ >].*?</hp:tr>', tb, flags=re.S)] for tb in re.findall(r'<hp:tbl[ >].*?</hp:tbl>', xml, flags=re.S)]
    big = max(tbs, key=len)                                            # 가장 큰 표 = 노인보호구역 (나머지는 장애인보호구역)
    return [dict(연번=int(r[0]), 자치구명=r[1] if r[1].endswith('구') else r[1] + '구', 시설명=r[2], 위치=r[3], 지정연도=int(r[4][:4])) for r in big if r and r[0].isdigit()]
nsp = lambda s: re.sub(r'\s', '', str(s))
def core(name):                                                        # 시설명 비교용: 괄호·접두어 제거
    s = re.sub(r'\(.*?\)', '', name); s = nsp(s)
    return re.sub(r'^(구립|시립|\S{2,3}구립)', '', s)
def alts(name):                                                       # 본명 + 괄호 안 별칭
    return [core(name)] + [core(x) for x in re.findall(r'\((.*?)\)', name)]
def sim(a, b): return max(difflib.SequenceMatcher(None, x, y).ratio() for x in alts(a['시설명']) for y in alts(b['시설명']))
def same(a, b):                                                        # a, b: 명단 행 → 같은 시설이면 점수(>0)
    if a['자치구명'] != b['자치구명']: return 0
    x, y = nsp(a['위치']), nsp(b['위치']); r = sim(a, b)
    if x == y: return 2 + r
    if r >= 0.8: return 1 + r
    if r >= 0.5 and a['지정연도'] == b['지정연도'] and (x.startswith(y) or y.startswith(x)): return r
    return 0
master = []
YEARS = []
for path in sorted(glob.glob(RAW + '*노인장애인보호구역_지정현황.hwpx')):
    y = int(os.path.basename(path)[:4]); YEARS.append(y)
    todo = read_list(path)
    for exact in (True, False):                                        # 1차: 주소 일치, 2차: 이름 유사
        rest = []
        for row in todo:
            sc = [(same(m['최근'], row), j) for j, m in enumerate(master) if y not in m['등재']]
            sc = [t for t in sc if t[0] >= (2 if exact else 0.01)]
            if sc: m = master[max(sc)[1]]; m['등재'][y] = row; m['다음'] = row
            else: rest.append(row)
        todo = rest
    for row in todo: master.append(dict(등재={y: row}, 최근=row, 다음=row))
    for m in master: m['최근'] = m['다음']
rows = []
for i, m in enumerate(master, 1):
    r, e = m['최근'], m['등재']; first, last = min(e), max(e)
    yrs = sorted({v['지정연도'] for v in e.values()}); names = list(dict.fromkeys(v['시설명'] for v in e.values()))
    rows.append(dict(시설ID=f'Z{i:03d}', 자치구코드=GU[r['자치구명']], 자치구명=r['자치구명'], 시설명=r['시설명'], 위치=r['위치'], 지정연도=r['지정연도'],
                     **{f'명단{y}': int(y in e) for y in YEARS}, 최초등재명단=first, 최종등재명단=last,
                     명단변동='신규등재' if first > YEARS[0] else ('명단제외' if last < YEARS[-1] else '유지'),
                     지정연도_명단간불일치=' / '.join(map(str, yrs)) if len(yrs) > 1 else '', 과거표기=' / '.join(names[:-1]) if len(names) > 1 else ''))
zm = pd.DataFrame(rows)
zm.loc[(zm['최초등재명단'] > YEARS[0]) & (zm['최종등재명단'] < YEARS[-1]), '명단변동'] = '신규등재후제외'

# ───────── 05 보호구역 경계 (API) + 명단 매칭 ─────────
zb = api.rename(columns={'PRTC_ZONE_SEQ': '보호구역SEQ', 'SGG_CD': '자치구코드', 'SGG_NM': '자치구명', 'OBFA_NM': 'API시설명', 'LCTN_ROAD_NM_ADDR': '도로명주소',
                         'LCTN_LOTNO_ADDR': '지번주소', 'LMT_SPD': '제한속도', 'CCTV_INSTLN_CNT': 'CCTV대수', 'PRTC_ZONE_ROAD_WDTH_DTL': '도로폭',
                         'DTIN_CRTR_YMD': '데이터기준일', 'LOT': '경도', 'LAT': '위도', 'CMPTNC_POLSTN_NM': '관할경찰서', 'MNG_INST_NM': '관리기관', 'GEOM': '경계WKT'})
zb['CCTV설치'] = (zb['CCTV_INSTLN_YN'] == 1).astype(int)              # 원본 코드 1=설치, 2=미설치 (대수와 교차 확인)
def match(a):                                                          # API 한 행 → (시설ID, 방식)
    cand = zm[zm['자치구명'] == a['자치구명']]; addr = nsp(a['도로명주소']) + '|' + nsp(a['지번주소']); nm = core(a['API시설명'])
    for _, m in cand.iterrows():
        w = nsp(m['위치'])
        if re.search(r'\d$', w) and re.search(re.escape(w) + r'(?!\d|-\d)', addr) and core(m['시설명']) == nm: return m['시설ID'], '주소+시설명'
    for _, m in cand.iterrows():
        allnames = [m['시설명']] + (m['과거표기'].split(' / ') if m['과거표기'] else [])
        if any(core(x) == nm or nsp(x) == nsp(a['API시설명']) for x in allnames): return m['시설ID'], '시설명'
    for _, m in cand.iterrows():
        w = nsp(m['위치'])
        if re.search(r'\d$', w) and re.search(re.escape(w) + r'(?!\d|-\d)', addr): return m['시설ID'], '주소만(검수필요)'
    for _, m in cand.iterrows():                                       # 명단 위치가 '○○길'까지만 있는 경우
        w = nsp(m['위치'])
        if not re.search(r'\d$', w) and w in addr and core(m['시설명'])[:3] == nm[:3]: return m['시설ID'], '길이름+유사명(검수필요)'
    best = max(((difflib.SequenceMatcher(None, core(m['시설명']), nm).ratio(), m['시설ID']) for _, m in cand.iterrows()), default=(0, None))
    return (best[1], '유사명(검수필요)') if best[0] >= 0.7 else (None, '미매칭')
mm = zb.apply(match, axis=1, result_type='expand'); zb['시설ID'] = mm[0]; zb['명단매칭방식'] = mm[1]
zb = zb.merge(zm[['시설ID', '시설명', '지정연도']].rename(columns={'시설명': '명단시설명'}), on='시설ID', how='left')
zb = zb[['보호구역SEQ', '시설ID', '명단매칭방식', '자치구코드', '자치구명', 'API시설명', '명단시설명', '지정연도', '도로명주소', '지번주소', '제한속도', 'CCTV설치', 'CCTV대수',
         '도로폭', '관할경찰서', '관리기관', '데이터기준일', '경도', '위도', '경계WKT']].sort_values(['자치구코드', 'API시설명', '보호구역SEQ'])
cnt = zb.groupby('시설ID').size(); zm['API경계기록수'] = zm['시설ID'].map(cnt).fillna(0).astype(int)
zm['API매칭방식'] = zm['시설ID'].map(zb.groupby('시설ID')['명단매칭방식'].agg(lambda s: ' / '.join(sorted(set(s))))).fillna('경계없음')
save(zm, '04_보호구역_마스터.csv'); save(zb, '05_보호구역_경계.csv')
rev = pd.concat([
    zb[zb['명단매칭방식'].str.contains('검수|미매칭')][['자치구명', 'API시설명', '도로명주소', '보호구역SEQ', '명단매칭방식', '시설ID', '명단시설명']].assign(구분='API경계→명단'),
    zm[(zm['API경계기록수'] == 0) & (zm['명단2025'] == 1)][['자치구명', '시설명', '위치', '지정연도', '시설ID']].rename(columns={'시설명': '명단시설명', '위치': '명단위치'}).assign(구분='명단(2025)에 있으나 경계없음')], ignore_index=True)
rev['확인결과(직접입력)'] = ''
save(rev.sort_values(['구분', '자치구명']), '검수_명단_API_매칭.csv')

# ───────── 06 다발지역–보호구역 연결 (국소 평면 근사, m) ─────────
def rings_geojson(s): return [np.array(r, float)[:, :2] for r in json.loads(s)['coordinates']]
def polys_wkt(s):                                                      # → [폴리곤(외곽 링)] 목록
    out = []
    for poly in re.findall(r'\(\(.*?\)\)', s[s.index('('):] if s.startswith('POLYGON') else s[s.index('(') + 1:-1], flags=re.S):
        ring = poly.strip('()').split('),(')[0]
        out.append(np.array([list(map(float, pt.split()[:2])) for pt in ring.split(',')]))
    return out
A_, F_ = 6378137.0, 1 / 298.257222101; E2 = F_ * (2 - F_)
def proj(ll, lat0, lon0):                                              # 경위도 → 기준점 주변 평면좌표(m)
    s = np.sin(np.radians(lat0)); N = A_ / np.sqrt(1 - E2 * s * s); M = A_ * (1 - E2) / (1 - E2 * s * s) ** 1.5
    return np.c_[np.radians(ll[:, 0] - lon0) * N * np.cos(np.radians(lat0)), np.radians(ll[:, 1] - lat0) * M]
def pt_seg(P, R):                                                      # 점들 P ↔ 링 R의 변들 최소거리
    A, B = R[:-1], R[1:]; d = B - A; L = (d * d).sum(1); L[L == 0] = 1e-12
    t = np.clip(((P[:, None, :] - A[None]) * d[None]).sum(2) / L[None], 0, 1)
    return np.sqrt((((A[None] + t[..., None] * d[None]) - P[:, None, :]) ** 2).sum(2)).min()
def crosses(R1, R2):
    a, b, c, d = R1[:-1][:, None], R1[1:][:, None], R2[:-1][None], R2[1:][None]
    o = lambda p, q, r: (q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1]) - (q[..., 1] - p[..., 1]) * (r[..., 0] - p[..., 0])
    # 방향 판정과 선분 bounding box를 함께 확인 (일직선상 분리된 선분 제외)
    same_side = (o(a, b, c) * o(a, b, d) <= 0) & (o(c, d, a) * o(c, d, b) <= 0)
    x_overlap = np.maximum(np.minimum(a[..., 0], b[..., 0]), np.minimum(c[..., 0], d[..., 0])) <= np.minimum(np.maximum(a[..., 0], b[..., 0]), np.maximum(c[..., 0], d[..., 0]))
    y_overlap = np.maximum(np.minimum(a[..., 1], b[..., 1]), np.minimum(c[..., 1], d[..., 1])) <= np.minimum(np.maximum(a[..., 1], b[..., 1]), np.maximum(c[..., 1], d[..., 1]))
    return bool((same_side & x_overlap & y_overlap).any())
def pair(H, Zs):                                                       # 다발지역 외곽링 H ↔ 보호구역 폴리곤들 → (거리, 중첩)
    best = np.inf
    for Z in Zs:
        if crosses(H, Z) or Path(Z).contains_points(H[:1])[0] or Path(H).contains_points(Z[:1])[0]: return 0.0, True
        best = min(best, pt_seg(H, Z), pt_seg(Z, H))
    return best, False
zb['_polys'] = zb['경계WKT'].map(polys_wkt)
zc = np.array([np.vstack(p).mean(0) for p in zb['_polys']])
zinfo = zb[['보호구역SEQ', '시설ID', 'API시설명', '지정연도']].reset_index(drop=True); zpol = zb['_polys'].tolist()
def nearest(H_ll, idx):
    lon0, lat0 = H_ll.mean(0); H = proj(H_ll, lat0, lon0)
    cd = np.hypot(*proj(zc[idx], lat0, lon0).T); order = np.argsort(cd); best = (np.inf, False, None); n300 = 0
    for k in order:
        if cd[k] > best[0] + 1500 and cd[k] > 1800: break               # 구역·다발지역 크기(최대 반경 합 < 1.5km) 감안한 가지치기
        dist, ov = pair(H, [proj(Z, lat0, lon0) for Z in zpol[idx[k]]])
        n300 += dist <= 300
        if dist < best[0]: best = (dist, ov, idx[k])
    return best, n300
all_idx = np.arange(len(zinfo)); rows = []
for _, h in hs.iterrows():
    H_ll = rings_geojson(h['다발지역폴리곤'])[0]
    (d, ov, k), n300 = nearest(H_ll, all_idx)
    r = dict(다발지역FID=h['다발지역FID'], 사고연도=h['사고연도'], 자치구명=h['자치구명'], 지점명=h['지점명'], 사고건수=h['사고건수'], 사망자수=h['사망자수'],
             최근접_보호구역SEQ=zinfo['보호구역SEQ'][k], 최근접_시설ID=zinfo['시설ID'][k], 최근접_API시설명=zinfo['API시설명'][k], 최근접_지정연도=zinfo['지정연도'][k],
             최단거리_m=round(d, 1), 경계중첩=int(ov), 반경300m내_경계기록수=n300)
    then = all_idx[(zinfo['지정연도'] <= h['사고연도']).values]           # 사고연도 당시 이미 지정돼 있던 구역만 (지정연도 미상 구역 제외)
    if len(then):
        (d2, ov2, k2), _ = nearest(H_ll, then)
        r.update(당시지정_최근접_API시설명=zinfo['API시설명'][k2], 당시지정_최근접_지정연도=zinfo['지정연도'][k2], 당시지정_최단거리_m=round(d2, 1), 당시지정_경계중첩=int(ov2))
    rows.append(r)
lk = pd.DataFrame(rows); save(lk, '06_다발지역_보호구역_연결.csv')

# ───────── 01 자치구×연도 패널 ─────────
pop = []
q = pd.read_csv(RAW + '2022-2023-2024_고령인구.csv'); q = q[q['동별(2)'].isin(GU)]
for y in (2022, 2023, 2024): pop.append(pd.DataFrame(dict(사고연도=y, 자치구명=q['동별(2)'], 총인구=q[f'{y} 4/4.1'].astype(int), 고령인구=q[f'{y} 4/4.11'].astype(int))))
q = pd.read_csv(RAW + '2025_고령인구.csv'); q = q[q['동별(2)'].isin(GU)]
pop.append(pd.DataFrame(dict(사고연도=2025, 자치구명=q['동별(2)'], 총인구=q['2025 4/4'].astype(int), 고령인구=q['2025 4/4.3'].astype(int))))
panel = pd.concat(pop, ignore_index=True)
def stat(f, pre):
    t = pd.read_excel(RAW + f, header=None).iloc[1:]; t.columns = ['시도', '자치구명', '지표', '값']; t['시도'] = t['시도'].astype(str).str.strip()
    t = t[(t['시도'] == '서울') & (t['자치구명'] != '합계')]; w = t.pivot(index='자치구명', columns='지표', values='값').astype(int)
    return w.rename(columns={'사고[건]': pre + '사고건수', '사망[명]': pre + '사망자수', '부상[명]': pre + '부상자수'}).reset_index().assign(사고연도=2025)
e25 = stat('2025_고령보행자사고.xlsx', '고령보행자_').assign(고령보행자_출처='TAAS 시군구통계')
dg = det.groupby(['사고연도', '자치구명']).agg(고령보행자_사고건수=('구분번호', 'size'), 고령보행자_사망자수=('사망자수', 'sum'), 고령보행자_부상자수=('부상자수', 'sum')).reset_index()
dg = dg[dg['사고연도'] < 2025]
# TAAS 2022~2024년 전체 25개 자치구 사고·사망·부상 통계
counts = pd.read_csv(RAW + '2022-2024_서울25개구_고령보행자사고.csv', encoding='utf-8-sig')
e22_24 = pd.read_csv(RAW + '2022-2024_서울_사고사망부상.csv', encoding='utf-8-sig')
keys = ['사고연도', '자치구명']
assert len(e22_24) == 75 and not e22_24.duplicated(keys).any()
assert e22_24.groupby('사고연도')['자치구명'].nunique().to_dict() == {2022: 25, 2023: 25, 2024: 25}
check = counts.merge(e22_24[keys + ['고령보행자_사고건수']], on=keys,
                     how='outer', indicator=True, suffixes=('_기존', '_신규'), validate='one_to_one')
assert len(check) == 75 and (check['_merge'] == 'both').all()
assert (check['고령보행자_사고건수_기존'] == check['고령보행자_사고건수_신규']).all(), '기존 75개 사고건수와 불일치'
comp = e22_24.merge(dg[keys + ['고령보행자_사고건수']], on=keys,
                    how='inner', suffixes=('_TAAS', '_상세'))
assert (comp['고령보행자_사고건수_TAAS'] == comp['고령보행자_사고건수_상세']).all(), '상세 사고건수와 불일치'
e22_24['고령보행자_출처'] = 'TAAS 시군구통계'
panel = panel.merge(pd.concat([e25, e22_24], ignore_index=True), on=['사고연도', '자치구명'], how='left', validate='one_to_one').merge(stat('2025_전체보행자사고.xlsx', '전체보행자_'), on=['사고연도', '자치구명'], how='left')

# 2025년 65세 이상 생활인구 (남녀 65~69세 + 70세 이상)
lv = pd.read_csv(RAW + '250_LOCAL_RESD_GU_2025.csv', encoding='cp949')
age_cols = ['남자 65~69세', '남자 70세 이상', '여자 65~69세', '여자 70세 이상']
lv['고령'] = lv[age_cols].sum(axis=1)
lvg = lv.groupby('자치구코드')['고령'].mean().round(2).rename('고령생활인구_연평균').reset_index().assign(사고연도=2025)
lvg['자치구명'] = lvg['자치구코드'].map(GU_R)
assert lvg['자치구명'].notna().all(), '생활인구 자치구코드 매칭 오류'
panel = panel.merge(lvg.drop(columns='자치구코드'), on=['사고연도', '자치구명'], how='left')

zl = pd.concat([zm[zm[f'명단{y}'] == 1].groupby('자치구명').size().rename('보호구역_명단시설수').reset_index().assign(사고연도=y) for y in YEARS])
hg = hs.groupby(['사고연도', '자치구명']).agg(다발지역_수=('다발지역FID', 'size'), 다발지역_사고건수=('사고건수', 'sum')).reset_index()
lg = lk.groupby(['사고연도', '자치구명'])['경계중첩'].sum().rename('다발지역_보호구역중첩수').reset_index()
panel = panel.merge(zl, on=['사고연도', '자치구명'], how='left').merge(hg, on=['사고연도', '자치구명'], how='left').merge(lg, on=['사고연도', '자치구명'], how='left')
for c in ['보호구역_명단시설수', '다발지역_수', '다발지역_사고건수', '다발지역_보호구역중첩수']: panel[c] = panel[c].fillna(0).astype(int)   # 이 네 항목은 전 자치구 자료가 있으므로 빈칸=0
panel['고령인구비율_%'] = (panel['고령인구'] / panel['총인구'] * 100).round(2)
panel['고령인구1만명당_고령보행자사고'] = (panel['고령보행자_사고건수'] / panel['고령인구'] * 1e4).round(2)
panel['고령보행자사고_비중_%'] = (panel['고령보행자_사고건수'] / panel['전체보행자_사고건수'] * 100).round(2)
panel['고령생활인구1만명당_고령보행자사고'] = (panel['고령보행자_사고건수'] / panel['고령생활인구_연평균'] * 1e4).round(2)
panel.insert(1, '자치구코드', panel['자치구명'].map(GU))
for c in panel.columns:
    if c.endswith(('건수', '자수')) and panel[c].isna().any(): panel[c] = panel[c].astype('Int64')
save(panel.sort_values(['사고연도', '자치구코드']), '01_자치구연도_패널.csv')
