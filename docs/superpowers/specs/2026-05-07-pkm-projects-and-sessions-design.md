# PKM V3 설계 — Project Knowledge & AI Session Extraction

**Status**: design (브레인스토밍 통과, plan 분해 대기)
**Date**: 2026-05-07
**Author**: hwijung-park
**Predecessor**:
- `docs/superpowers/specs/2026-05-01-pkm-design.md` (V1 — 6 레이어/철학/경계의 SoT)
- `docs/superpowers/specs/2026-05-06-pkm-v2-design.md` (V2 — Graph / Grounding / Migration)

본 문서는 V1·V2 의 6 레이어 / 4 게이트 / 결정론 / 자동 git / strict 권한을 모두 보존하며, 그 위에 **7번째 레이어 (Projects)** 와 **AI 세션 transcript 어댑터** 를 추가한다.

---

## TL;DR

V2 GA 직후의 V3 사이클. 두 마일스톤으로 분해.

- **M13 — Project scope foundation**: `data/projects/<id>/` 7번째 레이어 도입. `pkm project link/list/current/show/rebuild-index/rm`, `pkm project knowledge add` CLI. m003 마이그레이션 (chunks 테이블에 `project`, `category`, `session_id` 컬럼 + 인덱스). search 새 스코프 (`project|project:<id>|projects`) + cwd 자동 감지 default. lint 4 신규 룰. `~/.pkm/config.toml` 글로벌 설정 (데이터 repo 위치 SoT). *데이터 평면 완성*.
- **M14 — Session adapter + skills**: `pkm session list/show/forget/mark-processed`, `pkm context inject`, `pkm.session.adapters.claude_code` 어댑터, Claude Code 통합 (`pkm install --for claude-code` — 글로벌 슬래시 4 종, 스킬 3 종, `~/.claude/CLAUDE.md` managed 블록), backfill 워크플로우. *AI 통합 완성*.

본 사이클이 닫는 사용자 요구:
1. **Post-session extract** — Claude Code 작업 끝난 후 transcript 분석 → 카테고리별 (decisions/pitfalls/snippets/qna/notes) 지식 추출 → 사용자 검수 → `data/projects/<id>/<category>/` 저장.
2. **Pre-session retrieve** — 어떤 프로젝트로 cd 하든 현재 프로젝트의 지식이 자동 인지됨 (skill + CLAUDE.md, hook 없음).
3. **Backfill** — `~/.claude/projects/**/*.jsonl` 의 과거 세션을 일괄 분석 → 지식 등록. 재진입 가능, idempotent.
4. **Multi-PC + cross-project portability** — 임의 cwd 에서 임의 PC 에서 동일 동작. SoT 는 데이터 repo 의 frontmatter, 머신별 차이는 `.pkm/config.local.toml` 만.

---

## 목차

1. 동기 + V2 GA 이후 갭
2. 결정 요약 (Q1–Q7 브레인스토밍 결과)
3. 아키텍처 경계 (보존 + 확장)
4. 데이터 레이아웃 + frontmatter 스키마
5. CLI 명령 surface
6. 세션 어댑터 인터페이스 (`pkm.session.adapters`)
7. cwd → project-id 해석 알고리즘
8. 글로벌 인프라 + portability 보장 룰
9. Claude Code 통합 — 스킬 · 슬래시 · CLAUDE.md
10. 인덱싱 + 검색 + related + lint + 그래프
11. Backfill 워크플로우
12. 에러 계약
13. 테스팅 전략
14. doctor 통합
15. 호환성 + 결정론
16. M13/M14 마일스톤 로드맵
17. 비-스코프 + 미해결 이슈
18. 위험 & 완화

---

## 1. 동기 + V2 GA 이후 갭

### 1.1 사용자 관찰 — V2 GA 후

V2 GA (M10–M12 완료) 시점의 사용자 운영 관찰:

| 갭 | 사용자 체감 | V1·V2 대응 한계 |
|---|---|---|
| **공용 wiki 와 프로젝트별 노하우의 혼재 위험** | 한 데이터 repo 에 다 쌓다 보면 *"이 결정이 OAuth 라이브러리 X 에만 적용되나, 일반 원리인가"* 가 흐려짐 | V1·V2 는 wiki 만 존재. *공용 vs 프로젝트별* 의 명시적 분리 없음 |
| **AI 세션이 휘발성 자산** | Claude Code 한 세션에서 30+ 의사결정·삽질·코드 스니펫이 쌓이는데 모두 transcript 로만 저장 → 다음 세션에서 재발견 비용 발생 | V1·V2 의 capture 는 *URL/텍스트* 만 가정. 세션 transcript 처리 부재 |
| **프로젝트 컨텍스트 로딩이 사람의 기억에 의존** | 새 세션 시작 시 *"이 프로젝트에서 우리가 뭘 결정했더라"* 를 사람이 회상해서 컨텍스트에 주입 | hooks/skills/CLAUDE.md 같은 자동 인지 메커니즘 부재 |
| **여러 프로젝트 / 여러 PC 운영 부재** | hwi_PKM 외 다른 코드베이스에서 작업하면 PKM 이 따라가지 않음. 다른 PC 에서도 같은 프로젝트 매핑이 동기화되지 않음 | `pkm` CLI 자체는 글로벌이지만 슬래시·스킬·hook 은 데이터 repo 안에만 설치 |
| **과거 누적된 세션 transcript 의 사장** | `~/.claude/projects/**/*.jsonl` 에 수개월치 작업이 있는데 활용 0 | 어댑터 없음. 과거 세션 분석 도구 없음 |

V3 사이클은 위 5 갭을 단일 흐름으로 닫는다 — *세션이라는 새 입력 소스* + *프로젝트라는 새 분류 축* + *글로벌 인프라로의 확장*.

### 1.2 Karpathy "LLM Wiki" + safishamsi/graphify 와의 정합

V1 의 `/ask` 가 이미 *Karpathy grounding* 룰 (인용 강제, 추측 금지) 을 따르고, V2 의 `pkm wiki suggest` + `dashboard/graph.html` 이 graphify 류의 *그래프 네비게이션* 일부를 제공한다. V3 는 이 두 자료의 핵심 정신 — *"LLM 이 즉석 재발견하지 않고 누적 위키를 유지보수"* — 을 *AI 세션이라는 가장 풍부한 입력원* 으로 확장한다. 추출된 프로젝트 지식은 시간이 지나며 일반화되면 기존 `pkm promote` 게이트로 공용 wiki 에 승격된다 (*compounding*).

### 1.3 V1·V2 매핑

| V3 작업 | V1·V2 참조 | 관계 |
|---|---|---|
| 7번째 레이어 (Projects) | V1 §3 6 레이어 | 6 → 7 레이어 확장. 라이프사이클·게이트는 기존 capture 와 통합 |
| `pkm project knowledge add` | V1 §5.2 capture create | 동일 frontmatter 패턴 (status: draft → reviewed → archived) |
| wiki 승격 게이트 | V1 §5.5 promote | 출처가 `data/projects/**` 든 `data/raw/captures/**` 든 무관. 기존 게이트 그대로 |
| m003 마이그레이션 | V2 §5 M12 migrate runner | 기존 runner 재사용 — 추가 인프라 0 |
| lint 신규 4 룰 | V1 §6.5 + V2 §4 grounding | 기존 룰 패턴 동일 (코드, 종류, --fix 가능 여부) |
| graph 노드 종류 확장 | V2 §3 graph.html | `[dashboard.graph]` 의 `include_projects` 옵션 추가 |
| `--scope project` | V1 §5.4 search scope | 기존 wiki/raw/writing/all 에 항목 추가 |
| Skill + CLAUDE.md 통합 | (V3 신규) | superpowers 의 skill 모델을 PKM 에 도입 |
| `pkm install --for claude-code` | (V3 신규) | 글로벌 인프라 진입점 |

---

## 2. 결정 요약 (브레인스토밍 Q1–Q7)

