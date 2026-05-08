---
title: Code Seeding Guide — AI 가 코드를 분석하여 PKM 프로젝트 지식을 시드하는 행동 매뉴얼
status: design
created_at: 2026-05-08
related_specs:
  - 2026-05-07-pkm-projects-and-sessions-design.md
---

# Code Seeding Guide — Design

## 1. 문제

`pkm project link` 직후의 신규 프로젝트는 `data/projects/<id>/` 가 비어 있다. 사용자는 "지식 0" 상태에서 시작해 세션 추출 (`/pkm-extract-session`) 또는 backfill (`/pkm-backfill`) 로 채워야 하는데, 두 경로 모두 **사람의 대화 흔적** 이 전제다. 이미 존재하는 **코드 자체** 에 녹아 있는 지식 — 자주 쓰이는 helper, 모듈 책임 — 은 별도 채널이 없어 활용되지 못한다.

목표: 신규 링크 직후 또는 임의 시점에 사용자가 명시적으로 호출하면, AI 에이전트가 코드를 훑어 후보 지식 (snippets · notes) 을 제안하고, 항목별 사용자 검토 후 기존 `pkm project knowledge add` 로 시드한다. **자동화는 명시적으로 거부** — 노이즈 통제를 사용자 검토에 의존한다.

## 2. 비-목표

- 자동 트리거 (cron / git hook / link-time 자동 실행). 매번 사용자 명시 호출.
- decisions / pitfalls / qna 카테고리. 코드만으로 신호가 약하거나 오해 위험. 추후 별도 가이드로 확장 가능.
- 신규 CLI · 신규 슬래시 · 신규 스킬 · frontmatter 필드 · lint 룰 · install manifest 변경. **PKM 코어 0 변경.**
- Incremental seeding (last-seeded-commit 추적). full scan 매번, dedupe 는 사용자 검토 + 기존 항목 휴리스틱 매칭으로.
- 언어별 AST. ripgrep regex 만으로 Python · TS · Go · Rust · C# 등을 한 코드 경로로 커버.

## 3. 디자인 결정 (대안 vs 선택)

| # | 결정 | 대안 | 채택 | 이유 |
|---|---|---|---|---|
| 1 | 트리거 | (a) link 직후 1 회만 (b) 언제든 명시 호출 (c) link 후 hint + 별도 명령 | **(b)** | 코드는 시간이 지나며 자란다. 1 회 한정은 가치 작음. |
| 2 | 분석 방법 | (a) static-only ripgrep (b) LLM 전체 스캔 (c) hybrid | **(c)** | static 으로 후보 풀 좁힘 (노이즈 ↓) + LLM 이 의미 부여 (제목/요약). M14 의 결정론 CLI + Claude 분업 컬러와 동형. |
| 3 | 카테고리 | (a) snippets+notes (b) +pitfalls (c) +decisions (d) qna 빼고 4 종 | **(a)** | 사용자 의도 ("자주 쓰는 helper", "공통 로직") 와 직결. 다른 카테고리는 코드 시그널이 약하거나 잘못된 추론 위험. |
| 4 | 언어 | (a) ripgrep regex 무관 (b) Python AST 우선 (c) 어댑터 | **(a)** | PKM 도구는 다양한 언어 프로젝트에 깔린다. Python·TS·Go·Rust·C# 모두 정의 시그니처 regex 로 커버. 정밀도 부족분은 사용자 검토가 흡수. |
| 5 | 검토 UX | (a) 표 일괄 + 라운드 2 (b) 한 항목씩 inline (c) auto-threshold | **(a)** | `extracting-session-knowledge` 와 동일 패턴 → 일관성. 노이즈는 후보 풀 자체를 좁혀 (top-N 컷) 통제. |
| 6 | Dedupe | (a) source_ref frontmatter 신설 (b) 제목/path 휴리스틱 (c) 사용자 표시만 | **(b)** | (a) 는 frontmatter 필드 추가 + lint 룰 → PKM 코어 변경 발생. **사용자가 "PKM 과 무관, 문서로만" 으로 변경 요청.** 휴리스틱만으로 충분. |
| 7 | Incremental | (a) full scan 매번 (b) last-seeded-commit (c) 옵션 플래그 | **(a)** | 단순. dedupe 가 "이미 시드된 후보" 를 거를 수 있으면 incremental 의 가치는 미미. |
| 8 | 배포 형태 | (a) 단일 가이드 markdown (b) +슬래시 1 줄 (c) +템플릿 스킬 정식 등록 | **(a)** | 사용자 요청: "pkm 과 관련없이 문서로만". install manifest 변경 0. |

