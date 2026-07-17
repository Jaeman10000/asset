# Vitality Nexus — 로컬 백엔드

Tauri 프론트엔드가 폴링하는 FastAPI 서버. `localhost:8787`에서만 뜬다 (외부 노출 안 함).
전체 그림은 [../VITALITY_NEXUS_SPEC.md](../VITALITY_NEXUS_SPEC.md) 2장·4장 참고.

## 실행

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8787 --reload
```

`GET http://localhost:8787/health` → `{"status":"ok"}`이면 정상.

## 확인된 스택 (2026-07 기준)

로컬 Python이 **3.14.5**로 아주 최신이라, 버전을 고정하지 않고 설치하면
`pydantic-core`가 Rust 소스 빌드를 시도하다 링커 에러로 실패한다
(`--only-binary :all:`로 재설치해서 이미 해결됨 — `requirements.txt`가 실제로
설치된 버전으로 고정돼 있음). 다른 환경에서 설치가 안 되면 이 부분부터 의심할 것.

| 패키지 | 버전 |
|---|---|
| fastapi | 0.139.2 |
| uvicorn | 0.51.0 |
| pydantic | 2.13.4 |
| httpx | 0.28.1 |
| keyring | 25.7.0 |

## 엔드포인트

- `GET /health` — 헬스체크
- `GET /portfolio/snapshot` — 통합 포트폴리오 (스펙 4장 `PortfolioSnapshot` 그대로, 7초 TTL 캐시)
- `GET /config/sources` — 어댑터별 API 키 등록 여부 (값은 노출 안 함)

## 어댑터 상태 (2026-07-17 기준)

| 소스 | 상태 | 비고 |
|---|---|---|
| **manual (수동입력)** | ✅ 실동작 | `data/holdings.json`의 보유 종목을 Position으로 변환. **API 키 불필요** — 미지원 증권사/키 미설정 사용자를 위한 만능 폴백. 암호화폐+주식 모두 현재가 자동 갱신 |
| **Yahoo Finance (섹터)** | ✅ 실동작 | API 키 불필요, 11개 SPDR 섹터 ETF 일간 등락률 |
| **공개 시세 (업비트/빗썸)** | ✅ 실동작 | `services/quotes.py`. 키 없이 암호화폐 현재가/등락률 |
| **주식 시세 (Yahoo)** | ✅ 실동작 | `services/stock_quotes.py`. 국내('.KS')/미국 주식 현재가+32개 history+USD/KRW 환율. 키 불필요 |
| 키움 | 🔲 설정대기 | REST API 키 발급 필요. Open API+(레거시)는 32비트 COM이라 이 프로세스에서 직접 호출 불가 — 별도 브리지 필요 |
| KIS | 🔲 설정대기 | KIS Developers 앱키/시크릿 발급 필요. 순수 REST라 구현은 단순함 |
| 업비트 (계좌) | 🔲 설정대기 | 시세는 위에서 키 없이 되지만 **보유 수량(계좌 조회)은 JWT 서명 API 키 필수** |
| 빗썸 (계좌) | 🔲 설정대기 | 업비트와 동일 |
| KRX 정보데이터시스템 | 🔲 설정대기 | 접근 방식(공식 API vs 파싱) 미결정 |

**부분 실패 원칙**(스펙 4장)이 실제로 동작함을 확인:
- 설정 안 된 소스(키 미입력/미구현)는 `unconfigured=True`로 표시 → `errors`에는
  상태 표시용으로 담기지만 **`isEstimate`를 True로 만들지 않는다**. 키를 일부러
  안 넣은 사용자에게 상시 "추정치" 경고를 띄우지 않기 위함.
- 진짜 데이터 조회 실패(예: 시세 API 다운)만 `isEstimate=True`로 만든다.

## 수동입력 (판매 전략의 핵심 폴백)