| # | 항목 | 결정 |
|---|---|---|
| Q1 | 입력 소스 | Claude Code 세션 transcripts (`~/.claude/projects/<encoded-cwd>/<uuid>.jsonl`) |
| Q2 | 프로젝트 식별 | git remote 기본 + 사용자 override (B+C hybrid) |
| Q3 | 저장 레이아웃 | `data/projects/<project-id>/` + 기존 `pkm promote` 로 wiki 승격 게이트 (D) |
| Q4 | 추출 단위 | 5 카테고리 (`decisions/pitfalls/snippets/qna/notes`) + 사용자 승인 게이트 (D) |
| Q5 | Pre-session retrieve | **스킬 + 글로벌 CLAUDE.md** (SessionStart hook 미사용) |
| Q6 | Cross-project 배포 | 글로벌 한 번 + `pkm project link` 로 등록 (B) |
| Q7 | V1 multi-CLI 스코프 | Claude Code 만, adapter 패턴은 준비 (A) |

추가 결정:
- **저장 레이아웃 SoT** — `data/projects/<id>/index.md` frontmatter 가 SoT. 별도 registry 파일 없음. `git_remotes` 리스트가 universal 매핑.
- **프로젝트 매핑 동기화** — 데이터 repo git push/pull 로 자동 전파. 머신별 차이는 `.pkm/config.local.toml` 의 `[project_overrides]` 만.
- **추출 LLM 호출** — Claude Code 세션 안에서 *Claude 본인이 transcript Read* 함. `llm_bridge` 셸아웃 없음 (V1 의 `/ask` 와 동일 정신).
- **검토 게이트 UX** — Claude 가 후보 markdown 한 덩어리 출력 → 사용자가 자연어로 일괄 수정 지시 → Claude 재출력 → 사용자 OK 시 일괄 작성 (2 라운드 흐름).
- **재처리 정책** — `pkm session forget <uuid>` 명시 호출 시에만 재처리. transcript 길이 변화 자동 감지 안 함 (idempotent).
- **검색 default 스코프** — cwd 가 linked 면 `wiki + 현재 project`, 아니면 기존 `all` 의미 유지.
- **Graph default** — `include_projects = true` (`max_nodes` cap 이 안전망).
- **`.pkm/sessions/` 메타파일** — gitignored (PC 별 transcript 와 동일 의미).

---

## 3. 아키텍처 경계 (보존 + 확장)

### 3.1 V1·V2 경계 — 변경 없음

| 경계 | V3 영향 |
|---|---|
| **markdown = 진실** | 변경 없음. `data/projects/**` 도 markdown SoT, `.pkm/index.db` 에서 결정론적 재생성 |
| **CLI 코어 = 결정론, LLM SDK 0** | 변경 없음. 추출은 *Claude Code 세션 안* 에서 Claude 가 in-session 으로 처리 — pkm CLI 코어는 LLM 호출 0 |
| **옵트인 셸아웃** | 변경 없음. `expand_query` 등 기존 task 그대로. 새 `extract_session` task 는 만들지 않음 |
| **자동 git 커밋** | 변경 없음. `pkm project link`, `pkm project knowledge add`, `pkm session mark-processed` 모두 mutate → 자동 커밋 |
| **Strict 권한 (`data/wiki/**` deny-write)** | 변경 없음. `data/projects/**` 는 (capture 와 동일하게) writable. wiki 승격 시에만 `data/wiki/**` 진입 — 기존 게이트 그대로 |

### 3.2 신규 데이터 평면

추가되는 디렉토리:
- `data/projects/<project-id>/` — 7번째 레이어
- `data/projects/<project-id>/{decisions,pitfalls,snippets,qna,notes}/` — 5 카테고리
- `.pkm/sessions/<project-id>/` — 세션 처리 메타 (gitignored)

추가되는 파일 (글로벌, PC 별 1 회):
- `~/.pkm/config.toml` — 데이터 repo 위치 SoT (`data_repo = "..."`)
- `~/.claude/CLAUDE.md` — managed 블록 (PKM project context loading 지시)
- `~/.claude/commands/pkm-*.md` — 슬래시 4 종 (extract-session, recall, backfill, project)
- `~/.claude/skills/pkm/<skill-name>/` — 스킬 3 종 (extracting-session-knowledge, recalling-project-context, backfilling-sessions)

추가되는 SQL 컬럼 (m003):
- `chunks.project TEXT NULL`
- `chunks.category TEXT NULL`
- `chunks.session_id TEXT NULL`
- `INDEX idx_chunks_project_category (project, category)`

### 3.3 신규 Python 모듈

| 모듈 | 역할 |
|---|---|
| `pkm/commands/project.py` | `pkm project {link, list, current, show, rebuild-index, rm, knowledge-add}` |
| `pkm/commands/session.py` | `pkm session {list, show, forget, mark-processed}` |
| `pkm/commands/context.py` | `pkm context inject` |
| `pkm/commands/install.py` | `pkm install --for claude-code` (외 어댑터) |
| `pkm/session/adapters/__init__.py` | adapter registry |
| `pkm/session/adapters/base.py` | `SessionAdapter` Protocol |
| `pkm/session/adapters/claude_code.py` | Claude Code `.jsonl` discovery + 정규화 |
| `pkm/session/registry.py` | cwd → project-id 해석 (5 단계 알고리즘) |
| `pkm/store/migrations/m003_project_scope.py` | `project`/`category`/`session_id` 컬럼 + 인덱스 |
| `pkm/templates/skills/**/*.md` | 스킬 본체 (설치 시 `~/.claude/skills/` 로 복사) |
| `pkm/templates/commands/pkm-*.md` | 슬래시 본체 (설치 시 `~/.claude/commands/` 로 복사) |
| `pkm/templates/claude_md_block.md` | `~/.claude/CLAUDE.md` managed 블록 |

---

## 4. 데이터 레이아웃 + frontmatter 스키마

### 4.1 디렉토리 구조 (데이터 repo)

```
~/Documents/pkm/                          ← 데이터 repo (단일, 기존 위치)
  data/
    raw/                                   ← (기존)
      captures/  chunks/
    wiki/                                  ← (기존, 공용 지식)
      concepts/  entities/  notes/  reports/
    writing/                               ← (기존)
    projects/                              ★ V3 신규 (7번째 레이어)
      <project-id>/
        index.md                             ★ 결정론적 빌드 — 수기 편집 비권장
        decisions/                           ADR 류 결정
        pitfalls/                            함정 · 삽질 · 하지 말 것
        snippets/                            재사용 코드/명령
        qna/                                 질의응답 쌍
        notes/                               위 4종에 안 맞는 자유 메모
    log.md  index.md                       ← (기존, projects 도 append)
  .pkm/
    index.db                               ← (기존, projects 도 인덱싱)
    config.toml                            ← (기존, git tracked)
    config.local.toml                      ← (기존, gitignored, [project_overrides] 추가)
    sessions/                              ★ V3 신규, gitignored
      <project-id>/<session-uuid>.json     세션 처리 메타
```

### 4.2 글로벌 인프라 (PC 별 1 회 설치)

```
~/.pkm/
  config.toml                              ★ 데이터 repo 위치 SoT
                                            data_repo = "/Users/me/Documents/pkm"

~/.claude/                                 (Claude Code 표준 위치)
  CLAUDE.md                                ★ pkm:start ... pkm:end managed 블록
  commands/
    pkm-extract-session.md                 ★ 슬래시 진입점
    pkm-recall.md                          ★
    pkm-backfill.md                        ★
    pkm-project.md                         ★
  skills/
    pkm/
      extracting-session-knowledge/
        SKILL.md
        extraction-categories.md
        output-schema.md
        review-protocol.md
      recalling-project-context/
        SKILL.md
        search-scope-guidelines.md
      backfilling-sessions/
        SKILL.md
```

