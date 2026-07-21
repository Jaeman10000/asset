"""장 시간 판별 — 장이 닫혀 있으면 데이터가 변하지 않으므로 API를 아예 안 부른다.

유저 요구: 낮(한국장)엔 한국 것만 갱신하고 미국은 멈춰 있어야 한다. 밤(미국장)엔 반대로
한국은 앱 시작/새로고침 때만 받고 미국을 갱신한다. 키움 레이트리밋(실측 초당 ~1.25콜)에
계속 붙어 도는 걸 막는 게 목적이라, '간격을 늘리는 것'보다 '닫힌 장은 0회'가 효과가 크다.
"""
from __future__ import annotations

from datetime import datetime, time as dtime, timedelta, timezone

# 한국은 서머타임이 없어 UTC+9 고정이다 → zoneinfo(IANA DB)를 쓰지 않는다.
# (윈도우엔 tzdata가 기본 탑재가 아니라 ZoneInfo('Asia/Seoul')이 실패한다. 사이드카로
#  묶어 배포하는 백엔드라 외부 tz 패키지 의존을 만들지 않는 편이 안전하다.)
_KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    return datetime.now(_KST)


def kr_session(now: datetime | None = None) -> bool:
    """한국 정규장(09:00~15:30) ± 여유. 주말 제외.

    장전 동시호가/장후 정리를 감안해 08:50~15:40으로 조금 넓게 잡는다.
    """
    n = now or now_kst()
    if n.weekday() >= 5:  # 토(5)·일(6)
        return False
    return dtime(8, 50) <= n.time() <= dtime(15, 40)


def us_session(now: datetime | None = None) -> bool:
    """미국 정규장을 한국시간 기준으로 판별.

    미국 정규장 09:30~16:00 ET = KST 22:30~05:00(서머타임) / 23:30~06:00(표준시).
    해마다 바뀌는 DST 경계를 직접 계산하지 않고 22:00~06:30 KST로 넉넉히 잡는다
    (조금 일찍 켜지는 건 손해가 없다 — 그 시간엔 한국장이 닫혀 있어 여유가 있다).
    미국 월~금장 = 한국시간 월~금 밤 + 화~토 새벽.
    """
    n = now or now_kst()
    t, wd = n.time(), n.weekday()
    if t >= dtime(22, 0):
        return wd <= 4  # 월~금 밤
    if t <= dtime(6, 30):
        return 1 <= wd <= 5  # 화~토 새벽 (= 미국 월~금)
    return False
