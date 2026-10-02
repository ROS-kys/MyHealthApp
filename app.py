"""운동 스케줄 — Streamlit 버전.

브라우저 앱(index.html / app.js)을 파이썬으로 옮긴 것. 데이터는 같은 JSON 형식
({ version: 1, workouts, customExercises, routines, settings })으로 이 폴더의
workout_data.json에 저장하므로, 브라우저 앱에서 내보낸 백업 파일을 그대로 가져올 수 있다.

실행: streamlit run app.py
"""

from __future__ import annotations

import io
import json
import math
import os
import re
import struct
import time
import uuid
import wave
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# =========================================================
# 상수: 카테고리와 기본 운동 목록 (PRD 3.6절)
# badge: st.badge 색 이름 / color: 차트·달력 점 색
# =========================================================
CATEGORIES = [
    {
        'key': 'chest', 'name': '가슴', 'color': '#EF4444', 'badge': 'red', 'unit': 'reps', 'has_weight': True,
        'groups': {
            '프리웨이트': ['벤치 프레스', '인클라인 벤치 프레스', '디클라인 벤치 프레스', '덤벨 프레스', '인클라인 덤벨 프레스',
                       '덤벨 플라이', '인클라인 덤벨 플라이', '덤벨 풀오버'],
            '머신': ['체스트 프레스 머신', '인클라인 체스트 프레스 머신', '디클라인 체스트 프레스 머신', '펙덱 플라이',
                   '스미스 머신 벤치 프레스', '스미스 머신 인클라인 프레스', '해머 스트렝스 체스트 프레스', '어시스트 딥스 머신'],
            '케이블': ['케이블 크로스오버', '하이 케이블 플라이', '로우 케이블 플라이', '원암 케이블 프레스'],
            '맨몸': ['푸시업', '인클라인 푸시업', '디클라인 푸시업', '딥스'],
        },
    },
    {
        'key': 'back', 'name': '등', 'color': '#3B82F6', 'badge': 'blue', 'unit': 'reps', 'has_weight': True,
        'groups': {
            '프리웨이트': ['데드리프트', '랙 풀', '바벨 로우', '펜들레이 로우', '덤벨 로우', '원암 덤벨 로우', 'T바 로우'],
            '머신': ['랫 풀다운', '머신 랫 풀다운', '시티드 로우 머신', '하이 로우 머신', 'T바 로우 머신',
                   '어시스트 풀업 머신', '풀오버 머신', '백 익스텐션'],
            '케이블': ['시티드 케이블 로우', '원암 케이블 로우', '클로즈 그립 랫 풀다운', '스트레이트 암 풀다운', '페이스 풀'],
            '맨몸': ['풀업', '친업', '인버티드 로우'],
        },
    },
    {
        'key': 'legs', 'name': '하체', 'color': '#22C55E', 'badge': 'green', 'unit': 'reps', 'has_weight': True,
        'groups': {
            '프리웨이트': ['스쿼트', '프론트 스쿼트', '고블릿 스쿼트', '루마니안 데드리프트', '스모 데드리프트', '런지', '워킹 런지',
                       '불가리안 스플릿 스쿼트', '스텝업', '힙 쓰러스트', '카프 레이즈'],
            '머신': ['레그 프레스', '핵 스쿼트', '스미스 머신 스쿼트', '펜듈럼 스쿼트', '브이 스쿼트', '레그 익스텐션', '라잉 레그 컬',
                   '시티드 레그 컬', '이너싸이 머신 (힙 어덕션)', '아웃싸이 머신 (힙 어브덕션)', '글루트 킥백 머신', '힙 쓰러스트 머신',
                   '스탠딩 카프 레이즈 머신', '시티드 카프 레이즈'],
            '케이블': ['케이블 킥백', '케이블 풀스루'],
            '맨몸': ['에어 스쿼트', '점프 스쿼트', '글루트 브릿지'],
        },
    },
    {
        'key': 'shoulders', 'name': '어깨', 'color': '#F97316', 'badge': 'orange', 'unit': 'reps', 'has_weight': True,
        'groups': {
            '프리웨이트': ['오버헤드 프레스', '덤벨 숄더 프레스', '아놀드 프레스', '사이드 레터럴 레이즈', '프론트 레이즈',
                       '리어 델트 플라이', '업라이트 로우', '슈러그'],
            '머신': ['숄더 프레스 머신', '스미스 머신 숄더 프레스', '레터럴 레이즈 머신', '리버스 펙덱 플라이', '슈러그 머신'],
            '케이블': ['케이블 사이드 레터럴 레이즈', '케이블 프론트 레이즈', '케이블 리어 델트 플라이', '케이블 업라이트 로우'],
            '맨몸': ['파이크 푸시업', '핸드스탠드 푸시업'],
        },
    },
    {
        'key': 'arms', 'name': '팔', 'color': '#A855F7', 'badge': 'violet', 'unit': 'reps', 'has_weight': True,
        'groups': {
            '프리웨이트': ['바벨 컬', 'EZ바 컬', '덤벨 컬', '해머 컬', '인클라인 덤벨 컬', '컨센트레이션 컬', '프리처 컬',
                       '라잉 트라이셉스 익스텐션', '오버헤드 트라이셉스 익스텐션', '클로즈 그립 벤치 프레스', '덤벨 킥백', '리스트 컬'],
            '머신': ['바이셉스 컬 머신', '프리처 컬 머신', '트라이셉스 익스텐션 머신', '트라이셉스 딥스 머신'],
            '케이블': ['케이블 컬', '로프 해머 컬', '트라이셉스 푸시다운', '로프 푸시다운', '케이블 오버헤드 트라이셉스 익스텐션'],
            '맨몸': ['벤치 딥스', '다이아몬드 푸시업'],
        },
    },
    {
        'key': 'core', 'name': '복근/코어', 'color': '#EAB308', 'badge': 'yellow', 'unit': 'reps', 'has_weight': True,
        'groups': {
            '맨몸': ['크런치', '바이시클 크런치', '싯업', 'V업', '레그 레이즈', '행잉 레그 레이즈', '플랭크', '사이드 플랭크',
                   '러시안 트위스트', '마운틴 클라이머', '데드버그'],
            '머신': ['앱 크런치 머신', '토르소 로테이션 머신', '캡틴스 체어 레그 레이즈', '디클라인 싯업'],
            '케이블': ['케이블 크런치', '케이블 우드찹', '팔로프 프레스'],
            '소도구': ['앱 롤아웃', '메디신볼 슬램'],
        },
    },
    {
        'key': 'cardio', 'name': '유산소', 'color': '#14B8A6', 'badge': 'gray', 'unit': 'min', 'has_weight': False,
        'groups': {
            '머신': ['러닝머신', '사이클', '리컴번트 바이크', '스텝밀(천국의 계단)', '로잉머신', '일립티컬', '에어 바이크', '스키 에르그'],
            '기타': ['줄넘기', '배틀 로프', '버피', '인터벌 트레이닝(HIIT)'],
        },
    },
]
for _c in CATEGORIES:
    _c['exercises'] = [name for names in _c['groups'].values() for name in names]
    _c['group_of'] = {name: group for group, names in _c['groups'].items() for name in names}
CAT = {c['key']: c for c in CATEGORIES}

# 운동명 변경 이력 — 불러오기·가져오기 때 옛 이름을 새 이름으로 바꿔 '지난 기록' 매칭을 잇는다
EXERCISE_RENAMES = {
    'chest': {'싱글암 케이블 프레스': '원암 케이블 프레스'},
    'legs': {'힙 어덕션 머신': '이너싸이 머신 (힙 어덕션)', '힙 어브덕션 머신': '아웃싸이 머신 (힙 어브덕션)', '레그 컬': '라잉 레그 컬'},
    'shoulders': {'리어 델트 머신': '리버스 펙덱 플라이'},
    'arms': {'킥백': '덤벨 킥백', '케이블 오버헤드 익스텐션': '케이블 오버헤드 트라이셉스 익스텐션'},
}

UNIT_LABEL = {'reps': '회', 'min': '분', 'sec': '초'}
REPS_FIELD_LABEL = {'reps': '횟수(회)', 'min': '시간(분)', 'sec': '시간(초)'}
TIMED_EXERCISES = {'core': ['플랭크', '사이드 플랭크']}

LIMITS = {'name': 30, 'memo': 100, 'weight': (0, 500), 'reps': (1, 100), 'sets': (1, 20)}
REPS_LIMITS = {'reps': (1, 100), 'min': (1, 100), 'sec': (1, 600)}
ROUTINE_LIMITS = {'name': 20, 'items': 30}
DEFAULTS = {'weight': 0, 'reps': 10, 'sets': 3}
DEFAULT_REPS = {'reps': 10, 'min': 10, 'sec': 30}
WEIGHT_STEP = 2.5

DEFAULT_SETTINGS = {'restSeconds': 90, 'restSound': True, 'weeklyGoal': 3}
REST_OPTIONS = [0, 30, 45, 60, 90, 120, 150, 180, 240, 300]
REST_ADJUST = 15
HISTORY_LIMIT = 30
TREND_PERIODS = 8
E1RM_MAX_REPS = 12
UNDO_SECONDS = 30  # '실행 취소' 안내를 보여주는 시간

DATA_VERSION = 1
DATA_FILE = Path(__file__).with_name('workout_data.json')
BACKUP_FILE = Path(__file__).with_name('workout_data.backup.json')

CUSTOM_OPTION = '__custom__'
WEEKDAY_NAMES = '일월화수목금토'  # 저장 형식과 같은 0=일 ~ 6=토
WEEKDAY_ORDER = [1, 2, 3, 4, 5, 6, 0]  # 화면에는 월요일부터


def migrate_name(category: str, name: str) -> str:
    return EXERCISE_RENAMES.get(category, {}).get(name, name)


def unit_of(category: str, name: str) -> str:
    return 'sec' if name in TIMED_EXERCISES.get(category, []) else CAT[category]['unit']


# =========================================================
# 날짜 유틸 — 로컬 시간 기준 'YYYY-MM-DD'
# =========================================================
def today_key() -> str:
    return date.today().isoformat()


def parse_key(key: str) -> date:
    return date.fromisoformat(key)


