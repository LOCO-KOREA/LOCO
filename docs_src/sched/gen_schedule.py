"""일정서 생성: 템플릿 + 아래 일정 데이터 + 기능정의서·API 계약서에서 읽은 값 → docs/일정서.md

- 기능 목록·우선순위·수용 기준(AC)·미결 사항(OI)은 기능정의서에서, 결정 기한(D-API)은 API 계약서에서 읽는다.
- 요일은 날짜로 계산한다.
- 확인: 기능이 빠짐없이 있는지, 모두 동결 전에 끝나는지, 앞 기능보다 늦게 끝나는지,
  기능이 끝나는 날의 날짜별 계획에 그 기능이 적혀 있는지, 날짜별 계획에 빠진 날이 없는지.
"""
import datetime as dt, re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402
DOCS = paths.DOCS
OUT = DOCS / "일정서.md"
WD = "월화수목금토일"


def d(s):
    m, dd = map(int, s.split("/"))
    return dt.date(2026, m, dd)


def lab(x):
    return f"{x.month}/{x.day:02d} ({WD[x.weekday()]})"


START, TECH_REVIEW, FREEZE, END = d("10/12"), d("10/17"), d("10/23"), d("10/30")

# ---------------------------------------------------------------- 원본 문서에서 읽기
fd = (DOCS / "기능정의서.md").read_text(encoding="utf-8")
api = (DOCS / "API_계약서.md").read_text(encoding="utf-8")

FEAT = {}
for fid, name, fr, scr, prio in re.findall(
        r"^\| (F0\d-0\d) \| ([^|]+?) \| ([^|]+?) \| ([^|]+?) \| (Must|Should|Could) \|$", fd, re.M):
    FEAT[fid] = {"name": name, "prio": prio}
for m in re.finditer(r"^#### (F0\d-0\d) [^\n]*\n(.*?)(?=^#{2,4} )", fd, re.M | re.S):
    FEAT[m.group(1)]["ac"] = re.findall(r"^\s+- (AC-\d{2}):", m.group(2), re.M)
assert len(FEAT) == 30 and all("ac" in v and v["ac"] for v in FEAT.values()), \
    [k for k, v in FEAT.items() if not v.get("ac")]

sec_oi = fd[fd.index("## 10. 미결 사항"):fd.index("## 11.")]
OI = re.findall(r"^\| (OI-\d{2}) \| (.+?) \| (.+?) \| (.+?) \|$", sec_oi, re.M)
assert len(OI) == 12, len(OI)

sec_dapi = api[api.index("## 12. 결정이 필요한 것"):api.index("## 13.")]
DAPI = re.findall(r"^\| (D-API-\d{2}) \| ([^|]+?) \| ([^|]+?) \| (10/\d\d) \|$", sec_dapi, re.M)
assert len(DAPI) == 5, DAPI

