# PKM V2 설계 — Graph Surfacing · Writing Grounding · Migration Infra

**Status**: design (브레인스토밍 통과, plan 분해 대기)
**Date**: 2026-05-06
**Author**: hwijung-park
**Predecessor**: `docs/superpowers/specs/2026-05-01-pkm-design.md` (V1 — 본 문서는 V1 의 6 레이어/철학/경계를 전제하며, 그 위에 쌓는 V2 확장만 다룸. V1 의 어휘·구조·결정론 약속을 변경하지 않음.)

---

## TL;DR

V1 GA 이후 첫 V2 사이클. 세 마일스톤으로 분해.

- **M10 — Graph Surfacing**: `pkm wiki suggest <slug>` CLI + dashboard 의 `graph.html` 페이지. 이미 결정된 `find_suggestions`(missing-link) 결과를 일상 워크플로우와 시각화에 동시 노출.
- **M11 — Writing Grounding**: writing → wiki promote 의 인용 무결성 게이트화. lint 사전 경고 + promote hard 게이트로 4 가지 정합성 룰 강제. `/write --from-search` 흐름이 suggested-link 후보를 함께 노출.
- **M12 — Migration & Kiwi**: `pkm migrate` 인프라 + 첫 마이그레이션 `002_kiwi_tokenizer`. 한국어 BM25 정밀도 향상을 옵셔널 의존성(`[korean]` extra)으로 도입.

V2 GA 도달 시점에 V1 §9.2 의 V2 보류 항목 4 개 (graph 시각화 / Citation 그래프 / 한국어 형태소 분석기 / 스키마 마이그레이션 명령) 가 닫힘.

---

## 목차

1. 동기 + V1 매핑
2. 아키텍처 경계 (보존 + 확장)
3. M10 — Graph Surfacing
4. M11 — Writing Grounding
5. M12 — Migration Infra + Kiwi
6. 횡단 사항 (에러 코드 / config / 의존성 / 문서)
7. 결정론 + 재현성 보장
8. V2 수락 기준 (V1 delta)
9. 위험 & 완화
10. 비-스코프
11. 마일스톤 로드맵

---

## 1. 동기 + V1 매핑

### 1.1 V1 GA 이후 운영 관찰

V1 (M1–M9) 운영 결과 다음 갭이 드러남:

| 갭 | 사용자 체감 | V1 대응 한계 |
|---|---|---|
| **고립된 wiki** 가 lint warning 으로만 잡힘 | "어디로 연결해야 할지" 단서 없음 | `ORPHAN_WIKI` 가 사실만 알려줌 — 후보를 제안하지 않음 |
| **방금 추가한 `MISSING_LINK_CANDIDATE`** 의 가치를 lint 한 군데에서만 받음 | 한 페이지 작업 중에 즉시 묻기 어려움 | CLI 표면 부재. 시각화 부재 |
| **writing 의 인용** 이 슬래시 가이드만으로 강제 | AI 가 인용 안 하고 본문만 쓰면 wiki 로 promote 까지 통과 | `derived_from` path 존재 검사만 — 본문 인용 검사 없음 |
| **한국어 BM25 회수율** 이 trigram 한계에서 멈춤 | "환경설정의 인증 토큰 저장" 같은 어절형 쿼리 누락 | V1 §9.5 위험표가 V2 Kiwi 옵션으로 명시 보류 |
| **스키마 변경 절차** 부재 | 다음 V2 기능에서 스키마 손대면 마이그레이션 비용 즉시 발생 | V1 §8.6 이 V2 `pkm migrate` 로 명시 보류 |

V2 사이클은 위 갭을 닫는 것에 집중하며, V1 의 6 레이어 / 4 게이트 / 결정론 / 자동 git / strict 권한을 모두 보존한다.

### 1.2 V1 spec 과의 매핑

| V2 작업 | V1 spec 참조 | 관계 |
|---|---|---|
| M10 graph 페이지 | §7.7 V2 확장 슬롯 → graph.html (D3) | 스택만 vis-network 로 변경 — 사유는 §3.2 |
| M10 `pkm wiki suggest` | §5.8 관계도 + `pkm related` | `pkm related` 가 보여주는 backlinks/semantic 을 *제안* 측면으로 확장 |
| M11 writing grounding | §4.2 Citation 계약 (`/ask` 그라운딩) | V1 의 `/ask` 인용 약속을 writing → wiki promote 게이트로 확장 |
| M11 `find_suggestions` 통합 | §6.5 Lint 룰 | 방금 추가된 `MISSING_LINK_CANDIDATE` (V1.x) 를 writing 작성 흐름에도 노출 |
| M12 `pkm migrate` | §8.6 신뢰성 — 마이그레이션 보류 | V2 명시 작업 |
| M12 Kiwi | §5.5 한국어 처리 + §9.5 위험표 | trigram 한계 보완 |

---

## 2. 아키텍처 경계 (보존 + 확장)

### 2.1 V1 경계 — 변경 없음