def is_valid_date_key(key) -> bool:
    if not isinstance(key, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', key):
        return False
    try:
        date.fromisoformat(key)
        return True
    except ValueError:
        return False


def add_days(key: str, n: int) -> str:
    return (parse_key(key) + timedelta(days=n)).isoformat()


def js_weekday(key: str) -> int:
    """0=일 ~ 6=토 (브라우저 앱의 Date.getDay()와 같은 기준)"""
    return (parse_key(key).weekday() + 1) % 7


def week_start(key: str) -> str:
    """주는 일요일 시작 (달력과 같은 기준)"""
    return add_days(key, -js_weekday(key))


def add_months(month: str, n: int) -> str:
    y, m = map(int, month.split('-'))
    total = y * 12 + (m - 1) + n
    return f'{total // 12:04d}-{total % 12 + 1:02d}'


def month_end(month: str) -> str:
    return add_days(f'{add_months(month, 1)}-01', -1)


def fmt_month_day(key: str) -> str:
    return f'{key[5:7]}/{key[8:10]}'


def fmt_date_short(key: str) -> str:
    return f'{fmt_month_day(key)}({WEEKDAY_NAMES[js_weekday(key)]})'


def fmt_date_long(key: str) -> str:
    d = parse_key(key)
    return f'{d.month}월 {d.day}일 ({WEEKDAY_NAMES[js_weekday(key)]})'


def fmt_month_title(month: str) -> str:
    y, m = map(int, month.split('-'))
    return f'{y}년 {m}월'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def iso_to_ms(text) -> int:
    try:
        return int(datetime.fromisoformat(str(text).replace('Z', '+00:00')).timestamp() * 1000)
    except ValueError:
        return 0


# =========================================================
# 숫자·문자 표시
# =========================================================
def num(x):
    """80.0 → 80 (브라우저 앱이 저장하는 모양과 맞춘다)"""
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return x


def fmt_num(x) -> str:
    return f'{num(x):,}' if isinstance(num(x), int) else f'{x:g}'


_MD_SPECIAL = re.compile(r'([\\`*_{}\[\]()#+\-.!|~<>$:=])')


def esc(text: str) -> str:
    """사용자 입력(운동명·메모)을 마크다운 문법으로 해석하지 않도록 이스케이프"""
    return _MD_SPECIAL.sub(r'\\\1', text)


def is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def clamp(n, lo, hi):
    return max(lo, min(hi, n))


# =========================================================
# 저장 계층 — 같은 형식의 JSON 파일
# =========================================================
def empty_data() -> dict:
    return {'version': DATA_VERSION, 'workouts': [], 'customExercises': {}, 'routines': [], 'settings': dict(DEFAULT_SETTINGS)}


def normalize_set_logs(raw, sets: int, has_weight: bool, unit: str) -> list:
    items = raw if isinstance(raw, list) else []
    lo, hi = REPS_LIMITS[unit]
    out = []
    for i in range(sets):
        log = items[i] if i < len(items) else None
        if not isinstance(log, dict) or not is_int(log.get('reps')):
            out.append(None)
            continue
        weight = None
        if has_weight:
            w = log.get('weight')
            weight = num(clamp(round(w * 2) / 2, *LIMITS['weight'])) if is_number(w) else 0
        out.append({'weight': weight, 'reps': clamp(log['reps'], lo, hi)})
    return out


def normalize_workout(raw):
    """저장된 운동 하나를 현재 스키마로 정규화. 복구 불가능하면 None (관대한 복구)"""
    if not isinstance(raw, dict):
        return None
    if not isinstance(raw.get('id'), str) or not raw['id']:
        return None
    if not is_valid_date_key(raw.get('date')) or raw.get('category') not in CAT:
        return None
    if not isinstance(raw.get('name'), str) or not raw['name'].strip():
        return None
    category = raw['category']
    sets = raw['sets'] if is_int(raw.get('sets')) and raw['sets'] > 0 else 1
    done = raw.get('done') is True
    completed = raw['completedSets'] if is_int(raw.get('completedSets')) else (sets if done else 0)
    completed = clamp(completed, 0, sets)
    name = migrate_name(category, raw['name'])
    created = raw['createdAt'] if isinstance(raw.get('createdAt'), str) else now_iso()
    has_weight = CAT[category]['has_weight']
    return {
        'id': raw['id'],
        'date': raw['date'],
        'category': category,
        'name': name,
        'weight': raw['weight'] if has_weight and is_number(raw.get('weight')) else None,
        'reps': raw['reps'] if is_int(raw.get('reps')) and raw['reps'] > 0 else 1,
        'sets': sets,
        'completedSets': completed,
        'done': completed == sets,
        'memo': raw['memo'] if isinstance(raw.get('memo'), str) else '',
        'order': raw['order'] if is_number(raw.get('order')) else iso_to_ms(created),
        'setLogs': normalize_set_logs(raw.get('setLogs'), sets, has_weight, unit_of(category, name)),
        'createdAt': created,
        'updatedAt': raw['updatedAt'] if isinstance(raw.get('updatedAt'), str) else now_iso(),
    }


def to_routine_item(src: dict) -> dict:
    return {
        'category': src['category'],
        'name': src['name'],
        'weight': (src.get('weight') or 0) if CAT[src['category']]['has_weight'] else None,
        'reps': src['reps'],
        'sets': src['sets'],
        'memo': src.get('memo') or '',
    }


def normalize_routine_item(raw):
    if not isinstance(raw, dict) or raw.get('category') not in CAT:
        return None
    if not isinstance(raw.get('name'), str) or not raw['name'].strip():
        return None
    category = raw['category']
    name = migrate_name(category, raw['name'])
    def as_int(n, limits, fallback):
        return clamp(n, *limits) if is_int(n) else fallback
    return to_routine_item({
        'category': category,
        'name': name,
        'weight': clamp(raw['weight'], *LIMITS['weight']) if is_number(raw.get('weight')) else 0,
        'reps': as_int(raw.get('reps'), REPS_LIMITS[unit_of(category, name)], DEFAULTS['reps']),
        'sets': as_int(raw.get('sets'), LIMITS['sets'], DEFAULTS['sets']),
        'memo': raw['memo'] if isinstance(raw.get('memo'), str) else '',
    })


def normalize_weekdays(raw) -> list:
    if not isinstance(raw, list):
        return []
    return sorted({d for d in raw if is_int(d) and 0 <= d <= 6})


def normalize_routine(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get('id'), str) or not raw['id']:
        return None
    if not isinstance(raw.get('name'), str) or not raw['name'].strip() or not isinstance(raw.get('items'), list):
        return None
    items = [i for i in (normalize_routine_item(x) for x in raw['items']) if i][:ROUTINE_LIMITS['items']]
    if not items:
        return None
    now = now_iso()
    return {
        'id': raw['id'],
        'name': raw['name'].strip(),
        'items': items,
        'weekdays': normalize_weekdays(raw.get('weekdays')),
        'createdAt': raw['createdAt'] if isinstance(raw.get('createdAt'), str) else now,
        'updatedAt': raw['updatedAt'] if isinstance(raw.get('updatedAt'), str) else now,
    }


def normalize_settings(raw) -> dict:
    s = raw if isinstance(raw, dict) else {}
    goal = s.get('weeklyGoal')
    return {
        'restSeconds': s['restSeconds'] if s.get('restSeconds') in REST_OPTIONS and is_int(s.get('restSeconds')) else DEFAULT_SETTINGS['restSeconds'],
        'restSound': s['restSound'] if isinstance(s.get('restSound'), bool) else DEFAULT_SETTINGS['restSound'],
        'weeklyGoal': clamp(goal, 1, 7) if is_int(goal) else DEFAULT_SETTINGS['weeklyGoal'],
    }


def normalize_data(raw) -> dict:
    if not isinstance(raw, dict) or not isinstance(raw.get('workouts'), list):
        raise ValueError('잘못된 데이터 구조')
    workouts = [w for w in (normalize_workout(x) for x in raw['workouts']) if w]
    routines = [r for r in (normalize_routine(x) for x in raw.get('routines', [])) if r] if isinstance(raw.get('routines'), list) else []
    custom = {}
    if isinstance(raw.get('customExercises'), dict):
        for key, names in raw['customExercises'].items():
            if key in CAT and isinstance(names, list):
                custom[key] = [migrate_name(key, n) for n in names if isinstance(n, str) and n.strip()]
    return {'version': DATA_VERSION, 'workouts': workouts, 'customExercises': custom, 'routines': routines,
            'settings': normalize_settings(raw.get('settings'))}


def load_data() -> dict:
    """파일이 없으면 빈 상태. 손상됐으면 빈 상태로 시작하고 원본은 백업 파일에 보관한다"""
    try:
        text = DATA_FILE.read_text(encoding='utf-8')
    except FileNotFoundError:
        return empty_data()
    except OSError as err:
        warn_once(f'데이터 파일을 읽을 수 없어 빈 상태로 시작합니다: {err}')
        return empty_data()
    try:
        return normalize_data(json.loads(text))
    except (ValueError, TypeError) as err:
        if not BACKUP_FILE.exists() or BACKUP_FILE.read_text(encoding='utf-8') != text:
            write_backup(text)
        warn_once(f'저장된 데이터가 손상되어 빈 상태로 시작합니다. 원본은 {BACKUP_FILE.name}에 보관했습니다. ({err})')
        return empty_data()


def save_data(data: dict) -> None:
    """임시 파일에 쓴 뒤 바꿔치기 — 쓰는 도중 꺼져도 기존 파일이 깨지지 않게"""
    try:
        tmp = DATA_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, DATA_FILE)
    except OSError as err:
        warn_once(f'저장하지 못했어요. 설정 화면에서 데이터를 내보내 두세요. ({err})')


def write_backup(text: str) -> None:
    try:
        BACKUP_FILE.write_text(text, encoding='utf-8')
    except OSError:
        pass


def warn_once(message: str) -> None:
    warned = st.session_state.setdefault('warned', set())
    if message not in warned:
        warned.add(message)
        queue_toast(message)


def mutate(fn) -> dict:
    """영속 변경은 항상 여기로: 파일에서 최신 데이터를 읽어 → 바꾸고 → 바로 저장"""
    data = load_data()
    fn(data)
    save_data(data)
    return data


def next_order(data: dict) -> int:
    """새 운동은 맨 뒤 — 한꺼번에 여러 개를 만들어도 겹치지 않게"""
    last = max((w['order'] for w in data['workouts']), default=0)
    stamp = int(time.time() * 1000)
    order = max(stamp, last + 1, st.session_state.get('last_order', 0) + 1)
    st.session_state['last_order'] = order
    return order


def create_workout(data, *, date_key, category, name, weight=0, reps=10, sets=3, memo='') -> dict:
    now = now_iso()
    return {
        'id': str(uuid.uuid4()),
        'date': date_key,
        'category': category,
        'name': name.strip(),
        'weight': num(weight) if CAT[category]['has_weight'] else None,
        'reps': reps,
        'sets': sets,
        'completedSets': 0,
        'done': False,
        'memo': memo.strip(),
        'order': next_order(data),
        'setLogs': [None] * sets,
        'createdAt': now,
        'updatedAt': now,
    }


def find_workout(data, workout_id):
    return next((w for w in data['workouts'] if w['id'] == workout_id), None)


# 운동 상태 변경 규칙 — done == (completedSets == sets)를 항상 유지
def set_completed(w, n):
    w['completedSets'] = clamp(n, 0, w['sets'])
    w['done'] = w['completedSets'] == w['sets']