위 모든 파일은 `pkm install --for claude-code` 가 작성/갱신/삭제. managed 마커 (`<!-- managed by pkm install -->` 또는 `<!-- pkm:start -->` ... `<!-- pkm:end -->`) 로 사용자 수동 편집 부분과 격리.

### 4.3 frontmatter 스키마 — `data/projects/<id>/<category>/<slug>.md`

기존 capture 스키마 확장 (V3 = lifecycle 통합 접근):

```yaml
---
# === 기존 필수 필드 (V1) ===
title: "OAuth refresh token 은 httpOnly cookie 에 저장"
slug: 2026-05-07-oauth-cookie-storage
created_at: 2026-05-07T14:23:00+09:00
status: draft                             # draft → reviewed → archived (기존 라이프사이클)
source_type: ai_session                   # ★ V3 신규 enum 값 (기존: web_capture, manual, ...)
lang: ko

# === V3 신규 필드 (project scope) ===
project: hwi-pkm                          # ★ 필수 (data/projects/<id>/** 일 때)
category: decisions                       # ★ 필수. {decisions, pitfalls, snippets, qna, notes}
session_id: 01952f...                     # ★ 옵션. 어느 세션에서 추출됐나 (Claude Code session uuid)
session_path: ~/.claude/projects/.../*.jsonl  # ★ 옵션. transcript 파일
extracted_at: 2026-05-07T14:30:00+09:00   # ★ 옵션. 추출 in-session 시각

# === 기존 옵션 필드 (V1·V2) ===
tags: [oauth, security]
summary: "..."
derived_from: []                          # 추출 시 비어있고, 검수 중 사용자가 인용 추가
promoted_to: null                         # wiki 승격 시 자동 채워짐 (기존)
---

본문 — 추출된 지식의 markdown.
```

조건부 필수 룰:
- 파일 경로가 `data/projects/<id>/**` 패턴 ⇒ `project`, `category` 필수.
- `project` 값이 경로의 `<id>` 와 다르면 `MISSING_PROJECT_FIELD` 또는 `CATEGORY_PATH_MISMATCH` (lint).
- `category` 가 경로의 카테고리 디렉토리와 다르면 `CATEGORY_PATH_MISMATCH`.
- 그 외 경로 (wiki/raw/writing) 는 `project`/`category` NULL OK — 변경 없음.

### 4.4 frontmatter 스키마 — `data/projects/<id>/index.md`

```yaml
---
project: hwi-pkm
git_remotes:
  - github.com:hwijung-park/hwi_PKM
created_at: 2026-05-07T14:23:00+09:00
data_repo_local_paths:
  []
---

# hwi-pkm

_이 페이지는 `pkm project rebuild-index hwi-pkm` 가 자동 갱신합니다._

## 핵심 결정 (decisions, 최근 N)
...
## 함정 / 하지 말 것 (pitfalls, 최근 N)
...
## 재사용 스니펫 (snippets, 최근 N)
...
## 활동 (최근 세션 N)
...
```

본문은 `pkm project rebuild-index <id>` 가 frontmatter 에서 결정론적으로 빌드. 사용자 편집 가능하지만 다음 빌드에서 덮어씀 (의도된 동작 — index.md 는 캐시 페이지). frontmatter 의 `git_remotes` 와 `created_at`, `data_repo_local_paths` 는 보존.

### 4.5 머신별 override (`.pkm/config.local.toml`)

```toml
# 같은 데이터 repo 를 두 PC 에서 공유 — git remote 매칭이 안 되는 케이스 (예: monorepo 의 sub-dir)
[project_overrides]
"/Users/me/Code/big-mono/services/payments" = "payments"
"/Users/me/Code/big-mono/services/users"    = "users"
```

이 파일은 gitignore (기존 `config.local.toml` 패턴). 머신별 cwd 가 다를 때 universal git remote 매칭 실패를 보완.

---

## 5. CLI 명령 surface

### 5.1 `pkm project ...`

```bash
pkm project link [--id SLUG] [--remote URL] [--no-commit] [--allow-no-remote] [--json]
                                  # cwd 의 git repo 등록.
                                  # 절차: git repo 검증 → remote 정규화 → 중복 검사 →
                                  #       project-id 결정 → 디렉토리 시드 → frontmatter 작성 → 자동 커밋

pkm project list [--json]         # 등록 프로젝트 모두 + 통계 (지식 N, 마지막 추출 시각)
pkm project current [--json]      # cwd → project-id 해석 (5 단계 알고리즘)
pkm project show <id> [--json]    # index.md 렌더 + 카테고리별 카운트
pkm project rebuild-index <id> [--json]
                                  # data/projects/<id>/index.md 결정론 재생성

pkm project rm <id> [--keep-data] [--json]
                                  # 등록 해제. 기본 = 디렉토리 archived/projects/<id>/ 로 이동

pkm project knowledge add --project ID --category CATEGORY --slug SLUG --title "TITLE"
                          [--tags TAG,TAG] [--source-type ai_session|manual]
                          [--session-id UUID] [--session-path PATH]
                          [--json]
                          # 본문은 stdin
                                  # 새 markdown 작성 (frontmatter 검증 + slug 정규화 + auto-commit)
```

### 5.2 `pkm session ...`

```bash
pkm session list [--project ID] [--unprocessed] [--since DATE] [--until DATE]
                 [--min-messages N=5] [--limit N] [--json]
                                  # ~/.claude/projects/**/*.jsonl 스캔 → 정규화된 메타 출력.
                                  # NOT_LINKED 세션은 자동 제외 (untracked cwd 는 backfill 대상 아님).

pkm session show <session-uuid> [--json]
                                  # transcript 메타 + 경로 (transcript 본문 자체는 출력 안 함 — 크기 큼)

pkm session forget <session-uuid> [--json]
                                  # .pkm/sessions/<id>/<uuid>.json 삭제 → 재처리 후보 복귀

pkm session mark-processed <session-uuid> --extracted-count N [--json]
                                  # 메타파일 작성 (스킬이 추출 완료 후 호출)
```

### 5.3 `pkm context ...`

```bash
pkm context inject [--project ID] [--max-tokens N=600] [--json]
                                  # data/projects/<id>/index.md 본문 stdout (max-tokens 자동 트림).
                                  # NOT_LINKED 면 stdout 비우고 exit 0 (--quiet-on-not-linked 기본 ON).
```

### 5.4 `pkm install ...`

```bash
pkm install --for {claude-code} [--data-repo PATH] [--uninstall] [--json]
                                  # claude-code:
                                  #   ~/.pkm/config.toml 작성 (data_repo = ...)
                                  #   ~/.claude/CLAUDE.md 의 managed 블록 추가/갱신
                                  #   ~/.claude/commands/pkm-*.md 작성
                                  #   ~/.claude/skills/pkm/**/*.md 작성
                                  # --uninstall: managed 마커 가진 항목만 제거 (사용자 수동 추가 보존).
```

### 5.5 기존 명령 확장

| 명령 | 추가 옵션 |
|---|---|
| `pkm reindex db` | `--scope projects`, `--scope project:<id>` 추가. `--scope all` 의미는 *projects 포함* 으로 확장 (backward-compat: 더 넓어질 뿐) |
| `pkm search` | `--scope project|project:<id>|projects` 추가. `--project ID` additive 옵션. cwd-linked 시 default = `wiki + 현재 project` |
| `pkm related` | `--scope same-project|wiki|all` 옵션 추가. 기본 = `same-project + wiki` |
| `pkm lint` | 4 신규 룰 (§10.4) |
| `pkm doctor` | 4 신규 row (§14) |
| `pkm migrate` | m003 자동 등록 (기존 runner) |

---

## 6. 세션 어댑터 인터페이스

V1 = `claude_code` 어댑터만 구현. 인터페이스는 V2+ multi-CLI 준비.

### 6.1 Protocol

