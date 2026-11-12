"""보호구역 지정 전후 주변(300m) 고령 보행자 사고다발지역 변화 — 탐색 분석
사용: python analysis_before_after.py data/processed
"""
import sys, re, json, numpy as np, pandas as pd
from matplotlib.path import Path
P = sys.argv[1].rstrip('/') + '/'
hs = pd.read_csv(P + '03_다발지역_서울.csv'); zb = pd.read_csv(P + '05_보호구역_경계.csv'); zm = pd.read_csv(P + '04_보호구역_마스터.csv')
A_, F_ = 6378137.0, 1 / 298.257222101; E2 = F_ * (2 - F_)
def proj(ll, lat0, lon0):
    s = np.sin(np.radians(lat0)); N = A_ / np.sqrt(1 - E2 * s * s); M = A_ * (1 - E2) / (1 - E2 * s * s) ** 1.5
    return np.c_[np.radians(ll[:, 0] - lon0) * N * np.cos(np.radians(lat0)), np.radians(ll[:, 1] - lat0) * M]
def polys_wkt(s):
    body = s[s.index('('):] if s.startswith('POLYGON') else s[s.index('(') + 1:-1]
    return [np.array([list(map(float, pt.split()[:2])) for pt in poly.strip('()').split('),(')[0].split(',')]) for poly in re.findall(r'\(\(.*?\)\)', body, flags=re.S)]
def pt_seg(Pt, R):
    A, B = R[:-1], R[1:]; d = B - A; L = (d * d).sum(1); L[L == 0] = 1e-12
    t = np.clip(((Pt[:, None, :] - A[None]) * d[None]).sum(2) / L[None], 0, 1)
    return np.sqrt((((A[None] + t[..., None] * d[None]) - Pt[:, None, :]) ** 2).sum(2)).min()
def crosses(R1, R2):
    a, b, c, d = R1[:-1][:, None], R1[1:][:, None], R2[:-1][None], R2[1:][None]
    o = lambda p, q, r: (q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1]) - (q[..., 1] - p[..., 1]) * (r[..., 0] - p[..., 0])
    # 방향 판정과 선분 bounding box를 함께 확인 (일직선상 분리된 선분 제외)
    same_side = (o(a, b, c) * o(a, b, d) <= 0) & (o(c, d, a) * o(c, d, b) <= 0)
    x_overlap = np.maximum(np.minimum(a[..., 0], b[..., 0]), np.minimum(c[..., 0], d[..., 0])) <= np.minimum(np.maximum(a[..., 0], b[..., 0]), np.maximum(c[..., 0], d[..., 0]))
    y_overlap = np.maximum(np.minimum(a[..., 1], b[..., 1]), np.minimum(c[..., 1], d[..., 1])) <= np.minimum(np.maximum(a[..., 1], b[..., 1]), np.maximum(c[..., 1], d[..., 1]))
    return bool((same_side & x_overlap & y_overlap).any())
def dist(H, Zs):
    best = np.inf
    for Z in Zs:
        if crosses(H, Z) or Path(Z).contains_points(H[:1])[0] or Path(H).contains_points(Z[:1])[0]: return 0.0
        best = min(best, pt_seg(H, Z), pt_seg(Z, H))
    return best
zp = zb['경계WKT'].map(polys_wkt).tolist(); zc = np.array([np.vstack(p).mean(0) for p in zp])
pairs = []
for _, h in hs.iterrows():
    H_ll = np.array(json.loads(h['다발지역폴리곤'])['coordinates'][0], float)[:, :2]; lon0, lat0 = H_ll.mean(0); H = proj(H_ll, lat0, lon0)
    cd = np.hypot(*proj(zc, lat0, lon0).T)
    for k in np.where(cd < 2000)[0]:
        d = dist(H, [proj(Z, lat0, lon0) for Z in zp[k]])
        if d <= 500: pairs.append((h['다발지역FID'], h['사고연도'], h['사고건수'], h['사망자수'], zb['보호구역SEQ'][k], zb['시설ID'][k], round(d, 1)))