def toggle_chip(w, n):
    set_completed(w, n - 1 if w['completedSets'] == n else n)


def set_done(w, done: bool):
    set_completed(w, w['sets'] if done else 0)


def sync_set_logs(w, exercise_changed=False):
    logs = [] if exercise_changed else (w.get('setLogs') or [])
    w['setLogs'] = [logs[i] if i < len(logs) else None for i in range(w['sets'])]


def touch(w):
    w['updatedAt'] = now_iso()


# =========================================================
# 가져오기 검증 — 하나라도 잘못되면 전체 거부 (엄격)
# =========================================================
def in_range(n, limits) -> bool:
    return is_number(n) and limits[0] <= n <= limits[1]


def is_valid_plan_fields(w: dict) -> bool:
    category = CAT.get(w.get('category'))
    if not category:
        return False
    name = w.get('name')
    if not isinstance(name, str) or not name.strip() or len(name) > LIMITS['name']:
        return False
    if category['has_weight']:
        if not in_range(w.get('weight'), LIMITS['weight']) or not float(w['weight'] * 2).is_integer():
            return False
    elif w.get('weight') is not None:
        return False
    unit = unit_of(w['category'], migrate_name(w['category'], name))
    return (is_int(w.get('reps')) and in_range(w['reps'], REPS_LIMITS[unit])
            and is_int(w.get('sets')) and in_range(w['sets'], LIMITS['sets'])
            and isinstance(w.get('memo'), str) and len(w['memo']) <= LIMITS['memo'])


def is_valid_set_logs(w: dict) -> bool:
    if 'setLogs' not in w:
        return True
    logs = w['setLogs']
    if not isinstance(logs, list) or len(logs) != w['sets']:
        return False
    has_weight = CAT[w['category']]['has_weight']
    limits = REPS_LIMITS[unit_of(w['category'], migrate_name(w['category'], w['name']))]
    for log in logs:
        if log is None:
            continue
        if not isinstance(log, dict) or not is_int(log.get('reps')) or not in_range(log['reps'], limits):
            return False
        if has_weight:
            if not in_range(log.get('weight'), LIMITS['weight']) or not float(log['weight'] * 2).is_integer():
                return False
        elif log.get('weight') is not None:
            return False
    return True


def is_valid_stored_workout(w) -> bool:
    return (isinstance(w, dict)
            and isinstance(w.get('id'), str) and w['id'] != ''
            and is_valid_date_key(w.get('date'))
            and is_valid_plan_fields(w)
            and is_int(w.get('completedSets')) and 0 <= w['completedSets'] <= w['sets']
            and w.get('done') == (w['completedSets'] == w['sets'])
            and ('order' not in w or is_number(w['order']))
            and is_valid_set_logs(w)
            and isinstance(w.get('createdAt'), str) and isinstance(w.get('updatedAt'), str))


def is_valid_stored_routine(r) -> bool:
    return (isinstance(r, dict)
            and isinstance(r.get('id'), str) and r['id'] != ''
            and isinstance(r.get('name'), str) and r['name'].strip() != '' and len(r['name']) <= ROUTINE_LIMITS['name']
            and isinstance(r.get('items'), list) and 1 <= len(r['items']) <= ROUTINE_LIMITS['items']
            and all(isinstance(i, dict) and is_valid_plan_fields(i) for i in r['items'])
            and ('weekdays' not in r or (isinstance(r['weekdays'], list) and all(is_int(d) and 0 <= d <= 6 for d in r['weekdays'])))
            and isinstance(r.get('createdAt'), str) and isinstance(r.get('updatedAt'), str))


def is_valid_settings(s) -> bool:
    return (isinstance(s, dict)
            and ('restSeconds' not in s or (is_int(s['restSeconds']) and s['restSeconds'] in REST_OPTIONS))
            and ('restSound' not in s or isinstance(s['restSound'], bool))
            and ('weeklyGoal' not in s or (is_int(s['weeklyGoal']) and 1 <= s['weeklyGoal'] <= 7)))


def validate_import(raw):
    """오류 메시지 또는 None"""
    if not isinstance(raw, dict):
        return '올바른 백업 파일이 아닙니다.'
    if raw.get('version') != DATA_VERSION:
        return f"지원하지 않는 데이터 버전입니다. (version: {raw.get('version')})"
    if not isinstance(raw.get('workouts'), list):
        return '운동 목록(workouts)이 없거나 형식이 잘못되었습니다.'
    ids = set()
    for i, w in enumerate(raw['workouts']):
        if not is_valid_stored_workout(w) or w['id'] in ids:
            return f'{i + 1}번째 운동 데이터가 올바르지 않습니다.'
        ids.add(w['id'])
    if 'customExercises' in raw:
        ce = raw['customExercises']
        if not isinstance(ce, dict) or not all(k in CAT and isinstance(v, list) and all(isinstance(n, str) for n in v) for k, v in ce.items()):
            return '직접 입력 운동 목록(customExercises) 형식이 잘못되었습니다.'
    if 'routines' in raw:
        if not isinstance(raw['routines'], list):
            return '루틴 목록(routines) 형식이 잘못되었습니다.'
        rids = set()
        for i, r in enumerate(raw['routines']):
            if not is_valid_stored_routine(r) or r['id'] in rids:
                return f'{i + 1}번째 루틴 데이터가 올바르지 않습니다.'
            rids.add(r['id'])
    if 'settings' in raw and not is_valid_settings(raw['settings']):
        return '설정(settings) 형식이 잘못되었습니다.'
    return None


# =========================================================
# 조회·계산 (순수 함수)
# =========================================================
def workouts_on(data, key):
    return [w for w in data['workouts'] if w['date'] == key]


def sort_by_order(workouts):
    return sorted(workouts, key=lambda w: (w['order'], w['createdAt']))


def sort_workouts(workouts):
    """미완료 위, 완료 아래. 같은 그룹 안에서는 사용자가 정한 순서"""
    return sorted(sort_by_order(workouts), key=lambda w: w['done'])


def calc_progress(workouts):
    total = sum(w['sets'] for w in workouts)
    done = sum(w['completedSets'] for w in workouts)
    return {
        'total_workouts': len(workouts),
        'done_workouts': sum(1 for w in workouts if w['done']),
        'total_sets': total,
        'done_sets': done,
        'percent': 0 if total == 0 else round(done / total * 100),
    }


def exercise_options(data, category):
    defaults = CAT[category]['exercises']
    custom = [n for n in data['customExercises'].get(category, []) if n not in defaults]
    return defaults + custom


def find_last_record(data, category, name, on_or_before):
    """같은 운동의 가장 최근 기록 — 선택한 날짜 이후(미래 계획)는 제외"""
    best = None
    for w in data['workouts']:
        if w['category'] != category or w['name'] != name or w['date'] > on_or_before:
            continue
        if not best or (w['date'], w['updatedAt']) > (best['date'], best['updatedAt']):
            best = w
    return best


def find_previous_date(data, key):
    dates = [w['date'] for w in data['workouts'] if w['date'] < key]
    return max(dates) if dates else None


def set_value(w, i):
    logs = w.get('setLogs') or []
    return (logs[i] if i < len(logs) else None) or {'weight': w['weight'], 'reps': w['reps']}


def completed_values(w):
    return [set_value(w, i) for i in range(w['completedSets'])]


def has_overrides(w):
    return any(w.get('setLogs') or [])


def fmt_set(category, name, v):
    unit = UNIT_LABEL[unit_of(category, name)]
    return f"{fmt_num(v['weight'])}kg × {v['reps']}{unit}" if v.get('weight') else f"{v['reps']}{unit}"


def fmt_summary(w):
    unit_key = unit_of(w['category'], w['name'])
    unit = UNIT_LABEL[unit_key]
    if unit_key == 'min':
        return f"{w['reps']}{unit} × {w['sets']}세트" if w['sets'] > 1 else f"{w['reps']}{unit}"
    parts = [f"{fmt_num(w['weight'])}kg"] if w.get('weight') else []
    parts += [f"{w['reps']}{unit}", f"{w['sets']}세트"]
    return ' × '.join(parts)


def estimate_1rm(weight, reps):
    """Epley 공식, 0.5kg 단위. 12회 이하 + 무게가 있을 때만"""
    if not weight or reps < 1 or reps > E1RM_MAX_REPS:
        return None
    value = weight if reps == 1 else weight * (1 + reps / 30)
    return num(round(value * 2) / 2)


def is_better(a, b) -> bool:
    """무게 우선, 같으면 횟수(시간)"""
    if b is None:
        return True
    aw, bw = a.get('weight') or 0, b.get('weight') or 0
    return aw > bw or (aw == bw and a['reps'] > b['reps'])


def best_set(w):
    best = None
    for v in completed_values(w):
        if is_better(v, best):
            best = v
    return best


def volume_of(w):
    if unit_of(w['category'], w['name']) != 'reps':
        return 0
    return sum((v.get('weight') or 0) * v['reps'] for v in completed_values(w))


def best_1rm(w):
    if unit_of(w['category'], w['name']) != 'reps':
        return None
    values = [e for e in (estimate_1rm(v.get('weight'), v['reps']) for v in completed_values(w)) if e is not None]
    return max(values) if values else None


def exercise_workouts(data, category, name):
    return [w for w in data['workouts'] if w['category'] == category and w['name'] == name]


def personal_record(data, category, name, exclude_id=None, on_or_before=None):
    best, e1rm = None, None
    for w in exercise_workouts(data, category, name):
        if w['id'] == exclude_id or (on_or_before and w['date'] > on_or_before):
            continue
        s = best_set(w)
        if s and (best is None or is_better(s, best['set'])):
            best = {'set': s, 'date': w['date']}
        e = best_1rm(w)
        if e is not None and (e1rm is None or e > e1rm):
            e1rm = e
    if best:
        best['e1rm'] = e1rm
    return best


def is_new_record(data, w) -> bool:
    """그날까지의 다른 기록보다 좋은 세트를 했는가 (첫 기록은 신기록으로 보지 않는다)"""
    mine = best_set(w)
    if not mine:
        return False
    prev = personal_record(data, w['category'], w['name'], exclude_id=w['id'], on_or_before=w['date'])
    return prev is not None and is_better(mine, prev['set'])


def workout_days(data) -> set:
    return {w['date'] for w in data['workouts'] if w['completedSets'] > 0}


def calc_streaks(data, today=None):
    today = today or today_key()
    days = workout_days(data)
    goal = data['settings']['weeklyGoal']
    day_streak = 0
    d = today if today in days else add_days(today, -1)
    while d in days:
        day_streak += 1
        d = add_days(d, -1)

    def count_week(start):
        return sum(1 for i in range(7) if add_days(start, i) in days)

    this_week = week_start(today)
    week_count = count_week(this_week)
    goal_streak = 1 if week_count >= goal else 0
    oldest = min(days, default=today)
    w = add_days(this_week, -7)
    while w >= week_start(oldest):
        if count_week(w) < goal:
            break
        goal_streak += 1
        w = add_days(w, -7)
    return {'day_streak': day_streak, 'week_count': week_count, 'week_goal': goal, 'goal_streak': goal_streak}