```python
# pkm/session/adapters/base.py

@dataclass
class SessionRef:
    uuid: str                              # 세션 식별자 (CLI 별로 의미)
    cwd: pathlib.Path                      # 세션이 시작된 cwd
    started_at: datetime
    last_message_at: datetime
    message_count: int
    model: str | None                      # claude-opus-4-7 등
    transcript_path: pathlib.Path

@dataclass
class NormalizedMessage:
    role: Literal["user", "assistant", "system", "tool"]
    content_blocks: list[dict]             # text | tool_use | tool_result 등 (CLI 호환 위해 dict)
    timestamp: datetime

@dataclass
class NormalizedTranscript:
    ref: SessionRef
    messages: list[NormalizedMessage]

class SessionAdapter(Protocol):
    name: str                              # "claude_code"
    transcript_root: pathlib.Path          # ~/.claude/projects/

    def discover(self) -> Iterator[SessionRef]: ...
        """transcript_root 스캔 → SessionRef 생성 (전체 본문 파싱 안 함, header 만)"""

    def resolve_project_id(
        self, ref: SessionRef, registry: ProjectRegistry
    ) -> str | None: ...
        """cwd → git remote → registry 매칭 → project-id (없으면 None)"""

    def parse(self, ref: SessionRef) -> NormalizedTranscript: ...
        """전체 jsonl 파싱 — extracting-session-knowledge 스킬이 Read 로 직접 호출하므로 V3 에선 거의 사용 안 됨.
        backfill 스킬도 Read 직접 사용. 본 메서드는 doctor / 디버그용 fallback."""
```

### 6.2 `claude_code` 어댑터 구현

```
pkm/session/adapters/claude_code.py
```

- `transcript_root = ~/.claude/projects/`
- discover: `<transcript_root>/<encoded-cwd>/<uuid>.jsonl` glob. encoded-cwd 는 Claude Code 가 사용하는 path-encoding 규칙 (`/` → `-`). uuid 는 파일명 (확장자 제거).
- resolve_project_id:
  1. encoded-cwd 디코딩 → 절대 cwd 경로 복원.
  2. cwd 가 git repo 면 `git remote get-url origin` 실행 + 정규화.
  3. registry 의 frontmatter `git_remotes` 와 매칭.
  4. 매칭 없으면 `[project_overrides]` 의 cwd 매칭.
  5. 모두 실패 시 None.
- parse: jsonl 읽고 `{type: "user_message"|"assistant_message"|"tool_use"|"tool_result"} → NormalizedMessage` 매핑.

### 6.3 V3 에서 어댑터의 실질 책임 = discovery 만

스킬이 Claude in-session 으로 transcript 를 직접 Read 하므로 `parse` 는 V3 의 critical path 에서 호출되지 않는다. 어댑터는 사실상 **discovery + resolve_project_id 두 메서드** 만 critical path. `parse` 는 doctor/디버그/V4 어댑터 (Codex 등) 에서 in-session 처리가 어려운 경우의 fallback.

---

## 7. cwd → project-id 해석 알고리즘

### 7.1 우선순위 5 단계

```
1. PKM_PROJECT 환경변수 명시        → 그것 사용 (한 회성 override)
2. .pkm/config.local.toml [project_overrides] cwd 매칭
                                   → 머신별 override
3. cwd 의 git remote 정규화 → 모든 data/projects/*/index.md 의 git_remotes 와 매칭
                                   → universal SoT, multi-PC 동기화
4. cwd path 가 frontmatter data_repo_local_paths 에 있는지
                                   → 머신별 fallback (드물게)
5. 모두 실패                       → NOT_LINKED (exit 1)
```

### 7.2 git remote 정규화

다음 변형을 모두 동일 키로 매핑:
- `git@github.com:user/repo.git` → `github.com:user/repo`
- `https://github.com/user/repo` → `github.com:user/repo`
- `https://github.com/user/repo.git` → `github.com:user/repo`
- `ssh://git@github.com/user/repo` → `github.com:user/repo`

기타 호스트 (gitlab, bitbucket, 회사 git) 도 같은 형태 (`<host>:<path>`).

### 7.3 `pkm project current --json`

```json
{
  "ok": true,
  "project_id": "hwi-pkm",
  "resolved_via": "git_remote",       // env | local_override | git_remote | local_path
  "data_dir": "data/projects/hwi-pkm",
  "data_repo": "/Users/me/Documents/pkm"
}
```

NOT_LINKED 응답:
```json
{"ok": false, "error": {"code": "NOT_LINKED", "message": "...", "hint": "Run `pkm project link`"}}
```

---

## 8. 글로벌 인프라 + portability 보장 룰

### 8.1 `pkm install --for claude-code` 멱등 동작

1. `~/.pkm/config.toml` 검사:
   - 없음 → 생성 (`data_repo = <argv 또는 cwd>`)
   - 있음 + `--data-repo` 명시 → 갱신
   - 있음 + 인자 없음 → 보존
2. `~/.claude/CLAUDE.md` 검사:
   - 없음 → 생성 (managed 블록만)
   - 있음 + managed 마커 (`<!-- pkm:start -->` ... `<!-- pkm:end -->`) → 마커 사이 갱신
   - 있음 + managed 마커 없음 → append (기존 사용자 내용 보존)
3. `~/.claude/commands/pkm-*.md` 4 종 → `pkm/templates/commands/` 에서 복사 (덮어쓰기, managed 마커 포함)
4. `~/.claude/skills/pkm/**` → `pkm/templates/skills/` 에서 복사 (덮어쓰기, managed 마커)
5. `--uninstall`: managed 마커 가진 파일/블록만 제거. 마커 없는 사용자 수동 편집은 보존.

### 8.2 Portability 보장 룰 (모든 스킬·슬래시 준수)

| 룰 | 의미 |
|---|---|
| **R1** 모든 경로는 `pkm` CLI 출력에서 해석 | 스킬/슬래시 본문에 `~/Documents/pkm/...` hardcode 금지. 항상 `pkm session show <uuid> --json` 의 `transcript_path`, `pkm project current --json` 의 `data_dir` 사용 |
| **R2** 데이터 repo 위치 SoT = `~/.pkm/config.toml` | PC 별 한 번 주입. CLI 가 어디서든 이 파일 읽어 데이터 repo 찾음 |
| **R3** 스킬 본체는 pkm 패키지에 포함 | `pkm/templates/skills/` 가 SoT. `pkm install` 이 복사. PC 마다 동일 pkm 버전이면 동일 스킬 |
| **R4** 프로젝트 매핑 SoT = 데이터 repo frontmatter | `data/projects/<id>/index.md` 의 `git_remotes`. git push/pull 로 multi-PC 동기화 |
| **R5** cwd 독립성 | 스킬은 cwd = 데이터 repo 가정 안 함. 모든 mutate 는 `pkm <cmd>` 로만 (Edit/Write 직접 사용 금지) |
| **R6** 동적 프로젝트 해석 | 스킬 시작 시 *반드시* `pkm project current --json`. project-id hardcode 금지 |
| **R7** Untracked cwd graceful degradation | `NOT_LINKED` 시 사용자 노이즈 0. CLAUDE.md 가 *silently proceed* 명시 |

### 8.3 새 PC 셋업 흐름 (검증 시나리오)

```bash
# 새 PC, 한 번씩만
brew install uv
git clone <소스 repo> ~/Downloads/Claude_lab/hwi_PKM
cd ~/Downloads/Claude_lab/hwi_PKM
uv sync --all-extras
uv tool install --reinstall -e ".[ml,extract,korean]"

git clone <데이터 repo> ~/Documents/pkm
cd ~/Documents/pkm
pkm bootstrap                                    # doctor → reindex → dashboard

# ★ V3 새 단계
pkm install --for claude-code --data-repo ~/Documents/pkm

pkm doctor --strict                              # 모두 ✓
cd ~/Code/whatever                               # 임의 프로젝트
pkm project current                              # 등록되어 있으면 project-id, 아니면 NOT_LINKED
```

다른 PC 가 `git pull` 만 하면 같은 프로젝트가 자동 인식 (R4).