# ---------------------------------------------------------------- 일정 데이터
WP_NAME = {"WP0": "WP0 총괄·데이터", "WP1": "WP1 자세 분석", "WP2": "WP2 경고·확신도", "WP3": "WP3 판정·보고서"}
PLAN = {   # 기능: (묶음, 끝나는 날, 10/16 Pose MVP에 핵심이 먼저 동작하는지)
    "F01-01": ("WP0", "10/19", False), "F01-02": ("WP0", "10/20", False), "F01-03": ("WP0", "10/22", False),
    "F02-01": ("WP0", "10/19", False), "F02-02": ("WP3", "10/19", False), "F02-03": ("WP0", "10/22", False),
    "F03-01": ("WP1", "10/16", True),  "F03-02": ("WP1", "10/21", False), "F03-03": ("WP1", "10/20", False),
    "F03-04": ("WP1", "10/16", True),
    "F04-01": ("WP1", "10/16", True),  "F04-02": ("WP1", "10/20", False),  "F04-03": ("WP1", "10/16", True),
    "F04-04": ("WP1", "10/19", False), "F04-05": ("WP1", "10/19", False), "F04-06": ("WP1", "10/20", True),
    "F04-07": ("WP1", "10/20", False),
    "F05-01": ("WP3", "10/20", False), "F05-02": ("WP2", "10/21", False), "F05-03": ("WP2", "10/21", False),
    "F05-04": ("WP3", "10/21", False), "F05-05": ("WP3", "10/22", False), "F05-06": ("WP3", "10/22", False),
    "F06-01": ("WP3", "10/22", False), "F06-02": ("WP2", "10/22", False), "F06-03": ("WP2", "10/21", False),
    "F07-01": ("WP1", "10/22", False), "F07-02": ("WP3", "10/21", False), "F07-03": ("WP2", "10/22", False),
    "F07-04": ("WP1", "10/22", False),
}
DEPS = {   # 앞 기능 (끝나는 날이 같거나 빨라야 함). "TP" = 10/17 기술 검토 뒤
    "F01-02": ["F01-01"], "F01-03": ["F01-02"], "F02-01": ["F01-01"], "F02-02": ["F02-01"], "F02-03": ["F01-01"],
    "F03-02": ["F03-01"], "F03-03": ["F03-01"], "F03-04": ["F03-01"],
    "F04-02": ["F04-01"], "F04-03": ["F04-01"], "F04-04": ["F04-03", "TP"], "F04-05": ["F04-04"],
    "F04-06": ["F04-03"], "F04-07": ["F04-06", "F04-02"],
    "F05-01": ["F04-05", "F02-02"], "F05-02": ["F05-01"], "F05-03": ["F05-01"], "F05-04": ["F05-01"],
    "F05-05": ["F05-01"], "F05-06": ["F05-05"],
    "F06-01": ["F05-05", "F04-07"], "F06-02": ["F05-03"], "F06-03": ["F05-03"],
    "F07-01": ["F04-01"], "F07-02": ["F04-04"], "F07-03": ["F06-02"], "F07-04": ["F04-03"],
}

MILESTONES = [  # (날짜, ID, 이름, 멘토가 보는 것, 우리 완료 기준)
    ("10/09", "M1", "방향 확정 (멘토링)", "벤치앱 조사 · 사용자/문제 · MVP 후보 정리", "완료 (주제 발표)"),
    ("10/14", "M2", "요구사항·설계 1차 확정", "FR/NFR · User Flow · 화면 · 기술구조",
     "기능정의서 v0.3, 화면설계서, ERD, API 계약서 확정 표시. 담당 확정. 결정 {DUE_10/14}"),
    ("10/16", "M3", "Pose MVP", "입력 → Pose → 핵심 분석 → 화면까지 동작",
     "사진 한 장, 이어서 짧은 영상 (8초 이하)으로 관절 → 각도 → REBA 점수가 화면에 나온다. 진행률과 취소가 동작한다 (AC-10). 30초 영상 처리 시간을 잰다 (NFR-007). 얼굴 가림은 10/20"),
    ("10/17", "M4", "기술 검토 (멘토링)", "Pose 구현 검토 · 기술 이슈 · 개선 방향",
     "측정 표: 각도 오차 (AC-13), 판별 불가 비율, 모델 후보 속도. 결정 {DUE_10/17}"),
    ("10/23", "M5", "서비스 MVP", "Frontend/Backend/Pose 통합 · 선택 기능 포함",
     "**개발 동결.** UC-001 → UC-002 → UC-003이 처음부터 끝까지 된다. 수용 기준 AC-01 ~ AC-36 확인. 계약 시험과 DB 시험 통과. 인터넷을 끊어도 동작 (AC-32)"),
    ("10/24", "M6", "중간 결과 발표 (멘토링)", "동작 데모 · 피드백 · 최종 수정 목록", "동결 버전으로 데모하고 수정 목록을 만든다"),
    ("10/27", "M7", "기능 동결", "신규 기능 종료 · 테스트/평가 중심", "수정 목록 처리 끝. evaluation.md 초안 (NFR-015 수치)"),
    ("10/29", "M8", "배포·발표 준비", "배포 URL · 평가 · 발표자료 · 리허설",
     "설치 파일을 팀원 PC 2대와 발표 노트북에서 확인 (NFR-016, NFR-007). README. 리허설 2회"),
    ("10/30", "M9", "최종 발표", "최종 서비스 · 결과 · 한계 · 데모", "발표"),
]