def period_stats(data, start, end):
    days = set()
    cat_sets = {c['key']: 0 for c in CATEGORIES}
    done_sets = volume = cardio = done_workouts = 0
    for w in data['workouts']:
        if w['date'] < start or w['date'] > end or w['completedSets'] == 0:
            continue
        days.add(w['date'])
        done_sets += w['completedSets']
        cat_sets[w['category']] += w['completedSets']
        volume += volume_of(w)
        done_workouts += w['done']
        if unit_of(w['category'], w['name']) == 'min':
            cardio += sum(v['reps'] for v in completed_values(w))
    return {'days': len(days), 'done_sets': done_sets, 'done_workouts': done_workouts,
            'volume': round(volume), 'cardio': cardio, 'cat_sets': cat_sets}


def period_range(kind, anchor):
    if kind == 'week':
        start = week_start(anchor)
        return start, add_days(start, 6)
    month = anchor[:7]
    return f'{month}-01', month_end(month)


def shift_period(kind, anchor, n):
    return add_days(anchor, n * 7) if kind == 'week' else f'{add_months(anchor[:7], n)}-01'


def fmt_period(kind, anchor):
    if kind == 'month':
        return fmt_month_title(anchor[:7])
    start, end = period_range('week', anchor)
    return f'{fmt_month_day(start)} ~ {fmt_month_day(end)}'


def fmt_rest(seconds):
    if seconds == 0:
        return '끄기'
    m, s = divmod(seconds, 60)
    return ' '.join(p for p in (f'{m}분' if m else '', f'{s}초' if s else '') if p)


def fmt_weekdays(days):
    return '·'.join(WEEKDAY_NAMES[d] for d in WEEKDAY_ORDER if d in days)


# =========================================================
# 화면 상태 — 보기·날짜는 주소(query params)에 두어 새로고침·뒤로 가기에도 유지
# =========================================================
VIEWS = {'calendar': '달력', 'day': '그날 운동', 'routines': '루틴', 'stats': '통계', 'settings': '설정·백업'}
VIEW_ICONS = {'calendar': ':material/calendar_month:', 'day': ':material/fitness_center:', 'routines': ':material/list:',
              'stats': ':material/bar_chart:', 'settings': ':material/settings:'}


def current_view():
    view = st.query_params.get('view', 'calendar')
    return view if view in VIEWS else 'calendar'


def selected_date():
    key = st.query_params.get('date', '')
    return key if is_valid_date_key(key) else today_key()


def go(view, date_key=None, **extra):
    """보기 전환 (콜백에서 부른다)"""
    params = {'view': view, 'date': date_key or selected_date()}
    params.update(extra)
    st.query_params.from_dict(params)
    st.session_state['nav'] = view
    if view == 'day':
        st.session_state['filter'] = 'all'
        st.session_state['reordering'] = False


def queue_toast(message, icon=None):
    st.session_state.setdefault('toasts', []).append((message, icon))


def flush_toasts():
    for message, icon in st.session_state.pop('toasts', []):
        st.toast(message, icon=icon)


def set_undo(label, action):
    st.session_state['undo'] = {'label': label, 'action': action, 'at': time.time()}


def run_undo():
    undo = st.session_state.pop('undo', None)
    if not undo:
        return
    kind, *args = undo['action']

    def apply(data):
        if kind == 'restore':  # 삭제 취소: 원래 위치로
            workout, index = args
            data['workouts'].insert(min(index, len(data['workouts'])), workout)
        elif kind == 'remove':  # 추가 취소
            ids = set(args[0])
            data['workouts'] = [w for w in data['workouts'] if w['id'] not in ids]
        elif kind == 'move':  # 이동 취소
            wid, original = args
            w = find_workout(data, wid)
            if w:
                w.update(original)
    mutate(apply)


def open_dialog(kind, **params):
    st.session_state['open_dialog'] = (kind, params)


# =========================================================
# 콜백 — 운동
# =========================================================
def on_chip(workout_id, n):
    data = load_data()
    w = find_workout(data, workout_id)
    if not w:
        return
    before = w['completedSets']
    was_record = is_new_record(data, w)
    toggle_chip(w, n)
    touch(w)
    save_data(data)
    if w['completedSets'] > before:
        announce_record(data, w, was_record)
        seconds = data['settings']['restSeconds']
        if seconds:
            st.session_state['rest_end'] = time.time() + seconds


def on_toggle_done(workout_id, key):
    checked = st.session_state[key]
    data = load_data()
    w = find_workout(data, workout_id)
    if not w:
        return
    was_record = is_new_record(data, w)
    set_done(w, checked)
    touch(w)
    save_data(data)
    if checked:
        announce_record(data, w, was_record)


def announce_record(data, w, was_record):
    if not was_record and is_new_record(data, w):
        queue_toast(f"{w['name']} 신기록! {fmt_set(w['category'], w['name'], best_set(w))}", ':material/trophy:')


def on_weight(workout_id, delta):
    def apply(data):
        w = find_workout(data, workout_id)
        if w:
            w['weight'] = num(clamp(round(((w['weight'] or 0) + delta) * 2) / 2, *LIMITS['weight']))
            touch(w)
    mutate(apply)


def on_delete(workout_id):
    close_popover(workout_id)
    data = load_data()
    index = next((i for i, w in enumerate(data['workouts']) if w['id'] == workout_id), -1)
    if index < 0:
        return
    removed = data['workouts'].pop(index)
    save_data(data)
    set_undo(f"{removed['name']} 삭제됨", ('restore', removed, index))


def on_move_order(workout_id, delta, filter_key):
    data = load_data()
    visible = sort_by_order([w for w in workouts_on(data, selected_date()) if filter_key == 'all' or w['category'] == filter_key])
    i = next((k for k, w in enumerate(visible) if w['id'] == workout_id), -1)
    j = i + delta
    if i < 0 or not 0 <= j < len(visible):
        return
    a, b = visible[i], visible[j]
    if a['order'] == b['order']:
        a['order'], b['order'] = b['order'] + delta, a['order']
    else:
        a['order'], b['order'] = b['order'], a['order']
    save_data(data)


def on_copy_to(workout_id, key):
    close_popover(workout_id)
    target = st.session_state[key].isoformat()
    data = load_data()
    w = find_workout(data, workout_id)
    if not w:
        return
    if target == w['date']:
        queue_toast('지금 날짜와 다른 날을 선택해주세요', ':material/error:')
        return
    copy = create_workout(data, date_key=target, category=w['category'], name=w['name'], weight=w['weight'] or 0,
                          reps=w['reps'], sets=w['sets'], memo=w['memo'])
    copy['setLogs'] = list(w['setLogs'])
    data['workouts'].append(copy)
    save_data(data)
    set_undo(f"{fmt_date_short(target)}에 {w['name']} 복사됨", ('remove', [copy['id']]))


def on_move_to(workout_id, key):
    close_popover(workout_id)
    target = st.session_state[key].isoformat()
    data = load_data()
    w = find_workout(data, workout_id)
    if not w:
        return
    if target == w['date']:
        queue_toast('지금 날짜와 다른 날을 선택해주세요', ':material/error:')
        return
    original = {'date': w['date'], 'order': w['order']}
    w['date'] = target
    w['order'] = next_order(data)
    touch(w)
    save_data(data)
    set_undo(f"{w['name']} → {fmt_date_short(target)}로 옮김", ('move', w['id'], original))


def on_copy_previous():
    target = selected_date()
    data = load_data()
    source_date = find_previous_date(data, target)
    if not source_date:
        return
    created = []
    for w in sort_by_order(workouts_on(data, source_date)):
        nw = create_workout(data, date_key=target, category=w['category'], name=w['name'], weight=w['weight'] or 0,
                            reps=w['reps'], sets=w['sets'], memo=w['memo'])
        data['workouts'].append(nw)
        created.append(nw['id'])
    save_data(data)
    set_undo(f'{fmt_month_day(source_date)} 운동 {len(created)}개 불러옴', ('remove', created))


def on_apply_routine(routine_id):
    data = load_data()
    routine = next((r for r in data['routines'] if r['id'] == routine_id), None)
    if not routine:
        return
    target = selected_date()
    created = [create_workout(data, date_key=target, **item_kwargs(item)) for item in routine['items']]
    data['workouts'].extend(created)
    save_data(data)
    go('day', target)
    set_undo(f"{routine['name']} {len(created)}개 추가됨", ('remove', [w['id'] for w in created]))


def item_kwargs(item):
    return {'category': item['category'], 'name': item['name'], 'weight': item['weight'] or 0,
            'reps': item['reps'], 'sets': item['sets'], 'memo': item['memo']}


def remember_custom(data, category, name):
    if name not in exercise_options(data, category):
        data['customExercises'].setdefault(category, []).append(name)


# =========================================================
# 운동 추가/수정 폼 (대화상자) — 날짜의 운동과 루틴 항목이 함께 쓴다
# ctx: {'mode': 'add' | 'edit' | 'item', 'id': 운동 id, 'index': 루틴 항목 번호(None이면 새 항목)}
# =========================================================
def open_form(ctx):
    data = load_data()
    ss = st.session_state
    ss['form_ctx'] = ctx
    ss['f_edited'] = False
    source = None
    if ctx['mode'] == 'edit':
        source = find_workout(data, ctx['id'])
    elif ctx['mode'] == 'item' and ctx.get('index') is not None:
        source = ss['routine_draft']['items'][ctx['index']]
    ss['f_editing'] = source is not None
    if source:
        category = source['category']
        ss['f_cat'] = category
        options = exercise_options(data, category)
        if source['name'] in options:
            ss['f_ex'], ss['f_custom'] = source['name'], ''
        else:
            ss['f_ex'], ss['f_custom'] = CUSTOM_OPTION, source['name']
        ss['f_weight'] = float(source['weight'] or 0)
        ss['f_reps'] = source['reps']
        ss['f_sets'] = source['sets']
        ss['f_memo'] = source.get('memo', '')
        ss['f_hint'] = ''
    else:
        flt = ss.get('filter', 'all')
        category = flt if flt in CAT and ctx['mode'] == 'add' else CATEGORIES[0]['key']
        ss['f_cat'] = category
        ss['f_ex'] = exercise_options(data, category)[0]
        ss['f_custom'] = ''
        ss['f_memo'] = ''
        apply_last_record()
    open_dialog('form')


def form_name():
    ss = st.session_state
    return (ss.get('f_custom', '') if ss.get('f_ex') == CUSTOM_OPTION else ss.get('f_ex', '')).strip()