## 4. Architecture

```
┌──────────────────────────────────────────────────────────┐
│ docs/code-seeding-guide.md  (단일 신규 파일)                  │
│   = AI 행동 매뉴얼                                          │
│   - 단계 (project_id resolve → 후보 풀링 → 검토 → 시드)        │
│   - ripgrep 패턴 카탈로그 (정의 시그니처, 호출 빈도)           │
│   - 카테고리 룰 (snippets vs notes 판단 기준)                 │
│   - 검토 표 포맷 (extracting-session-knowledge review-protocol 차용) │
│   - dedupe 휴리스틱 (`pkm search` + `grep -l`)               │
│   - 후처리 명령 시퀀스                                       │
└──────────────────────────────────────────────────────────┘
                       │ (사용자가 어태치 + 요청)
                       ▼
                 Claude (Read)
                       │
                       ▼ (가이드 단계 따라)
┌──────────────────────────────────────────────────────────┐
│ 기존 PKM CLI (코드 변경 0)                                   │
│   pkm project current                                     │
│   pkm project knowledge add  --source-type ai_session     │
│   pkm project rebuild-index                              │
│   pkm reindex db --scope project:<id>                    │
│   pkm search          (dedupe 보조)                       │
└──────────────────────────────────────────────────────────┘
```

호출 UX:

```
[Claude Code 세션, cwd = ~/Code/some-app]
> @~/Downloads/Claude_lab/hwi_PKM/docs/code-seeding-guide.md
> 이 가이드 따라 cwd 코드 분석해서 시드 해줘
```

또는 사용자가 가이드 본문을 평문으로 컨텍스트에 들고 와서 요청.

## 5. Data Flow

```
[1] project resolve
    pkm project current --json
    ok=false  → "현 cwd 미링크. pkm project link 먼저" + stop
    ok=true   → project_id 기록

[2] 후보 풀링 (Static, ripgrep)
    snippets:
      rg -nU --type-add 'src:*.{py,ts,tsx,js,go,rs,cs,kt,swift}' --type src \
         '^\s*(def |function |func |fn |public\s+\w+\s+|private\s+\w+\s+)\w+\s*\('
      → 정의 시그니처 + 함수명 추출
      → 각 이름에 대해 다른 파일에서 호출 횟수 카운트:
        rg -c -w '<name>' --type src
      → 호출 횟수 ≥ N (디폴트 5) 인 top-K (디폴트 20) 후보

    notes:
      depth 1~2 의 디렉토리 중:
        - README* / __init__.py / index.{ts,js} 가 있는 디렉토리
        - 또는 파일 ≥ 5 개 들어있는 모듈 디렉토리
      → top-K (디폴트 10) 후보

[3] 의미 부여 (Claude Read)
    각 후보에 대해 정의/디렉토리 내용을 Read →
    title (한 줄), summary (3-4 문장), tags (3-5 개) 생성

[4] dedupe 휴리스틱
    각 후보 (title, source_path) 페어에 대해:
      pkm search "<title>" --scope project --json -n 3
      grep -l "<source_path>" data/projects/<id>/{snippets,notes}/*.md
    매칭이 있으면 후보 표에 "⚠ 기존 항목과 유사 (<path>)" 마크.
    사용자가 round 1 에서 빼라 하면 빠짐.

[5] 검토 round 1
    extracting-session-knowledge/review-protocol.md 와 동일 포맷:
    ## snippets (N)
    1. **<title>** — <summary 1줄> _src:_ `<source_path>` _신호:_ 호출 12회
    2. ...
    ## notes (M)
    ...
    > "위 후보들 중 변경/제외할 것 알려주세요. 다 OK 면 '진행'."

[6] round 2
    응답 적용 → 재출력 → "최종 OK?"
    OK → step 7. 더 수정 → 라운드 추가 (최대 3).

[7] 시드 (× N)
    for each accepted candidate:
      <body> | pkm project knowledge add \
        --project <project_id> \
        --category snippets|notes \
        --slug <human-slug> \
        --title '<title>' \
        --tags 'code-seed,<category-tags>' \
        --source-type ai_session \
        --json
    body 안엔 코드 인용:
      ## 사용 예
      ```python
      [pkm/llm_bridge.py:L42-L58]
      def send(...): ...
      ```
    `--source-type ai_session` 은 기존 enum 재사용 (신규 enum 추가 X).
    출처 표시는 `--tags code-seed` 로.

[8] 후처리
    pkm project rebuild-index <project_id>
    pkm reindex db --scope project:<project_id>

[9] 보고
    "코드 시드 완료. <project_id>: snippets N, notes M. 새 항목은 data/projects/<id>/.
     다음 세션에서 /pkm-recall <topic> 로 검색됨.
     이미 시드된 항목과 같은 helper 라면 다음 호출에서 dedupe 휴리스틱이 표에 마크함."
```