거래소 API 없이도 `data/holdings.json`에 보유 종목을 적으면 대시보드가 채워진다.
`data/holdings.example.json`을 복사해서 쓴다. 이게 중요한 이유:
- **미지원 증권사 사용자**도 쓸 수 있음 (수량만 적으면 시세는 공개 API로)
- **업비트 API 상업적 이용 제한**을 우회하는 경로 — 본체는 API를 안 건드리고
  거래소 어댑터는 선택적 플러그인으로 분리 가능

업비트 배치 시세는 심볼 하나가 잘못되면 전체가 404가 나는 특성이 있어서,
`fetch_upbit_quotes`가 배치 실패 시 심볼별 개별 재시도로 유효한 것만 건진다
(holdings.json 오타 하나가 나머지 시세를 죽이지 않음 — 로컬 테스트로 확인).

## API 키 등록 (나중에 실계좌 연동할 때)

키는 `.env`나 코드에 절대 넣지 않고 OS 키체인(Windows Credential Locker)에 저장한다:

```bash
.venv/Scripts/python scripts/set_api_key.py kiwoom app_key
.venv/Scripts/python scripts/set_api_key.py kis app_key
.venv/Scripts/python scripts/set_api_key.py upbit access_key
.venv/Scripts/python scripts/set_api_key.py upbit secret_key
.venv/Scripts/python scripts/set_api_key.py bithumb api_key
.venv/Scripts/python scripts/set_api_key.py bithumb api_secret
```

값은 `getpass`로 입력받아 터미널 히스토리에 남지 않는다. 등록 후 해당 어댑터의
`app/adapters/*.py`에서 `TODO: 실제 구현` 부분을 채우면 된다 — 스텁이 키
등록 여부를 이미 확인하고 있어서, 키만 넣으면 나머지 배선은 그대로 작동한다.

## 로컬 검증 완료 항목 (2026-07-17)

- `/health`, `/config/sources`, `/portfolio/snapshot` 실제 HTTP 요청으로 확인
- Yahoo 어댑터가 실제 11개 섹터 데이터를 가져오는지 확인 (`ret`/`volume` 값 실측)
- 7초 TTL 캐시: 연속 호출은 같은 `fetchedAt`, 8초 후엔 갱신되는지 확인
- SQLite에 스냅샷이 실제로 쌓이는지 확인
- 키체인 set/get/delete 왕복 확인 (`keyring.backends.Windows.WinVaultKeyring` 사용 확인)

## 다음 (Day 6+)

- KIS 앱키 발급받아 계좌 조회 REST 어댑터 구현 (미국 주식, 가장 REST 친화적)
- 업비트/빗썸 계좌 조회 API 구현 (JWT 서명 + `/v1/accounts`) — 지금은 수동입력이 대체
- 키움 Open API+ 32비트 브리지 방식 조사 또는 REST API 전환 검토
- KRX 투자자별 매매동향 접근 방식 결정
- 암호화폐 history(스파크라인) — 업비트 candles API로 추가 가능 (지금은 주식만 history 있음)
- (선택) Week 2: 프론트엔드 대시보드 본편 이식 + 이 백엔드 폴링 연동

## 로컬 검증 완료 (Day 3-5, 2026-07-17)

- 업비트/빗썸 공개 시세 실시간 확인 (BTC 9,350만원 등)
- **주식 시세**: 삼성전자(255,000원, history 32)·애플($333.26→KRW 환산)·환율 자동 적용 확인
- 수동입력 혼합(암호화폐+국내주식+미국주식)이 스냅샷에 반영되고
  `stock == kr+us`, `total == stock+crypto` 등 totals 계산이 정확한지 확인
- **일간 등락률 버그 수정**: 섹터/주식 모두 일봉 close[-2](전일 종가) 기준으로 계산.
  이전엔 `chartPreviousClose`(range 시작점 = 5일 전) 기준이라 5일 등락률이 나왔음
- `isEstimate`가 설정대기만 있을 때 False, 진짜 실패 시에만 True인지 확인
- 견고성: 없는 심볼/필수필드 누락 행을 섞어도 유효 종목만 살아남고,
  업비트 배치 실패 시 심볼별 개별 재시도 폴백이 동작하는지 확인