def apply_last_record():
    """추가 모드에서만: 같은 운동의 최근 기록으로 기본값 채우기 (직접 고친 숫자는 덮어쓰지 않는다)"""
    ss = st.session_state
    if ss.get('f_editing'):
        return
    data = load_data()
    category, name = ss['f_cat'], form_name()
    record = find_last_record(data, category, name, selected_date()) if name else None
    if not ss.get('f_edited'):
        unit = unit_of(category, name) if name else CAT[category]['unit']
        src = record or {'weight': DEFAULTS['weight'], 'reps': DEFAULT_REPS[unit], 'sets': DEFAULTS['sets']}
        ss['f_weight'] = float(src['weight'] or 0)
        ss['f_reps'] = src['reps']
        ss['f_sets'] = src['sets']
    if record:
        pr = personal_record(data, category, name, on_or_before=selected_date())
        hint = f"지난 기록: {fmt_summary(record)} ({fmt_month_day(record['date'])})"
        if pr:
            hint += f" · 최고 {fmt_set(category, name, pr['set'])}"
        ss['f_hint'] = hint
    else:
        ss['f_hint'] = ''


def on_form_category():
    data = load_data()
    st.session_state['f_ex'] = exercise_options(data, st.session_state['f_cat'])[0]
    st.session_state['f_custom'] = ''
    apply_last_record()


def on_form_numbers_edited():
    st.session_state['f_edited'] = True


def form_dialog():
    ss = st.session_state
    ctx = ss['form_ctx']
    title = {'add': '운동 추가', 'edit': '운동 수정', 'item': '루틴 운동 수정' if ctx.get('index') is not None else '루틴에 운동 추가'}[ctx['mode']]

    @st.dialog(title, width='medium')
    def body():
        data = load_data()
        st.selectbox('카테고리', [c['key'] for c in CATEGORIES], format_func=lambda k: CAT[k]['name'],
                     key='f_cat', on_change=on_form_category)
        category = CAT[ss['f_cat']]
        options = exercise_options(data, category['key'])
        if ss.get('f_ex') not in options + [CUSTOM_OPTION]:
            ss['f_ex'] = options[0]

        def label(name):
            if name == CUSTOM_OPTION:
                return '직접 입력…'
            group = category['group_of'].get(name, '직접 입력한 운동')
            return f'{name}  ·  {group}'
        st.selectbox('운동명', options + [CUSTOM_OPTION], format_func=label, key='f_ex', on_change=apply_last_record)
        if ss['f_ex'] == CUSTOM_OPTION:
            st.text_input('운동명 직접 입력', key='f_custom', max_chars=LIMITS['name'], on_change=apply_last_record,
                          placeholder='예: 케이블 체스트 플라이')
        if ss.get('f_hint'):
            st.caption(ss['f_hint'])

        name = form_name()
        unit = unit_of(category['key'], name) if name else category['unit']
        lo, hi = REPS_LIMITS[unit]
        ss['f_reps'] = clamp(int(ss.get('f_reps') or lo), lo, hi)  # 단위가 바뀌어 범위를 벗어나면 맞춘다
        cols = st.columns(3 if category['has_weight'] else 2)
        i = 0
        if category['has_weight']:
            cols[0].number_input('무게(kg)', min_value=0.0, max_value=500.0, step=WEIGHT_STEP, format='%g',
                                 key='f_weight', on_change=on_form_numbers_edited)
            i = 1
        cols[i].number_input(REPS_FIELD_LABEL[unit], min_value=lo, max_value=hi, step=1, key='f_reps', on_change=on_form_numbers_edited)
        cols[i + 1].number_input('세트', min_value=1, max_value=20, step=1, key='f_sets', on_change=on_form_numbers_edited)
        st.text_input('메모', key='f_memo', max_chars=LIMITS['memo'], placeholder='선택 (최대 100자)')

        left, right = st.columns([1, 2])
        if left.button('취소', width='stretch'):
            st.rerun()
        if right.button('저장', type='primary', width='stretch'):
            error = None
            weight = float(ss.get('f_weight') or 0)
            if not name:
                error = '운동명을 입력해주세요'
            elif len(name) > LIMITS['name']:
                error = f"{LIMITS['name']}자 이내로 입력해주세요"
            elif category['has_weight'] and not float(weight * 2).is_integer():
                error = '무게는 0.5 단위로 입력해주세요'
            if error:
                st.error(error)
                return
            values = {'category': category['key'], 'name': name,
                      'weight': num(weight) if category['has_weight'] else None,
                      'reps': int(ss['f_reps']), 'sets': int(ss['f_sets']), 'memo': ss.get('f_memo', '').strip()}
            save_form(ctx, values)
            st.rerun()

    body()


def save_form(ctx, values):
    if ctx['mode'] == 'item':
        mutate(lambda d: remember_custom(d, values['category'], values['name']))
        draft = st.session_state['routine_draft']
        item = to_routine_item(values)
        if ctx.get('index') is None:
            draft['items'].append(item)
        else:
            draft['items'][ctx['index']] = item
        return

    def apply(data):
        remember_custom(data, values['category'], values['name'])
        if ctx['mode'] == 'edit':
            w = find_workout(data, ctx['id'])
            if not w:
                return  # 수정 중 삭제된 경우
            changed = w['category'] != values['category'] or w['name'] != values['name']
            w.update(values)
            sync_set_logs(w, changed)
            set_completed(w, w['completedSets'])  # 세트 수가 줄었을 때 보정 + done 재계산
            touch(w)
        else:
            data['workouts'].append(create_workout(data, date_key=selected_date(), **{
                **values, 'weight': values['weight'] or 0}))
    mutate(apply)


# =========================================================
# 세트별 기록 / 운동 기록 대화상자
# =========================================================
def setlog_dialog(workout_id):
    @st.dialog('세트별 기록', width='medium')
    def body():
        data = load_data()
        w = find_workout(data, workout_id)
        if not w:
            st.warning('운동을 찾을 수 없어요.')
            return
        has_weight = CAT[w['category']]['has_weight']
        unit = unit_of(w['category'], w['name'])
        lo, hi = REPS_LIMITS[unit]
        st.caption(f"{w['name']} · 계획 {fmt_summary(w)}")
        st.caption('비워 두면 계획한 값으로 기록돼요. 피라미드 세트나 실제로 한 횟수를 적어 두세요.')
        with st.form(f'setlog-{workout_id}', border=False):
            entries = []
            for i in range(w['sets']):
                log = w['setLogs'][i]
                done = i < w['completedSets']
                cols = st.columns([1, 2, 2] if has_weight else [1, 3], vertical_alignment='bottom')
                cols[0].markdown(f"**{i + 1}세트**" + ('  \n:green[완료]' if done else ''))
                wv = None
                if has_weight:
                    wv = cols[1].number_input('무게(kg)', min_value=0.0, max_value=500.0, step=WEIGHT_STEP, format='%g',
                                              value=float(log['weight']) if log else None,
                                              placeholder=fmt_num(w['weight'] or 0), key=f'sl-w-{workout_id}-{i}')
                rv = cols[-1].number_input(REPS_FIELD_LABEL[unit], min_value=lo, max_value=hi, step=1,
                                           value=log['reps'] if log else None, placeholder=str(w['reps']),
                                           key=f'sl-r-{workout_id}-{i}')
                entries.append((wv, rv))
            c1, c2 = st.columns(2)
            reset = c1.form_submit_button('모두 계획대로', width='stretch')
            submit = c2.form_submit_button('저장', type='primary', width='stretch')
        if reset or submit:
            logs = []
            for wv, rv in entries:
                if reset or (wv is None and rv is None):
                    logs.append(None)
                    continue
                if wv is not None and not float(wv * 2).is_integer():
                    st.error('무게는 0.5 단위로 입력해주세요')
                    return
                weight = num(wv if wv is not None else (w['weight'] or 0)) if has_weight else None
                reps = int(rv) if rv is not None else w['reps']
                logs.append(None if (weight == w['weight'] and reps == w['reps']) else {'weight': weight, 'reps': reps})
            fresh = load_data()
            target = find_workout(fresh, workout_id)
            if target:
                was_record = is_new_record(fresh, target)
                target['setLogs'] = logs
                touch(target)
                save_data(fresh)
                announce_record(fresh, target, was_record)
            st.rerun()

    body()


def history_dialog(workout_id):
    data = load_data()
    w0 = find_workout(data, workout_id)
    title = w0['name'] if w0 else '운동 기록'

    @st.dialog(title, width='large')
    def body():
        data = load_data()
        w = find_workout(data, workout_id)
        if not w:
            st.warning('운동을 찾을 수 없어요.')
            return
        cat, name = w['category'], w['name']
        records = sorted((x for x in exercise_workouts(data, cat, name) if x['completedSets'] > 0),
                         key=lambda x: (x['date'], x['order']), reverse=True)
        pr = personal_record(data, cat, name)
        cols = st.columns(3)
        cols[0].metric('최고 기록', fmt_set(cat, name, pr['set']) if pr else '-')
        if unit_of(cat, name) == 'reps' and CAT[cat]['has_weight']:
            cols[1].metric('추정 1RM', f"{fmt_num(pr['e1rm'])}kg" if pr and pr['e1rm'] else '-')
        cols[2].metric('기록한 날', f"{len({r['date'] for r in records})}일")
        if not records:
            st.info('아직 완료한 세트가 없어요. 세트를 체크하면 여기에 기록이 쌓여요.')
            return

        # 날짜별 최고 세트 추이 (선 하나 — 범례 없이 제목이 계열을 말한다)
        by_date = {}
        for r in records:
            b = best_set(r)
            if b and (r['date'] not in by_date or is_better(b, by_date[r['date']])):
                by_date[r['date']] = b
        points = sorted(by_date.items())[-20:]
        if len(points) >= 2:
            use_weight = any(v.get('weight') for _, v in points)
            unit = 'kg' if use_weight else UNIT_LABEL[unit_of(cat, name)]
            df = pd.DataFrame({
                '날짜': [pd.Timestamp(d) for d, _ in points],
                '값': [(v.get('weight') or 0) if use_weight else v['reps'] for _, v in points],
                '기록': [fmt_set(cat, name, v) for _, v in points],
            })
            st.markdown(f"**날짜별 최고 {'무게' if use_weight else '기록'} ({unit})**")
            base = alt.Chart(df).encode(
                x=alt.X('날짜:T', title=None, axis=alt.Axis(format='%m/%d', grid=False)),
                y=alt.Y('값:Q', title=None, scale=alt.Scale(zero=False)),
                tooltip=[alt.Tooltip('날짜:T', format='%Y-%m-%d'), '기록:N'],
            )
            chart = base.mark_line(strokeWidth=2) + base.mark_point(filled=True, size=64)
            st.altair_chart(chart.properties(height=200), width='stretch')

        st.markdown(f'**날짜별 기록 (최근 {min(len(records), HISTORY_LIMIT)}회)** — 누르면 그날로 이동')
        for r in records[:HISTORY_LIMIT]:
            best = best_set(r)
            meta = [f"{r['completedSets']}/{r['sets']}세트"]
            if volume_of(r):
                meta.append(f'볼륨 {fmt_num(round(volume_of(r)))}kg')
            if best_1rm(r):
                meta.append(f'1RM {fmt_num(best_1rm(r))}kg')
            is_pr = pr and best and pr['date'] == r['date'] and not is_better(pr['set'], best)
            sets = ' · '.join(fmt_set(cat, name, v) for v in completed_values(r))
            # 버튼 글자는 줄바꿈을 지원하지 않아 한 줄로
            label = f"**{fmt_date_short(r['date'])}** {esc(sets)} :gray[({esc(' · '.join(meta))})]" + (' :green[**최고**]' if is_pr else '')
            if st.button(label, key=f"hist-{r['id']}", width='stretch'):
                go('day', r['date'])
                st.rerun()

    body()