---

## 9. Claude Code 통합 — 스킬 · 슬래시 · CLAUDE.md

### 9.1 글로벌 CLAUDE.md managed 블록

`~/.claude/CLAUDE.md` 안:

```md
<!-- pkm:start managed by pkm install -->
## PKM project context loading

When you start working in a directory, **before** any non-trivial work:

1. Check if the cwd is a linked PKM project: run `pkm project current --json`.
2. If linked (`ok: true`): invoke the `pkm:recalling-project-context` skill — it loads the project's index.md and recent decisions/pitfalls into context.
3. If not linked (`code: NOT_LINKED`): silently proceed. Do not surface this to the user unless they ask about PKM.

This applies to any cwd, any project — the skill resolves which project automatically.
<!-- pkm:end managed by pkm install -->
```

### 9.2 스킬 3 종 (`~/.claude/skills/pkm/`)

| 스킬 | description (자동 트리거) | 본체 |
|---|---|---|
| `pkm:recalling-project-context` | "Use at the start of work in any project, or whenever the user references prior decisions, patterns, or pitfalls in their codebase." | SKILL.md (3 단계 절차) + `search-scope-guidelines.md` |
| `pkm:extracting-session-knowledge` | "Use when user wants to harvest knowledge from a Claude Code session, or signals that work is complete in a linked project." | SKILL.md (10 단계 절차) + `extraction-categories.md` + `output-schema.md` + `review-protocol.md` |
| `pkm:backfilling-sessions` | "Use when user wants to process historical Claude Code sessions in bulk to seed project knowledge." | SKILL.md (배치 절차, 재진입 보장) |

### 9.3 슬래시 4 종 (`~/.claude/commands/`)

| 슬래시 | 동작 |
|---|---|
| `/pkm-extract-session [uuid]` | `pkm:extracting-session-knowledge` 스킬 invoke (uuid 인자 전달) |
| `/pkm-recall <task>` | `pkm:recalling-project-context` 스킬 invoke (task 인자 전달) |
| `/pkm-backfill [opts]` | `pkm:backfilling-sessions` 스킬 invoke |
| `/pkm-project link\|current\|show` | `pkm project <verb>` 직접 호출 (스킬 없음) |

### 9.4 `pkm:extracting-session-knowledge` 스킬 절차

1. uuid 미명시 시 *현재 세션* (Claude Code 환경변수 또는 마지막 세션 추론).
2. `pkm session show <uuid> --json` → transcript_path + cwd + project-id.
3. project-id `NOT_LINKED` → *"이 cwd 는 link 안 됨. `pkm project link` 먼저 실행 권장"* 후 종료.
4. transcript jsonl 을 Read 툴로 읽기 (긴 transcript 는 50 메시지 + overlap 5 윈도우 슬라이딩).
5. Claude 가 5 카테고리 후보 markdown 한 덩어리 작성 (Q4 b — 사용자 자연어 응답으로 일괄 수정).
6. 1 라운드: 사용자 검토 → Claude 가 변경 반영 후 재출력.
7. 2 라운드: 사용자 OK → 일괄 작성 모드 진입.
8. 항목별 `pkm project knowledge add --project <id> --category <c> --slug <s> --title "..." [tags] <<< body` (frontmatter 검증 + slug 정규화 + auto-commit).
9. `pkm session mark-processed <uuid> --extracted-count <N>`.
10. `pkm project rebuild-index <id>` + `pkm reindex db --scope project:<id>` 일괄.

### 9.5 `pkm:recalling-project-context` 스킬 절차

1. `pkm project current --json` → project-id (NOT_LINKED → silent exit).
2. `pkm context inject --json --max-tokens 600` → index.md 본문.
3. (옵션, 사용자 task 명확하면) `pkm search --scope project <task> --json -n 5` → top-K hit path.
4. *"이 프로젝트의 핵심 정보 인지. 관련 결정/함정 N 개 인지. 필요 시 `/pkm-recall` 또는 specific path Read."* 한 줄 보고.

### 9.6 `pkm:backfilling-sessions` 스킬 절차

1. `pkm session list --unprocessed --json` (옵션: `--project`, `--since`, `--min-messages 5`).
2. 사용자 확인 (총 세션 수 + 예상 시간) + 첫 세션 자세히 vs 일괄 모드 선택.
3. 한 세션씩:
   - `pkm session show <uuid> --json` → transcript_path.
   - Read 로 transcript 읽기 (윈도우 슬라이딩).
   - 카테고리 후보 (첫 세션은 Q4 b 두 라운드, 이후 일괄 모드는 한 라운드).
   - `pkm project knowledge add` 항목별 + `pkm session mark-processed`.
4. 중단 시 마지막 처리된 세션까지 메타파일 → 다음 호출에서 자동 재개.
5. 끝에 `pkm project rebuild-index` 일괄 + `pkm reindex db --scope projects` 한 번 + 통계 요약.

---

## 10. 인덱싱 + 검색 + related + lint + 그래프

### 10.1 인덱싱 (`pkm reindex db`)

새 스코프:
- `--scope projects` — `data/projects/**` 전체
- `--scope project:<id>` — 특정 프로젝트
- `--scope all` 의미 확장 = wiki + raw + writing + projects (기존 동작 superset)

m003 마이그레이션 적용 후 점진 reindex 만으로도 동작 (수정 시 자연 채워짐). `--full reindex` 권장이지만 강제 아님 — 기존 wiki/raw/writing 행은 `project`/`category` NULL 이 정상 (NULL = 비프로젝트 스코프).

### 10.2 검색 (`pkm search`)

새 스코프:
| `--scope` | 검색 범위 |
|---|---|
| (생략) | cwd-linked → `wiki + project:<auto>` / 아니면 `wiki + raw + writing` |
| `wiki` | 공용 wiki 만 |
| `project` | cwd 매핑 프로젝트 (NOT_LINKED → hard-fail) |
| `project:<id>` | 특정 프로젝트 |
| `projects` | 모든 프로젝트 union (wiki 제외) |
| `all` | wiki + raw + writing + projects |

추가 옵션 `--project ID` 는 additive (e.g. `--scope wiki --project hwi-pkm` = wiki + hwi-pkm).

내부 5 단계 파이프라인 (쿼리확장 → BM25/vec0 병렬 → RRF → 재랭킹 → top-K) 변경 없음. retrieval SQL 의 WHERE 절에 `project IN (...)` 추가만.

검색 결과 JSON 에 새 메타:
```json
{"path": "data/projects/hwi-pkm/decisions/...", "scope": "project", "project": "hwi-pkm", "category": "decisions", ...}
```

### 10.3 `pkm related` 크로스-스코프

```bash
pkm related <path> [--mode backlinks|semantic|both] [--scope same-project|wiki|all]
```

기본 = `same-project + wiki`:
- `data/projects/<id>/**` 의 related → 같은 프로젝트 + 공용 wiki. 다른 프로젝트 노이즈 제외.
- `data/wiki/**` 의 related → 모든 wiki + 옵션으로 cwd 의 현재 프로젝트.
- `--scope all` 명시 시에만 cross-project (패턴 발견용).

### 10.4 Lint 신규 4 룰

| 코드 | 종류 | 의미 | --fix |
|---|---|---|---|
| `MISSING_PROJECT_FIELD` | error | `data/projects/<id>/**` 인데 `project` 누락 또는 `<id>` 와 불일치 | ✅ (경로 SoT 추론) |
| `INVALID_CATEGORY` | error | `category` 가 5 enum 외 | — |
| `CATEGORY_PATH_MISMATCH` | error | 경로 카테고리 디렉토리와 frontmatter `category` 불일치 | ✅ (경로 SoT) |
| `ORPHAN_PROJECT_DIR` | warning | `data/projects/<id>/index.md` 누락 또는 `git_remotes` 비어있음 | — |

