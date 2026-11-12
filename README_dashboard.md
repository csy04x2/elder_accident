## Streamlit 탐색 대시보드 실행

기존 `data/processed/` CSV 파일을 읽으며 원본 데이터나 분석 스크립트는 수정하지 않습니다.

Windows PowerShell에서 저장소 루트로 이동해 실행합니다.

```powershell
cd "C:\Users\EZ\OneDrive\바탕 화면\project\elder_accident"
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

브라우저에 표시되는 로컬 주소(기본값 `http://localhost:8501`)를 엽니다. 좌측에서 화면·사고연도·자치구를 선택합니다.

필수 파일: `data/processed/01_자치구연도_패널.csv`, `03_다발지역_서울.csv`, `04_보호구역_마스터.csv`, `05_보호구역_경계.csv`, `06_다발지역_보호구역_연결.csv`.

주의: 2022~2024년의 고령 보행자 사고건수는 동대문·도봉만 확보되어 있습니다. 사고다발지역 선정 기록은 개별 사고건수가 아니며 선정 기준이 연도에 따라 바뀌었습니다. 지도는 현행 API 경계를 쓰므로 과거 경계와 다를 수 있고, API가 공식 지정 시설 전체를 포괄하지 않을 수 있습니다. 지정 전후 인과효과 분석은 추가 사고자료 확보 전까지 불가능합니다.