DAILY = {
    "10/12": [("한정욱", "설계 문서 (기능정의서, 화면설계서, ERD, DB 아키텍처, API 계약서, 일정서)를 담은 저장소 LOCO-KOREA/LOCO를 팀에 공유"),
              ("총괄", "고시 원문 대조 완료 (OI-10 해결). 해설 '주'의 각도 값은 글 3건으로 확인했고 고용노동부 원문은 못 찾아 10/14까지 문의 (OI-09)"),
              ("노트북 담당", "발표 노트북에서 30초 영상 처리 시간 실측 (NFR-007)"),
              ("한정욱", "화면설계서 초안과 ERD 그림(ERD.drawio) 공유 (WBS 3.1)")],
    "10/13": [("전원", "설계 문서 읽고 질문 적기 (10/14 회의 준비). 담당 가배정 (4절)"),
              ("WP1", "사진 한 장 → 관절 → 각도 → REBA부터 시작 (WBS 4.1, 멘토 10/9: 정지 영상 먼저)"),
              ("WP0", "저장소 계층 시작. 연결 규칙은 ergo/db/connection.py에 있음. 남은 것: 저장소 클래스, 마이그레이션 틀 (DB 아키텍처 4·7절)"),
              ("WP0", "DB 아키텍처 설계서 검토: 구성도, 연결·트랜잭션 규칙, 결정 DB-01 ~ DB-09 (WBS 3.2)"),
              ("각 묶음", "저장소를 받아 (git clone) 시험을 돌려 본다 (python -m unittest discover -s tests -t .). 스텁은 이미 있다. 맡은 모듈의 POC 단위 시험을 시작 (멘토 10/9)"),
              ("한정욱", "ERD.drawio를 draw.io에서 열어 검토하고 이름 확정 (멘토 10/9: 많이 쓰는 도구로)")],
    "10/14": [("전원", "설계 1차 확정 회의: 기능정의서, 화면설계서, ERD, API 계약서"),
              ("전원", "결정 {DUE_10/14}. 담당 확정"),
              ("함께", "재연 촬영 1차: AC-14, AC-15, AC-24 자세를 각도기로 재며 찍음"),
              ("WP1", "짧은 영상 (8초 이하, 240프레임)을 메모리 배열로 프레임별 처리")],
    "10/15": [("WP0", "ERD·API 계약 확정 (WBS 3.3 끝). 결정 {DUE_10/15}"),
              ("WP3", "판정 엔진을 judge_criteria로 옮기고 지침 부록 1 예시 11개로 시험 (AC-21)"),
              ("WP2", "GPT 어댑터 시작: v_gpt_payload → 요청 → 숫자 검사"),
              ("함께", "재연 촬영 2차 (필요하면)")],
    "10/16": [("WP1", "Pose MVP (짧은 영상 기준): 영상 선택 (F03-01), 분석 실행·진행률·취소 (F03-04), 관절 (F04-01), 각도 (F04-03) 끝. REBA 잠정 점수까지"),
              ("WP1", "결정 {DUE_10/16} (분석 중 화면이 멈추는지 재 봄)"),
              ("노트북 담당", "30초 영상 처리 시간 다시 잼 (NFR-007)"),
              ("WP0", "분석 결과 저장 연결: frame_angle, reba_result. 대표 장면 이미지는 얼굴 가림이 끝나는 10/20부터 (ERD가 가리지 않은 이미지를 막음)")],
    "10/17": [("전원 + 멘토", "기술 검토: 각도 오차 (AC-13), 판별 불가 비율 (TP-03), 모델 후보 속도 (F07-04 1차 측정)"),
              ("전원", "결정 {DUE_10/17}"),
              ("한정욱", "배포 형태를 멘토에게 확인")],
    "10/18": [("전원", "예비일. 밀린 주요 경로 작업만")],
    "10/19": [("WP0", "통합 시작 (WBS 5.3): 스텁을 실제 함수로 바꿈. 조사 만들기 (F01-01), 단위작업 (F02-01) 끝"),
              ("WP1", "기술 검토 결정을 반영해 자세 판별 (F04-04), 비율·노출 시간 (F04-05) 끝. 긴 영상 (30초)은 프레임별 각도를 DB에 저장해 처리"),
              ("WP3", "작업 정보 입력 (F02-02) 끝"),
              ("WP2", "확신도·경고 시작")],
    "10/20": [("WP3", "판정 초안 (F05-01) 끝"),
              ("WP1", "촬영 동의 (F03-03), 얼굴 가림 (F04-02), REBA 사람 입력 (F04-06), 대표 장면 (F04-07) 끝"),
              ("WP0", "저장·목록 (F01-02) 끝"),
              ("함께", "시험 케이스 설계 시작 (WBS 6.1)"),
              ("총괄", "중간 점검: 통합하지 못한 Must가 있으면 9절 적용")],
    "10/21": [("WP2", "확신도 (F05-02), 경고 (F05-03), 기본 문구 (F06-03) 끝. 인터넷을 끊고 확인 (AC-32)"),
              ("WP3", "다시 계산 (F05-04), 각도 기준 (F07-02) 끝"),
              ("WP1", "촬영 안내 (F03-02) 끝")],
    "10/22": [("WP3", "확정 (F05-05), 수정 이력 (F05-06), 엑셀 보고서 (F06-01) 끝"),
              ("WP2", "GPT 문장 (F06-02), GPT 설정 (F07-03) 끝"),
              ("WP1", "모델 선택 (F07-01), 모델 비교 (F07-04) 끝"),
              ("WP0", "다음 정기조사 예정일 (F01-03), 참여 근로자 (F02-03) 끝"),
              ("함께", "정답 채점표 양식"),
              ("전원", "동결 전 리허설: UC-001 → UC-002 → UC-003")],
    "10/23": [("전원", "서비스 MVP 확인: 수용 기준, 계약 시험, DB 시험"),
              ("한정욱", "개발 동결. 코드에 `freeze-1023` 이름 붙임"),
              ("함께", "정답 채점 시작 (팀원 2명이 따로), 평가 (WBS 6.2)")],
    "10/24": [("전원 + 멘토", "중간 결과 발표 (동결 버전 데모)"),
              ("한정욱", "수정 목록 작성")],
    "10/25": [("전원", "예비일")],
    "10/26": [("각 묶음", "수정 목록 처리"),
              ("배정", "설치 파일 만들기 (WBS 7.1)"),
              ("함께", "시험 케이스 설계 끝 (WBS 6.1)")],
    "10/27": [("각 묶음", "수정 목록 마감"),
              ("함께", "evaluation.md 초안: NFR-015 수치 (WBS 6.2 끝)"),
              ("배정", "README 시작 (WBS 7.2), 발표자료 시작 (WBS 7.3)")],
    "10/28": [("배정", "설치 파일 시험: 팀원 PC 2대와 발표 노트북 (NFR-016, NFR-007). 배포 (WBS 7.1 끝)"),
              ("전원", "발표자료")],
    "10/29": [("전원", "배포본 확정, README 끝, 리허설 2회")],
    "10/30": [("전원", "최종 발표")],
}