추가 warning (V3 dedup):
| `SIMILAR_KNOWLEDGE_CANDIDATE` | warning | 코사인 유사도 ≥ 0.92 인 항목 페어 — 사용자에게 노출 (자동 머지 안 함) |

### 10.5 Dashboard graph (`graph.html`)

`[dashboard.graph]` 옵션 추가:

```toml
[dashboard.graph]
max_nodes = 1000                    # (기존)
include_writing = false             # (기존)
include_captures = false            # (기존)
include_projects = true             # ★ V3 신규, 기본 true
project_filter = []                 # ★ V3 신규. 빈 배열 = 모든 프로젝트, 명시 시 그것만
overlay_suggestions = true          # (기존)
```

노드 색 분류 확장:
- 기존: concepts(파랑) · entities(녹) · notes(노) · reports(주황)
- V3 신규: projects/decisions(보라) · pitfalls(빨강) · snippets(회) · qna(하늘) · notes(베이지)

엣지: 기존 wikilink (실선) + derived_from (점선) + suggested (빨간 점선) + V3 신규 *session-origin* (얇은 회색, 옵션, 기본 OFF — 시각 노이즈 방지).

`max_nodes` cap 동작 (connectivity 낮은 노드부터 drop) 변경 없음 — projects 추가로 cap 자주 hit 가능, `stats.trimmed` 카운트로 표면화.

---

## 11. Backfill 워크플로우

### 11.1 Discovery — `pkm session list --unprocessed`

1. `~/.claude/projects/**/*.jsonl` glob.
2. 각 jsonl header (첫 message 또는 sidecar) 에서 cwd, started_at, model, message_count 추출. 본문 미파싱.
3. cwd → project-id (`NOT_LINKED` 세션 자동 제외).
4. `.pkm/sessions/<project-id>/<session-uuid>.json` 존재 여부 → `--unprocessed` 시 제외.
5. 필터 (`--since`, `--min-messages 5` default 등) + oldest-first 정렬.

### 11.2 재진입 가능 배치 — `/pkm-backfill` 스킬

(§9.6 참조)

핵심 보장:
- **idempotent**: 처리된 세션은 메타파일 → 재호출 시 skip.
- **resume**: 중단 시 마지막 처리된 세션까지 진행, 다음 호출에서 자동 재개.
- **batch reindex**: 매 세션마다 reindex 안 함, 끝에 `pkm reindex db --scope projects` 한 번.

### 11.3 안전장치

| 위협 | 대응 |
|---|---|
| transcript 길이 → 토큰 한계 | 50 메시지 + overlap 5 윈도우 슬라이딩, 카테고리 dedup |
| 중간 중단 / abort | 부분 결과 폐기 (메타파일 미작성). 다음 backfill 에서 처음부터 재처리 |
| 동일 지식 중복 | lint `SIMILAR_KNOWLEDGE_CANDIDATE` (코사인 ≥ 0.92) 로 표면화. 자동 머지 안 함 |
| outdated cutoff | `--since DATE` 사용자 명시. 자동 cutoff 없음 |
| jsonl 손상 | `CORRUPT_TRANSCRIPT` 에러 + skip + 끝에 요약 |

### 11.4 세션 메타파일 라이프사이클

```
.pkm/sessions/<project-id>/<session-uuid>.json     # gitignored
```

```json
{
  "session_uuid": "01952f...",
  "project_id": "hwi-pkm",
  "transcript_path": "/Users/me/.claude/projects/.../01952f....jsonl",
  "transcript_sha256": "ab3c...",
  "transcript_message_count": 142,
  "processed_at": "2026-05-07T14:30:00+09:00",
  "extracted": {
    "decisions": 3, "pitfalls": 1, "snippets": 5, "qna": 0, "notes": 2
  },
  "extracted_paths": [
    "data/projects/hwi-pkm/decisions/2026-05-07-oauth-cookie-storage.md"
  ]
}
```

- 생성: `pkm session mark-processed`
- 삭제: `pkm session forget <uuid>` 명시 호출만
- gitignored: PC 별 transcript 와 동일 의미 (transcript 자체가 PC 별).

---

## 12. 에러 계약

### 12.1 신규 에러 코드 (`pkm/errors.py` 추가)

| 코드 | 종류 | 발생 |
|---|---|---|
| `NOT_A_GIT_REPO` | error | `pkm project link` 인데 cwd 가 git 아님 (`--allow-no-remote` 우회) |
| `ALREADY_LINKED` | info (exit 0) | 같은 git remote 가 이미 등록됨 — idempotent |
| `NOT_LINKED` | error (exit 1) | `pkm project current` / `--scope project` 인데 매핑 없음 |
| `PROJECT_ID_CONFLICT` | error | `--id <slug>` 명시했는데 이미 사용 중 |
| `INVALID_PROJECT_ID` | error | slug 가 영문/숫자/하이픈 외 포함 |
| `MISSING_PROJECT_FIELD` | error | `data/projects/<id>/**` frontmatter `project` 누락/불일치 (lint) |
| `INVALID_CATEGORY` | error | `category` 가 5 enum 외 (lint) |
| `CATEGORY_PATH_MISMATCH` | error | 경로 카테고리와 frontmatter `category` 불일치 (lint) |
| `ORPHAN_PROJECT_DIR` | warning | `data/projects/<id>/index.md` 누락 또는 `git_remotes` 비어있음 (lint) |
| `SIMILAR_KNOWLEDGE_CANDIDATE` | warning | 코사인 ≥ 0.92 인 항목 페어 (lint) |
| `CORRUPT_TRANSCRIPT` | error | jsonl 파싱 실패 — `pkm session show/mark-processed` |
| `PKM_INSTALL_MISSING` | error (strict only) | `pkm doctor --strict` 인데 `pkm install --for claude-code` 미실행 |

기존 `MIGRATION_FAILED` / `MIGRATION_PENDING` 은 m003 에 그대로 적용. 추출 LLM 실패는 *Claude in-session* 으로 처리되므로 별도 코드 없음.

### 12.2 실패 계약 (V1 §9.4 패턴 그대로)

- 비-0 종료 코드
- stderr `Error [<CODE>]: <message>`
- `--json`: `{"ok": false, "error": {"code", "message", "hint"}}`

### 12.3 Failure-mode matrix 커버리지

`tests/test_failure_mode_matrix.py` 에 위 12 코드 모두 시나리오 추가. 각 (a) 트리거 입력 (b) exit code (c) JSON 응답 검증.

---

## 13. 테스팅 전략

### 13.1 신규 테스트 파일

```
tests/
  test_project_resolution.py            # 5 단계 알고리즘, git remote 정규화 변형
  test_project_link.py                  # 멱등성, ALREADY_LINKED, --no-commit, frontmatter 시드
  test_project_knowledge_add.py         # frontmatter 검증, slug 정규화, auto-commit, --json
  test_project_rebuild_index.py         # index.md 결정론 빌드, 사용자 편집 덮어쓰기

  test_session_adapter_claude.py        # claude_code 어댑터 — discovery, header 파싱, encoded-cwd 디코딩
  test_session_lifecycle.py             # mark-processed 멱등, forget 후 재진입, gitignore 정합성
  test_session_list_filters.py          # --since, --min-messages, --unprocessed 조합

  test_context_inject.py                # --on-session-start, NOT_LINKED → stdout 비움, max-tokens 트림
  test_install_claude_code.py           # 멱등 install/uninstall, managed 마커, 사용자 수동 보존

  test_search_scope_project.py          # 새 스코프, cwd 자동 default, m003 후 NULL 행 동작
  test_related_scope.py                 # same-project + wiki default, --scope all
  test_lint_project_rules.py            # 4 신규 룰, --fix (MISSING_PROJECT_FIELD/CATEGORY_PATH_MISMATCH)
  test_lint_similar_knowledge.py        # SIMILAR_KNOWLEDGE_CANDIDATE 페어 검출

  test_migration_m003.py                # 컬럼/인덱스 추가, 기존 NULL backfill, 적용 전후 search 호환

  test_dashboard_graph_projects.py      # include_projects=true 노드 추가, project_filter, max_nodes cap

  fixtures/sessions/
    short_session.jsonl                 # min-messages cutoff
    typical_session.jsonl               # 일반 추출
    long_session.jsonl                  # 윈도우 분할
    corrupt_session.jsonl               # CORRUPT_TRANSCRIPT
```