# =========================================================
# 휴식 타이머 — 끝나는 시각(rest_end) 기준이라 화면을 다시 그려도 남은 시간이 맞다
# =========================================================
def beep_wav() -> bytes:
    rate, buf = 22050, io.BytesIO()
    frames = bytearray()
    for k in range(3):
        for i in range(int(rate * 0.2)):
            env = min(1.0, i / 200, (rate * 0.2 - i) / 400)
            frames += struct.pack('<h', int(12000 * env * math.sin(2 * math.pi * 880 * i / rate)))
        frames += b'\x00\x00' * int(rate * 0.1)
    with wave.open(buf, 'wb') as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(bytes(frames))
    return buf.getvalue()


@st.fragment(run_every=1)
def rest_timer():
    ss = st.session_state
    end = ss.get('rest_end')
    if not end:
        return
    left = math.ceil(end - time.time())
    if left <= 0:
        ss['rest_end'] = None
        ss['rest_finished'] = True
        queue_toast('휴식 끝! 다음 세트를 시작하세요.', ':material/timer:')
        st.rerun()
    with st.container(border=True, horizontal=True, vertical_alignment='center'):
        st.markdown(f':material/timer: 휴식 **{left // 60}:{left % 60:02d}**')
        if st.button('−15', key='rest-minus', help='15초 줄이기'):
            ss['rest_end'] = max(time.time() + 1, end - REST_ADJUST)
            st.rerun(scope='fragment')
        if st.button('+15', key='rest-plus', help='15초 늘리기'):
            ss['rest_end'] = end + REST_ADJUST
            st.rerun(scope='fragment')
        if st.button('건너뛰기', key='rest-skip', type='tertiary'):
            ss['rest_end'] = None
            st.rerun()


# =========================================================
# 화면: 달력
# =========================================================
CALENDAR_CSS = """
<style>
.cal { width: 100%; border-collapse: separate; border-spacing: 2px; table-layout: fixed; }
.cal th { font-size: .75rem; font-weight: 700; opacity: .7; padding: 4px 0; text-align: center; }
.cal th.sun, .cal td.sun .n { color: #DC2626; }
.cal th.sat, .cal td.sat .n { color: #2563EB; }
.cal td { padding: 0; text-align: center; }
.cal a { display: grid; gap: 3px; justify-items: center; align-content: center; min-height: 54px; padding: 4px 0;
         border-radius: 8px; text-decoration: none !important; color: inherit !important; }
.cal a:hover { background: rgba(127,127,127,.12); }
.cal .n { display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; font-weight: 600; }
.cal td.out a { opacity: .35; }
.cal td.today .n { background: currentColor; }
.cal td.today .n span { color: white; mix-blend-mode: normal; }
.cal td.sel a { box-shadow: inset 0 0 0 2px #2563EB; }
.cal td.done a { background: rgba(34,197,94,.18); }
.cal .dots { display: flex; gap: 3px; height: 6px; }
.cal .dot { width: 6px; height: 6px; border-radius: 50%; }
.cal .bar { width: 70%; height: 4px; border-radius: 99px; background: rgba(127,127,127,.25); overflow: hidden; }
.cal .bar i { display: block; height: 100%; background: #2563EB; }
.cal td.done .bar i { background: #16A34A; }
</style>
"""


def render_calendar(data):
    ss = st.session_state
    month = st.query_params.get('month', '')
    if not re.fullmatch(r'\d{4}-\d{2}', month):
        month = selected_date()[:7]
    this_month = today_key()[:7]

    def set_month(m):
        st.query_params['month'] = m

    with st.container(horizontal=True, vertical_alignment='center'):
        st.button('', icon=':material/chevron_left:', key='cal-prev', on_click=set_month, args=(add_months(month, -1),), help='이전 달')
        st.subheader(fmt_month_title(month), anchor=False)
        st.button('', icon=':material/chevron_right:', key='cal-next', on_click=set_month, args=(add_months(month, 1),), help='다음 달')
        if month != this_month:
            st.button('이번 달', key='cal-today', type='tertiary', on_click=set_month, args=(this_month,))

    first = f'{month}-01'
    start = add_days(first, -js_weekday(first))
    days_in_month = parse_key(month_end(month)).day
    weeks = math.ceil((js_weekday(first) + days_in_month) / 7)
    end = add_days(start, weeks * 7 - 1)
    summary = {}
    for w in data['workouts']:
        if start <= w['date'] <= end:
            s = summary.setdefault(w['date'], {'total': 0, 'done': 0, 'sets': 0, 'done_sets': 0, 'cats': set()})
            s['total'] += 1
            s['done'] += w['done']
            s['sets'] += w['sets']
            s['done_sets'] += w['completedSets']
            s['cats'].add(w['category'])

    today, sel = today_key(), selected_date()
    head = ''.join(f'<th class="{"sun" if i == 0 else "sat" if i == 6 else ""}">{d}</th>' for i, d in enumerate(WEEKDAY_NAMES))
    rows = []
    for wk in range(weeks):
        cells = []
        for i in range(7):
            key = add_days(start, wk * 7 + i)
            s = summary.get(key)
            classes = ['sun' if i == 0 else 'sat' if i == 6 else '']
            if not key.startswith(month):
                classes.append('out')
            if key == today:
                classes.append('today')
            if key == sel:
                classes.append('sel')
            if s and s['done_sets'] == s['sets']:
                classes.append('done')
            pct = round(s['done_sets'] / s['sets'] * 100) if s else 0
            # 카테고리 색 점 최대 3개 (카테고리 순서대로)
            dot_colors = [c['color'] for c in CATEGORIES if s and c['key'] in s['cats']][:3]
            dots = ''.join(f'<span class="dot" style="background:{color}"></span>' for color in dot_colors)
            label = f"{fmt_date_long(key)}{', 오늘' if key == today else ''}, " + (f"운동 {s['total']}개 중 {s['done']}개 완료" if s else '운동 없음')
            bar = f'<span class="bar"><i style="width:{pct}%"></i></span>' if s else ''
            cells.append(f'<td class="{" ".join(c for c in classes if c)}"><a href="?view=day&date={key}" target="_self" aria-label="{label}">'
                         f'<span class="n"><span>{parse_key(key).day}</span></span><span class="dots">{dots}</span>{bar}</a></td>')
        rows.append(f'<tr>{"".join(cells)}</tr>')
    st.markdown(CALENDAR_CSS + f'<table class="cal" role="grid"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>',
                unsafe_allow_html=True)

    month_days = {k: v for k, v in summary.items() if k.startswith(month)}
    c1, c2, c3 = st.columns(3)
    c1.metric('운동한 날', f"{sum(1 for v in month_days.values() if v['done_sets'] > 0)}일")
    c2.metric('완료한 운동', f"{sum(v['done'] for v in month_days.values())}개")
    c3.metric('계획한 날', f'{len(month_days)}일')

    streak = calc_streaks(data)
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment='center'):
            st.markdown('**이번 주 목표**')
            st.space('stretch')
            st.markdown(f"### {streak['week_count']} / {streak['week_goal']}일")
        st.progress(min(1.0, streak['week_count'] / streak['week_goal']))
        left = streak['week_goal'] - streak['week_count']
        st.caption(':green[**이번 주 목표를 채웠어요!**]' if left <= 0 else f'목표까지 {left}일 남았어요')
        c1, c2 = st.columns(2)
        c1.metric('연속 운동', f"{streak['day_streak']}일")
        c2.metric('목표 달성 연속', f"{streak['goal_streak']}주")

    with st.container(horizontal=True):
        st.button('오늘 운동', icon=':material/today:', type='primary', on_click=go, args=('day', today_key()))
        st.button('통계 보기', icon=':material/bar_chart:', on_click=go, args=('stats',))
    st.caption('날짜를 누르면 그날 운동을 추가하거나 기록을 볼 수 있어요. 점은 카테고리, 막대는 완료한 세트 비율이에요.')


# =========================================================
# 화면: 그날 운동
# =========================================================
def render_day(data):
    ss = st.session_state
    key = selected_date()
    is_today = key == today_key()

    with st.container(horizontal=True, vertical_alignment='center'):
        st.button('', icon=':material/chevron_left:', key='day-prev', help='이전 날', on_click=go, args=('day', add_days(key, -1)))
        st.subheader(('오늘 · ' if is_today else '') + fmt_date_long(key), anchor=False)
        st.button('', icon=':material/chevron_right:', key='day-next', help='다음 날', on_click=go, args=('day', add_days(key, 1)))
        if not is_today:
            st.button('오늘', key='day-today', type='tertiary', on_click=go, args=('day', today_key()))

    workouts = workouts_on(data, key)
    p = calc_progress(workouts)
    if workouts:
        with st.container(border=True):
            with st.container(horizontal=True, vertical_alignment='bottom'):
                st.markdown(f"## {p['percent']}%")
                st.caption(f"운동 {p['done_workouts']}/{p['total_workouts']} 완료 · 세트 {p['done_sets']}/{p['total_sets']}")
            st.progress(p['percent'] / 100)
            if p['percent'] == 100:
                st.success('오늘 운동 완료!' if is_today else '운동 완료!', icon=':material/celebration:')

    if ss.get('rest_end'):
        rest_timer()
    if ss.pop('rest_finished', False) and data['settings']['restSound']:
        st.audio(beep_wav(), format='audio/wav', autoplay=True)

    undo = ss.get('undo')
    if undo and time.time() - undo['at'] < UNDO_SECONDS:
        with st.container(border=True, horizontal=True, vertical_alignment='center'):
            st.markdown(esc(undo['label']))
            st.button('실행 취소', key='undo-btn', type='primary', on_click=run_undo)

    if not workouts:
        render_empty_day(data, key)
        st.button('운동 추가', icon=':material/add:', type='primary', width='stretch', on_click=open_form, args=({'mode': 'add'},))
        return

    # 카테고리 필터 — 진행률은 필터와 관계없이 전체 기준
    def filter_label(k):
        if k == 'all':
            return '전체'
        items = [w for w in workouts if w['category'] == k]
        return f"{CAT[k]['name']} {sum(w['done'] for w in items)}/{len(items)}" if items else CAT[k]['name']
    if ss.get('filter') not in ['all'] + list(CAT):
        ss['filter'] = 'all'
    st.pills('카테고리', ['all'] + list(CAT), format_func=filter_label, key='filter', required=True, label_visibility='collapsed')
    flt = ss['filter']
    filtered = workouts if flt == 'all' else [w for w in workouts if w['category'] == flt]

    with st.container(horizontal=True, vertical_alignment='center'):
        st.button('운동 추가', icon=':material/add:', type='primary', on_click=open_form, args=({'mode': 'add'},))
        st.button('루틴', icon=':material/list:', on_click=go, args=('routines',))
        st.space('stretch')
        if len(workouts) >= 2:
            st.toggle('순서 변경', key='reordering')

    if not filtered:
        st.info(f"{CAT[flt]['name']} 운동이 없어요")
        return
    if ss.get('reordering'):
        st.caption('화살표로 순서를 바꾸세요. 평소에는 완료한 운동이 아래로 내려가요.')
        ordered = sort_by_order(filtered)
        for i, w in enumerate(ordered):
            with st.container(border=True, horizontal=True, vertical_alignment='center'):
                st.markdown(f"**{i + 1}** &nbsp; " + esc(w['name']))
                st.badge(CAT[w['category']]['name'], color=CAT[w['category']]['badge'])
                st.space('stretch')
                st.button('', icon=':material/arrow_upward:', key=f"up-{w['id']}", disabled=i == 0,
                          help='위로', on_click=on_move_order, args=(w['id'], -1, flt))
                st.button('', icon=':material/arrow_downward:', key=f"down-{w['id']}", disabled=i == len(ordered) - 1,
                          help='아래로', on_click=on_move_order, args=(w['id'], 1, flt))
        return
    for w in sort_workouts(filtered):
        render_card(data, w)