EXTRA_DEC = [  # (기한, ID, 무엇, 기본안, 누가)
    ("10/12", "NFR-007", "발표 노트북에서 30초 영상 처리 시간 실측", "10/16 Pose MVP 때 다시 잼", "노트북 담당"),
    ("10/13", "담당", "WP1 ~ WP3 담당 가배정 (10/14 확정)", "총괄이 정함", "전원"),
    ("10/17", "TP-01 ~ TP-11", "기술 파라미터 값 (판정 기준이 아님)", "기능정의서 8절의 제안값", "전원 + 멘토"),
    ("10/17", "AC-13, NFR-015", "각도 오차와 평가 지표의 목표치", "첫 측정값을 보고 팀이 정함", "전원 + 멘토"),
    ("10/17", "배포 형태", "PC 설치 파일인지 웹 주소인지 (10/9 발표에서 질문함)", "PC 설치 파일 (NFR-016)", "한정욱 → 멘토"),
    ("10/20", "빼는 기능", "9절 순서를 적용할지", "빼지 않음", "전원"),
]
DAPI_DEFAULT = {
    "D-API-01": ("총괄이 정함", "전원"),
    "D-API-02": ("총괄이 정함", "WP3"),
    "D-API-03": ("GPT 끔 (기본 문구만, F06-03)", "WP2"),
    "D-API-04": ("keyring (API 계약서 6.6절)", "WP2"),
    "D-API-05": ("스레드. 화면이 멈추면 별도 프로세스", "WP1"),
}
OI_WHO = {"OI-09": "총괄", "OI-10": "총괄", "OI-12": "한정욱 (데이터)"}
OI_DEFAULT_NOTE = {"OI-12": " (ERD D-01에 반영됨)"}