### 13.2 통합 + 엔드투엔드

- `test_v3_acceptance.py` — 이 spec 의 §16.3 수락 기준 항목별 검증 (V1 `test_v1_acceptance.py` 패턴).
- `test_install_e2e.py` — `pkm install --for claude-code --dry-run` 결과 검증 (실제 `~/.claude/` 안 건드림).
- `test_backfill_idempotent.py` — fixtures 의 5 세션을 두 번 backfill 실행 → 두 번째는 모두 skip.

### 13.3 fixture 전략

- transcript fixtures 는 합성 jsonl (실제 사용자 대화 노출 위험 0).
- 인코딩된 cwd 는 `tests/fixtures/.claude-projects/-tmp-fake-repo/` 형태로 흉내.
- `~/.pkm/config.toml` 은 `tmp_path / "pkm-config.toml"` 로 mock (`PKM_CONFIG` 환경변수 또는 monkeypatch).

---

## 14. doctor 통합

`pkm doctor` 출력에 row 4 추가 (모두 `--json` items 배열):

| Row | 의미 | --strict |
|---|---|---|
| `projects` | `data/projects/<id>/` 디렉토리 카운트 + 매핑된 git remote 총 개수 | NULL OK |
| `pkm_install` | `~/.claude/{commands,skills,CLAUDE.md}` 의 managed 블록 존재 + 버전 | 누락 → `PKM_INSTALL_MISSING` exit 1 |
| `current_project` | cwd → project-id 해석 (또는 `not_linked`) | informational |
| `unprocessed_sessions` | 현재 프로젝트의 미처리 세션 수 | informational |

기존 `schema_version` row 가 m003 도 자동 추적 (V2 의 m002 처리와 동일).

---

## 15. 호환성 + 결정론

### 15.1 V1·V2 데이터 호환

- 기존 `data/wiki/**`, `data/raw/**`, `data/writing/**` 의 스키마 변경 없음.
- 기존 frontmatter 에 `project`/`category` 필드 추가 없음 (조건부 필수: `data/projects/**` 일 때만).
- m003 적용 후 기존 chunks 행은 모두 `project = NULL, category = NULL, session_id = NULL`. 검색 SQL WHERE 절에서 자연스럽게 wiki/raw/writing 으로 분류.

### 15.2 기존 명령 동작 변경

| 명령 | V3 변경 | Backward-compat |
|---|---|---|
| `pkm search` (no `--scope`) | cwd-linked 시 default = `wiki + project:<auto>` | linked 안 된 cwd 는 기존 동작과 동일. linked cwd 는 default 가 더 좁아짐 → release note 명시. `--scope all` 로 옛 동작 강제 가능 |
| `pkm reindex db --scope all` | 의미 확장 (projects 포함) | 더 넓어질 뿐, 기존 호출 깨지지 않음 |
| `pkm related` (no `--scope`) | default = `same-project + wiki` | wiki 페이지 기준이면 기존과 동일. 새 `data/projects/**` 에서만 의미 있음 |
| `pkm lint` | 신규 4 룰 추가 | 기존 wiki/raw/writing 파일은 새 룰에 안 걸림 (조건부 적용). 새 디렉토리만 영향 |

### 15.3 결정론

- `data/projects/<id>/index.md` 는 frontmatter 에서 결정론적 빌드 — 동일 corpus → 동일 출력.
- session adapter discovery 는 mtime 정렬 이후 path 정렬 (tie-breaker) — 동일 transcript 집합 → 동일 순서.
- `data/projects/<id>/<category>/<slug>.md` 의 slug 는 `YYYY-MM-DD-<title-slugified>` — 동일 입력 → 동일 slug.
- `pkm context inject` 의 max-tokens 트림은 *문장 경계* 우선, 동일 입력 → 동일 출력.

### 15.4 외부 의존성 추가 0

- 새 PyPI 의존성 없음. (V2 의 `kiwipiepy[korean]` extra 그대로.)
- 새 vendored asset 없음. (V2 의 `vis-network` 그대로 사용.)
- Claude Code 의 standard 메커니즘 (commands/, skills/, CLAUDE.md) 만 사용.

---

## 16. M13/M14 마일스톤 로드맵

### 16.1 M13 — Project scope foundation (데이터 평면)

V3 의 절반. 사용자가 *손으로* 프로젝트 지식을 운용할 수 있게 됨 (AI 자동화 제외).

| 단계 | 산출 |
|---|---|
| M13.1 | `pkm/store/migrations/m003_project_scope.py` + `pkm migrate` 자동 등록 + `pkm doctor` row |
| M13.2 | `pkm/session/registry.py` + 7.1 5 단계 해석 + git remote 정규화 |
| M13.3 | `pkm/commands/project.py` — link/list/current/show/rebuild-index/rm |
| M13.4 | `pkm/commands/project.py` — `knowledge add` (frontmatter 검증 + slug 정규화 + auto-commit) |
| M13.5 | `pkm reindex db --scope projects|project:<id>` + search 새 스코프 + cwd default |
| M13.6 | `pkm related --scope same-project|wiki|all` |
| M13.7 | lint 4 신규 룰 + `SIMILAR_KNOWLEDGE_CANDIDATE` |
| M13.8 | dashboard graph `include_projects` + 노드 색 + project_filter |
| M13.9 | `~/.pkm/config.toml` 글로벌 설정 + `.pkm/config.local.toml` `[project_overrides]` |
| M13.10 | SCHEMA.md / FEATURES.md / README.md (6 → 7 레이어) 갱신 |

### 16.2 M14 — Session adapter + skills (AI 통합)

V3 의 나머지 절반. AI 가 자동화.

| 단계 | 산출 |
|---|---|
| M14.1 | `pkm/session/adapters/{base,claude_code}.py` |
| M14.2 | `pkm/commands/session.py` — list/show/forget/mark-processed |
| M14.3 | `pkm/commands/context.py` — `pkm context inject` |
| M14.4 | `pkm/commands/install.py` — `pkm install --for claude-code` (--uninstall 포함) |
| M14.5 | `pkm/templates/skills/recalling-project-context/**` |
| M14.6 | `pkm/templates/skills/extracting-session-knowledge/**` |
| M14.7 | `pkm/templates/skills/backfilling-sessions/**` |
| M14.8 | `pkm/templates/commands/pkm-*.md` (4 종) |
| M14.9 | `pkm/templates/claude_md_block.md` + managed 마커 갱신 로직 |
| M14.10 | doctor `pkm_install` row + `--strict` 게이트 |
| M14.11 | UC8 (post-session extract) + UC9 (backfill) walk-through 추가 (FEATURES.md) |

### 16.3 V3 수락 기준 (V2 delta)

이 사이클이 끝났다고 부를 수 있으려면:

**M13 수락 기준:**
- [ ] m003 적용 후 기존 wiki/raw/writing 검색 결과 ≡ V2 (regression 0)
- [ ] `pkm project link` 멱등 (재호출 → ALREADY_LINKED, exit 0)
- [ ] 두 PC 가 같은 데이터 repo 를 git pull 했을 때 두 PC 모두 동일 `pkm project current` 결과 (universal git remote 매칭)
- [ ] `pkm search --scope project` 가 NOT_LINKED cwd 에서 hard-fail
- [ ] cwd-linked 검색 default 가 `wiki + 현재 project` 로 좁혀짐 (release note 명시)
- [ ] lint 4 신규 룰 모두 `tests/test_failure_mode_matrix.py` 에 추가
- [ ] `pkm/errors.py` 신규 7 코드 (M13 분량) 모두 정의

