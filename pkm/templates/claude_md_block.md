<!-- pkm:start managed by pkm install -->
## PKM 프로젝트 컨텍스트 로딩

디렉토리에서 작업을 시작할 때, 비자명한 작업을 시작하기 **전에** cwd에서 다음 한 줄을 실행한다:

```sh
[ -f .pkm-link ] && pkm project current --json 2>/dev/null; :
```

그런 다음 결과에 따라 행동한다:

1. **출력 없음** (마커 부재, 또는 `pkm`이 PATH에 없음): 조용히 진행한다. 추가 PKM 호출도, 사용자 대상 출력도 하지 않는다.
2. **`{"ok": true, ...}`**: `pkm-recall` 스킬을 호출한다 — 프로젝트의 `index.md`와 최근 결정/함정(decisions/pitfalls)을 컨텍스트에 로드한다.
3. **`{"ok": false, ...}`** (오래된 마커, 환경 설정 오류): 조용히 진행한다. 사용자가 PKM에 대해 묻지 않는 한 드러내지 않는다.

참고:
- 끝에 붙은 `; :`는 종료 코드를 0으로 강제하여, `hwi_PKM_data` 같은 링크되지 않은 repo에서도 부트스트랩이 에러로 표시되지 않게 한다.
- 마커 `.pkm-link`는 `pkm project link`로 생성되며 project_id를 담는다. 드리프트를 복구하려면 프로젝트 cwd에서 `pkm doctor --fix`를 실행한다. gitignore 권장(머신별 링크 상태).
- 이 블록은 `pkm install`이 관리하며 머신 간 이식 가능하다 — `pkm`이 PATH에 있다는 것만 가정한다.
<!-- pkm:end managed by pkm install -->