GANTT = [  # (구역, 이름, 시작, 끝(포함), 주요 경로)
    ("설계", "화면설계서", "10/12", "10/14", False),
    ("설계", "DB 아키텍처 검토", "10/13", "10/14", False),
    ("설계", "ERD·API 계약 확정", "10/12", "10/15", False),
    ("함께", "재연 촬영", "10/14", "10/15", True),
    ("함께", "시험 케이스 설계", "10/20", "10/26", False),
    ("함께", "정답 채점·평가", "10/23", "10/27", True),
    ("함께", "설치 파일·배포", "10/26", "10/28", False),
    ("함께", "README", "10/27", "10/29", False),
    ("함께", "발표자료·리허설", "10/27", "10/30", False),
    ("WP0 총괄·데이터", "저장소 모듈", "10/13", "10/16", False),
    ("WP0 총괄·데이터", "서비스 공통 (트랜잭션·이력)", "10/15", "10/18", False),
    ("WP0 총괄·데이터", "조사·단위작업 기능", "10/19", "10/22", False),
    ("WP0 총괄·데이터", "통합", "10/19", "10/23", True),
    ("WP1 자세 분석", "사진 → 짧은 영상, 관절·각도·REBA", "10/13", "10/16", True),
    ("WP1 자세 분석", "자세 판별·비율 (기준값 반영)", "10/17", "10/19", True),
    ("WP1 자세 분석", "얼굴 가림·동의·대표 장면·모델", "10/19", "10/22", False),
    ("WP2 경고·확신도", "GPT 어댑터", "10/15", "10/22", False),
    ("WP2 경고·확신도", "확신도·경고·기본 문구", "10/19", "10/21", True),
    ("WP3 판정·보고서", "판정 엔진", "10/15", "10/20", True),
    ("WP3 판정·보고서", "입력·다시 계산·각도 기준", "10/19", "10/21", False),
    ("WP3 판정·보고서", "확정·이력·엑셀", "10/21", "10/22", True),
]