pr = pd.DataFrame(pairs, columns=['다발지역FID', '사고연도', '사고건수', '사망자수', '보호구역SEQ', '시설ID', '거리_m'])
pr = pr.sort_values('거리_m').drop_duplicates(['다발지역FID', '시설ID'])            # 시설 단위(경계 여러 건 → 최단거리)
pr.to_csv(P + '07_다발지역_보호구역_500m쌍.csv', index=False, encoding='utf-8-sig'); print('500m 이내 쌍', len(pr))
fac = zm[zm['API경계기록수'] > 0][['시설ID', '자치구명', '시설명', '지정연도']]
def era(y): return 'A' if y <= 2020 else 'B'                                          # 사고연도 기준: A=2012~2020, B=2021~2025
YA, YB = range(2012, 2021), range(2021, 2026)
tot = hs.groupby('사고연도').size()
def event(R, years, Ts, K, label):
    f = fac[fac['지정연도'].isin(Ts)]; rows = []
    for _, z in f.iterrows():
        near = pr[(pr['시설ID'] == z['시설ID']) & (pr['거리_m'] <= R)]
        for y in years:
            k = y - z['지정연도']
            if abs(k) <= K: rows.append((z['시설ID'], z['지정연도'], k, (near['사고연도'] == y).sum(), near.loc[near['사고연도'] == y, '사고건수'].sum(), tot[y]))
    e = pd.DataFrame(rows, columns=['시설ID', 'T', 'k', '다발지역수', '사고건수', '서울전체다발지역수'])
    g = e.groupby('k').agg(시설수=('시설ID', 'nunique'), 주변다발지역_합=('다발지역수', 'sum'), 주변다발지역있는시설=('다발지역수', lambda s: (s > 0).sum()),
                           주변사고건수_합=('사고건수', 'sum'), 서울전체_평균=('서울전체다발지역수', 'mean')).round(1)
    print(f'\n[{label}] 반경 {R}m, 지정연도 {min(Ts)}~{max(Ts)}, 대상 시설 {f.shape[0]}곳'); print(g.T.to_string())
    pre, post = e[e.k < 0], e[e.k > 0]
    print(f'  지정 전 {K}년 합 {pre["다발지역수"].sum()}곳 / 지정 후 {K}년 합 {post["다발지역수"].sum()}곳   (같은 기간 서울 전체 비율: 후/전 = {post["서울전체다발지역수"].sum() / pre["서울전체다발지역수"].sum():.2f})')
    w = e.pivot_table(index='시설ID', columns=np.sign(e.k), values='다발지역수', aggfunc='sum')
    print(f'  시설별: 전에만 있음 {((w[-1] > 0) & (w[1] == 0)).sum()}, 후에만 있음 {((w[-1] == 0) & (w[1] > 0)).sum()}, 전후 모두 {((w[-1] > 0) & (w[1] > 0)).sum()}, 전후 모두 없음 {((w[-1] == 0) & (w[1] == 0)).sum()}')
    return e
for R in (300, 100):
    event(R, YA, range(2015, 2018), 3, '기준 A · 전후 3년 균형')
    event(R, YA, range(2014, 2019), 2, '기준 A · 전후 2년 균형')
event(300, YB, [2023], 2, '기준 B · 2023년 지정 · 전후 2년')
# 대조: 같은 기간 아직 지정 전이던 시설(지정연도 2019~2020 → 2012~2017 구간에서는 미지정)
print('\n[대조] 지정연도별 대상 시설 수(경계 있음):', fac['지정연도'].value_counts().sort_index().to_dict())
ctl = fac[fac['지정연도'].isin([2019, 2020])]
for nm, yrs in (('2013~2015', range(2013, 2016)), ('2016~2018', range(2016, 2019))):
    n = pr[pr['시설ID'].isin(ctl['시설ID']) & (pr['거리_m'] <= 300) & pr['사고연도'].isin(yrs)]; print(f'  2019~2020 지정 시설 {len(ctl)}곳 주변 300m 다발지역, {nm}: {len(n)}곳 (서울 전체 {tot[list(yrs)].sum()})')
