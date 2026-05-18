# PKM Link Marker — cwd-local 마커로 미링크 프로젝트의 PKM 호출 회피

**Status**: design (브레인스토밍 통과, plan 분해 대기)
**Date**: 2026-05-11
**Author**: hwijung-park
**Predecessor**: `docs/superpowers/specs/2026-05-07-pkm-projects-and-sessions-design.md` (M13–M14, projects layer)

---

## TL;DR

`~/.claude/CLAUDE.md` 의 PKM 컨텍스트 로딩 인스트럭션은 매 세션 시작 시 `pkm project current --json` 을 실행한다. 미링크 프로젝트(cwd 가 어떤 project_id 와도 매칭되지 않는 디렉토리)에서는 이 명령이 exit 1 + `NOT_LINKED` JSON 을 반환하면서 harness UI 에 시뻘건 `Error: Exit code 1` 메시지를 노출한다.

본 변경은 cwd 에 `.pkm-link` 파일을 두는 컨벤션을 도입한다. CLAUDE.md 인스트럭션은 `[ -f .pkm-link ]` 한 번으로 미링크 프로젝트를 가려내고, 마커가 있을 때에만 `pkm project current` 를 호출한다. 결과적으로 **미링크 프로젝트에서는 `pkm` 바이너리가 단 한 번도 실행되지 않으며, 사용자에게 노출되는 에러 메시지는 0건**이다.

마커 동기화는 best-effort: `pkm project link` 가 생성, `pkm project rm` 이 (cwd 매칭 시) 삭제, `pkm project doctor` 가 누락/불일치/orphan 을 진단/수정한다. **ProjectIndex (data repo) 는 여전히 single source of truth**, 마커는 hint 일 뿐이다.

---

## 1. 동기

### 1.1 현재 동작

`~/.claude/CLAUDE.md` 글로벌 인스트럭션 (사용자 머신):

```markdown
1. Check if the cwd is a linked PKM project: run `pkm project current --json`.
2. If linked (`ok: true`): invoke the `pkm:recalling-project-context` skill.
3. If not linked (`code: NOT_LINKED`): silently proceed.
```

`pkm project current --json` 은 NOT_LINKED 시 다음을 반환:

```text
exit 1
{"ok": false, "error": {"code": "NOT_LINKED", "message": "cwd ... is not linked to any project", "hint": "run `pkm project link` first"}}
```

Claude Code harness 는 exit 1 을 `Error: Exit code 1` 헤더와 함께 사용자에게 노출한다. 인스트럭션상 "silently proceed" 가 명시되어 있어도, 명령 자체의 종료코드는 harness 단에서 가려진다.

### 1.2 사용자 관찰

미링크 디렉토리에서 세션을 시작할 때마다:
- 시각적 노이즈 (`Error: Exit code 1`)
- 매 세션마다 `pkm` 프로세스 spawn 비용 (~수십 ms × N 머신)
- 신규 사용자가 "에러가 있나?" 오해

### 1.3 목표

1. 미링크 cwd 에서 `pkm` 바이너리 미실행
2. 미링크 cwd 에서 사용자에게 노출되는 에러 0건
3. PKM 사용자가 추가로 학습할 컨벤션은 1개 (`.pkm-link` 마커) 이내
4. 마커 동기화 실수가 데이터 무결성을 해치지 않음 (ProjectIndex 가 SoT)

### 1.4 비목표

- walk-up ancestor 탐색 (cwd 외 디렉토리에서 세션 시작은 사용자 운영 패턴 A 에서 제외)
- 마커에 path/메타 추가 (project_id 한 줄로 충분)
- 자동 `.gitignore` 수정 (surprise factor)
- pkm 측 exit code 변경 (호출자 호환성 위험)

---

## 2. 결정 요약 (브레인스토밍 결과)

| Q | 결정 | 근거 |
|---|---|---|
| 마커 vs exit-0 변경 vs is-linked CLI | **마커** | pkm 미설치 환경 안전, 호출 비용 0 |
| 탐색 범위 | **cwd-only** | 세션은 거의 항상 repo 루트에서 시작 |
| 기존 링크 마이그레이션 | **`pkm project doctor`** | 명시적, 결정론적, 부수효과 없음 |
| 마커 포맷 | **`<project_id>\n` 한 줄** | human-readable, 디버깅 용이 |
| git tracking | **사용자 자율 (gitignore 권장)** | 자동 수정은 surprise |