DELIVERABLES = [  # (WBS, 멘토 산출물, 우리 문서, 기한, 상태)
    ("1.1, 1.3", "project-overview.md", "project-overview.md", "10/09", "있음. 10/12에 동결일 반영"),
    ("1.2", "benchmark-apps.md", "benchmark-apps.md (ergo-C 포함)", "10/09", "있음"),
    ("2.1", "requirements.md", "requirements.md", "10/12", "있음. 10/12에 동결일 반영"),
    ("2.2", "requirements.md (Use Case)", "requirements.md 5절 UC-001 ~ UC-003", "10/13", "있음"),
    ("(팀 추가)", "—", "기능정의서 v0.3", "10/14", "초안 있음"),
    ("3.1", "user-flow-wireframe.md", "화면설계서.md (와이어프레임 14장 + 화면 흐름도)", "10/14", "초안 있음 (10/12)"),
    ("3.2", "architecture.md", "DB 아키텍처 설계서 (시스템 구성도 포함) + API 계약서 9.1절 (분석 흐름)", "10/14", "초안 있음 (10/12)"),
    ("3.3", "api-data-design.md", "API 계약서 + ERD (ERD.drawio 그림 포함)", "10/15", "초안 있음"),
    ("4.1, 4.2", "pose module, analysis module", "코드 (WP1)", "10/16", "—"),
    ("4.3", "Pose MVP", "코드 (M3 시연)", "10/17", "—"),
    ("5.1, 5.2", "frontend, backend", "코드 (각 묶음)", "10/22", "—"),
    ("5.3", "Service MVP", "통합 앱 (M5)", "10/23", "—"),
    ("5.4", "extension (DB 기록 / 생성형 AI 피드백 / 비교 기능)", "저장소, GPT 문장, 모델 비교로 이미 범위에 있음", "10/23", "—"),
    ("6.1, 6.2", "evaluation.md", "evaluation.md", "10/27", "—"),
    ("7.1", "Deployment URL", "설치 파일 (웹 주소가 필요한지 멘토 확인)", "10/28", "—"),
    ("7.2", "README.md", "README.md", "10/29", "—"),
    ("7.3", "presentation + demo", "발표자료, 데모 순서", "10/30", "—"),
]

# ---------------------------------------------------------------- 확인
problems = []
if set(PLAN) != set(FEAT):
    problems.append(f"기능 불일치: 일정에만 {set(PLAN) - set(FEAT)}, 기능정의서에만 {set(FEAT) - set(PLAN)}")
end = {f: d(v[1]) for f, v in PLAN.items()}
for f, e in end.items():
    if not (START <= e <= FREEZE):
        problems.append(f"{f} 끝 {lab(e)}가 동결 {lab(FREEZE)} 밖")
    if FEAT[f]["prio"] == "Could":
        problems.append(f"{f}는 Could인데 일정에 있음")
n_deps = 0
for f, pre in DEPS.items():
    for p in pre:
        n_deps += 1
        if p == "TP":
            if not end[f] > TECH_REVIEW:
                problems.append(f"{f}는 기술 검토({lab(TECH_REVIEW)}) 뒤에 끝나야 함")
        elif end[p] > end[f]:
            problems.append(f"{f} ({lab(end[f])})가 앞 기능 {p} ({lab(end[p])})보다 먼저 끝남")
days = [START + dt.timedelta(n) for n in range((END - START).days + 1)]
if sorted(d(k) for k in DAILY) != days:
    problems.append("날짜별 계획에 빠지거나 넘치는 날이 있음")
for f, e in end.items():
    text = " ".join(w for _, w in DAILY.get(f"{e.month}/{e.day:02d}", []))
    if f not in text:
        problems.append(f"{f}가 끝나는 날 {lab(e)}의 계획에 없음")
    for k, items in DAILY.items():
        if d(k) != e and any(f in w and "끝" in w for _, w in items):
            problems.append(f"{f}가 {k}에도 '끝'으로 적힘")
for sec, name, s, e2, _ in GANTT:
    if not (START <= d(s) <= d(e2) <= END):
        problems.append(f"간트 {name} 기간 오류")
    if ":" in name or "#" in name:
        problems.append(f"간트 이름에 쓸 수 없는 글자: {name}")