def render_empty_day(data, key):
    st.info('오늘 운동을 추가해보세요' if key == today_key() else '이 날의 운동을 추가해보세요', icon=':material/fitness_center:')
    weekday = js_weekday(key)
    suggested = [r for r in data['routines'] if weekday in r['weekdays']]
    if suggested:
        st.markdown(f'**{WEEKDAY_NAMES[weekday]}요일 루틴**')
        for r in suggested:
            st.button(f"{r['name']} 불러오기 ({len(r['items'])}개)", key=f"sug-{r['id']}", icon=':material/playlist_add:',
                      type='primary', on_click=on_apply_routine, args=(r['id'],))
    with st.container(horizontal=True):
        if data['routines']:
            st.button('루틴 불러오기', icon=':material/list:', on_click=go, args=('routines',))
        if find_previous_date(data, key):
            st.button('지난 루틴 불러오기', icon=':material/history:', on_click=on_copy_previous)


def render_card(data, w):
    category = CAT[w['category']]
    wid = w['id']
    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment='center'):
            title = f"~~{esc(w['name'])}~~" if w['done'] else f"**{esc(w['name'])}**"
            ck = f"done-{wid}-{w['completedSets']}-{w['sets']}"
            st.checkbox(title, value=w['done'], key=ck, on_change=on_toggle_done, args=(wid, ck))
            st.badge(category['name'], color=category['badge'])
            st.space('stretch')
            st.button('', icon=':material/edit:', key=f'edit-{wid}', help='수정', on_click=open_form, args=({'mode': 'edit', 'id': wid},))
            # 열림 상태를 추적해야 메뉴에서 고른 뒤 닫을 수 있다 (닫혀 있으면 내용도 그리지 않는다)
            more = st.popover('', icon=':material/more_horiz:', help='더보기', key=popover_key(wid), on_change='rerun')
            with more:
                if more.open:
                    render_more_menu(w)

        lines = [fmt_summary(w)]
        if has_overrides(w):
            lines.append('세트별 ' + ' · '.join(fmt_set(w['category'], w['name'], set_value(w, i)) for i in range(w['sets'])))
        st.markdown('  \n'.join(esc(x) for x in lines))
        if w['memo']:
            st.caption(esc(w['memo']))
        record = record_line(data, w)
        if record:
            st.markdown(record)

        with st.container(horizontal=True, vertical_alignment='center', gap='small'):
            for i in range(1, w['sets'] + 1):
                st.button(str(i), key=f'chip-{wid}-{i}', type='primary' if i <= w['completedSets'] else 'secondary',
                          help=f'{i}세트 완료', on_click=on_chip, args=(wid, i))
            if category['has_weight']:
                st.space('stretch')
                st.button('', icon=':material/remove:', key=f'wdec-{wid}', help=f'{WEIGHT_STEP}kg 줄이기',
                          disabled=(w['weight'] or 0) <= 0, on_click=on_weight, args=(wid, -WEIGHT_STEP))
                st.markdown(f"**{fmt_num(w['weight'] or 0)}kg**")
                st.button('', icon=':material/add:', key=f'winc-{wid}', help=f'{WEIGHT_STEP}kg 늘리기',
                          disabled=(w['weight'] or 0) >= 500, on_click=on_weight, args=(wid, WEIGHT_STEP))


def record_line(data, w):
    prev = personal_record(data, w['category'], w['name'], exclude_id=w['id'], on_or_before=w['date'])
    new = is_new_record(data, w)
    if not prev and not new:
        return None
    e1rm = max((prev or {}).get('e1rm') or 0, best_1rm(w) or 0)
    text = (f"신기록 {fmt_set(w['category'], w['name'], best_set(w))}" if new
            else f"최고 {fmt_set(w['category'], w['name'], prev['set'])}")
    if e1rm:
        text += f' · 추정 1RM {fmt_num(e1rm)}kg'
    return f":green-background[:material/trophy: **{esc(text)}**]" if new else f":gray[:material/trophy: {esc(text)}]"


def popover_key(workout_id):
    return f'pop-{workout_id}'


def close_popover(workout_id):
    st.session_state[popover_key(workout_id)] = False


def on_menu_dialog(kind, workout_id):
    close_popover(workout_id)
    open_dialog(kind, workout_id=workout_id)


def render_more_menu(w):
    wid = w['id']
    st.button('세트별 무게·횟수 기록', icon=':material/format_list_numbered:', key=f'sl-{wid}', width='stretch',
              on_click=on_menu_dialog, args=('setlog', wid))
    st.button('지난 기록·최고 기록 보기', icon=':material/show_chart:', key=f'hi-{wid}', width='stretch',
              on_click=on_menu_dialog, args=('history', wid))
    st.divider()
    dk = f'mv-{wid}'
    st.date_input('다른 날로 복사·이동', value=parse_key(add_days(w['date'], 1)), key=dk, format='YYYY-MM-DD')
    c1, c2 = st.columns(2)
    c1.button('복사', icon=':material/content_copy:', key=f'cp-{wid}', width='stretch', on_click=on_copy_to, args=(wid, dk))
    c2.button('이동', icon=':material/arrow_forward:', key=f'mvb-{wid}', width='stretch', on_click=on_move_to, args=(wid, dk))
    st.caption('복사는 미완료 상태로 새로 추가하고, 이동은 완료 상태까지 그대로 옮겨요.')
    st.divider()
    st.button('삭제', icon=':material/delete:', key=f'del-{wid}', width='stretch', on_click=on_delete, args=(wid,))


# =========================================================
# 화면: 루틴
# =========================================================
def start_routine_editor(routine=None, items=None):
    st.session_state['routine_draft'] = {
        'id': routine['id'] if routine else None,
        'name': routine['name'] if routine else '',
        'items': [to_routine_item(i) for i in (items if items is not None else (routine['items'] if routine else []))],
        'weekdays': list(routine['weekdays']) if routine else [],
    }
    st.session_state['r_name'] = st.session_state['routine_draft']['name']
    st.session_state['r_weekdays'] = [d for d in WEEKDAY_ORDER if d in st.session_state['routine_draft']['weekdays']]


def on_routine_delete(routine_id):
    mutate(lambda d: d.__setitem__('routines', [r for r in d['routines'] if r['id'] != routine_id]))
    queue_toast('루틴을 삭제했어요. 이미 추가된 운동 기록은 그대로 남아요.')


def on_draft_move(index, delta):
    items = st.session_state['routine_draft']['items']
    j = index + delta
    if 0 <= j < len(items):
        items[index], items[j] = items[j], items[index]


def on_draft_remove(index):
    st.session_state['routine_draft']['items'].pop(index)


def on_routine_save():
    ss = st.session_state
    draft = ss['routine_draft']
    name = ss.get('r_name', '').strip()
    if not name:
        queue_toast('루틴 이름을 입력해주세요', ':material/error:')
        return
    if len(name) > ROUTINE_LIMITS['name']:
        queue_toast(f"이름은 {ROUTINE_LIMITS['name']}자 이내로 입력해주세요", ':material/error:')
        return
    if not draft['items']:
        queue_toast('운동을 1개 이상 추가해주세요', ':material/error:')
        return
    weekdays = normalize_weekdays(ss.get('r_weekdays') or [])
    now = now_iso()

    def apply(data):
        existing = next((r for r in data['routines'] if r['id'] == draft['id']), None) if draft['id'] else None
        if existing:
            existing.update({'name': name, 'items': draft['items'], 'weekdays': weekdays, 'updatedAt': now})
        else:
            data['routines'].append({'id': str(uuid.uuid4()), 'name': name, 'items': draft['items'],
                                     'weekdays': weekdays, 'createdAt': now, 'updatedAt': now})
    mutate(apply)
    ss.pop('routine_draft', None)
    queue_toast(f'{name} 루틴을 저장했어요.', ':material/check:')


