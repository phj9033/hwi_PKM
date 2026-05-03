# hwi_PKM — 개인 지식 관리 시스템 설계

| 항목 | 값 |
|---|---|
| 일자 | 2026-05-01 |
| 상태 | Draft v1 |
| 작성자 | hwijung-park@linecorp.com (with Claude Code) |
| 위치 | `docs/superpowers/specs/2026-05-01-pkm-design.md` |
| 영감 | Karpathy *LLM Wiki* gist · KiwiFS · qmd |

---

## TL;DR

`hwi_PKM`은 **마크다운 파일을 진실의 원천으로 두고, AI 에이전트(Claude Code)가 결정론적 CLI 도구셋(`pkm`)을 조작해 지식을 수집·정제·합성·검색하는 솔로 PKM 시스템**이다.

설계는 Karpathy의 "compounding wiki" 패턴을 따르되, 사용자의 6가지 요구(수집·덩어리·wiki·RAG·작성·대시보드)에 맞춰 **3단 라이프사이클(`raw → wiki → writing`)** 과 **status 기반 승격 게이트**를 도입한다. 검색은 qmd 정신의 풀하이브리드(BM25 + 벡터 + RRF + 재랭킹 + 쿼리확장)를 한국어 친화적으로 구현한다.

핵심 약속:
- **API 키 0개, 비용 0원.** LLM이 필요하면 사용자의 로컬 AI CLI(`claude`/`codex`/`gemini`)를 셸아웃으로 호출.
- **CLI는 결정론.** 해석/창작은 AI 에이전트가, IO/검색/인덱스는 CLI가.
- **Hard-fail by default.** "조용한 degraded"로 잘못된 결과를 누적시키지 않는다.
- **PC를 다운시키지 않는다.** stub 임베더 기본, 메모리 동적 throttle, RSS 캡.

---

## 목차