## 6. 가이드 문서 구조 (`docs/code-seeding-guide.md`)

| 섹션 | 내용 |
|---|---|
| 1. When to use | 사용 시점 (link 직후 + 임의 시점), 사전 조건 (linked PKM project) |
| 2. Steps | 위 §5 의 9 단계를 사용자 향 순서로 |
| 3. Ripgrep patterns | 언어별 정의 시그니처 정규식, 호출 횟수 카운트 명령. fallback (`ripgrep` 미설치 시 `grep -rE`) |
| 4. Category rules | snippets vs notes 결정 기준 (함수 단위 → snippets, 디렉토리 단위 → notes) |
| 5. Review protocol | 표 포맷, round 1/2 명령. `extracting-session-knowledge/review-protocol.md` 와 동형 |
| 6. Dedupe heuristics | `pkm search` 호출 + `grep -l` 휴리스틱 디테일 |
| 7. Knowledge add 호출 | `pkm project knowledge add` 인자 매핑 + 본문 템플릿 |
| 8. Post-processing | rebuild-index + reindex 명령 시퀀스 |
| 9. Failure modes | NOT_LINKED, ripgrep 미설치, 후보 0, knowledge add 실패 |
| 10. Self dry-run example | 본 hwi_PKM repo 자기 자신에 한 번 돌려 얻은 후보 표 예시 (가이드 품질 가드) |

## 7. Error / Failure Modes

| 상황 | 가이드 동작 |
|---|---|
| `pkm project current` → NOT_LINKED | "현 cwd 미링크. `pkm project link --id <slug>` 먼저 실행" 안내 후 stop |
| `ripgrep` 미설치 | `grep -rE` fallback 패턴으로 동등 결과 (정밀도 약간 ↓), 한 줄 노티스 |
| 후보 0 | "코드 시그널 부족 또는 이미 모두 시드됨" 보고, 종료 — 빈 라운드 진입 X |
| `pkm project knowledge add` 실패 | 1 회 재시도. 두 번째 실패 시 verbatim surface, 나머지 후보는 시드 진행 (`--no-commit` X — 부분 성공 허용) |
| 라운드 3 까지도 사용자 OK 안 함 | "후보를 명시적 리스트로 알려주세요" 요청 후 정확 매칭만 시드 |

## 8. Testing

- 가이드 자체엔 자동 테스트 없음 (행동 명세 markdown)
- 가이드가 호출하는 명령은 기존 테스트가 커버:
  - `pkm project current` → `tests/test_project_link.py`
  - `pkm project knowledge add` → `tests/test_project_knowledge_add.py`
  - `pkm project rebuild-index` → `tests/test_project_rebuild_index.py`
  - 검색 dedupe → `tests/test_search_scope_project.py`
- **품질 가드 (수동)**: 가이드 §10 의 dry-run 예시는 본 hwi_PKM repo 에서 가이드를 따라 한 번 돌려 얻은 실제 후보 표여야 한다. 향후 가이드 수정 시 이 예시도 같이 갱신 (사양 review 시 chk).

## 9. Open Questions

- 가이드 위치를 `docs/code-seeding-guide.md` 로 할지 `docs/guides/code-seeding.md` 로 할지. → `docs/code-seeding-guide.md` 로 시작, 추후 `docs/guides/` 디렉토리 생기면 이전.
- 본 hwi_PKM repo 의 README / FEATURES.md 에 가이드 포인터 한 줄 추가할지. → 추가 권장 (UC10 정도로). 단 PKM 코어 변경은 아니므로 별도 미니 PR 가능.

## 10. Out of Scope (V2 후보)

- decisions / pitfalls 카테고리 — TODO/FIXME 댓글, "regression for ..." 테스트명 시그널은 일부 가치 있지만 정밀도 검증 필요. 별도 가이드 (`docs/code-pitfalls-guide.md`) 로 분리.
- Incremental seeding (`--since-last-commit`)
- 슬래시 명령 (`/pkm-seed-from-code`) 정식 등록 — UX 가치 vs install manifest 변경 비용 trade-off, V1 사용 후 데이터로 결정.
- 언어별 AST 어댑터 (`tree-sitter` 등) — ripgrep 정밀도가 부족하다고 판명될 때만.