def render_routines(data):
    ss = st.session_state
    draft = ss.get('routine_draft')
    if draft is not None:
        render_routine_editor(draft)
        return
    key = selected_date()
    st.subheader('루틴', anchor=False)
    st.caption(f"루틴을 고르면 {'오늘' if key == today_key() else fmt_date_short(key)} 목록에 운동이 한꺼번에 추가돼요. "
               '루틴을 수정해도 이미 날짜에 추가된 운동 기록은 바뀌지 않아요.')
    with st.container(horizontal=True):
        st.button('새 루틴', icon=':material/add:', type='primary', on_click=start_routine_editor)
        current = sort_by_order(workouts_on(data, key))
        st.button(f'{fmt_date_short(key)} 목록 저장', icon=':material/save:', disabled=not current,
                  on_click=start_routine_editor, args=(None, current))
    if not data['routines']:
        st.info('저장된 루틴이 없어요. 자주 하는 운동 조합을 루틴으로 만들어 두면 한 번에 추가할 수 있어요.')
        return
    for r in data['routines']:
        with st.container(border=True):
            with st.container(horizontal=True, vertical_alignment='center'):
                st.markdown(f"**{esc(r['name'])}**")
                st.space('stretch')
                st.caption((f"{fmt_weekdays(r['weekdays'])} · " if r['weekdays'] else '') + f"{len(r['items'])}개")
            with st.container(horizontal=True):
                for c in CATEGORIES:
                    n = sum(1 for i in r['items'] if i['category'] == c['key'])
                    if n:
                        st.badge(f"{c['name']} {n}", color=c['badge'])
            st.markdown('  \n'.join(f"{esc(i['name'])} — {esc(fmt_summary(i))}" for i in r['items'][:4])
                        + (f"  \n:gray[외 {len(r['items']) - 4}개]" if len(r['items']) > 4 else ''))
            with st.container(horizontal=True):
                st.button('불러오기', icon=':material/playlist_add:', type='primary', key=f"ap-{r['id']}",
                          on_click=on_apply_routine, args=(r['id'],))
                st.button('수정', icon=':material/edit:', key=f"ed-{r['id']}", on_click=start_routine_editor, args=(r,))
                with st.popover('삭제', icon=':material/delete:'):
                    st.write(f"'{esc(r['name'])}' 루틴을 삭제할까요?")
                    st.button('삭제', type='primary', key=f"rdel-{r['id']}", on_click=on_routine_delete, args=(r['id'],))


def render_routine_editor(draft):
    ss = st.session_state
    st.subheader('루틴 수정' if draft['id'] else '새 루틴', anchor=False)
    st.text_input('루틴 이름', key='r_name', max_chars=ROUTINE_LIMITS['name'], placeholder='예: 하체 데이, 가슴·삼두')
    st.pills('하는 요일 (선택)', WEEKDAY_ORDER, format_func=lambda d: WEEKDAY_NAMES[d], selection_mode='multi', key='r_weekdays')
    st.caption('요일을 고르면 그 요일에 운동이 없을 때 이 루틴을 바로 불러올 수 있게 보여줘요.')
    items = draft['items']
    with st.container(horizontal=True, vertical_alignment='center'):
        st.markdown(f"**운동 {len(items)}/{ROUTINE_LIMITS['items']}**")
        st.space('stretch')
        st.button('운동 추가', icon=':material/add:', disabled=len(items) >= ROUTINE_LIMITS['items'],
                  on_click=open_form, args=({'mode': 'item', 'index': None},))
    if not items:
        st.info('운동 추가 버튼으로 운동을 넣으세요.')
    for i, item in enumerate(items):
        with st.container(border=True, horizontal=True, vertical_alignment='center'):
            st.badge(CAT[item['category']]['name'], color=CAT[item['category']]['badge'])
            st.markdown(f"**{esc(item['name'])}** :gray[{esc(fmt_summary(item))}]")
            st.space('stretch')
            st.button('', icon=':material/arrow_upward:', key=f'ri-up-{i}', disabled=i == 0, on_click=on_draft_move, args=(i, -1))
            st.button('', icon=':material/arrow_downward:', key=f'ri-down-{i}', disabled=i == len(items) - 1, on_click=on_draft_move, args=(i, 1))
            st.button('', icon=':material/edit:', key=f'ri-edit-{i}', on_click=open_form, args=({'mode': 'item', 'index': i},))
            st.button('', icon=':material/delete:', key=f'ri-del-{i}', on_click=on_draft_remove, args=(i,))
    with st.container(horizontal=True):
        st.button('취소', on_click=lambda: ss.pop('routine_draft', None))
        st.button('루틴 저장', type='primary', on_click=on_routine_save)


# =========================================================
# 화면: 통계
# =========================================================
def render_stats(data):
    ss = st.session_state
    ss.setdefault('stats_anchor', today_key())
    st.subheader('통계', anchor=False)
    kind = st.segmented_control('기간', ['week', 'month'], format_func=lambda k: '주간' if k == 'week' else '월간',
                                key='stats_kind', default='week', required=True, label_visibility='collapsed')
    anchor = ss['stats_anchor']
    start, end = period_range(kind, anchor)
    word = '주' if kind == 'week' else '달'

    def shift(n):
        ss['stats_anchor'] = today_key() if n == 0 else shift_period(kind, ss['stats_anchor'], n)

    with st.container(horizontal=True, vertical_alignment='center'):
        st.button('', icon=':material/chevron_left:', key='st-prev', help=f'이전 {word}', on_click=shift, args=(-1,))
        st.markdown(f'#### {fmt_period(kind, anchor)}')
        st.button('', icon=':material/chevron_right:', key='st-next', help=f'다음 {word}', on_click=shift, args=(1,))
        if not start <= today_key() <= end:
            st.button('이번 주' if kind == 'week' else '이번 달', key='st-today', type='tertiary', on_click=shift, args=(0,))

    s = period_stats(data, start, end)
    c = st.columns(4)
    c[0].metric('운동한 날', f"{s['days']}일")
    c[1].metric('완료 세트', s['done_sets'])
    c[2].metric('총 볼륨', f"{s['volume']:,}kg")
    c[3].metric('유산소', f"{s['cardio']}분")

    st.markdown('**카테고리별 완료 세트**')
    if s['done_sets'] == 0:
        st.info(f'이 {word}에는 완료한 세트가 없어요.')
    else:
        df = pd.DataFrame({'카테고리': [c['name'] for c in CATEGORIES], '세트': [s['cat_sets'][c['key']] for c in CATEGORIES]})
        chart = alt.Chart(df).mark_bar(cornerRadiusEnd=4, height=14).encode(
            y=alt.Y('카테고리:N', sort=None, title=None),
            x=alt.X('세트:Q', title=None, axis=alt.Axis(tickMinStep=1)),
            color=alt.Color('카테고리:N', scale=alt.Scale(domain=[c['name'] for c in CATEGORIES], range=[c['color'] for c in CATEGORIES]), legend=None),
            tooltip=['카테고리:N', '세트:Q'],
        )
        labels = chart.mark_text(align='left', dx=4).encode(text='세트:Q', color=alt.value('#888'))
        st.altair_chart((chart + labels).properties(height=7 * 28), width='stretch')

    st.markdown(f'**최근 {TREND_PERIODS}{word} 완료 세트**')
    rows = []
    for i in range(TREND_PERIODS):
        a = shift_period(kind, anchor, i - TREND_PERIODS + 1)
        ps, pe = period_range(kind, a)
        p = period_stats(data, ps, pe)
        rows.append({'기간': fmt_month_day(ps) if kind == 'week' else f'{int(ps[5:7])}월', '전체': fmt_period(kind, a),
                     '세트': p['done_sets'], '운동한 날': p['days'], '볼륨(kg)': p['volume'], '선택': i == TREND_PERIODS - 1})
    df = pd.DataFrame(rows)
    bars = alt.Chart(df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X('기간:N', sort=None, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y('세트:Q', title=None, axis=alt.Axis(tickMinStep=1)),
        color=alt.condition('datum.선택', alt.value('#2563EB'), alt.value('#93B4F5')),
        tooltip=['전체:N', '세트:Q', '운동한 날:Q', '볼륨(kg):Q'],
    )
    st.altair_chart(bars.properties(height=200), width='stretch')
    st.caption('완료한 세트만 셉니다. 볼륨은 무게 × 횟수의 합이에요(시간으로 하는 운동 제외).')


# =========================================================
# 화면: 설정·백업
# =========================================================
def on_setting(name, key):
    value = st.session_state[key]
    mutate(lambda d: d.__setitem__('settings', normalize_settings({**d['settings'], name: value})))
    if name == 'restSeconds' and value == 0:
        st.session_state['rest_end'] = None


def render_settings(data):
    ss = st.session_state
    s = data['settings']
    st.subheader('설정', anchor=False)
    ss['set_rest'] = s['restSeconds']
    ss['set_sound'] = s['restSound']
    ss['set_goal'] = s['weeklyGoal']
    st.selectbox('세트 사이 휴식 타이머', REST_OPTIONS, format_func=fmt_rest, key='set_rest', on_change=on_setting, args=('restSeconds', 'set_rest'))
    st.toggle('휴식이 끝나면 소리로 알림', key='set_sound', on_change=on_setting, args=('restSound', 'set_sound'))
    st.caption('세트 번호를 눌러 완료하면 타이머가 시작돼요.')
    st.selectbox('주간 목표 (운동하는 날)', list(range(1, 8)), format_func=lambda n: f'일주일에 {n}일', key='set_goal',
                 on_change=on_setting, args=('weeklyGoal', 'set_goal'))

    st.subheader('백업', anchor=False)
    st.caption(f'데이터는 이 컴퓨터의 {DATA_FILE.name} 파일에 저장돼요. 브라우저 앱에서 내보낸 백업 파일도 그대로 가져올 수 있어요.')
    st.download_button('데이터 내보내기', data=json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'),
                       file_name=f'workout-backup-{today_key()}.json', mime='application/json', icon=':material/download:')
    uploaded = st.file_uploader('데이터 가져오기 (JSON)', type=['json'])
    if uploaded is not None:
        try:
            raw = json.loads(uploaded.getvalue().decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            st.error('가져오기 실패: JSON 파일을 읽을 수 없습니다.')
            return
        error = validate_import(raw)
        if error:
            st.error(f'가져오기 실패: {error} 기존 데이터는 그대로 유지됩니다.')
            return
        st.warning(f"운동 {len(raw['workouts'])}개를 가져옵니다. 기존 데이터를 덮어씁니다. "
                   f'(덮어쓰기 직전 데이터는 {BACKUP_FILE.name}에 보관돼요)')
        if st.button('덮어쓰고 가져오기', type='primary'):
            write_backup(json.dumps(data, ensure_ascii=False))
            save_data(normalize_data(raw))
            ss.pop('undo', None)  # 이전 데이터 기준의 실행 취소가 남지 않도록
            queue_toast('데이터를 가져왔습니다.', ':material/check:')
            st.rerun()


# =========================================================
# 메인
# =========================================================
def on_nav():
    view = st.session_state.get('nav') or current_view()
    go(view)


def main():
    st.set_page_config(page_title='운동 스케줄', page_icon=':material/fitness_center:', layout='centered')
    ss = st.session_state
    view = current_view()
    if ss.get('nav') != view:
        ss['nav'] = view
    data = load_data()

    st.title('운동 스케줄', anchor=False)
    st.segmented_control('화면', list(VIEWS), format_func=lambda v: VIEWS[v], key='nav', required=True,
                         label_visibility='collapsed', on_change=on_nav)

    {'calendar': render_calendar, 'day': render_day, 'routines': render_routines,
     'stats': render_stats, 'settings': render_settings}[view](data)

    flush_toasts()
    dialog = ss.pop('open_dialog', None)
    if dialog:
        kind, params = dialog
        if kind == 'form':
            form_dialog()
        elif kind == 'setlog':
            setlog_dialog(params['workout_id'])
        elif kind == 'history':
            history_dialog(params['workout_id'])


if __name__ == '__main__':
    main()