---

## 3. 마커 파일 명세

| 항목 | 값 |
|---|---|
| 경로 | cwd 의 `.pkm-link` |
| 내용 | `<project_id>\n` (UTF-8) |
| 권한 | `0644` |
| 라이프사이클 소유자 | `pkm project link` (생성), `pkm project rm` (cwd 매칭 시 삭제), `pkm project doctor --fix` (sync) |
| git 권장 | `.gitignore` 등재 (per-machine link 상태) |
| 잘못된 형식일 때 | 무시 후 NOT_LINKED 처럼 fallback (CLAUDE.md `2>/dev/null` 로 silent) |
| 디렉토리일 때 | INVALID 처리 (무시) |
| 심볼릭일 때 | target 이 정상 regular file 이면 정상 처리 (read 가 `is_file()` 따라감), broken/dangling 이면 무시 |
| 읽기 의미론 | 파일 전체를 UTF-8 로 읽고, 첫 번째 비-공백 라인을 `strip()` 한 결과를 project_id 로 채택. 비어 있거나 첫 라인이 공백뿐이면 INVALID. |

### 3.1 신뢰 모델

마커는 **hint** 다. `pkm project current` 의 실제 resolver (env / overrides / git remote / local_paths / NOT_LINKED 5단계 — `pkm/session/registry.py`) 는 변경하지 않는다.

- 마커가 존재 + 실제로는 NOT_LINKED → `pkm project current` 가 `ok: false` 반환, CLAUDE.md 인스트럭션이 silently proceed. 한 번의 불필요한 spawn 비용만 발생.
- 마커가 없음 + 실제로는 linked → CLAUDE.md 가 pkm 미호출. 사용자는 `pkm project doctor --fix` 로 복구 가능.
- 마커가 존재 + 실제로 linked + project_id 불일치 → `pkm project current` 가 실제 id 를 반환, recalling-project-context skill 이 올바른 project 를 로드. 마커는 `doctor` 가 다음 실행 시 정정.

---

## 4. CLI 동작 변경

### 4.1 `pkm project link`

**기존 동작 보존**: data repo 의 ProjectIndex 등록, frontmatter 작성, auto-commit (옵션). 멱등.

**추가 동작 (성공 경로 끝):**
1. cwd 에 `.pkm-link` 쓰기 시도 (내용 `<project_id>\n`).
2. 실패 (readonly fs / 권한 / 디스크) 시:
   - stderr 에 1줄 경고: `warning: failed to write .pkm-link marker: <reason>`
   - link 자체는 성공 처리 (exit 0)
3. `--json` 모드에서 응답 페이로드에 `marker_written: bool` 필드 추가 (디버깅/테스트 용).

**`ALREADY_LINKED` 경로** (재link 멱등): 동일하게 마커 write 시도 (누락 복구 효과).

### 4.2 `pkm project rm <id>`

**기존 동작 보존**: ProjectIndex 에서 삭제, `data/projects/<id>/` 디렉토리 제거 (`--keep-data` 면 인덱스만).

**추가 동작 (성공 경로 끝):**
1. 현재 cwd 가 해당 project 의 `git_remotes` 또는 `local_paths` 와 매칭되는가?
   - 매칭: `.pkm-link` 가 존재하면 **내용까지 일치 (`marker_id == removed_id`)** 확인 후 삭제 시도. 내용 불일치(다른 project_id) 시: 다른 project 의 마커일 수 있으므로 보존, stderr 경고 1줄. 실패 시 stderr 경고.
   - 비매칭: 마커는 그대로 둠 (다른 cwd 에 있을 수도 있으므로 추측 금지). `doctor` 가 orphan 으로 탐지하게 위임.

### 4.3 `pkm project doctor`

기존 doctor 의 검사 목록에 4종 진단 추가:

| 진단 코드 | 조건 | 심각도 | `--fix` 액션 |
|---|---|---|---|
| `MARKER_MISSING` | cwd 가 linked + 마커 부재 | warning | 마커 생성 |
| `MARKER_MISMATCH` | cwd 가 linked + 마커 내용 ≠ resolved project_id | warning | 마커 덮어쓰기 |
| `MARKER_ORPHAN` | cwd 가 NOT_LINKED + 마커 존재 | warning | 마커 삭제 |
| `MARKER_INVALID` | 마커가 디렉토리/심볼릭/비-UTF8/공백 | warning | 마커 삭제 후 (조건부) 재생성 |

`--fix` 없이는 출력만, exit code 는 `--strict` 에서만 1. 기존 doctor 의 `--strict` 룰을 그대로 따른다.

**스코프 한정:** 마커 검사는 **cwd 한 곳만** 대상. ProjectIndex 전체를 순회하거나 파일시스템을 walk 해서 다른 디렉토리의 마커를 찾지 않는다. 멀티-cwd 환경에서는 각 디렉토리에서 `pkm project doctor` 를 별도 실행해야 한다.

### 4.4 `pkm project current`

**변경 없음.** 마커는 CLI 명령이 아닌 CLAUDE.md 인스트럭션의 fast-path 용. `pkm project current` 자체는 여전히 ProjectIndex 기반 5단계 resolver 를 그대로 사용하므로, 마커가 잘못돼도 결과가 틀어지지 않는다.

---

## 5. CLAUDE.md 인스트럭션 변경

`~/.claude/CLAUDE.md` 의 PKM 블록 교체 (사용자 머신 외부 — pkm 가 직접 수정하지 않음, 본 spec 의 README/FEATURES.md 에 새 문구를 안내):

```markdown
## PKM project context loading

When you start working in a directory, **before** any non-trivial work:

1. Quick check: is `.pkm-link` present in cwd? If not, silently proceed.
   No PKM call, no user-facing output.
2. If marker exists, run `pkm project current --json 2>/dev/null`.
3. If `ok: true`: invoke the `pkm:recalling-project-context` skill — it loads
   the project's index.md and recent decisions/pitfalls into context.
4. If marker exists but `ok: false` (stale marker, env misconfig, pkm missing):
   silently proceed. Do not surface unless the user asks about PKM.

The marker `.pkm-link` is created by `pkm project link` and contains the
project_id. Recommended to gitignore (per-machine link state).
```

핵심 차이:
- step 1 의 `[ -f .pkm-link ]` 가 비PKM 프로젝트에서 즉시 종료 → pkm 호출 0건
- step 2 의 `2>/dev/null` 이 pkm 측 stderr 를 잠재워 harness UI 에 노출 회피
- step 4 가 마커-실제 불일치를 graceful 하게 처리 (사용자 작업 차단 없음)

---

## 6. 공통 유틸 — `pkm/marker.py` (신규)

마커 read/write/delete 의 best-effort 의미론을 한 곳에 모은다. CLI 명령들이 직접 파일 IO 하지 않도록.

```python
# 의사 인터페이스 (구현은 plan 단계)
def read(cwd: Path) -> str | None: ...
    # 파일이 없거나 디렉토리/심볼릭/비-UTF8 이면 None
def write(cwd: Path, project_id: str) -> bool: ...
    # 성공 True, 실패 False (호출자가 경고 출력)
def delete(cwd: Path) -> bool: ...
    # 성공/원래 없음 True, 실패 False
def diagnose(cwd: Path, resolved_id: str | None) -> "MarkerDiagnosis | None": ...
    # doctor 용. MARKER_MISSING / MISMATCH / ORPHAN / INVALID / None(정상)
```

테스트가 `pkm/marker.py` 단위에서 분기를 모두 커버하면 CLI 명령 테스트는 통합 1줄로 충분.

---

## 7. 테스트 전략

### 7.1 단위 테스트 (`tests/test_marker.py`)

- `read`: 정상, 부재, 디렉토리, 심볼릭, 비-UTF8, 공백/개행만, 멀티라인 (첫 줄만 채택)
- `write`: 새 파일 생성, 덮어쓰기, 권한 거부 시 False
- `delete`: 존재 시 삭제, 부재 시 True (멱등)
- `diagnose`: 4가지 진단 코드 + 정상 케이스

### 7.2 CLI 통합 테스트