if problems:                              # 표를 만들기 전에 멈춘다
    print("\n".join(problems))
    raise SystemExit(f"문제 {len(problems)}개 — 일정서를 쓰지 않음")

# ---------------------------------------------------------------- 결정 일정
dec = []
oi_due = {}
for oid, what, default, whowhen in OI:
    m = re.search(r"10/(\d\d)", whowhen)
    oi_due[oid] = d(f"10/{m.group(1)}") if m else None
for oid, what, default, whowhen in OI:
    if whowhen.startswith("완료"):               # 이미 해결된 미결 사항은 결정 일정에 올리지 않는다
        continue
    due = oi_due[oid] or oi_due["OI-09"]
    who = OI_WHO.get(oid) or re.sub(r",?\s*10/\d\d", "", whowhen).strip(" ,") or "팀"
    if who == "기술 검토":
        who = "전원 + 멘토 (기술 검토)"
    dec.append((due, oid, what, default + OI_DEFAULT_NOTE.get(oid, ""), who))
for did, what, options, due in DAPI:
    default, who = DAPI_DEFAULT[did]
    dec.append((d(due), did, what, default, who))
for due, did, what, default, who in EXTRA_DEC:
    dec.append((d(due), did, what, default, who))
dec.sort(key=lambda r: (r[0], r[1]))
due_ids = {}
for r in dec:
    due_ids.setdefault(r[0], []).append(r[1])


def fill_due(text):
    def rep(m):
        ids = [i for i in due_ids.get(d(m.group(1)), []) if i not in ("담당", "빼는 기능")]
        return ", ".join(ids) if ids else "(없음)"
    return re.sub(r"\{DUE_(10/\d\d)\}", rep, text)


dec_tbl =["| 기한 | ID | 무엇 | 기본안 | 누가 |", "|---|---|---|---|---|"]
for due, did, what, default, who in dec:
    dec_tbl.append(f"| {lab(due)} | {did} | {what} | {default} | {who} |")

# ---------------------------------------------------------------- 표 만들기
ms_tbl = ["| 날짜 | 마일스톤 | 멘토가 보는 것 | 우리 완료 기준 |", "|---|---|---|---|"]
for day, mid, name, mentor, ours in MILESTONES:
    star = "**" if mid == "M5" else ""
    ms_tbl.append(f"| {star}{lab(d(day))}{star} | {star}{mid} {name}{star} | {mentor} | {fill_due(ours)} |")

ft = ["| 기능 | 이름 | 우선순위 | 묶음 | 끝 | 확인 (수용 기준) |", "|---|---|---|---|---|---|"]
for f in sorted(FEAT):
    wp, e, m3 = PLAN[f]
    ft.append(f"| {f} | {FEAT[f]['name']} | {FEAT[f]['prio']} | {wp} | {lab(d(e))}{' ★' if m3 else ''} | {', '.join(FEAT[f]['ac'])} |")
ft.append("")
ft.append("★ = 10/16 Pose MVP에 핵심이 먼저 동작한다.")

daily_tbl = ["| 날짜 | 누가 | 할 일 |", "|---|---|---|"]
ms_by_day = {d(x[0]): x for x in MILESTONES}
for day in days:
    key = f"{day.month}/{day.day:02d}"
    tag = lab(day)
    if day in ms_by_day:
        mid, name = ms_by_day[day][1], ms_by_day[day][2]
        tag = f"**{tag} {mid}**"
    if day == FREEZE:
        tag = f"**{lab(day)} M5 · 개발 동결**"
    for i, (who, what) in enumerate(DAILY[key]):
        daily_tbl.append(f"| {tag if i == 0 else ''} | {who} | {fill_due(what)} |")