1. [동기와 핵심 철학](#1-동기와-핵심-철학)
2. [저장소 레이아웃](#2-저장소-레이아웃)
3. [CLI 명령 표면](#3-cli-명령-표면)
4. [AI 에이전트 통합](#4-ai-에이전트-통합)
5. [검색 & RAG 파이프라인](#5-검색--rag-파이프라인)
6. [승격 & Lint 정책](#6-승격--lint-정책)
7. [대시보드](#7-대시보드)
8. [테스트 & 신뢰성](#8-테스트--신뢰성)
9. [V1 (MVP) vs V2+ + 마일스톤](#9-v1-mvp-vs-v2--마일스톤)
10. [부록](#10-부록)

---

## 1. 동기와 핵심 철학

### 1.1 영감의 출처

**Andrej Karpathy의 *LLM Wiki* gist** — 전통 RAG는 매 쿼리마다 원문에서 답을 재합성한다. *LLM Wiki* 패턴은 그 합성을 **누적·영구화**한다. LLM은 ingest 시 raw source를 읽어 entity/concept/summary 페이지를 갱신·교차참조한다. 즉 wiki 자체가 **compounding artifact**다. 3계층(Raw / Wiki / Schema), 3연산(Ingest / Query / Lint).

**KiwiFS** — Karpathy 패턴의 Go 구현체. 마크다운 = 진실, Git = WAL, SQLite FTS5 + 벡터 = 3티어 검색, 다중 프로토콜(REST/MCP/FUSE/NFS). 폴더 컨벤션과 SCHEMA.md로 에이전트 행동 규약화.

**qmd** — local-first 하이브리드 검색 엔진. node-llama-cpp로 임베딩/재랭킹/쿼리확장 모두 로컬. API 키 없음. 출력은 JSON으로 에이전트 친화. **본 설계는 qmd의 LLM 사용 부분을 "사용자가 이미 설치한 로컬 AI CLI 셸아웃"으로 대체** — 모델 1.7B 추가 다운로드를 피하고, 사용자가 인증한 환경 그대로 활용.

### 1.2 사용자의 6가지 기능과 본 설계의 매핑

| # | 사용자 요구 | 본 설계 |
|---|---|---|
| 1 | 지식 수집 (URL+요약, 웹리서치) | `raw/captures/` + `pkm capture *` + `/collect` `/research` 슬래시 |
| 2 | 지식 덩어리 (수동/로컬 폴더) | `raw/chunks/<topic>/` + `pkm chunks *` + `pkm extract` (PDF/HTML→md) |
| 3 | 지식 wiki (임베딩 대상, 승격) | `wiki/{concepts,entities,notes,reports}/` + `pkm promote` + status 게이트 |
| 4 | 지식 RAG (검색, 확장) | `pkm search` 풀하이브리드 + `pkm related` + 3-layer 그래프 + `--with-related` |
| 5 | 지식 작성 (AI가 CLI로) | `writing/` + `pkm write *` + `/write` 슬래시 + SCHEMA.md 워크플로우 |
| 6 | 지식 대시보드 (HTML, 검색, help) | 정적 HTML 8페이지 + 클라이언트 메타 검색 + help.html |

### 1.3 핵심 설계 원칙

1. **파일 = 진실의 원천.** 모든 인덱스/캐시/대시보드는 `data/`에서 결정론적으로 재생성된다.
2. **CLI 코어 = 결정론, AI 셸아웃 = 옵트인.** CLI는 LLM SDK를 import하지 않고 API 키를 보관하지 않는다. 해석/창작은 AI 에이전트(Claude Code)가 CLI를 도구로 조합해 수행한다. 일부 품질-향상 기능(쿼리확장 등)은 사용자의 로컬 AI CLI에 **옵트인** 셸아웃 — 기본 검색 경로는 모델만 호출하는 결정론.
3. **Compounding wiki.** wiki는 캡처/덩어리에서 정제된 누적 아티팩트. 매 검색마다 재합성하지 않는다.
4. **Status 기반 라이프사이클.** frontmatter `status`가 라이프사이클 상태를 표현하고, `pkm promote`가 게이트로 동작한다 (정책 C).
5. **Hard-fail by default.** 의도된 기능이 실패하면 종료코드 ≠ 0 + 명확한 에러. 우회는 명시적 opt-out 플래그로만.
6. **API 키 0개. SDK 미사용.** 보조 LLM 기능이 필요하면 사용자가 인증한 로컬 AI CLI(`claude`/`codex`/`gemini` 등)에 셸아웃 — **옵트인**.
7. **재현 가능한 빌드.** `pkm bootstrap`만으로 어느 PC에서든 동일 인덱스/대시보드 재생성.
8. **PC를 안전하게.** 메모리 폭주는 자동 throttle, 그래도 부족하면 명시적 에러로 종료. OS OOM에 의존하지 않는다.
9. **Raw immutability.** `data/raw/**`의 본문은 한 번 작성된 후 immutable. 정정·갱신은 (a) 새 capture 추가 또는 (b) 승격 후 wiki에서 표현. raw 파일에서 허용되는 변경은 **메타 전이**(`status` 변경, `archived` 이행)뿐. 사실 갱신을 raw 본문에 덮어쓰면 compounding이 깨진다 (Karpathy 핵심). lint가 reviewed 이후 본문 해시 변경을 `RAW_BODY_MUTATED` warning으로 감지.

---

## 2. 저장소 레이아웃

```
hwi_PKM/
├── SCHEMA.md                     # AI 에이전트의 진입 매뉴얼 (Karpathy 패턴 SoT)
├── README.md                     # 사람용 빠른 시작
├── pyproject.toml                # uv 또는 poetry
├── .python-version
│
├── pkm/                          # Python 패키지 — CLI 구현
│   ├── __init__.py
│   ├── cli.py                    # `pkm` 엔트리포인트 (typer/click)
│   ├── commands/                 # 서브커맨드 모듈
│   │   ├── capture.py
│   │   ├── chunks.py
│   │   ├── promote.py
│   │   ├── search.py
│   │   ├── write.py
│   │   ├── reindex.py
│   │   ├── dashboard.py
│   │   ├── log.py
│   │   ├── lint.py
│   │   ├── doctor.py
│   │   ├── mode.py
│   │   ├── extract.py
│   │   └── init.py
│   ├── store/                    # 파일/SQLite/벡터/Git IO
│   │   ├── files.py
│   │   ├── frontmatter.py
│   │   ├── index.py              # SQLite + sqlite-vec
│   │   └── git.py                # 자동 커밋
│   ├── retrieval/                # 검색 로직
│   │   ├── bm25.py
│   │   ├── vector.py
│   │   ├── rrf.py
│   │   ├── rerank.py
│   │   └── expand.py             # 쿼리확장 (AI CLI 셸아웃)
│   ├── models/                   # 로컬 모델 로더 (~/.cache/pkm/models)
│   │   ├── embedder.py           # bge-m3
│   │   └── reranker.py           # bge-reranker-v2-m3
│   ├── llm_bridge.py             # AI CLI 셸아웃 (자동탐지/TOML/훅)
│   ├── dashboard/                # 정적 HTML 빌더
│   │   ├── builder.py
│   │   └── templates/
│   └── errors.py
│
├── tests/                        # pytest
│   ├── conftest.py               # 메모리 캡, stub 임베더 기본
│   └── fixtures/sample-pkm/
│
├── data/                         # 사용자의 지식 (= 진실)
│   ├── log.md                    # append-only 이벤트 로그 (Karpathy)
│   ├── index.md                  # 자동생성 카테고리 TOC
│   ├── raw/
│   │   ├── captures/             # 수집 — flat, 낱개 노트
│   │   │   └── 2026-05-01-foo.md
│   │   └── chunks/               # 덩어리 — 폴더 단위 묶음
│   │       └── topic-A/
│   │           ├── README.md
│   │           └── *.{md,pdf,txt,...}
│   ├── wiki/                     # 승격된 canonical (임베딩 대상)
│   │   ├── concepts/
│   │   ├── entities/
│   │   ├── notes/
│   │   └── reports/
│   └── writing/                  # AI 합성 작성 산출물
│
├── .pkm/                         # 인덱스/캐시 (gitignore)
│   ├── index.db                  # SQLite + FTS5 + sqlite-vec
│   ├── cache/
│   ├── config.toml               # 공용 설정 (커밋) — indexing/memory/ai_cli 이름 별칭만
│   └── config.local.toml         # 개인 오버라이드 (gitignore) — exec/env/credentials/타임아웃
│
├── dashboard/                    # 빌드 산출물 (gitignore)
│   ├── index.html
│   └── assets/
│
└── .claude/                      # Claude Code 통합
    ├── commands/                 # 슬래시 커맨드
    │   ├── collect.md
    │   ├── research.md
    │   ├── promote.md
    │   ├── ask.md
    │   ├── write.md
    │   ├── lint.md
    │   ├── dashboard.md
    │   └── review-captures.md
    ├── settings.json             # strict 권한 (커밋)
    └── settings.local.json       # 개인 오버라이드 (gitignore)
```

**3계층 매핑** — `data/raw/` = Raw Sources (Karpathy), `data/wiki/` = The Wiki, `SCHEMA.md` = The Schema. `data/writing/`은 wiki 합성을 위한 작업 공간으로, Karpathy 모델의 ingest를 사람·AI가 함께 운영하는 영역이다.

**`.gitignore` 핵심**:
```gitignore
/dashboard/
/.pkm/index.db
/.pkm/cache/
/.pkm/config.local.toml
/.claude/settings.local.json
__pycache__/
.venv/
*.pyc
.DS_Store
```

`data/` · `SCHEMA.md` · `.pkm/config.toml` · `.claude/settings.json` · `.claude/commands/` 는 **commit**.

---

## 3. CLI 명령 표면

### 3.1 설계 원칙

- 한 명령 = 한 결정론적 작업
- 기본 경로엔 LLM 호출 없음. 로컬 모델 호출(임베더/재랭커)은 OK. **옵트인 플래그**(`pkm search --expand` 등)에서만 AI CLI 셸아웃 허용 — SDK 미사용·API 키 미사용 원칙은 유지
- `--json` 모든 명령에 제공 (AI 파싱 친화). 깊이는 명령 성격에 차등:
  - **Read**(list/show/search/related): 풍부한 구조, 안정 스키마
  - **Mutate**(create/promote/set-status/rm): `{"ok":true,"id":...,"path":...,"git_commit":"..."}`
  - **부수효과**(log/reindex/dashboard build): `{"ok":true,"stats":{...}}`
  - **실패**: 종료코드 ≠ 0 + `{"ok":false,"error":{"code":"...","message":"...","hint":"..."}}`
- 부수효과 있는 명령은 자동 git 커밋 (옵션 `--no-git`은 권한 deny로 차단)

### 3.2 명령 그룹

#### 부트스트랩
```
pkm init                              # 빈 디렉토리에 data/.pkm/SCHEMA.md/.claude/ 스캐폴드
pkm bootstrap                         # 새 clone 환경 셋업: doctor --download → reindex → dashboard
pkm doctor [--download] [--json]      # 환경/데이터/인덱스/모델/AI CLI 헬스체크
pkm mode {strict|allow-wiki|show}     # 권한 모드 토글 (settings.local.json 조작)
```

#### 수집 (raw/captures/)
```
pkm capture create --slug SLUG [--url URL] [--from-file PATH] [--status draft|reviewed]
                                      # 본문은 stdin 또는 --from-file
pkm capture list   [--status STATUS] [--lang LANG] [--json]
pkm capture show   <id-or-slug>      [--json]
pkm capture set-status <id-or-slug> <status>
pkm capture rm     <id-or-slug>
```

#### 덩어리 (raw/chunks/)
```
pkm chunks new        <topic>             # 폴더 + README.md 스캐폴드
pkm chunks add        <topic> <file>...   # 자료 복사/이동
pkm chunks list       [<topic>] [--json]
pkm chunks show       <topic>             [--json]
pkm chunks set-status <topic> <collecting|curating|ready>
pkm chunks rm         <topic>
pkm extract           <file> [--out PATH] # PDF/HTML/docx → md
```

#### 승격 (raw/writing → wiki)
```
pkm promote <path> --to concepts|entities|notes|reports [--slug NEW_SLUG] [--keep-source]
                                      # raw/captures/* 또는 writing/* 만 받음. status 게이트.
pkm demote  <wiki-path>               # promoted_from 따라 복원
pkm wiki edit <wiki-path>             # CLI-매개 편집. 입력 모드:
                                      #   --replace (기본): stdin 전체 본문 (frontmatter 포함)으로 교체
                                      #   --patch:          stdin unified diff (git apply 호환). frontmatter 영역도 패치 가능.
                                      # 둘 다 무결성 검증(필수 frontmatter, 위키링크) 통과해야 쓰기. strict 모드에서도 가능.
pkm wiki set-status <wiki-path> <stub|active|deprecated>
```

#### RAG 검색
```
pkm search <query> [-n N]
                   [--scope wiki|raw|writing|all]
                   [--expand] [--no-rerank]
                   [--with-related]
                   [--explain] [--json]
                   # --expand: 옵트인. AI CLI 셸아웃으로 쿼리확장. 미지정 시 결정론.
pkm related <path> [--mode backlinks|semantic|both] [-n N] [--json]
```

#### 인덱싱 / 임베딩
```
pkm reindex db [<path>] [--full] [--scope wiki|raw|all] [--low-memory]
            # 기본: 증분 (content_hash 비교) — 변경 감지된 파일만 재임베딩.
            # <path>      : 특정 파일/글롭만 재임베딩 (예: pkm reindex db data/wiki/concepts/foo.md)
            # --scope     : 버킷 단위 enum (예: --scope wiki). <path>와 상호배타.
            # --full      : 처음부터 전부 재구축.
            # --low-memory: batch=4, reranker 무로드.
            # `db`는 typer 서브커맨드 — 후속 슬롯(예: `pkm reindex toc` 별칭) 확장용.
            # M2의 `pkm index rebuild`(TOC = data/index.md)와 별개 명령.
```

#### 로그 / TOC
```
pkm log append <message> [--type capture|promote|wiki-edit|...]
pkm log show   [--since DATE] [--type ...] [--json]
pkm index rebuild                     # data/index.md 재생성
```

#### 작성 (writing/)
```
pkm write new        --slug SLUG [--from-search QUERY | --from-chunks TOPIC] [--purpose guideline|report|summary|essay]
pkm write list       [--json]
pkm write set-status <id-or-slug> <draft|final|abandoned>
                                      # finalize는 별도 명령 없이 pkm promote 로 통합
```

#### 정합성 / 대시보드
```
pkm lint [--fix] [--errors-only] [--json]
pkm dashboard build [--out PATH]
pkm dashboard open                    # 빌드 + open
pkm dashboard clean
pkm bench [--docs N] [--real] [--json] # M7: 합성 N문서 인덱싱 + 검색 latency 측정 (soft 임계, 출력만)
```

### 3.3 의도적으로 추가하지 않은 명령

| 명령 | 대체 |
|---|---|
| `pkm get` / `pkm multi-get` | AI는 Read/Glob 직접 사용. ID→path 매핑이 필요하면 `pkm capture show --json` |
| `pkm git ...` | `git` 직접 호출. 자동 커밋만 내부 처리 |
| `pkm config get/set` | 공용 키는 `.pkm/config.toml` 직접 편집, 비공개 키(`exec`/`env`/credentials)는 `.pkm/config.local.toml`. AI가 Read/Edit |
| `pkm embed <single>` | `pkm reindex <path>`(positional)로 흡수 |
| `pkm write finalize` | `pkm promote`가 writing/* 도 받음 |
| `pkm chunks promote` | 단일 명령 X. `/write --from-chunks` 워크플로우만 |

---

## 4. AI 에이전트 통합

### 4.1 SCHEMA.md — 진실의 원천

`SCHEMA.md`는 AI 세션의 진입 매뉴얼이다. `pkm init`이 템플릿을 생성하고, 이후 사용자/AI가 진화시킨다.

**섹션 구성**
1. **Mission** — 6 레이어와 compounding wiki 철학
2. **Layout** — 디렉토리 구조와 의미
3. **Frontmatter** — 4종 스키마 (capture/chunk/wiki/writing)
4. **Workflows** — 6 레이어의 표준 절차 (capture/research/chunk-curate/promote/ask/write/write-from-chunks/lint/dashboard/review-captures)
5. **CLI Reference** — `pkm <cmd>` 치트시트
6. **Invariants** — "wiki/에 직접 쓰지 마라(promote 또는 wiki edit)", "log 누락 금지", "환각 금지"
7. **Anti-patterns** — 자주 발생하는 실수와 회피

**SoT 원칙**: 슬래시 커맨드는 SCHEMA의 워크플로우를 참조하고 짧게 요약만 한다. `pkm lint` 메타 룰(V2)이 SCHEMA의 워크플로우 이름과 `.claude/commands/` 매핑을 검증한다.

### 4.2 슬래시 커맨드 (`.claude/commands/*.md`)

| 커맨드 | 워크플로우 |
|---|---|
| `/collect <url\|text>` | WebFetch → 요약 → `pkm capture create --status draft` → log |
| `/research <topic>` | 다중 WebSearch+Fetch → 다수 캡처 일괄 생성 |
| `/promote` | `pkm capture list --status reviewed --json` → 검토 → `pkm promote --to ...` |
| `/ask <question>` | **Claude Code 자체 능력**으로 동작 (외부 AI CLI 불필요): `pkm search --json` → top-K Read → Claude 본인이 답변 합성. **Citation 계약** 준수 (아래) → (선택) 답변을 새 capture로 저장 |

#### `/ask` Citation 계약 (Karpathy 인용 grounding)

`/ask` 답변은 다음 규칙을 반드시 따른다:

1. **모든 사실 주장은 인용을 동반한다** — 문장 끝에 출처 경로를 대괄호로 표기.
   - 예: `OAuth refresh token은 httpOnly cookie에 저장한다 [data/wiki/concepts/oauth-token-storage.md].`
   - 다중 출처는 `[a.md][b.md]` 또는 `[a.md, b.md]`.
2. **검색 결과에 없는 내용은 주장하지 않는다.** 검색 결과 부족 시 정직하게 "wiki에 관련 내용이 부족합니다. 추가 수집이 필요합니다" 라고 답하고 종료.
3. **인용 경로는 실재해야 한다.** 환각 인용 금지. 답변 후 lint가 검증 가능하도록 `[wiki/...]` 패턴은 path-resolvable해야 한다.
4. **답변을 capture로 저장 시** (옵션 단계): 답변 본문이 그대로 `raw/captures/<slug>.md` 본문이 되며, frontmatter `derived_from: [...인용된 모든 경로]` 필수. 이렇게 저장된 capture는 promote 시 정상 wiki 페이지가 됨 (compounding).

**Anti-pattern**: "내가 알기로는...", "일반적으로는...", 인용 없는 일반 지식 — 모두 금지. PKM의 진실은 wiki에 있고 wiki에 없으면 답하지 않는다.
| `/write <topic>` | 검색 시드 또는 chunk 또는 freeform → writing/에 작성 → promote |
| `/lint [--fix]` | `pkm lint --json` → 보고/자동수리 |
| `/dashboard` | `pkm dashboard build` → 위치 안내 |
| `/review-captures` | draft 캡처 일괄 검토 → reviewed 또는 폐기 추천 |

각 슬래시 커맨드 파일은 5–10줄의 절차 + SCHEMA.md 섹션 참조. 길어지면 SCHEMA로 이동.

**병렬 실행 패턴** — 사용자가 `/ask` 등을 병렬로 돌리고 싶을 때 별도 CLI 추가 불필요. Claude Code의 자체 CLI를 Bash로 fork하면 됨:
```bash
# Claude Code 세션 안에서:
claude -p "/ask OAuth 토큰 저장"  &     # 백그라운드 실행, 다른 세션 fork
claude -p "/ask CSRF 방어"        &
wait
```
이 패턴은 `llm_bridge` Tier 2/3와 동일 메커니즘이며, `config.local.toml`의 `my-claude.exec`이 그대로 재사용된다. PKM 내부에 `pkm ask` CLI를 추가하지 않는다.

### 4.3 권한 — 두 모드

#### 모드 1: Strict (기본, 커밋)

`.claude/settings.json`:
```json
{
  "permissions": {
    "allow": [
      "Bash(pkm *)",
      "Read(./**)",
      "Write(./data/raw/**)", "Edit(./data/raw/**)",
      "Write(./data/writing/**)", "Edit(./data/writing/**)",
      "WebFetch", "WebSearch"
    ],
    "ask": ["Bash(rm *)", "Bash(git push *)"],
    "deny": [
      "Write(./data/wiki/**)", "Edit(./data/wiki/**)",
      "Bash(pkm * --no-git*)"
    ]
  }
}
```

→ wiki/* 직접 Write/Edit는 **deny**. 정책 C 강제. `--no-git` 우회도 차단.

#### 모드 2: Allow-wiki (옵트인)

`.claude/settings.local.json` (gitignore):
```json
{ "permissions": { "allow": ["Write(./data/wiki/**)", "Edit(./data/wiki/**)"] } }
```

토글:
```
pkm mode allow-wiki     # local 생성 + 세션 재시작 안내
pkm mode strict         # local 제거
pkm mode show           # 현재 모드 출력 (allow 시 경고)
```

#### Escape valve — `pkm wiki edit`

strict 모드에서도 wiki 작은 수정은 가능. CLI-매개:
1. frontmatter 보존/검증
2. 위키링크 무결성 확인
3. 쓰기 → 단일 파일 인덱스 갱신 → git 커밋
4. log.md 이벤트 추가

**3가지 wiki 수정 경로 정리**:
- `pkm promote` — 새 콘텐츠를 raw/* 또는 writing/*에서 wiki로
- `pkm wiki edit` — 기존 wiki 페이지 작은 수정 (strict OK)
- 직접 Edit/Write — `pkm mode allow-wiki` 후 (대량 리팩토링 비상시)

### 4.4 LLM 브리지 (3-tier 커스터마이징)

**Tier 1: 자동탐지** — `pkm/llm_bridge.py` 내장 프리셋. PATH에서 `claude`/`codex`/`gemini`/`ollama` 순서로 첫 발견 사용.

**Tier 2: TOML 선언적 커스텀** — **두 파일로 분리** (보안·이식성):

- **`.pkm/config.toml`** (커밋, 공용 디폴트만): bucket/indexing/memory boolean·숫자, AI CLI **이름 별칭만**. `exec`/`env`/credentials/머신경로 **금지**.
- **`.pkm/config.local.toml`** (gitignore, 개인 오버라이드): 실행 명령(`exec`)·환경변수(`env`)·timeout·credentials. 머신/계정마다 다름.

`.pkm/config.toml` (커밋):
```toml
[ai_cli]
default        = "my-claude"
fallback_order = ["my-claude", "codex", "gemini"]

[indexing]
embed_captures = false        # raw/captures/*.md 를 벡터 임베딩 포함할지 (FTS5는 항상 포함)
embed_chunks   = false        # raw/chunks/*/*.{md,extracted} 를 벡터 임베딩 포함할지
batch_size     = 16           # 임베딩 배치 (auto_throttle이 동적으로 축소 가능)

[memory]
auto_throttle   = true        # 가용 RAM 임계 미만 시 batch 축소
low_memory_mode = false       # true면 batch=4, reranker 무로드
```

`.pkm/config.local.toml` (gitignore, 비공개):
```toml
[ai_cli.commands.my-claude]
exec    = ["claude", "--model", "haiku", "-p", "{prompt}"]
input   = "arg"               # "arg" | "stdin" | "file:{path}"
timeout = 30
env     = { ANTHROPIC_LOG = "error" }

[ai_cli.commands.ollama-local]
exec    = ["ollama", "run", "qwen2.5:3b"]
input   = "stdin"
timeout = 120

[ai_cli.tasks]
expand_query = "ollama-local"
lint_summary = "my-claude"
```

**머지 규칙**: `local`이 `commit` 위에 덮어씀. 누락된 `commit` 키는 V1 코드 상수 기본값. 동일 섹션 충돌 시 `local` 우선.

**스키마 검증**: `pkm doctor`가 `config.toml`에 `exec`/`env`/credentials-패턴 키 발견 시 **에러** (잘못된 위치). 자동수정 제안: "이 키들은 `config.local.toml`로 옮기세요".

V1 표준 task 이름: `expand_query`, `lint_summary`. 새 task는 `[ai_cli.tasks]`(local)에 등록 후 코드에서 동일 이름 참조.

플레이스홀더: `{prompt}`, `{model}`, `{system}`. `input = "stdin"`이면 `{prompt}` 자리는 비우고 stdin 전달.

**Tier 3: 셸 훅 (escape valve)** — `.pkm/hooks/<task>.sh` 가 존재하고 실행권 있으면 Tier 2를 무시하고 우선 호출:
```bash
#!/usr/bin/env bash
prompt=$(cat)
echo "$prompt" | claude --model haiku -p - | jq -r '.text // .'
```

**Env override**: `PKM_AI_CLI=ollama-local pkm search "..." --expand`  
(env override는 한 회성. 영구 변경은 `config.local.toml`)

**해석 순서**: 훅 → config tasks → config default → 자동탐지 → 모두 실패 시 명확한 에러.

### 4.5 PKM 자체 스킬 미작성

이미 superpowers 스킬을 사용하므로 별도 PKM 스킬은 만들지 않는다. SCHEMA.md + 슬래시 커맨드 + `.claude/settings.json`로 충분.

---

## 5. 검색 & RAG 파이프라인

### 5.1 인덱싱 범위 정책

| 자료 | FTS5 (BM25) | 벡터 임베딩 |
|---|---|---|
| `data/wiki/**/*.md` | ✅ | ✅ (사용자 #3 정의: "실제 임베딩 할 지식") |
| `data/raw/captures/**/*.md` | ✅ | 옵션 (config) |
| `data/raw/chunks/**/*.{md,txt,extracted}` | ✅ | 옵션 |
| `data/writing/**/*.md` | ✅ | ❌ (작성 중은 검색만) |

**기본 `pkm search` 스코프 = wiki**. `--scope` 로 확장.

### 5.2 SQLite 스키마

```sql
CREATE TABLE documents (
  id INTEGER PRIMARY KEY,
  path TEXT UNIQUE NOT NULL,
  bucket TEXT NOT NULL,
  title TEXT, lang TEXT, status TEXT, source_url TEXT,
  frontmatter_json TEXT,
  content_hash TEXT,
  indexed_at TIMESTAMP
);

CREATE TABLE chunks (
  id INTEGER PRIMARY KEY,
  doc_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
  chunk_idx INTEGER,
  heading_path TEXT,
  text TEXT,
  token_count INTEGER
);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
  text, title UNINDEXED,
  content='', tokenize='trigram'
);

CREATE VIRTUAL TABLE chunks_vec USING vec0(
  chunk_id INTEGER PRIMARY KEY,
  embedding FLOAT[1024]
);

CREATE VIRTUAL TABLE docs_vec USING vec0(
  doc_id INTEGER PRIMARY KEY,
  embedding FLOAT[1024]
);

CREATE TABLE links (
  src_doc_id INTEGER, dst_doc_id INTEGER,
  kind TEXT                       -- 'wikilink' | 'derived_from' | 'tag'
);

CREATE TABLE schema_version (version INTEGER NOT NULL);
```

### 5.3 청킹 전략

```
입력 마크다운
  ├── frontmatter 분리 (메타로 보관, 청크엔 미포함)
  ├── 헤딩 트리 파싱 (h1/h2/h3 경로 보존)
  ├── 헤딩 단위 1차 split
  ├── 큰 섹션은 ~500 token 목표 (15% overlap, qmd 표준)
  ├── 한국어: ~700 chars 기준 (token≈char 대응 안 됨)
  └── 문장경계: `[.!?。]\s` + 한국어 종결어미 `[다라네요까]\.\s`
출력: chunks[] with (heading_path, text, token_count)
```

### 5.4 검색 파이프라인

```
query
 │
 ├──[1] 쿼리확장 (옵션, **기본 OFF** — `--expand`로 옵트인)
 │      → AI CLI 셸아웃 (task=expand_query)
 │      → "원 쿼리 + 영문변환 + 패러프레이즈" 2-3개
 │      → 실패 시: hard-fail (exit≠0, EXPAND_FAILED) — 우회는 `--expand` 미지정으로
 │      → **기본 검색은 모델만 호출하는 결정론** (BM25 + 벡터 + RRF + 재랭킹)
 │
 ├──[2] 병렬 검색 (각 변형마다)
 │      ├─ BM25 (FTS5 + bm25()) top-50
 │      └─ 벡터 (bge-m3 임베딩 → vec0 코사인) top-50
 │      → N개 변형 × 2 retriever = 총 2N개의 ranked list
 │
 ├──[3] RRF 융합  score(d) = Σ_lists 1/(k + rank(d))   (k=60)
 │      → 2N개 ranked list 전체를 한 번에 융합 (변형 간 hit 누적이 점수 가산됨)
 │      → top-30 후보
 │
 ├──[4] 재랭킹 (옵션, 기본 ON)
 │      → bge-reranker-v2-m3 cross-encoder
 │      → query×chunk 점수, position-aware 블렌딩 (qmd: 고신뢰 retrieval 보존)
 │
 └──[5] top-K (기본 10) + 모든 점수 노출
```

CLI:
```bash
pkm search "OAuth 토큰 저장" --scope wiki -n 10 [--expand] [--no-rerank] [--with-related] [--explain] [--json]
```

JSON 출력 예:
```json
{
  "ok": true,
  "query": "OAuth 토큰 저장",
  "expanded": ["OAuth token storage", "토큰 보관 방식"],
  "scope": "wiki",
  "results": [{
    "path": "data/wiki/concepts/oauth-token-storage.md",
    "chunk_idx": 2,
    "heading_path": ["OAuth 토큰 저장", "보안 권고"],
    "snippet": "...refresh token은 httpOnly secure cookie...",
    "scores": {"bm25": 0.82, "vector": 0.91, "rrf": 0.064, "rerank": 0.95, "final": 0.93},
    "frontmatter": {"title": "...", "lang": "ko", "tags": ["auth"]}
  }]
}
```

### 5.5 한국어 처리

| 영역 | 선택 | 이유 |
|---|---|---|
| 임베딩 | `BAAI/bge-m3` (1024d, multilingual) | 한국어 강하고 다국어 단일 모델 |
| 재랭킹 | `BAAI/bge-reranker-v2-m3` | 동일 패밀리 cross-encoder |
| FTS5 토크나이저 | `tokenize='trigram'` | 외부 의존 0, CJK 안정 동작 |
| 형태소 분석기 | **MVP 미사용** (V2: Kiwi/KOMORAN 옵션) | trigram + 벡터로 충분 |
| 문장경계 | 영문 + 한국어 종결어미 패턴 | 청킹 정확도 |

### 5.6 모델 관리

- 캐시: `~/.cache/pkm/models/` (qmd 관습)
- 첫 실행: `pkm doctor --download` 또는 `pkm reindex`가 자동 다운로드 + 진행률
- GPU 자동감지(CUDA/MPS), 없으면 CPU. CPU도 검색 응답에 충분
- 디스크: bge-m3(~600MB) + reranker(~600MB) ≈ 1.2GB

### 5.7 실패 모드 — Hard-fail by default

| 상황 | 동작 |
|---|---|
| `--expand` 지정 → AI CLI 호출 실패 | exit≠0, `EXPAND_FAILED`. 옵트인이므로 미지정이 기본 |
| 재랭킹 활성 → 모델 로드 실패 | exit≠0, `RERANK_MODEL_MISSING`. `--no-rerank` 우회 |
| 임베딩 모델 미존재 | exit≠0, `EMBED_MODEL_MISSING` + `pkm doctor --download` 안내 |
| 인덱스 비어있음 | exit≠0, `INDEX_EMPTY` + `pkm reindex db` 안내 |
| 인덱스 손상 | `pkm doctor` 감지 → `pkm reindex db --full` 권장 |

**사전 점검**: `pkm doctor` 가 호출 전 모델/AI CLI/DB 상태 보고:
```
✓ index.db        OK (4,231 chunks)
✓ bge-m3          OK
✗ bge-reranker    MISSING — run: pkm doctor --download
~ AI CLI          OPTIONAL (claude detected, task=expand_query) — `pkm search --expand` 옵트인 시에만 필요
```

`pkm doctor` 종료코드:
- 기본: **항상 exit 0** (상태 리포트). 누락이 있어도 정상 종료. 대시보드 빌드가 내부 호출해도 안전.
- `pkm doctor --strict`: 누락 1개라도 있으면 exit ≠ 0 (CI/사전 검증용).

`pkm doctor --json` 출력 계약 (대시보드 `status.html`이 그대로 렌더하므로 보안 경계):
```json
{
  "ok": true,
  "items": [
    {"name": "index.db",      "status": "ok",       "detail": "4,231 chunks"},
    {"name": "bge-m3",        "status": "ok",       "detail": null},
    {"name": "bge-reranker",  "status": "missing",  "detail": null},
    {"name": "ai_cli",        "status": "optional", "detail": "detected: claude"}
  ],
  "system": {"ram_total_gb": 16, "ram_available_gb": 8.2, "recommended_batch_size": 32}
}
```

**필드 화이트리스트 — 절대 미포함**:
- `exec` 명령어 배열, `env` 값, 절대경로 (홈 디렉토리/사용자명 노출 금지)
- credentials, API 키, 토큰 패턴 일체
- AI CLI는 **`detected`/`missing` boolean + 식별자**만 (`detail` 에 `claude`/`codex`/`gemini` 이름까지). 실행 명령은 미노출.

> 이 계약은 `status.html` 보안 스토리의 종결자다 — config 마스킹 + doctor 화이트리스트 둘 다 통해야 leak 표면 0.

### 5.8 관계도 (3-layer) + `--with-related`

| 레이어 | 출처 | 비용 | 사용처 |
|---|---|---|---|
| **명시적 그래프** (`links` 테이블) | `[[wikilink]]` 본문 + frontmatter (`derived_from`/`related`/`tags`) | 낮음 | `pkm related --mode backlinks`, 대시보드 |
| **의미적 이웃** | 문서 단위 평균 임베딩 → top-N 코사인 (사전계산, `docs_vec`) | 중간 (재인덱싱 1회) | `pkm related --mode semantic` |
| **검색-시점 풍부화** | 위 둘을 검색 결과에 합성 (opt-in `--with-related`) | 거의 0 | `pkm search --with-related` |

`--with-related` 출력 추가:
```json
"related": {
  "wikilinks_out": ["..."],
  "wikilinks_in":  ["..."],
  "derived_from":  ["..."],
  "tags":          ["auth"],
  "semantic_neighbors": [{"path":"...","similarity":0.78}]
}
```

V2 확장 슬롯: 그래프 시각화, 인용 그래프, 콘셉트 클러스터링, orphan 감지.

---

## 6. 승격 & Lint 정책

### 6.1 Frontmatter 스키마 (4종)

#### Capture — `data/raw/captures/*.md`
```yaml
---
title: "..."
slug: 2026-05-01-foo
created_at: 2026-05-01T10:00:00+09:00
status: draft           # draft → reviewed → archived
source_type: url        # url | text | research
source_url: "https://..."
fetched_at: 2026-05-01T10:00:00+09:00
lang: ko                # ko | en | mixed
tags: [auth, security]
summary: "한 줄 요약"
---
```

#### Chunk README — `data/raw/chunks/<topic>/README.md`
```yaml
---
topic: oauth-deep-dive
created_at: ...
status: collecting      # collecting → curating → ready
description: "이 덩어리의 의도/범위"
sources: [paper-1.pdf, article-2.md]
tags: [auth, security]
lang: mixed
---
```

#### Wiki — `data/wiki/<bucket>/*.md`
```yaml
---
title: "OAuth Token Storage"
slug: oauth-token-storage
bucket: concepts        # concepts | entities | notes | reports
created_at: ...
updated_at: ...
status: active          # stub → active → deprecated
promoted_from: data/raw/captures/2026-05-01-oauth-token-storage.md
derived_from: [data/wiki/concepts/jwt.md]
related: [data/wiki/concepts/csrf.md]
tags: [auth, security]
lang: ko
---
```

#### Writing — `data/writing/*.md`
```yaml
---
title: "팀 OAuth 가이드라인"
slug: team-oauth-guideline
created_at: ...
updated_at: ...
status: draft           # draft → final → promoted | abandoned
purpose: guideline      # guideline | report | summary | essay
derived_from: [data/wiki/concepts/oauth-token-storage.md]
search_seed: "OAuth 토큰 저장"
tags: [auth]
lang: ko
---
```

### 6.2 Status 전이

```
[capture]    draft ──reviewed── reviewed ──promote── (wiki 사본, 원본 → archived)
                          ↘
                           archived

[chunk]      collecting ── curating ── ready
                              (ready여야 chunk-합성 권장)

[wiki]       stub ──active── active ──deprecated── deprecated

[writing]    draft ──final── final ──promote── (wiki 사본)
                ↘
                 abandoned
```

### 6.3 승격 게이트 — `pkm promote`

| 입력 경로 | 게이트 | 결과 |
|---|---|---|
| `raw/captures/*.md` | `status == reviewed` + 필수 frontmatter | wiki 사본, 원본 status→archived (`--keep-source`로 유지) |
| `writing/*.md` | `status == final` + `derived_from` 모두 실재 (wiki/* 또는 raw/* 경로 허용) | wiki 사본, writing status→promoted |
| `raw/chunks/<topic>` | **거부** | "AI에게 합성 요청 → writing/* 거쳐 promote" 안내 (워크플로우 SCHEMA § "Chunk → Wiki Synthesis") |
| `wiki/*.md` | **거부** | `pkm wiki edit` 사용 안내 |

실패 예:
```json
{"ok": false, "error": {"code": "STATUS_NOT_REVIEWED", "current": "draft",
                        "hint": "pkm capture set-status <id> reviewed 후 재시도"}}
```

### 6.4 Demote — `pkm demote <wiki-path>`

- `promoted_from` 추적 → 원본 위치로 복원 (또는 status reviewed로 되돌림)
- `derived_from`만 있고 단일 출처가 아니면 → 사용자에게 행선지 묻기 (`--target` 명시 가능)
- 인덱스/링크 정리 + git 커밋 + log

### 6.5 Lint 룰 — `pkm lint [--fix]`

#### Errors (블록킹)
| 코드 | 검사 | 자동수정 |
|---|---|---|
| `MISSING_FIELD` | 필수 frontmatter 필드 누락 | 일부 (created_at: mtime, slug: title 케밥) |
| `INVALID_VALUE` | enum 값 위반 | ✗ |
| `DUPLICATE_SLUG` | 같은 bucket 내 slug 중복 | ✗ |
| `BROKEN_WIKILINK` | `[[x]]`의 x 미존재 | ✗ |
| `BROKEN_DERIVED_FROM` | 참조 경로 미존재 | ✗ |
| `ORPHAN_PROMOTED_SOURCE` | wiki에 promoted_from 가리키는 raw가 status≠archived | ✓ (archived 처리) |

#### Warnings
| 코드 | 검사 |
|---|---|
| `STALE_DRAFT` | capture status=draft 30일+ |
| `STALE_STUB` | wiki status=stub 30일+ |
| `ORPHAN_WIKI` | 인커밍 위키링크/derived_from/태그 모두 없음 |
| `LARGE_CHUNK_NEVER_PROMOTED` | chunk topic 60일+ ready인데 wiki 자취 없음 |
| `LANG_INCONSISTENT` | 본문 언어 ≠ frontmatter lang (휴리스틱) |
| `RAW_BODY_MUTATED` | raw 파일이 status=reviewed 이후 본문 해시 변경됨 (immutability 위반 감지) |
| `BROKEN_CITATION` | wiki 본문의 `[path]` 인용이 실재하지 않는 경로 (Karpathy citation grounding) |

#### V2 Lint 룰 슬롯 (`pkm lint --deep`, LLM-매개)
| 코드 | 검사 | 구현 시점 |
|---|---|---|
| `CONTRADICTION` | 같은 사실에 대해 wiki 페이지 간 충돌하는 주장 (예: "X는 A다" vs "X는 B다") | V2+. AI CLI 셸아웃으로 페어와이즈 비교 |
| `DATA_GAP` | wiki에서 빈번히 인용되는 개념인데 해당 페이지가 stub/없음. 또는 frontmatter `related:`가 가리키는 미존재 토픽 | V2+. 그래프 분석 + LLM 판단 |
| `STALE_CLAIM` | 페이지의 사실 주장이 더 최근 capture/source와 충돌할 가능성 | V2+. 시간축 + 의미 비교 |

V1은 결정론 lint만 ON. `--deep`는 V2에서 AI CLI 옵트인 셸아웃으로 추가 (실패 시 hard-fail 동일 정책).

#### 통합
- `/lint` 슬래시 → `pkm lint --json` → AI 보고/일부 자동수리
- 대시보드 1면에 lint 상태 노출
- (옵션) git pre-commit 훅: `pkm lint --errors-only` 실패 시 커밋 거부

### 6.6 자동 부수효과 (모든 mutate 명령)

1. 인덱스 갱신 (해당 파일만, 증분)
2. `data/index.md` 재생성 (TOC)
3. `data/log.md`에 이벤트 append
4. git 자동 커밋 (`--no-git`은 deny로 차단)

### 6.7 워크플로우 SoT — SCHEMA.md

**3-tier 문서 위치**:
| 곳 | 역할 | 분량 |
|---|---|---|
| `SCHEMA.md § Workflows` | 진실의 원천 | 길게 |
| `.claude/commands/<n>.md` | 실행 트리거 + SCHEMA 참조 | 짧게 |
| CLI `--help` / 에러 메시지 | 즉석 안내 | 한 줄 |

drift 방지: 슬래시 커맨드는 5–10줄 제한, 길어지면 SCHEMA로. (V2) `pkm lint`가 워크플로우 이름과 명령 매핑을 검증.

#### chunk → wiki 합성 워크플로우 (SCHEMA § 6, 단일 CLI 없음)

```
1. pkm chunks show <topic> --json
2. AI: 자료 Read (PDF면 pkm extract 먼저)
3. pkm write new --slug <s> --purpose summary
4. AI: 본문 채움. derived_from에 chunks 자료 경로 기재
5. 사용자 검토 → status: final
6. pkm promote data/writing/<s>.md --to concepts
```

---

## 7. 대시보드

### 7.1 빌드 스택

| 항목 | 선택 |
|---|---|
| md → HTML | Python `markdown` 라이브러리 |
| 템플릿 | Jinja2 |
| 스타일 | 단일 CSS 파일 (~3KB), 다크모드 토글 |
| JS | 단일 JS 파일 (~5KB), 클라이언트 사이드 필터링/검색만 |
| 외부 CDN | 없음 (오프라인 동작) |
| 빌드 트리거 | `pkm dashboard build` (수동). git post-commit 훅으로 자동화 가능 |

### 7.2 페이지 구성

```
dashboard/
├── index.html         # 홈: 개요 + 최근 활동 + lint 상태
├── captures.html      # raw/captures 목록
├── chunks.html        # raw/chunks 토픽
├── wiki.html          # wiki/* 브라우즈 (bucket·tag 그룹)
├── writing.html       # writing/* 목록
├── search.html        # 클라이언트 사이드 메타 검색
├── help.html          # SCHEMA.md 렌더링 + CLI 치트시트
├── status.html        # doctor + config 가시화
├── doc/<path>.html    # 개별 문서 (백링크/이웃/provenance 포함)
├── search-index.json
├── assets/{style.css,search.js}
└── (graph.html — V2)
```

### 7.3 페이지 핵심

- **`index.html`** — 한눈 통계, lint 요약, 최근 log 20개, 빠른 링크
- **목록 페이지** — 필터바(status/lang/tags/bucket) + 표 + 상세 링크
- **`doc/<path>.html`** — frontmatter 사이드바 + 본문 렌더 + Backlinks/Outgoing/Semantic neighbors/Provenance
- **`search.html`** — 클라이언트 substring + 태그 매칭. 진지한 검색은 터미널 `pkm search`
- **`help.html`** — SCHEMA.md 렌더 + 자동수집 CLI help
- **`status.html`** — `pkm doctor --json` 렌더 + config (시크릿 마스킹) + 모드

### 7.4 빌드 파이프라인

```python
# 의사코드
def build(out_dir):
    docs       = scan_all_documents()
    lint_json  = run("pkm lint --json")
    doctor_json= run("pkm doctor --json")
    config     = read_toml(".pkm/config.toml")    # local.toml 미로드 — 대시보드는 공용만 표시
    log_recent = read_recent_log(20)
    links      = query_links_table()
    sem_nbrs   = query_doc_neighbors()

    write_index_html(...)
    write_list_html(captures/chunks/wiki/writing)
    write_doc_pages(docs, links, sem_nbrs)
    write_search(docs)        # search.html + search-index.json
    write_help(load("SCHEMA.md"), collect_cli_help())
    write_status(doctor_json, config, current_mode())
    copy_assets()
```

특징: 재현가능 / 빠름(< 1초 수천 문서) / 모델·AI CLI 미설치여도 빌드 가능.

### 7.5 보안 / gitignore

- `dashboard/`는 빌드 산출물 → **gitignore**
  - 이유: (1) 재생성 가능, (2) 디스크/히스토리 비대화, (3) 우발적 공유 표면 축소
- `.pkm/index.db`도 동일 이유로 gitignore (벡터/FTS 인덱스에 본문 단편 포함)
- 대시보드 `status.html`은 `.pkm/config.toml`(공용 커밋본)만 렌더. `.pkm/config.local.toml`은 **절대 렌더 안 함**.
- 추가 방어: 공용 config에서도 `secrets.*` / `*_token` / `*_key` / `*_password` 패턴 키는 `***` 마스킹 (defense in depth)

### 7.6 새 PC에서 복원

```bash
git clone <repo> && cd <repo>
uv sync
pkm bootstrap          # doctor --download → reindex --full → dashboard build
                       # AI CLI 불필요 — 위 단계 모두 모델·DB 작업뿐.
                       # /ask 도 Claude Code 자체로 동작 (외부 AI CLI 불필요).
                       # `pkm search --expand` 옵트인을 쓰려는 경우만 별도로
                       # claude/codex/gemini 중 하나 설치·인증 후 config.local.toml 작성.
open dashboard/index.html
```

첫 1회 모델 다운로드(~1.2GB) 후 캐시. 이후 clone부터 모델 다운 0.

GH Pages 배포가 필요하면 별도 브랜치(`dashboard-build`) 또는 별도 레포로 분리.

### 7.7 V2 확장 슬롯

- `graph.html` 시각화 (D3 force-directed)
- 인터랙티브 SPA (Vite/React) 마이그레이션
- 라이브 모드 (파일감시 + LiveReload)
- 활동 히트맵, 태그 네트워크

---

## 8. 테스트 & 신뢰성

### 8.1 5층 피라미드

```
                    ┌──────────────────────┐
                    │ E2E 시나리오 (소수)    │  ← slow, 실모델, 격리
                    ├──────────────────────┤
                    │ 워크플로우 통합        │  ← capture→promote→search 전체
                    ├──────────────────────┤
                    │ CLI 명령 통합          │  ← `pkm <cmd>` 단위, tmpdir
                    ├──────────────────────┤
                    │ 모듈 단위 (다수)        │  ← frontmatter/RRF/슬러그
                    ├──────────────────────┤
                    │ 정적 (lint/typecheck)  │  ← ruff, pyright/mypy
                    └──────────────────────┘
```

### 8.2 stub 임베더 (테스트 핵심)

```python
def stub_embed(text: str) -> np.ndarray:
    h = hashlib.sha256(text.encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(h[:8], "big"))
    v = rng.standard_normal(1024).astype("float32")
    return v / np.linalg.norm(v)
```
빠름·결정론. `PKM_TEST_STUB_EMBEDDER=1` 환경변수로 활성화 (conftest 기본 ON).

### 8.3 메모리 안전장치

#### 테스트 시
| 안전장치 | 어떻게 |
|---|---|
| stub 임베더 기본 | conftest에서 환경변수 자동 셋 |
| slow 마크 격리 | `pytest -m "not slow"` 기본 |
| 슬로우 직렬 실행 | `-n 0` (병렬 금지) |
| 모델 1회 로드 + 명시 해제 | `@pytest.fixture(scope="session")` + 종료 시 `del + gc + cuda.empty_cache` |
| 단위 timeout | `pytest-timeout` 300s/600s |
| 프로세스 격리 (slow) | `pytest-forked` |
| RSS 상한 (Unix) | conftest에서 `resource.setrlimit(RLIMIT_AS, 4GB)` |
| 메모리 모니터 | `--memcheck` (tracemalloc) 회귀 감지 |

CI 호출:
```bash
pytest -n auto -m "not slow"                          # 일상
pytest -m slow -n 0 --forked --timeout=600            # 슬로우 (별도 워크플로우)
```

#### 런타임 시
| 안전장치 | 어떻게 |
|---|---|
| 인덱싱 배치 크기 | `[indexing] batch_size` (config.toml), 기본 16 (보수적) |
| 가용 RAM 모니터 | `psutil.virtual_memory()` — 임계 < 1GB 시 batch 자동 축소 + warn |
| 재랭커 lazy load | 검색 시만 로드, 종료 시 unload |
| 동시 메모리 회피 | 인덱싱 중 reranker 무로드, 검색 중 임베더 후 reranker 순차 |
| `--low-memory` 모드 | batch=4, reranker 무로드 |
| OOM 가드 | `MemoryError` 자동 batch 축소 + 재시도 |
| `pkm doctor` 권장 | 시스템 RAM 표시 + 권장 batch_size 제안 |

**핵심 약속**: "어떤 명령이든 PC를 다운시키지 않는다. 메모리 부족이 감지되면 자동 throttle, 그래도 부족하면 명시적 에러로 종료."

### 8.4 실패 모드 테스트 (100% 커버)

| 시나리오 | 기대 |
|---|---|
| AI CLI 없음 → `pkm search` 기본 (확장 OFF) | 정상 (확장 안 함, 결정론) |
| AI CLI 없음 → `pkm search --expand` | exit≠0, `EXPAND_FAILED` |
| 임베딩 모델 미설치 → `pkm search` | exit≠0, `EMBED_MODEL_MISSING` + 안내 |
| `pkm promote` on draft | exit≠0, `STATUS_NOT_REVIEWED` |
| `pkm promote` on chunks/ folder | exit≠0, `/write --from-chunks` 안내 |
| `pkm wiki edit` with broken wikilink | exit≠0, `BROKEN_WIKILINK` |
| Wiki/* 직접 Write (strict) | Claude Code deny |
| `pkm * --no-git` 시도 | settings deny 차단 |

### 8.5 한국어 특화 테스트

- 한국어 본문 청킹: 종결어미 분리 + ~700자 목표
- FTS5 trigram 한글 검색: "OAuth 토큰" → "OAuth 토큰 저장" hit
- 다국어 혼합 frontmatter `lang: mixed` 처리
- 한글 슬러그 옵션 (한글 유지 또는 로마자)
- (slow) bge-m3 한국어 의미 hit

### 8.6 신뢰성 (런타임)

- **원자성**: tmp 쓰기 → atomic rename → DB 트랜잭션 → git commit
- **멱등성**: `pkm reindex --full` 동일 데이터 = 동일 결과 (해시 안정). 같은 slug 재호출은 `--force` 없이 거부
- **Crash recovery**: Git이 WAL — 마지막 커밋 = 일관 상태. DB 손상 시 `pkm doctor` 감지 → `pkm reindex --full`로 재구성
- **관측성**: `pkm doctor`, `pkm log show`, git history
- **마이그레이션**: `schema_version` 테이블, V2에 `pkm migrate`

### 8.7 CI 파이프라인

```yaml
on: [push, pull_request]
jobs:
  fast:
    - ruff check
    - pyright
    - pytest -n auto -m "not slow" --memcheck
    - dashboard 빌드 스모크
  slow:                    # 매일 1회 또는 수동
    - 모델 캐시 복원
    - pytest -m slow -n 0 --forked --timeout=600
```

Python 매트릭스: 3.11, 3.12.

### 8.8 테스트 fixtures

```
tests/fixtures/sample-pkm/
├── data/
│   ├── raw/captures/    # 5-10개, ko/en
│   ├── raw/chunks/      # 2 토픽
│   ├── wiki/concepts/   # 5-10개, 위키링크
│   ├── writing/         # 2 드래프트
│   ├── log.md, index.md
├── SCHEMA.md
└── .pkm/config.toml
```

### 8.9 의도적 비-테스트 (YAGNI)

- 실 AI CLI의 응답 품질 (제어 불가)
- 임베딩 모델 자체의 정확도 (벤더 책임)
- Windows: best-effort. 우선 macOS + Linux

### 8.10 커버리지 목표

| 영역 | 목표 |
|---|---|
| 모듈 단위 | 90%+ |
| CLI 명령 | 80%+ (모든 서브커맨드 1개 이상) |
| 실패 모드 | **100%** (모든 에러코드에 테스트) |
| E2E | 핵심 5개 (capture/promote/ask/write/lint) |

---

## 9. V1 (MVP) vs V2+ + 마일스톤

### 9.1 V1 스코프 — "완전한 6 레이어, 단순한 부가기능"

| 영역 | V1 포함 |
|---|---|
| 부트스트랩 | `pkm init`, `pkm bootstrap`, `pkm doctor`, `pkm mode` |
| #1 수집 | `pkm capture *`, `/collect`, `/research` |
| #2 덩어리 | `pkm chunks *`, `pkm extract` (PDF/HTML→md) |
| #3 wiki | `pkm promote`, `pkm demote`, `pkm wiki edit` |
| #4 RAG | `pkm search` 풀하이브리드, `pkm related`, `--with-related` |
| #5 작성 | `pkm write *`, `/write`, `/write --from-chunks`, `/write --from-search` |
| #6 대시보드 | 정적 HTML 8페이지 (graph 제외), 클라이언트 메타 검색, help, status |
| AI 통합 | SCHEMA.md 템플릿, 슬래시 8개, strict 권한 + allow-wiki opt-in |
| 한국어 | bge-m3, bge-reranker-v2-m3, FTS5 trigram, 종결어미 청킹 |
| LLM 브리지 | 자동탐지 + TOML 커스텀 + 훅 escape + env override |
| 인프라 | SQLite + sqlite-vec, 자동 git, log/index 자동 갱신 |
| 정합성 | `pkm lint` (errors+warnings+ --fix), 4종 frontmatter |
| 신뢰성 | 5층 테스트, 메모리 안전(stub 기본/slow 격리/동적 throttle/--low-memory) |

### 9.2 V2+ 명시적 보류

| 항목 | 보류 이유 |
|---|---|
| `graph.html` 시각화 (D3) | `links`/`docs_vec`은 V1에 다 있음. 시각화는 분리 가능 |
| Live 대시보드 (파일감시+LiveReload) | 정적 빌드로 충분 |
| 인터랙티브 SPA (Vite/React) | 단일 HTML로 충분 |
| Citation 그래프 (writing→wiki) | `derived_from`은 이미 존재. UI 노출만 V2 |
| 한국어 형태소 분석기 (Kiwi/KOMORAN) | trigram + 벡터로 MVP 충분 |
| 스키마 마이그레이션 명령 | V1 스키마 안정 |
| 메트릭 익스포터 | `pkm doctor`로 충분 |
| 활동 히트맵 / 태그 네트워크 | 대시보드 페이지 추가만 |
| MCP 서버 | **사용자 명시적 제외** |
| 멀티유저 / 동기화 / 클라우드 | 솔로 PKM 범위 밖 |
| 데몬 모드 (모델 상주) | 본인 PC에서 응답시간 충분 시 불필요 |

→ V2 추가 시 **데이터/스키마 변경 거의 없이** UI/명령만 추가.

### 9.3 마일스톤 (8주 솔로 가정)

| 기간 | 단계 | 산출물 |
|---|---|---|
| Week 1-2 | 기반 | 패키지 스캐폴드, frontmatter/files store, init/doctor, CI 스켈레톤, 테스트 스캐폴드 |
| Week 2-3 | 수집·덩어리 | capture/chunks 명령, log/index 자동갱신, /collect /research |
| Week 3-4 | 인덱싱·검색 | SQLite+sqlite-vec, FTS5 trigram, bge-m3, 검색 파이프라인, 메모리 가드 |
| Week 4-5 | 승격·정합성 | promote/demote/wiki edit/mode, lint, /promote /lint |
| Week 5-6 | AI·작성 | LLM 브리지, 쿼리확장, 재랭킹, write 명령, /ask /write |
| Week 6-7 | 대시보드 | 정적 빌더, 8페이지, help/status, search.html, bootstrap, dashboard |
| Week 7-8 | 하드닝 | 실패모드 100%, E2E, 메모리 강화, 문서화 |

각 마일스톤 끝에 **사용 가능한 누적 빌드** + 작은 데모.

### 9.4 V1 수락 기준

- [ ] 6개 사용자 기능이 슬래시 1개 + CLI 1-3개 조합으로 모두 가능
- [ ] 새 PC `git clone → uv sync → pkm bootstrap` 만으로 동작
- [ ] 한국어 100문서 인덱싱 5분 이내, 검색 응답 < 2s (CPU)
- [ ] `pkm doctor` 모두 ✓
- [ ] 빠른 테스트 < 2분, 느린 테스트 < 10분, RAM 4GB 이내
- [ ] 실패 모드 에러코드 모두 테스트 보유
- [ ] README + SCHEMA.md 템플릿 + dashboard help.html 충분
- [ ] strict 모드 wiki 직접 쓰기 거부 확인
- [ ] 모든 mutate에서 자동 git 커밋, `--no-git` 우회 deny 확인
- [ ] Claude Code 세션에서 `/ask` 전체 흐름 동작 (외부 AI CLI 없이 — pkm search → Read → Claude 합성)
- [ ] (옵션) AI CLI 1종 설치·인증 후 `pkm search --expand` 옵트인 흐름 동작

### 9.5 위험 & 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| bge-m3+reranker 1.2GB 다운로드 마찰 | 첫 사용 경험 저하 | `pkm doctor --download` 명시 단계, 진행률, 캐시. `--minimal` 옵션으로 작은 다국어 모델 |
| AI CLI 플래그 다양성 | 셸아웃 호환성 | TOML 프리셋 동봉 + 훅 escape valve. doctor 시도 검증 |
| FTS5 trigram 한국어 정밀도 부족 | 키워드 검색 누락 | 벡터 검색 보완. V2 Kiwi 옵션 |
| sqlite-vec 신생 (성숙도) | 의존성 안정성 | 버전 핀, JSON 백업 마이그레이션. 최악 시 FAISS 대체 |
| 큰 코퍼스 인덱싱 시간/메모리 | 첫 reindex 경험 | 배치 throttle + 증분 + `--low-memory` |
| `--no-git` deny 디버깅 마찰 | 개발 마찰 | V1: 단순 settings 편집. V2 `pkm dev` 모드 |

### 9.6 남은 결정 (현 시점 미확정)

| 결정 | 후보 | 권장 |
|---|---|---|
| 라이선스 | MIT / Apache-2.0 / BSL-1.1 | **MIT 또는 Apache-2.0** |
| 배포 | PyPI / pip from git / brew | V1: pip from git (`uv tool install ...`). V2: PyPI |
| CLI 이름 | `pkm` / 고유 브랜드 | **`pkm` 유지** |
| Python 버전 | 3.11+ / 3.12+ | **3.11+** |

README 작성 시점에 확정.

---

## 10. 부록

### 부록 A. 용어

| 용어 | 정의 |
|---|---|
| Capture | 외부에서 들어온 단편 노트 (URL+요약, 웹리서치 결과). raw/captures/ |
| Chunk | 사용자가 폴더 단위로 모은 자료 묶음. raw/chunks/<topic>/ |
| Wiki | 검토·승격된 canonical 지식. 임베딩 대상. wiki/{concepts,entities,notes,reports}/ |
| Writing | AI가 wiki 자료를 합성해 만드는 새 문서. writing/ |
| Promotion | raw/captures 또는 writing의 reviewed/final 콘텐츠를 wiki로 옮기는 행위 |
| Demotion | promotion 되돌리기 |
| RRF | Reciprocal Rank Fusion. BM25와 벡터 결과 융합 |
| Hard-fail | 실패 시 종료코드 ≠ 0 + 명확한 에러. silent fallback 금지 |
| Stub embedder | 테스트용 결정론적 가짜 임베더 (해시→고정벡터) |

### 부록 B. 의존성 핀 (제안)

```
python >= 3.11
typer or click
pyyaml, python-frontmatter
markdown, jinja2
sqlite-vec >= 0.1
sentence-transformers >= 2.7
psutil
pdfplumber, markdownify (extract용)
pytest, pytest-timeout, pytest-forked, pytest-xdist
ruff, pyright (or mypy)
```

GPU 옵션: `torch` (CUDA/MPS 자동). CI는 CPU.

### 부록 C. 참고

- Karpathy, *LLM Wiki* gist — https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- KiwiFS — https://github.com/kiwifs/kiwifs
- qmd — https://github.com/tobi/qmd
- Reciprocal Rank Fusion (Cormack et al., 2009)
- BAAI/bge-m3 — https://huggingface.co/BAAI/bge-m3
- BAAI/bge-reranker-v2-m3 — https://huggingface.co/BAAI/bge-reranker-v2-m3
- sqlite-vec — https://github.com/asg017/sqlite-vec

### 부록 D. 선택 통합 (V2 또는 사용자 재량)

V1 코드와 직접 통합 안 하지만, 사용자가 활용 가능한 외부 도구들. 모두 마크다운 + git 기반이라 **자연스럽게 호환**.

#### D.1 Obsidian as 뷰어/에디터
- `data/`를 Obsidian vault로 그대로 열면 작동
- **wikilinks** `[[ref]]` 인식, **graph view** 자동 동작 → 우리 `links` 테이블과 시각적으로 일치
- `data/wiki/` 만 vault root로 잡으면 noise 없는 그래프 가능
- 주의: Obsidian이 frontmatter 일부 필드를 무시할 수 있음. 표준 필드(`tags`, `aliases`)는 호환

#### D.2 Obsidian Web Clipper
- 브라우저 익스텐션. 기본은 Obsidian vault 직접 저장이지만, **출력 폴더를 `data/raw/captures/`로** 설정 가능
- `/collect` 슬래시커맨드의 수동 보완재 — 빠른 클립이 필요할 때
- frontmatter 자동 생성 — slug/title/source_url 들어옴. 이후 `pkm capture set-status reviewed`로 PKM 워크플로우 진입
- 클리핑 직후 `pkm reindex --scope raw` 한 번 실행 권장

#### D.3 이미지 첨부 워크플로우
- Web Clipper가 본문 이미지를 로컬 다운로드 → `data/attachments/<date>/<file>` 권장
- 마크다운 본문은 `![alt](attachments/2026-05-01/img.png)` 상대경로 인용
- frontmatter `attachments: [paths]` 추가하면 lint가 깨진 첨부 검출 가능 (V2 lint 슬롯)
- wiki 페이지에서 첨부 인용 시 promote가 attachments 경로 보존
- 이미지 OCR/캡션은 V2 (multimodal 통합)

#### D.4 Marp (발표 자료)
- wiki/reports/ 페이지를 Marp 헤더 추가해 슬라이드로 변환 가능
- 변환 산출물은 `dashboard/` 또는 별도 `presentations/`에 저장 (gitignore 권장)
- 자동화: `pkm dashboard build` 시 `purpose: presentation` writing은 Marp HTML도 함께 빌드 (V2 슬롯)

#### D.5 Apple Notes / Notion / Slack 등 자동수집
- V2+ polling integration. 외부 시스템 → `data/raw/captures/` 자동 import
- V1 시점에는 사용자가 수동 export 후 `pkm capture create` 또는 Web Clipper로 진입

#### D.6 NotebookLM / Whisper 등 음성 변환
- 오디오 → 텍스트 → `pkm capture create` 가능
- 직접 통합 없음. 사용자 도구로 변환 후 PKM 진입
- frontmatter `source_type: audio` + `transcript_tool` 메타 권장

> **공통 원칙**: 외부 도구는 PKM의 raw/ 진입점만 잘 맞추면 나머지 워크플로우(검토→승격→wiki)는 동일. 이게 마크다운+git 기반의 힘.

---

*End of design document.*