- `tests/commands/project/test_link_marker.py`
  - `link` 직후 cwd 에 마커 존재 + 내용 == project_id
  - `link` 재실행 (`ALREADY_LINKED`) 시 마커 보존/재생성
  - `--json` 출력에 `marker_written: true`
  - readonly cwd 에서 link → exit 0, stderr 에 경고, 마커 부재
- `tests/commands/project/test_rm_marker.py`
  - cwd 매칭 시 `rm` 후 마커 삭제
  - cwd 비매칭 시 마커 보존
- `tests/commands/doctor/test_marker_checks.py`
  - 4가지 진단 코드 각각 발생 + `--fix` 결과 검증
  - `--strict` + diagnosis 존재 시 exit 1

### 7.3 회귀

- 기존 link/rm/doctor 테스트가 마커 부수효과로 깨지지 않음 (CI 그린)

---

## 8. 영향 받는 파일

| 파일 | 변경 | 신규/수정 |
|---|---|---|
| `pkm/marker.py` | read/write/delete/diagnose 유틸 | 신규 |
| `pkm/commands/project.py` | `link` / `rm` 에 마커 hook | 수정 |
| `pkm/commands/doctor.py` | 4종 진단 + `--fix` 액션 | 수정 |
| `docs/FEATURES.md` | M14 섹션에 마커 컨벤션 + gitignore 권장 | 수정 |
| `README.md` | "PKM project linking" 단락에 마커 1줄 (있다면) | 수정 |
| `tests/test_marker.py` | 단위 테스트 | 신규 |
| `tests/commands/project/test_link_marker.py` | 통합 | 신규 |
| `tests/commands/project/test_rm_marker.py` | 통합 | 신규 |
| `tests/commands/doctor/test_marker_checks.py` | 통합 | 신규 |
| `~/.claude/CLAUDE.md` (외부) | PKM 블록 교체 안내 | 본 spec / README 에 명시 |

---

## 9. 호환성

- **기존 링크된 프로젝트**: 마커 없이도 `pkm project current` 는 그대로 동작. CLAUDE.md fast-path 만 miss → 사용자가 명시적 `pkm` 호출은 영향 없음. `pkm project doctor --fix` 한 번 실행으로 정상화.
- **기존 CLI 사용자**: link/rm/doctor 의 인자/출력 호환. `--json` 응답에 `marker_written` 필드만 추가 (additive).
- **CI / 자동화 스크립트**: link/rm exit code 불변. doctor exit code 는 `--strict` 에서만 변동 (기존 룰 일관).

---

## 10. 위험 & 완화

| 위험 | 완화 |
|---|---|
| 마커가 git 에 커밋되어 다른 머신에서 false positive | FEATURES.md / README 에 gitignore 권장 명시. 일부 사용자가 무시해도 CLAUDE.md step 4 가 graceful fail. |
| `pkm project link` 가 readonly fs 에서 동작 안 함 | best-effort, stderr 경고, link 자체는 성공. 사용자가 명시적으로 인지 가능. |
| 마커 동기화 실수 (예: 수동 cp/mv 후 미정정) | `doctor` 가 4종 진단으로 탐지. `--fix` 1회 실행으로 복구. |
| 사용자가 `.pkm-link` 를 수동 작성 후 link 누락 | `pkm project current` 가 ProjectIndex 기준 NOT_LINKED 반환, step 4 silently proceed. ProjectIndex 가 SoT 이므로 무결성 손상 없음. |
| Subdirectory 에서 세션 시작 (사용자 운영 패턴 B) | 본 spec 미커버. 추후 walk-up 필요 시 별도 spec. 현 시점에서는 `cd <repo-root>` 가 워크어라운드. |

---

## 11. 미해결 이슈 / 후속

- walk-up ancestor 탐색은 추후 필요 시 별도 마일스톤. 본 spec 에서는 cwd-only.
- `pkm project link` 가 사용자 의사와 무관하게 `.gitignore` 를 수정하지 않으므로, 팀 PKM 사용 시 첫 번째 사용자가 마커를 실수로 커밋할 가능성. README 에 명시적 경고.
- CLAUDE.md 글로벌 인스트럭션은 본 spec 의 적용 범위 외 (사용자 머신 파일). README/FEATURES.md 에 새 문구를 제공하고, 사용자가 직접 교체.