| 경계 | V2 영향 |
|---|---|
| **markdown = 진실** | 변경 없음 — 모든 신규 데이터는 `.pkm/index.db` 에서 결정론적으로 재생성 가능 |
| **CLI 코어 = 결정론, LLM SDK 0** | M10/M11/M12 모두 LLM 호출 없음. `find_suggestions`(이미 결정론) + grounding 검사(정규식) + tokenizer(로컬) |
| **옵트인 셸아웃** | `pkm search --expand` 흐름 변경 없음 |
| **자동 git 커밋** | 변경 없음 — `pkm migrate --apply` 도 mutate 라 자동 커밋 |
| **Strict 권한 (data/wiki/** deny)** | 변경 없음. graph 페이지·writing grounding 모두 권한 모델 우회 안 함 |

### 2.2 신규 의존성 (옵셔널)

| 의존성 | 도입 위치 | 미설치 시 동작 |
|---|---|---|
| `vis-network.min.js` (~70 KB gzip, ~200 KB raw) | `pkm/dashboard/assets/` 에 vendored | dashboard 빌드 + graph 페이지 로드만 영향. PyPI 의존성 아님. |
| `kiwipiepy>=0.17` | `[korean]` extra | trigram 폴백. 마이그레이션 SKIP. |

### 2.3 신규 데이터 플레인

추가되는 인덱스/테이블:
- `chunks.text_tokenized` 컬럼 (M12) — kiwi 사전 토큰화 결과 저장. 영문/혼합 lang 분기.

추가되는 산출물:
- `dashboard/graph.html` + 인라인 graph.json (M10) — `links` + `documents` + `find_suggestions` JOIN 결과를 빌드 시점에 박음.

추가되는 정규식 / 헬퍼:
- `pkm/lint/citations.py` — inline citation 추출 단일 진실 (M11)
- `pkm/search/tokenizer.py` — 토크나이저 어댑터 인터페이스 (M12)
- `pkm/store/migrations/` — 마이그레이션 등록·러너 (M12)

---

## 3. M10 — Graph Surfacing

### 3.1 `pkm wiki suggest <slug>` (item 1)

**역할**: 한 wiki 페이지에 한정해서 missing-link 후보를 즉시 보여주는 CLI. lint warning(전체 코퍼스) 의 보완.

**인터페이스**:

```bash
pkm wiki suggest <slug>                     # 텍스트 표 출력
pkm wiki suggest <slug> --json              # 머신리더블
pkm wiki suggest <slug> -n 10               # top-N 오버라이드 (기본: config.top_k_per_doc)
pkm wiki suggest <slug> --threshold 0.85    # ad-hoc 임계값 오버라이드
```

**텍스트 출력 형식**:

```
oauth-token-storage (3 suggestions):
  0.83  data/wiki/concepts/session-cookie-pinning.md
  0.79  data/wiki/concepts/csrf-token-rotation.md
  0.78  data/wiki/notes/refresh-token-leak-2024.md
hint: copy [[<slug>]] into your draft, or run `pkm wiki edit oauth-token-storage --patch`.
```

**JSON 출력 형식**:

```json
{
  "ok": true,
  "slug": "oauth-token-storage",
  "suggestions": [
    {"path": "data/wiki/concepts/session-cookie-pinning.md", "slug": "session-cookie-pinning", "similarity": 0.83},
    ...
  ]
}
```

**구현**:
- 핸들러: `pkm/commands/wiki.py` 의 `wiki` typer app 에 `suggest` 서브커맨드 추가
- 핵심 로직: `pkm/lint/missing_links.py` 에 `find_suggestions_for(root, slug, *, n=None, threshold=None)` 추가 — lint rule 과 코드 100% 공유. 단일-doc 모드는 `_find_suggestions` 의 source 루프를 한 doc 으로 좁힘.

**에러 코드 + hint**:
- 슬러그가 wiki 에 없음 → `PKMNotFoundError` (`NOT_FOUND`)
- 인덱스 없음 (`.pkm/index.db` 부재) → `PKMStateError` (`INDEX_MISSING`, hint=`Run pkm reindex db --full`)
- 임계값/n 음수 → `PKMValidationError`

### 3.2 Dashboard graph 페이지 (item 2)

**페이지 경로**: `dashboard/graph.html`

**파일 추가**:

| 파일 | 역할 |
|---|---|
| `pkm/dashboard/pages/graph.py` | `build_graph(out, ctx)` 빌더. context.suggestions + registry.outgoing/backlinks 를 graph.json 으로 직렬화 |
| `pkm/dashboard/templates/graph.html.j2` | vis-network 컨테이너 + 토글 UI. graph.json 을 `<script id="graph-data" type="application/json">…</script>` 로 인라인 |
| `pkm/dashboard/assets/vis-network.min.js` | vendored ~200 KB. 라이선스(Apache-2.0) 파일도 동봉. |
| `pkm/dashboard/assets/graph.js` | 페이지 진입 시 graph-data 읽어서 vis-network 초기화 |

**노드 정의**:

| 노드 종류 | 기본 표시 | bucket 별 색깔 |
|---|---|---|
| wiki (status ∈ active/stub) | ON | concepts(파랑) / entities(초록) / notes(주황) / reports(보라) |
| writing (status ∈ final/promoted) | OFF (토글) | 회색 |
| capture (status = reviewed) | OFF (토글) | 옅은 회색 |

deprecated 상태는 모두 제외.

**엣지 정의**:

| 엣지 종류 | 스타일 | 토글 |
|---|---|---|
| `wikilink` (본문 `[[slug]]`) | 진한 회색 실선 | ON (기본) |
| `derived_from` (frontmatter) | 회색 점선 | ON (기본) |
| `tag` (공통 태그 = 페어) | 옅은 점선 | OFF (노이즈 방지) |
| `suggested` (find_suggestions 결과) | 빨강/주황 점선 | ON (기본) — "이어졌으면 좋은" 가상 엣지 |

**페이지 레이아웃**:

```
┌────────────────────────────────────────────────────┐
│ [filter] bucket□ writing□ captures□ tags□         │
│ wikilinks☑ derived_from☑ suggested☑               │
│ search: ▭▭▭▭▭▭                                  │
├────────────────────────────────────────────────────┤
│                                                    │
│              [vis-network canvas]                  │
│                                                    │
├────────────────────────────────────────────────────┤
│ Selected: <slug>                                   │
│   incoming wikilinks: …                            │
│   outgoing wikilinks: …                            │
│   suggested:          …                            │
└────────────────────────────────────────────────────┘
```

**데이터 fetch**: `pkm/dashboard/context.py::_read_graph(root)` 추가. `links` 테이블 + `documents` JOIN + `find_suggestions(root)` 결과 (이미 `context.suggestions` 에 있음) 를 한 dict 으로 정리. **클라이언트 fetch 없음** (정적 페이지 원칙).

**스코프 한정**:
- 노드 수 cap = `config.dashboard.graph.max_nodes` (기본 1000). 초과 시 가장 연결성 낮은 노드부터 잘라내고 안내문 표시.
- 검색 박스: 클라이언트 측, slug 부분일치만.
- 노드 클릭 → `dashboard/doc/wiki/<bucket>/<slug>.html` 로 이동.

**비-스코프**:
- 줌 시 LOD, 시간축 애니메이션, edit-in-place — V3 슬롯
- D3 마이그레이션 — 본 spec 의 §10 비-스코프

### 3.3 vis-network 채택 사유

V1 §7.7 은 D3 force-directed 를 명시했으나 V2 에서 vis-network 로 변경:

| 비교 | D3 | vis-network |
|---|---|---|
| 코드 양 (force-directed) | 약 200 줄 | 약 30 줄 |
| 의존성 크기 | ~80 KB | ~70 KB gzip |
| 줌/드래그/필터 | 직접 구현 | 빌트인 |
| PKM 규모(수십~수백 노드) 적합 | 과함 | 정확히 맞음 |
| 결정론 (seed 고정) | 가능 | 가능 (`physics.barnesHut.gravitationalConstant` 등 결정론 옵션) |

D3 의 유연성 우위는 PKM 의 단순한 노드/엣지 구조에서 미미. V3 에 인터랙티브 SPA 수요 발생 시 D3 마이그레이션을 다시 고려.

### 3.4 테스트 계획

- 단위: `find_suggestions_for` (single-slug 필터링), 신규 `INDEX_MISSING` 코드
- CLI: `pkm wiki suggest` 정상 / 슬러그 없음 / JSON / 임계값 오버라이드
- 빌더: `build_graph` 가 graph.json 의 노드/엣지 카운트 정확, suggested 토글 데이터 포함
- 빌더: `max_nodes` cap 동작 (트리밍 안내문 포함)
- 회귀: 기존 dashboard 빌드 테스트가 graph.html 도 검증

---

## 4. M11 — Writing Grounding

### 4.1 정합성 룰 (Karpathy grounding 의 코드화)

writing 본문이 wiki 로 promote 되려면 다음 4 가지 정합성 조건을 만족해야 함.

| ID | 조건 | 검사 식 | 위반 코드 |
|---|---|---|---|
| **R1** | body 안 모든 inline 인용은 `derived_from` 에 있어야 함 | inline_set ⊆ frontmatter_set | `CITATION_NOT_DERIVED` |
| **R2** | `derived_from` 의 모든 항목은 body 에서 ≥ 1 회 인용되어야 함 | frontmatter_set ⊆ inline_set | `DERIVED_NOT_CITED` |
| **R3** | body 길이 ≥ `min_grounded_chars` 면 인용 ≥ 1 개 | len(body) ≥ N → \|inline_set\| ≥ 1 | `UNGROUNDED_WRITING` |
| **R4** | 모든 inline 인용 path 가 실제 존재 | `(root / path).exists()` | `BROKEN_CITATION` (기존 룰 강화) |

**면제 조항** (둘 다 충족 시 R3 만 생략, R1/R2/R4 는 항상 적용):
- frontmatter `purpose` ∈ `config.lint.writing_grounding.exempt_purposes` (기본 `["essay"]`)
- *또는* frontmatter `grounding_exempt: true` (명시적 옵트아웃)

### 4.2 두 게이트 — 사전 경고 + Hard 차단

**Lint warning 게이트** — `pkm/lint/rules.py` 에 4 개 룰 추가:

- writing 카인드 대상으로 R1/R2/R3/R4 를 동일 검사
- promote 가는 길에 `pkm lint` 가 미리 잡아주는 안전망
- severity = warning (errors 가 아닌 이유: 사용자가 작성 중인 draft 도 여기 걸리므로)

**Promote hard 게이트** — `pkm/commands/promote.py::_promote_from_writing`:

기존 `status == "final"` 검사 다음에 R1/R2/R3/R4 검사 삽입. 위반 시 첫 발견 케이스를 raise:

```python
if status != "final":
    raise PKMStatusError(...)
# === V2 신규 ===
violations = check_grounding(fm, body, root)  # R1, R2, R3, R4 순서
if violations:
    raise PKMValidationError(violations[0].message, code=violations[0].code, hint=violations[0].fix_hint)
```

종료 코드 1 + stderr 안내 메시지 (V1 의 실패 계약 그대로).

### 4.3 인용 추출 (단일 진실)

`pkm/lint/citations.py` (신규):

```python
# Markdown 링크 형태 — V1 의 _CITATION_RE 와 호환 유지
_LINK_CITATION_RE = re.compile(r"\[[^\]]+\]\((data/[^)]+\.md)\)")

# /write 슬래시가 권장하는 plain 형태
_INLINE_CITATION_RE = re.compile(
    r"\[(data/(?:raw|wiki|writing|style)/[^\]\s]+\.md)\]"
)

def extract_citations(body: str) -> set[str]:
    """본문에서 인용된 path 집합 (둘 다 합집합)."""
```

**lint + promote 가 둘 다 이 함수만 사용**. 미래의 인용 형태 추가 (예: footnote 스타일) 도 한 곳에서.

### 4.4 Writing 작성 흐름의 suggestions 통합

**`pkm write new --from-search "<query>"` 동작 변경**:

| 단계 | 기존 | V2 변경 |
|---|---|---|
| 1. search 결과 가져오기 | top-N path | (동일) |
| 2. derived_from 채우기 | 결과 path 만 | (동일 — 자동 인용 채움 *없음*) |
| 3. **신규**: suggestions 보강 | — | 결과 중 wiki path 들에 대해 `find_suggestions_for(root, slug)` 호출, 합집합을 *후보* 리스트로 출력 |
| 4. 출력 | "Created … (derived_from: N paths)" | 위 + "Related wiki you may also cite:" 블록 추가 |

**JSON 출력 확장**:

```json
{
  "ok": true,
  "path": "data/writing/<slug>.md",
  "derived_from": [...],
  "related_suggestions": [
    {"path": "...", "slug": "...", "similarity": 0.84, "via": "data/wiki/.../<seed>.md"}
  ]
}
```

이 후보들은 자동으로 `derived_from` 에 박지 *않음*. AI 또는 사용자가 의식적으로 frontmatter 편집해서 넣음.

**슬래시 커맨드 `/write` 가이드 갱신** (`pkm/templates/.claude/commands/write.md`):

- step 4 의 "Cite sources inline" 강화: "본문에서 적어도 한 번씩 모든 `derived_from` 을 [<path>] 로 인용해라. 안 그러면 promote 가 거부한다 (R2 — `DERIVED_NOT_CITED`)."
- step 5 갱신: `pkm write new` 출력의 *related_suggestions* 도 검토해서 추가 인용할지 판단.
- step 7 (promote) 에 grounding 게이트 4 개 코드 표시 + fix hint.

### 4.5 마이그레이션 영향 (기존 데이터)

| 케이스 | 영향 | 사용자 액션 |
|---|---|---|
| 기존 writing 들이 grounding 위반 | `pkm lint` 가 새 warning 으로 토함. 즉시 깨지진 않음 | 시간 날 때 본문 수정 (인용 추가 또는 면제 옵션) |
| 그 writing 들을 promote 시도 | 새 hard gate 거부 | 본문 수정 후 재시도, 또는 `purpose=essay` / `grounding_exempt: true` |
| 회귀 테스트 fixture 의 writing 들 | spec 작업 시 사전 점검 + 수정 | (개발자 측 책임) |

### 4.6 테스트 계획

- 단위: `extract_citations`, `check_grounding` (4 룰 + 면제), 신규 lint 룰 4 개
- 통합: `pkm promote` 가 R1/R2/R3 위반 시 거부 + 정확한 코드/hint 출력
- 통합: 면제 (`purpose=essay`) 흐름이 R3 만 우회하고 R1/R2/R4 는 그대로 검사
- 통합: `pkm write new --from-search` 가 `related_suggestions` 출력 (JSON, 텍스트 둘 다)
- 회귀: 기존 grounding 통과하는 writing 흐름이 그대로 promote 됨

### 4.7 비-스코프

- 인용의 *의미적 적절성* 검증 (LLM 영역) — 영원한 보류
- 자동 인용 삽입 (LLM 영역) — `/write` 의 책임
- 인용 quota (예: "최소 3 개 필요") — 추후 lint 옵션 슬롯으로만 남김

---

## 5. M12 — Migration Infra + Kiwi

### 5.1 Migration 러너 인프라 (item 5)

**디렉토리 구조**:

```
pkm/store/migrations/
├── __init__.py
├── _runner.py             # discover/apply/check 로직
├── _registry.py           # 등록된 마이그레이션 메타 (id, depends_on_extra, description)
├── m001_initial.py        # baseline (v1 스키마, no-op 등록)
└── m002_kiwi_tokenizer.py # 첫 실 마이그레이션
```

**마이그레이션 모듈 인터페이스**:

```python
# m002_kiwi_tokenizer.py
ID = 2
DESCRIPTION = "Switch chunks_fts tokenizer from trigram to kiwi (lang-aware pre-tokenization)"
DEPENDS_ON_EXTRA = "korean"  # extra 미설치 시 SKIP

def check(conn) -> dict:
    """Dry-run: return {needed: bool, reason: str, est_rows: int}."""

def apply(conn, *, embedder=None) -> dict:
    """Apply migration atomically. Return {ok, applied_at, stats}."""
```

**CLI**:

```bash
pkm migrate                  # 기본: --check 와 동일 (안전)
pkm migrate --check          # dry-run, 적용해야 할 게 있는지만 보고
pkm migrate --apply          # 실제 적용. 자동 git 커밋
pkm migrate --json
```

**런너 로직** (`_runner.py`):

1. `schema_version` 읽기 (`SELECT version FROM schema_version`)
2. 등록된 마이그레이션 중 `ID > current_version` 인 것 정렬 후 순차 적용
3. 각 마이그레이션의 `DEPENDS_ON_EXTRA` 가 import 가능한지 확인 → 불가 시 스킵 (warning + 종료 코드 0)
4. apply 성공 시 `schema_version` UPDATE → 다음 단계
5. 실패 시 트랜잭션 ROLLBACK + 에러 코드 `MIGRATION_FAILED`
6. 모든 단계 종료 후 `data/log.md` 에 `migrate.applied` 이벤트 기록 + `git add data/log.md && git commit`

**`pkm doctor` 통합**:

- doctor 가 `current schema_version vs latest registered` 비교
- 불일치 시 row 표시: `migrations: ⚠ 1 pending — run \`pkm migrate --apply\``
- `--strict` 모드에서 pending 이 있으면 `MIGRATION_PENDING` 에러로 비-0 종료

### 5.2 Tokenizer 어댑터 인터페이스

`pkm/search/tokenizer.py` (신규):

```python
@dataclass(frozen=True)
class TokenizerSpec:
    name: str                    # "trigram" | "kiwi"
    fts5_create_args: str        # CREATE VIRTUAL TABLE 의 tokenize=... 인자
    available: bool              # 런타임에 import 가능?
    version: str | None          # kiwi 버전 등 진단용

def get_tokenizer(name: str = "auto") -> TokenizerSpec:
    """name='auto' = kiwi 가용하면 kiwi, 아니면 trigram. config.indexing.tokenizer.preferred 사용."""

def detect_active(conn) -> str:
    """현재 chunks_fts 의 tokenize 인자 + schema_version 으로 식별."""

def tokenize_for_indexing(text: str, *, lang: str, tokenizer: TokenizerSpec) -> str:
    """인덱싱·쿼리 양쪽에서 동일하게 호출. lang='en' 이면 kiwi 안 거치고 통과."""
```

미래의 mecab/soynlp 추가 시 어댑터만 추가.

### 5.3 Kiwi 통합 (item 6) — `m002_*` 의 실 동작

**옵셔널 의존성** — `pyproject.toml`:

```toml
[project.optional-dependencies]
korean = ["kiwipiepy>=0.17"]
```

README quick-start 갱신:

```bash
uv tool install --reinstall -e ".[ml,extract,korean]"   # 한국어 코퍼스인 경우
```

**FTS5 결합 전략 — 사전 토큰화**:

SQLite FTS5 의 외부 토크나이저는 C API 가 필요해서 Python 에서 직접 결합 불가. 우회 전략:

1. `chunks` 테이블에 `text_tokenized TEXT` 컬럼 추가
2. 각 chunk 의 본문을 lang 별로 처리:
   - `lang ∈ (ko, mixed)`: kiwi 가 형태소 분리한 결과를 공백 join → `text_tokenized`
   - `lang == en`: 원본을 그대로 복사 → `text_tokenized`
3. `chunks_fts` 가 `text_tokenized` 컬럼을 인덱싱 (tokenizer = `unicode61`)
4. 쿼리 시점에도 동일 함수로 사전 토큰화

`bm25.py::query_bm25` 가 쿼리 토큰화 분기 — 토크나이저 메타는 `schema_version` 으로 식별 (V2: schema_version=2 ⇒ kiwi 사전 토큰화).

**`m002_kiwi_tokenizer.py::apply` 단계**:

1. `kiwipiepy` 가용성 확인 → 미설치면 SKIP (`schema_version` 안 올림)
2. `ALTER TABLE chunks ADD COLUMN text_tokenized TEXT`
3. 모든 chunk 를 lang 별로 사전 토큰화 → `text_tokenized` UPDATE
4. `chunks_fts` 를 `chunks_fts_old` 로 rename
5. 새 `chunks_fts` 를 unicode61 로 생성, `text_tokenized` 컬럼 인덱싱
6. `INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')` 로 인덱스 재구축
7. 검증 쿼리 (한국어 샘플 BM25 hit 카운트 ≥ 0) → 통과 시 `chunks_fts_old` DROP
8. 실패 시 atomic ROLLBACK (rename 역순 + 컬럼 제거)
9. 성공 시 `schema_version` = 2 UPDATE

### 5.4 doctor 출력 갱신

```
schema_version    : 2 / 2  ✓
tokenizer         : kiwi (kiwipiepy 0.17.4)  ✓
fts index         : 1248 chunks  ✓
```

미설치 시:

```
schema_version    : 1 / 2  ⚠
tokenizer         : trigram (kiwi unavailable — install with `uv tool install -e ".[ml,extract,korean]"`)
migrations        : 1 pending (m002_kiwi_tokenizer)
```

### 5.5 reindex 와의 관계

- 기존 `pkm reindex db --full` 은 현재 DB 의 토크나이저 그대로 사용 (`detect_active` 결과)
- 토크나이저 변경 후 사용자가 reindex 하지 않아도 `m002_*::apply` 가 재인덱스를 끝내므로 즉시 검색 가능
- 변경 후의 reindex 호출은 새 토크나이저 그대로 사용 — 일관됨

### 5.6 테스트 계획

- 단위: `_runner` (discover/순서/skip/rollback)
- 단위: `tokenizer.get_tokenizer`, `detect_active`, `tokenize_for_indexing`
- 통합: `pkm migrate --check` 가 pending 보고
- 통합: kiwi 미설치 환경에서 `--apply` 가 SKIP + 종료 코드 0 + `schema_version` 그대로
- 통합 (slow, kiwipiepy 설치된 경우만): `--apply` 후 한국어 BM25 회수율 개선 ("환경설정의 인증 토큰 저장" 같은 어절형 쿼리가 trigram 보다 hit)
- 회귀: 영문 코퍼스 검색 결과가 토크나이저 변경 전후로 동일 (`lang=en` 분기 검증)

### 5.7 비-스코프 (M12)

- `pkm migrate --rollback` (data 는 git, 인덱스는 reindex 로 충분)
- MeCab/KOMORAN/soynlp 어댑터 (인터페이스만 준비)
- 한국어 외 언어별 토크나이저 (영어 stemming 등)
- 토크나이저별 BM25 가중치 튜닝 (데이터 모이면 별도 spec)

---

## 6. 횡단 사항

### 6.1 신규 / 수정 에러 코드

`pkm/errors.py` 추가 (V1 의 안정성 약속 — 모든 에러 = `PKMError` 서브클래스 + 안정 코드):

| 코드 | 클래스 | M | 사용처 |
|---|---|---|---|
| `INDEX_MISSING` | `PKMStateError` | M10 | `pkm wiki suggest` 인덱스 없음 |
| `CITATION_NOT_DERIVED` | `PKMValidationError` | M11 | promote 게이트 R1 |
| `DERIVED_NOT_CITED` | `PKMValidationError` | M11 | promote 게이트 R2 |
| `UNGROUNDED_WRITING` | `PKMValidationError` | M11 | promote 게이트 R3 |
| `MIGRATION_FAILED` | `PKMStateError` | M12 | migrate apply 트랜잭션 실패 |
| `MIGRATION_PENDING` | `PKMStateError` | M12 | doctor --strict 가 pending 발견 |

기존 `BROKEN_CITATION` 은 그대로 유지 (M11 에서 강화만).

`tests/test_failure_mode_matrix.py` 가 모든 코드에 1 개 이상 테스트 보장 — V1 의 100% 커버리지 약속을 새 코드에도 적용.

### 6.2 Config 추가 항목 (`.pkm/config.toml`)

```toml
[lint.missing_link]
# (V1.x 작업으로 이미 추가됨)
enabled            = true
sim_threshold      = 0.78
min_graph_distance = 2
top_k_per_doc      = 3

[dashboard.graph]                    # M10
max_nodes              = 1000
include_writing        = false       # 토글 기본값
include_captures       = false
overlay_suggestions    = true        # graph 위에 점선 suggested 엣지

[lint.writing_grounding]             # M11
enabled               = true
min_grounded_chars    = 400
exempt_purposes       = ["essay"]    # purpose 면제 리스트

[indexing.tokenizer]                 # M12
preferred = "auto"                   # auto | trigram | kiwi
                                     # auto = kiwi 가용하면 kiwi, 아니면 trigram
```

### 6.3 의존성 변경 (`pyproject.toml`)

```toml
[project.optional-dependencies]
ml      = [...]                      # 기존
extract = [...]                      # 기존
korean  = ["kiwipiepy>=0.17"]        # M12 신규
```

`uv tool install -e ".[ml,extract,korean]"` — 한국어 사용자용 quick-start 갱신.

### 6.4 문서 갱신

| 문서 | 갱신 내용 |
|---|---|
| README | quick-start 의 `[ml,extract]` → `[ml,extract,korean]` (옵션). 명령표에 `pkm wiki suggest`, `pkm migrate` 추가. 진행 상황 체크박스에 M10/M11/M12 추가 |
| FEATURES.md | 2.4 (search) 토크나이저 옵션. 2.5 (promote) grounding 게이트. 2.7 (lint) 새 룰. 2.8 (dashboard) graph.html. 새 절 2.10 — Migration. UC8 (graph 발견) 추가 |
| SCHEMA.md.template | Workflows 섹션의 "Write" 단계에 grounding 강제 명시. 새 섹션 — "Migrations" 추가 |
| docs/superpowers/specs/2026-05-01-pkm-design.md (V1) | 변경 없음. V2 spec 이 V1 을 *전제* 함을 본 spec 의 헤더에 명시 |

### 6.5 슬래시 커맨드 갱신

| 파일 | 변경 |
|---|---|
| `.claude/commands/write.md` | step 4 grounding 강제 강화. step 5 에 suggested links 검토 추가 |
| `.claude/commands/promote.md` | grounding 실패 시 사용자에게 보일 안내 메시지 |
| `.claude/commands/lint.md` | 새 룰 코드 표시 (`UNGROUNDED_WRITING` 등) 와 fix 가이드 |

---

## 7. 결정론 + 재현성 보장

V1 의 핵심 약속 — "데이터 repo 만 있으면 인덱스/대시보드 결정론적으로 재생성" — 을 V2 에서도 유지:

| 산출물 | 재생성 방법 (V2 기준) |
|---|---|
| `.pkm/index.db` | `pkm reindex db --full` (토크나이저는 schema_version 으로 식별, 자동 결정) |
| `dashboard/` (graph 포함) | `pkm dashboard build` |
| `dashboard/graph.html` 의 graph.json | 빌드 시점에 결정론적 산출 (vis-network seed 고정) |
| 마이그레이션 idempotency | `pkm migrate --check` 결과가 항상 일관 |

**시드 고정 전략 (graph 페이지)**:

- vis-network 의 force layout 은 무작위 초기 좌표가 결정론을 깬다. 해결: 빌드 시점에 노드 ID(slug 해시) 로부터 초기 좌표를 결정해서 graph.json 에 박음.
- 결과: 같은 코퍼스 → 같은 graph.html (브라우저 렌더 후 layout 미세 조정은 사용자 경험이지 빌드 산출물 아님).

---

## 8. V2 수락 기준 (V1 §9.4 delta)

V1 수락 기준에 추가:

- [ ] `pkm wiki suggest <slug>` 정상/실패 모드 (없는 슬러그 / 인덱스 부재) 모두 동작
- [ ] dashboard 의 `graph.html` 이 수십~수백 노드에서 부드럽게 동작 (브라우저 렌더 < 2s, Chrome/Safari)
- [ ] writing grounding 4 개 룰이 lint warning + promote hard gate 양쪽에서 작동
- [ ] grounding 위반 4 가지 케이스 (R1/R2/R3/R4) 가 모두 회귀 테스트로 보호
- [ ] 면제 (`purpose=essay` / `grounding_exempt: true`) 가 R3 만 우회
- [ ] `[korean]` extra 미설치 환경에서 `pkm migrate --apply` 가 SKIP 후 종료 코드 0, `schema_version` 그대로
- [ ] `[korean]` extra 설치 환경에서 마이그레이션 후 한국어 BM25 회수율 개선 (slow test)
- [ ] 영문 코퍼스 검색 결과가 토크나이저 변경 전후 동일
- [ ] 신규 에러 코드 6 개 모두 실패 모드 매트릭스에 등록
- [ ] V1 의 모든 기존 테스트 회귀 통과

---

## 9. 위험 & 완화

| 위험 | 영향 | 완화 |
|---|---|---|
| vis-network 200KB JS 동봉 → dashboard 사이즈 증가 | 첫 배포 시 인지 마찰 | minified gzip 70KB. 그래프 페이지 미사용 시 로드 안 함 (script 분리) |
| FTS5 사전 토큰화가 영문 검색 회수율 떨어뜨릴 가능 | BM25 영문 정확도 회귀 | lang 별 분기 (en 은 kiwi 안 거침) + 회귀 테스트 명시 |
| 마이그레이션 실패 시 인덱스 손상 | 검색 안 됨 | atomic rename + 트랜잭션. 최악 시 `pkm reindex db --full` 무한 안전망 |
| grounding hard gate 가 기존 writing 막음 | 사용자 마찰 | lint warning 이 promote 전에 미리 알려줌. 면제 옵션 제공 |
| Kiwi 모델 자동 다운로드 (~30 MB, 첫 사용 시) | 첫 사용 지연 | doctor 단계에서 명시 안내. `~/.cache/kiwipiepy/` (모델 캐시 §5.6 분리) |
| graph.html 노드 1000+ 시 브라우저 정지 | 대형 코퍼스 사용자 영향 | `max_nodes` cap + 안내문. V3 에 LOD/server-side filtering 슬롯 |
| `find_suggestions_for` 가 lint 와 다른 결과를 보일 가능 (회귀) | 사용자 혼란 | 100% 코드 공유 + 단일-doc 모드는 source 루프 필터로 구현. 단위 테스트로 동치성 검증 |

---

## 10. 비-스코프 (V2 에서도 명시 보류)

| 항목 | 사유 |
|---|---|
| D3 force-directed 마이그레이션 | vis-network 로 충분, 코드 양 1/3 |
| Live 대시보드 (파일감시 + LiveReload) | 정적 빌드 유지 |
| 인터랙티브 SPA (Vite/React) | 단일 HTML 로 충분 |
| Citation 그래프 페이지 분리 | graph.html 의 derived_from 토글로 충분 |
| MeCab/KOMORAN/soynlp 어댑터 | 인터페이스만 준비, 구현은 데이터 수요 발생 시 |
| `pkm migrate --rollback` | data 는 git, 인덱스는 reindex 로 충분 |
| 자동 grounding 보강 | LLM 영역 (`/write` 슬래시 책임) |
| 인용 quota 룰 | 추후 lint 옵션 슬롯 |
| 그래프의 줌 시 LOD / 시간축 / edit-in-place | V3 슬롯 |

---

## 11. 마일스톤 로드맵

### 11.1 의존성 그래프

```
M10 (graph surfacing)  ──┐
                         ├── 둘 다 V2 의 입력. 독립.
M11 (writing grounding)  ─┘
        │
        ▼
M12 (migrate + kiwi)  ← M10/M11 와 데이터 의존성 없음. 마지막에 배치.
```

### 11.2 권장 구현 순서: M10 → M11 → M12

**근거**:
- M10 이 가장 작고 (CLI 1 개 + dashboard 페이지 1 개) 이미 만든 `find_suggestions` 에 직접 붙음 → 빠른 모멘텀
- M11 은 promote/lint 에 손대므로 회귀 위험 큼 → 중간 배치, 충분한 통합 테스트 후 다음 진행
- M12 는 인프라 + 의존성 추가라 격리 가능 → 마지막 배치해도 앞 두 마일스톤 영향 없음

### 11.3 plan 문서 매핑

| Plan | 파일 |
|---|---|
| M10 | `docs/superpowers/plans/2026-05-06-pkm-m10-graph-surfacing.md` |
| M11 | `docs/superpowers/plans/2026-05-06-pkm-m11-writing-grounding.md` |
| M12 | `docs/superpowers/plans/2026-05-06-pkm-m12-migrate-and-kiwi.md` |

각 plan 은 본 spec 의 §3/§4/§5 + §6 횡단 사항을 입력으로 받아 단계별 작업/테스트/커밋 흐름을 구체화한다.

---

## 부록 A — 본 spec 작업 시 점검 체크리스트

본 spec 을 plan 으로 분해하기 전에 점검할 것:

- [ ] V1 spec (`2026-05-01-pkm-design.md`) 의 어휘·경계와 충돌 없는지
- [ ] V1 의 자동 git / 결정론 / strict 권한 / 옵트인 셸아웃 약속을 모두 보존하는지
- [ ] 신규 에러 코드 6 개가 V1 의 실패 계약 형태(`Error [<CODE>]: <message>` + JSON shape)를 따르는지
- [ ] 신규 의존성 (`vis-network`, `kiwipiepy`) 이 옵셔널인지 + 미설치 시 폴백이 문서화됐는지
- [ ] V1 §9.2 의 V2 보류 항목 중 본 spec 에서 닫히는 것 / 보류 유지하는 것이 §10 에 명시됐는지

## 부록 B — 다음 V3 후보 (참고)

본 spec 에서 명시 보류했지만 V3 사이클 후보:

- D3 마이그레이션 + 인터랙티브 SPA (graph 페이지 LOD, edit-in-place)
- Live 대시보드 (파일감시)
- 추가 한국어 토크나이저 (MeCab-ko, soynlp)
- ORPHAN_WIKI 자동 deprecation (P3 후보, 현재 사이클 미선택)
- 인용 quota 룰
- Activity heatmap / tag network 대시보드 페이지

이 항목들은 V3 사이클 시작 시 별도 spec 으로 다시 검토.