gantt = ["gantt", "  title 10/12 ~ 10/30 (개발 동결 10/23)", "  dateFormat YYYY-MM-DD", "  axisFormat %m/%d",
         "  todayMarker off", "  section 마일스톤"]
for day, mid, name, mentor, ours in MILESTONES:
    if d(day) < START:
        continue
    label = f"{mid} {name}" + (" · 개발 동결" if mid == "M5" else "")
    label = label.replace("(멘토링)", "").strip()
    gantt.append(f"  {label} :{'crit, ' if mid == 'M5' else ''}milestone, {mid.lower()}, {d(day).isoformat()}, 0d")
cur = None
for i, (sec, name, s, e2, crit) in enumerate(GANTT):
    if sec != cur:
        gantt.append(f"  section {sec}")
        cur = sec
    dur = (d(e2) - d(s)).days + 1
    gantt.append(f"  {name} :{'crit, ' if crit else ''}t{i}, {d(s).isoformat()}, {dur}d")

dl = ["| WBS | 멘토 산출물 | 우리 문서 | 기한 | 상태 |", "|---|---|---|---|---|"]
for w, mentor, ours, due, st in DELIVERABLES:
    dl.append(f"| {w} | {mentor} | {ours} | {lab(d(due))} | {st} |")

wp_lists = {wp: ", ".join(f for f in sorted(PLAN) if PLAN[f][0] == wp) for wp in WP_NAME}
m3 = [f for f in sorted(PLAN) if PLAN[f][2]]

tpl = (HERE / "sched_template.md").read_text(encoding="utf-8")
doc = (tpl.replace("{{GANTT}}", "\n".join(gantt))
          .replace("{{MILESTONES}}", "\n".join(ms_tbl))
          .replace("{{FEATURES}}", "\n".join(ft))
          .replace("{{DAILY}}", "\n".join(daily_tbl))
          .replace("{{DECISIONS}}", "\n".join(dec_tbl))
          .replace("{{DELIVERABLES}}", "\n".join(dl))
          .replace("{{N_FEAT}}", str(len(PLAN)))
          .replace("{{N_DEC}}", str(len(dec)))
          .replace("{{N_MUST}}", str(sum(FEAT[f]["prio"] == "Must" for f in PLAN)))
          .replace("{{N_SHOULD}}", str(sum(FEAT[f]["prio"] == "Should" for f in PLAN)))
          .replace("{{N_DEPS}}", str(n_deps))
          .replace("{{M3_LIST}}", ", ".join(m3)))
for wp in WP_NAME:
    doc = doc.replace("{{" + wp + "}}", wp_lists[wp])
left = re.findall(r"\{\{[A-Z0-9_]+\}\}|\{DUE_[^}]+\}", doc)
if left:
    problems.append(f"채우지 못한 자리 {left}")

# 문서가 인용하는 ID가 원본에 있는지
for ref in sorted(set(re.findall(r"\b((?:F0\d-0\d)|(?:AC|EX|BR|TP|OI)-\d{2})\b", doc))):
    if ref not in fd:
        problems.append(f"{ref}가 기능정의서에 없음")
req = (DOCS / "requirements.md").read_text(encoding="utf-8")
for ref in sorted(set(re.findall(r"\b((?:NFR|FR|UC)-\d{3})\b", doc))):
    if ref not in req:
        problems.append(f"{ref}가 requirements.md에 없음")

if problems:
    print("\n".join(problems))
    raise SystemExit(f"문제 {len(problems)}개 — 일정서를 쓰지 않음")
paths.write_text(OUT, doc)
print(f"기능 {len(PLAN)} (Must {sum(FEAT[f]['prio']=='Must' for f in PLAN)}, Should {sum(FEAT[f]['prio']=='Should' for f in PLAN)}) "
      f"| 앞 기능 관계 {n_deps} | 결정 {len(dec)} | 날짜 {len(days)}일 | 간트 {len(GANTT)}줄")
print("→", OUT, len(doc), "chars")