**M14 수락 기준:**
- [ ] `pkm install --for claude-code` 멱등 (재실행 → 변경 0)
- [ ] `pkm install --uninstall --for claude-code` 가 managed 마커만 제거 (사용자 수동 추가 보존)
- [ ] cwd 가 untracked 인 세션에서 `~/.claude/CLAUDE.md` 의 PKM 블록이 노이즈 0 (silent proceed)
- [ ] `pkm session list --unprocessed` 가 메타파일 없는 세션만 반환
- [ ] backfill 두 번 실행 시 두 번째는 모두 skip (idempotent)
- [ ] backfill 중단 후 재호출 시 마지막 처리된 세션 다음부터 재개
- [ ] `pkm doctor --strict` 가 PKM install 누락 시 `PKM_INSTALL_MISSING` exit 1

**전체 V3 수락 기준:**
- [ ] V1·V2 의 모든 명령 동작 보존 (기존 테스트 통과)
- [ ] 새 PC 셋업 시나리오 (§8.3) 가 처음부터 끝까지 동작
- [ ] `data/projects/hwi-pkm/` 가 본 프로젝트 자체에 도그푸딩 (등록 + 첫 backfill 완료)

---

## 17. 비-스코프 + 미해결 이슈

### 17.1 V3 비-스코프

다음은 *의도적으로* V3 에서 다루지 않음:

| 항목 | 사유 / 향후 시점 |
|---|---|
| Codex / Cursor / Gemini CLI 어댑터 | Q7 결정 — V3 = Claude Code 만. 어댑터 인터페이스는 준비. V4 에서 1 개씩 추가 |
| MCP 서버 노출 (`pkm.search_project` 등) | Q5 에서 후보였으나 스킬 + CLAUDE.md 로 충분. V4 검토 |
| 프로젝트 지식의 자동 wiki 승격 추천 | 사용자 명시 `pkm promote` 호출만. 자동 추천 (예: 한 결정이 N 프로젝트 반복) 은 V4 |
| Cross-project 패턴 발견 (자동) | `--scope all` 검색으로 수동 가능. 자동 *"이 결정은 모든 프로젝트에 공통이라 wiki 로 승격하세요"* 같은 의견은 V4 |
| `data/projects/<id>/` 의 자체 그래프 (프로젝트 내 backlinks 만) | V3 는 통합 graph 만. 프로젝트 내부 그래프 페이지 분리는 V4 |
| Claude Code 외 세션 (e.g. claude.ai 웹 export) import | Q1 결정 — Claude Code only. 웹 export 도 V4 |
| `pkm session export` (다른 도구로 transcript 내보내기) | 사용자 요구 부재 |

### 17.2 미해결 이슈

- **Session UUID 중복**: 매우 드물지만 두 PC 가 같은 session-uuid 의 transcript 를 가질 수 있음 (Claude Code 의 uuid 생성 알고리즘 의존). 메타파일이 PC 별 gitignored 라 충돌은 없지만, *동일 지식이 두 PC 에서 두 번 추출* 될 수 있음. dedup 은 lint `SIMILAR_KNOWLEDGE_CANDIDATE` 가 사후 표면화. 명시적 globally-unique 보장은 V4 검토.

- **`pkm project rebuild-index` 의 컨텐츠 정책**: 어느 카테고리에서 몇 개 항목을 index.md 에 노출할지 (기본 5 개씩 가정) 가 사용자 선호에 따라 다를 수 있음. V3 는 hard-coded 5/5/5/5 + 최근 세션 5, 추후 `[index]` 설정 블록으로 사용자 조정 노출은 V4.

- **CLAUDE.md managed 블록의 markdown 파서 호환성**: 사용자가 CLAUDE.md 를 외부 도구 (Obsidian 등) 로 편집하면 managed 마커가 깨질 수 있음. V3 는 멱등 install 이 재생성하므로 큰 문제 아니지만, parser-resilient 마커 (예: `<!--PKMSTART-->`/`<!--PKMEND-->`) 로 강화 검토.

- **monorepo 의 sub-dir → project 매핑**: V3 는 머신별 `[project_overrides]` 로 해결. 한 데이터 repo 안에서 multi-PC 가 같은 monorepo sub-dir 매핑을 공유하려면 frontmatter `subpath` 필드 추가가 필요할 수 있음. V3 는 보류, 패턴 보이면 V4.

---

## 18. 위험 & 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| **검색 default 변경이 기존 사용자 경험 깨뜨림** | linked cwd 의 검색 결과가 좁아져서 *"옛 결과 어디 갔지?"* | release note 명시 + `--scope all` 강제 옵션 안내 + `pkm doctor` 가 default 변경 알림 |
| **스킬 자동 트리거 미발화** | Claude 가 CLAUDE.md 지시 무시 → 프로젝트 컨텍스트 미주입 | description 강화 + 사용자가 명시 `/pkm-recall` 으로 우회 가능 + 미주입은 노이즈 0 (조용한 실패) |
| **`pkm install` 이 사용자 settings.json 충돌** | 사용자가 직접 추가한 hooks/commands 와 충돌 | V3 디자인 결정 — settings.json 안 건드림. CLAUDE.md 와 commands/skills/ 만 작성 (managed 마커로 격리) |
| **m003 마이그레이션 후 `--full reindex` 미실행 → 검색 비대칭** | 기존 데이터의 project/category 가 SQL NULL 이라 `--scope project:<id>` 에서 안 잡힘 — *but 의도된 동작* | NULL = 비프로젝트 = wiki/raw/writing 분류. release note + doctor 안내. |
| **`/pkm-extract-session` 이 너무 긴 transcript 에서 실패** | 토큰 한계 hit | 50 메시지 + overlap 5 윈도우 슬라이딩 + 부분 결과 폐기 (재실행 시 처음부터) |
| **multi-PC backfill 중복 추출** | 같은 결정이 두 PC 에서 각각 추출 | `SIMILAR_KNOWLEDGE_CANDIDATE` lint warning 으로 사후 dedup 안내 |
| **글로벌 `~/.claude/CLAUDE.md` 가 다른 도구와 충돌** | 다른 PKM 류 도구가 같은 위치 사용 | managed 마커 (`<!-- pkm:start -->` ... `<!-- pkm:end -->`) 로 블록 격리. uninstall 시 마커 사이만 제거 |
| **세션 메타파일 누적 (`.pkm/sessions/<id>/<uuid>.json`)** | 수년 사용 시 수만 개 파일 | gitignored + 파일 크기 ~500B → 큰 문제 아님. cleanup 명령 (`pkm session prune`) 은 V4 검토 |
| **`pkm:extracting-session-knowledge` 스킬 출력 품질 (hallucination)** | 추출된 결정 중 일부가 실제로 결정 아님 | 사용자 검수 게이트 (Q4 D 두 라운드) 가 hard 차단. `--auto-approve` 명시 시만 우회 |

---

## 19. 부록 — 도그푸딩 체크리스트

본 spec 머지 + M13/M14 구현 후, hwi_PKM 프로젝트 자체에 도그푸딩:

```bash
cd ~/Documents/pkm
pkm migrate --apply                                   # m003 적용
pkm reindex db --full                                 # 권장
pkm install --for claude-code --data-repo $(pwd)      # 글로벌 인프라
cd ~/Downloads/Claude_lab/hwi_PKM
pkm project link --id hwi-pkm                         # 본 프로젝트 등록
# Claude Code 안에서:
/pkm-backfill --project hwi-pkm --since 2026-04-01    # 과거 세션 일괄 처리
/pkm-recall "M11 grounding gate 결정"                 # 검증
pkm project show hwi-pkm                              # 통계 + index.md 확인
pkm doctor --strict                                   # 모두 ✓
```

도그푸딩 결과는 후속 PR 에서 *"V3 GA 완료"* 의 evidence 로 제출.

---

**Status**: design (브레인스토밍 통과, plan 분해 대기)
