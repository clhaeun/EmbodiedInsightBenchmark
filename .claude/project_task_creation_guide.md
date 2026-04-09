---
name: task_creation_guide
description: Complete guide for creating new OmniGibson tasks — files to create/modify, pitfalls, safety rules, physics handling
type: project
---

# OmniGibson Task 생성 완전 가이드

draw_a_line_on_paper + spread_butter_on_toast 태스크 생성 경험 기반 (2026-03-17)

## 실행 명령어 형식
```bash
python -m omnigibson.examples.llm_agent.run_llm_agent \
  --model azure/gpt-4.1 \
  --task {task_name} \
  --scene {scene_model} \
  --robot Fetch \
  --symbolic
```

---

## 1. 반드시 생성해야 하는 파일 (3~4개)

### A. BDDL 정의 파일 (필수)
- **경로**: `bddl3/bddl/activity_definitions/{task_name}/problem0.bddl`
- 디렉토리를 만들고 problem0.bddl만 넣으면 자동 등록
  - `bddl_utils.py`의 `BEHAVIOR_ACTIVITIES`가 디렉토리를 스캔하므로 별도 등록 불필요
- 정의 내용: objects, init conditions (`ontop`, `future` 등), goal conditions
- `(future ...)` 마커로 런타임에 생성될 particle system 지정 가능 (예: `melted__butter`, `ink`)
- 오브젝트는 WordNet synset 이름 사용 (예: `rule.n.12_1`, `sheet.n.02_1`)
  - synset 이름은 category_mapping.csv에서 확인: `ruler` 카테고리 → `rule.n.12` synset

### B. Scene Template JSON (필수)
- **경로**: `datasets/2025-challenge-task-instances/scenes/{scene}/json/{scene}_task_{task_name}_0_0_template.json`
- **이 파일이 없으면 `FileNotFoundError`로 씬 로딩 실패** — 가장 빠뜨리기 쉬운 파일
- BDDL 인스턴스 → 실제 3D 모델 매핑 + 초기 위치 정의
- 핵심 구조:
  - `metadata.task.inst_to_name`: BDDL scope name → scene object name 매핑
  - `objects_info.init_info`: 각 오브젝트의 class, model ID, category, in_rooms
  - `state.registry.object_registry`: 초기 위치(pos, ori), 물리 상태
- 모델 ID 확인: `datasets/behavior-1k-assets/objects/{category}/` 하위 디렉토리명
- 기존 template에서 파생하는 Python 생성 스크립트 작성 권장 (아래 D 참조)

### C. available_tasks.yaml 엔트리 추가 (필수)
- **경로**: `joylo/sampled_task/available_tasks.yaml`
- scene_model, robot_start_position, robot_start_orientation 지정
- YAML 끝에 append — 기존 엔트리에 영향 없음

### D. Scene Template 생성 스크립트 (선택, 강력 권장)
- **경로**: `datasets/.../scenes/{scene}/json/create_{task}_task_template.py`
- 기존 template JSON 로드 → 오래된 task 오브젝트 제거 → 새 오브젝트 추가
- `INST_TO_NAME`, `NEW_OBJECTS`, `NEW_OBJECT_STATES` dict 정의 → JSON 조합
- 수작업으로 JSON을 편집하면 실수 가능성 높으므로 스크립트 권장

---

## 2. 수정이 필요할 수 있는 파일 (위험도별 분류)

### 위험도 높음 — 기존 액션 로직 변경

| 파일 | 수정이 필요한 경우 | 위험 |
|------|-------------------|------|
| `symbolic_semantic_action_primitives.py` | 새 액션 프리미티브 필요 시 (예: DRAW, STIR 등) | 기존 `_spread`, `_wait` 등의 로직을 건드리면 기존 태스크 실패 가능 |
| `eib_semantic_action_primitives.py` | 새 프리미티브 enum 추가 + 컨트롤러 매핑 | IntEnum에 값 추가 시 **반드시 맨 끝에** 추가 (auto() 순서) |
| `eib_action.py` | `PRIMITIVE_MAP`에 새 액션 문자열 매핑 추가 | 추가만 하면 안전, 기존 매핑 수정하면 위험 |
| `planner.py` | Goal/Progress 텍스트 커스터마이징, 커스텀 피드백 경로 | `_body_to_text()`가 인스턴스 메서드임 주의 (원래 @staticmethod였으나 변경됨) |

### 위험도 중간 — 메타데이터/상태 등록

| 파일 | 수정이 필요한 경우 | 위험 |
|------|-------------------|------|
| `category_mapping.csv` | BDDL에서 사용하는 synset이 기존에 없을 때 | 행 추가는 안전, 기존 행 수정은 위험 |
| `synsets.csv` | 새 오브젝트의 ability 정의 필요 시 | 행 추가는 안전, 기존 ability 플래그 변경은 위험 |
| `output_hierarchy_properties.json` | synset hierarchy에 새 노드 추가 시 | 기존 구조를 건드리면 다른 태스크의 오브젝트 매칭에 영향 |
| `object_states/factory.py` | 새 ability-state 매핑 필요 시 | `_ABILITY_DEPENDENCIES`에 추가만 하면 안전 |

### 위험도 낮음 — 새 상태/모듈 추가

| 파일 | 수정이 필요한 경우 | 위험 |
|------|-------------------|------|
| `object_states/__init__.py` | 새 ObjectState 클래스 생성 시 import 추가 | 기존 import에 영향 없음 |
| `run_llm_agent.py` | 태스크별 커스텀 상태 주입 (기존 if-elif 분기 존재) | 분기 추가이므로 기존에 영향 없음 |
| `domain_omnigibson.bddl` | BDDL에서 새 predicate 사용 시 | predicate 추가는 안전, 기존 시그니처 변경은 위험 |

---

## 3. 텍스트 커스터마이징 (Goal / Progress / 프롬프트)

### Goal 텍스트 생성 경로
1. BDDL goal 조건 → `task.ground_goal_state_options[0]` (HEAD 객체 리스트)
2. 각 HEAD의 `terms` 속성 (flat string list) → `_body_to_text(terms)` → 자연어 텍스트
3. `_body_to_text()` 내부의 `PRED_NAMES` dict가 predicate → 텍스트 매핑
   - 예: `"covered"` → `"covered with"` → `"sheet.n.02_1 is covered with ink.n.01_1"`
4. task-specific 분기: `self.task.activity_name`에 따라 `PRED_NAMES` 값을 override 가능
   - 예: draw 태스크에서 `"covered"` → `"has a straight line drawn with"`

### Goal 텍스트 커스터마이징 시 주의사항
- `_body_to_text()`는 **인스턴스 메서드** (`@staticmethod` 아님) — `self` 참조 가능
- `_fmt()` 함수가 `"{obj} is {pred} {obj2}"` 형식으로 생성하므로, pred가 `"has ..."`로 시작하면 `"is has"` 문법 오류 발생
  - **해결**: `VERB_PREDS` set에 해당 pred를 추가하면 `"is"` 생략 → `"{obj} {pred} {obj2}"`
- `_obj_name()`에서 synset 이름을 그대로 유지해야 Scene의 오브젝트 이름과 일치
  - `sheet.n.02_1` 그대로 사용 (축약하면 LLM이 다른 오브젝트로 착각)
- `_coerce()` 헬퍼가 tuple → list 재귀 변환 (BDDL이 tuple을 반환할 수 있음)

### Progress 텍스트
- 매 step 프롬프트에 자동 포함 (DONE 호출 불필요)
- `_get_goal_progress()` → `_idx_to_text()` → `_body_to_text()` 경로
- `_idx_to_text()` 전략 순서: terms 속성 → body 속성 → children 재구성

### 로봇 설명 프롬프트
- `prompt_utils.py`의 `build_system_prompt(robot_type=)`
- single arm (Fetch, Stretch): "You have a single arm, so you can only hold one object at a time."
- dual arm (Tiago, R1, R1Pro): "You have two arms and can hold one object in each hand."
- `planner.py`에서 `type(self.robot).__name__`으로 자동 전달

---

## 4. 커스텀 피드백 메커니즘

DRAW처럼 "액션은 성공하지만 조건부 피드백"이 필요한 경우:

### 데이터 흐름 (4단계)
1. **프리미티브 메서드**에서 `self._custom_success_feedback = "Drew a curvy line on the paper."` 설정
2. **planner.py `_execute_action()`**에서 `self.controller._custom_success_feedback` 읽기 → `self._last_success_feedback`에 저장
3. **caller**에서 `self._last_success_feedback`가 있으면 action_history에 `-> SUCCESS: {feedback}`으로 기록 + `step_log["execution"]["feedback"]`에 저장
4. **`_build_full_action_history()`**에서 `execution.get("feedback")` 반영 (result.json용)

### 주의: planner vs eib_action 경로 차이
- `planner.py`의 `_execute_action()`은 `eib_action.py`를 **거치지 않고** 직접 `controller.apply_ref()` 호출
- 따라서 `eib_action.py`에만 피드백 로직을 넣으면 planner 경로에서 안 탐
- **양쪽 모두에 로직 필요**: eib_action.py (EIB 경로용) + planner.py (기본 경로용)

---

## 5. 시나리오별 가이드

### 시나리오 A: 기존 액션만으로 충분한 태스크
예: "pick up trash", "set table" 등 GRASP/PLACE_ON_TOP/NAVIGATE_TO로 해결 가능

**생성 파일**: BDDL + scene template + available_tasks.yaml
**수정 파일**: 없음
**기존 태스크 영향**: 없음

### 시나리오 B: 새 오브젝트가 필요한 태스크
예: 기존 synsets.csv에 없는 오브젝트 사용

**추가 수정**:
- `category_mapping.csv` — 행 추가 (synset → category 매핑)
- `synsets.csv` — 행 추가 (ability 플래그 정의)
- `output_hierarchy_properties.json` — 노드 추가 (필요시)

**기존 태스크 영향**: 행 추가만이면 없음

### 시나리오 C: 새 액션 프리미티브가 필요한 태스크
예: DRAW, STIR, KNEAD 등 기존에 없는 조작

**수정 파일 (6개)**:
1. `eib_semantic_action_primitives.py` — enum 끝에 추가 + VALID_PRIMITIVES + controller_functions + 메서드 구현 + `_custom_success_feedback` 초기화
2. `symbolic_semantic_action_primitives.py` — 동일 (파티클 상태 변경 시 방식 A: `_freeze_particle_physics()` 또는 방식 B: monkey-patch, 섹션 7.5 참조)
3. `eib_action.py` — PRIMITIVE_MAP + TWO_TARGET_ACTIONS (또는 NO_TARGET_ACTIONS)
4. `prompt_utils.py` — `_SYMBOLIC_PRIMITIVES` + `_EIB_PRIMITIVES` + `PRIMITIVE_ARG_COUNT` + tool descriptions
5. `planner.py` — Goal/Progress 텍스트 커스터마이징 (필요시) + 커스텀 피드백 경로 (필요시)

**tool descriptions에 `(Requires: ~)` 전제조건 반드시 추가**:
- `prompt_utils.py`의 `_TOOL_DESCRIPTIONS_STARTER` 또는 `_TOOL_DESCRIPTIONS_SYMBOLIC_EXTRA`에 새 액션 설명을 추가할 때, 반드시 hand state 전제조건을 명시해야 함
- 형식: 설명 끝에 `(Requires: holding the [tool])`, `(Requires: holding an object)`, `(Requires: hand empty)`, 또는 `(Either hand state)` 중 하나
- 예시: `- HAMMER[target_nail, hammer]: Strike a nail with the hammer you are holding. (Requires: holding the hammer)`
- **이유**: 전제조건이 없으면 LLM이 손에 아무것도 없는 상태에서 PIERCE를 시도하거나, 이미 들고 있는데 GRASP를 시도하는 등의 에러가 빈번하게 발생함 (GPT-4.1, GPT-5-mini 등에서 관찰됨)

**기존 태스크 영향**: enum을 끝에 추가하면 기존 순서 유지. 공통 유틸리티 수정 시 위험.

### 시나리오 D: 새 ObjectState가 필요한 태스크
예: "Stirred", "Kneaded" 같은 커스텀 상태

**수정 파일 (5개)**:
1. `object_states/` 디렉토리에 새 .py 파일 생성
2. `object_states/__init__.py` — import 추가
3. `object_states/factory.py` — `_ABILITY_DEPENDENCIES`에 ability 매핑 추가
4. `bddl_utils.py` — `SUPPORTED_PREDICATES`에 새 predicate 추가
5. `domain_omnigibson.bddl` — predicate 선언 추가

---

## 6. 안전하게 작업하기 위한 원칙

1. **기존 파일은 "추가"만** 한다 (행 추가, elif 추가, enum 끝에 추가)
2. **기존 함수의 시그니처나 로직은 절대 변경하지 않는다**
3. 공통 유틸리티 수정이 필요하면 → **새 함수를 만들어서 새 프리미티브에서만 호출**
4. **IntEnum은 반드시 맨 끝에 추가** (auto() 순서 보장)
5. **CSV/JSON은 기존 행/키를 수정하지 않고 새 행/키만 추가**
6. `_body_to_text()`를 수정할 때 **task 분기는 activity_name 체크로 격리** — 다른 태스크에 영향 주지 않도록
7. 커스텀 피드백 필요 시 **planner.py와 eib_action.py 양쪽** 모두 반영 확인
8. synset 이름과 scene 오브젝트 이름의 **일관성 유지** — Goal, Progress, Objects in the scene에서 동일한 형태 사용

---

## 6.5 NAVIGATE_TO 규칙 및 카메라 연동

### NAVIGATE_TO 동작 방식
- **모든 오브젝트를 인자로 받을 수 있음**
- 고정 오브젝트(furniture) → 그 오브젝트 앞 1m로 텔레포트
- **비고정 오브젝트(toast 등)** → 내부적으로 `_find_nearest_fixed_object()`가 해당 물체와 가장 가까운 고정 오브젝트를 찾아서 그 가구 앞으로 텔레포트
  - 예: `NAVIGATE_TO[toast]` → toast 근처 countertop 앞으로 이동
- EIB `eib_primitives.py`는 여전히 `NAVIGABLE_CATEGORIES` 화이트리스트 방식 (별도)

### NAVIGATE_TO를 먼저 해야 하는 이유 (카메라)
- `_anchored_pos/ori`는 navigate 시 갱신됨
- navigate 없이 바로 GRASP하면 `_anchored_pos`가 로봇 초기 위치에 머물러 있음
- 카메라가 `_anchored_pos` 위 1.5m에서 찍으므로, 오브젝트와 너무 멀리 떨어져 카메라 앵글이 깨짐
- **mock LLM 테스트 시에도 navigate → grasp 순서를 반영하도록 mock 계획 수정 필요**

### 액션별 NAVIGATE_TO 필요 여부

**navigate 필수 — `_check_proximity` 있음 (멀면 에러):**

| 액션 | proximity 체크 대상 |
|---|---|
| GRASP | target_obj |
| OPEN / CLOSE | target_obj |
| TOGGLE_ON / TOGGLE_OFF | target_obj |
| PLACE_ON_TOP | surface |
| PLACE_INSIDE | container |
| WIPE | target_obj |
| CUT | target_obj |
| SOAK_UNDER / SOAK_INSIDE | target_obj |
| FILL_WITH | target_obj |
| POUR_INTO | target_obj |
| SPREAD | target_obj |
| DRAW | target_obj |
| PIERCE | target_obj |
| HAMMER | target_nail |
| PLACE_AGAINST | surface |
| PLACE_NEXT_TO | target_obj |
**navigate 권장 — proximity 체크는 없지만 근처에 있어야 정상 동작:**

| 액션 | 이유 |
|---|---|
| SWEEP | target_obj에 proximity 체크 없으나, 근처에 있어야 정상 동작 |
| PUSH | 로봇→물체 방향으로 미므로, 멀면 결과가 이상함 |
| PULL | 물체→로봇 방향으로 당기므로, 멀면 결과가 이상함 |
| CLIMB_ON | 물체 위로 로봇 z를 올리는데, XY가 멀면 공중에 뜸 |

**navigate 불필요:**

| 액션 | 이유 |
|---|---|
| NAVIGATE_TO | 자체가 이동 |
| RELEASE | 손에 든 물체를 놓기 — 위치 무관 |
| CLIMB_DOWN | 현재 올라간 물체에서 내려오기 |
| WAIT / WAIT_FOR_COOKED / WAIT_FOR_WASHED / WAIT_FOR_FROZEN | 상태 변경만 |
| PLACE_NEAR_HEATING_ELEMENT | proximity 없이 직접 텔레포트 배치 |

### LLM 프롬프트에서의 가이드
- `prompt_utils.py`의 tool description에 navigate 전제조건을 명시:
  - 위 "navigate 필수" 액션들은 proximity check가 있으므로 멀면 실패
  - LLM이 자연스럽게 navigate를 먼저 하도록 유도

---

## 7. 물리 처리 체계 (symbolic_semantic_action_primitives.py)

새 액션 프리미티브를 만들 때 물리 settle/snapshot을 어떻게 적용할지 결정해야 한다.

### 7.1 `_settle_robot()` — 액션 내 물리 (1 physics step)

```
로봇 위치/ori 저장 → NaN 가드 → 위치 재설정 + keep_still()
→ 잡은 물체 EEF에 핀 + keep_still()
→ no-op action 1스텝 yield → 로봇 위치 재고정
```

- 부모 클래스(Starter)의 50+ step 대신 **1 step만** 실행 (CUDA error 700 방지)
- teleport 기반이라 1 step이면 충분

### 7.2 OPTION-B Scene Freeze — 액션 간 물리 (스냅샷 시스템)

**문제**: 1 physics step이라도 관련 없는 물체가 drift함

**3단계 스냅샷**:

| 단계 | 메서드 | 시점 |
|------|--------|------|
| 저장 | `_save_scene_positions()` | `apply_ref`의 `finally` — 매 액션 완료/실패 후 |
| 복원 | `_restore_from_snapshot(exclude=...)` | 각 액션 **내부**의 `_settle_robot()` 직후 |
| 제외 | `exclude` 파라미터 | 현재 조작 중인 물체만 제외 |

**중요**: `apply_ref` 마지막의 `_settle_robot()`는 `finally` 블록 **바깥**이므로 restore 없음.
이 drift는 **다음 액션의 `_restore_from_snapshot()`이 보정**하는 구조.

### 7.3 액션별 물리 적용 현황

| 액션 | settle 후 restore | 추가 처리 |
|------|-------------------|----------|
| GRASP | `_restore_from_snapshot(exclude={target_obj})` | - |
| RELEASE | `_restore_from_snapshot(exclude={released_obj})` | `_recover_if_flew()` |
| PLACE (모든 경로) | `_restore_from_snapshot(exclude={target_obj})` | 배치 실패 시 재시도 |
| OPEN/CLOSE | **restore 없음** — `_no_op()` 사용 | 자체 보호: 내부 물체 + 로봇 위치 저장/복원 |
| TOGGLE | **restore 없음** — `_no_op()` 사용 | - |
| WIPE/CUT/SOAK/FILL/POUR | **restore 없음** | settle만 |
| SPREAD/DRAW | **restore 없음** | 방식 A: `_freeze_particle_physics()` + settle / 방식 B: monkey-patch `_get_value` + settle (섹션 7.5 참조) |

### 7.4 물체 날아감 방지

- **`_recover_if_flew()`**: RELEASE 전용. `_release_ag()`에서 위치 저장 → settle 후 `MAX_SETTLE_DISPLACEMENT` 초과 시 원위치
- **`_check_and_reset_object()`**: 임의 물체용. `_sample_on_top_heat_source`에서 사용

### 7.5 파티클 상태 처리 — 두 가지 방식

파티클 관련 상태(`Covered`, `Saturated`)를 변경하는 액션에는 두 가지 방식이 있으며, 상황에 따라 선택한다.

---

#### 방식 A: 물리 기반 — `_freeze_particle_physics()` (GPU dynamics 필요)

- 속도 0 + `physxParticle:particleEnabled = False`
- SPREAD와 DRAW에서 `Covered.set_value()` 성공 후 호출
- symbolic 모드에서 파티클이 중력으로 떨어지는 것 방지
- **전제조건**: `gm.USE_GPU_DYNAMICS = True` 필수

**알려진 문제** (물리 기반 접근이 불안정한 이유):
1. `gm.USE_GPU_DYNAMICS = True` 필수 → 환경 제약
2. `force_init=True` 후 system_prim이 PhysX에 의해 GC됨 → prim validation/reinit 필요
3. prim reinit 시 `BaseSystem.initialize()`가 `initialized = True`를 subclass 완료 전에 설정 → 반쪽 초기화 상태
4. `_freeze_particle_physics()` 후에도 `ContactParticles` 체크가 불안정 (파티클 생성 → physics step → 파티클 떨어짐 → `Covered._get_value` = False)
5. 전체 경로에 retry loop, instancer cleanup, scope prim 제거 등 복잡한 방어 코드 필요

---

#### 방식 B: 순수 symbolic — `_get_value` monkey-patch (GPU dynamics 불필요, 2026-03-20 최종)

**사용 의도**: OG upstream 파일(`covered.py`, `object_state_base.py`, BDDL 등)을 수정하지 않고, 특정 (object, system) 쌍에 대해서만 `_get_value`가 True를 반환하도록 만든다. PhysX 파티클을 아예 생성하지 않는다.

**적용 위치**: `symbolic_semantic_action_primitives.py`의 `_spread()`, `_draw()` 등 파티클 상태를 변경하는 액션

**코드 패턴** (`symbolic_semantic_action_primitives.py` 내):
```python
# _spread() 내부, fluid system resolve 후:
if object_states.Covered in target_obj.states:
    covered_state = target_obj.states[object_states.Covered]
    system_name = system.name
    original_fn = covered_state._get_value

    def _patched_get_value(sys, _orig=original_fn, _name=system_name):
        if getattr(sys, "name", None) == _name:
            return True
        return _orig(sys)

    covered_state._get_value = _patched_get_value
```

**전체 호출 체인 (BDDL goal evaluation → monkey-patch까지)**:
```
planner._get_goal_progress()                                    # planner.py:815
→ bddl.activity.evaluate_goal_conditions(ground_conditions)     # bddl/activity.py:144
→ evaluate_state(compiled_state)                                # bddl/condition_evaluation.py:546
→ HEAD.evaluate()                                               # condition_evaluation.py:487
→ ObjectStateBinaryPredicate._evaluate(entity1, entity2)        # bddl_utils.py:167
  │ entity1 = toast의 BDDLEntity (wrapped_obj = DatasetObject)
  │ entity2 = melted_butter의 BDDLEntity (wrapped_obj = FluidSystem)
  │ entity2.exists = True (wrapped_obj is not None)
  │ entity2.initialized = True (system.initialized)
→ entity1.get_state(Covered, entity2.wrapped_obj)               # bddl_utils.py:724
→ toast.wrapped_obj.states[Covered].get_value(melted_butter_system)  # DatasetObject.states[Covered]
→ object_state_base.get_value(*args)                            # object_state_base.py:309
  │ cache miss → update_cache(args)                             # object_state_base.py:185
→ self._get_value(*get_value_args)                              # object_state_base.py:195
→ ★ _patched_get_value(sys=melted_butter_system)                # monkey-patched!
  │ getattr(sys, "name", None) == "melted__butter" → True
  └─ return True → goal satisfied
```

**핵심 파일 연결 관계**:

| 파일 | 역할 | monkey-patch와의 관계 |
|------|------|----------------------|
| `symbolic_semantic_action_primitives.py` | `_spread()` 내에서 patch 적용 | **patch 생성 위치** |
| `object_states/object_state_base.py` | `get_value()` → `update_cache()` → `_get_value()` 호출 | **patch가 가로채는 지점** (`_get_value`) |
| `object_states/covered.py` | 원래의 `Covered._get_value(system)` 구현 | **원래 함수** (patch의 `_orig`로 보존) |
| `utils/bddl_utils.py` | `BDDLEntity.get_state()` → `wrapped_obj.states[Covered].get_value()` | **BDDL → OG state 연결** |
| `bddl3/bddl/condition_evaluation.py` | `HEAD.evaluate()` → `ObjectStateBinaryPredicate._evaluate()` | **BDDL goal evaluation 진입점** |
| `llm_agent/planner.py` | `_get_goal_progress()` → `evaluate_goal_conditions()` + `get_reward()` | **매 step goal 체크 + 최종 reward 계산** |

**왜 이 방식이 안전한가**:
- **인스턴스 수준 patch**: `target_obj.states[Covered]._get_value`만 교체. 다른 object의 Covered state에 영향 없음
- **OG upstream 수정 0개**: `covered.py`, `object_state_base.py`, `env_base.py` 등 일절 미수정
- **closure로 원래 함수 보존**: `_orig=original_fn` 디폴트 인자로 캡처. 다른 system에 대한 쿼리는 정상 동작
- **GPU dynamics 불필요**: 파티클 생성 자체를 하지 않으므로 `gm.USE_GPU_DYNAMICS` 설정 무관
- **PhysX prim 불필요**: USD stage의 particle system prim이 GC되어도 무관
- **중복 patch 안전**: 같은 (object, system) 쌍에 대해 여러 번 patch해도, 이전 patch가 `_orig`로 체이닝되므로 무해

**주의사항**:
- monkey-patch는 **Python 런타임 내에서만 유효**. 시뮬레이터를 재시작하면 초기화됨
- `_get_value`의 시그니처가 `(self, system)` → 실제로는 인스턴스 메서드이지만, 이미 바인딩된 메서드를 교체하므로 `self` 없이 `(sys)` 시그니처로 정의
- `getattr(sys, "name", None) == _name` 가드: system이 None이거나 예상치 못한 타입이어도 안전
- `object_state_base.py`의 **캐시 시스템**: `get_value()`는 캐시를 사용함. `_get_value`가 patch되면 캐시 miss 시 patch된 함수가 호출됨. 캐시 hit 시에는 이전에 계산된 값(True)이 반환되므로 문제 없음

**적용 사례**:

| 액션 | 패치 대상 | 패치하는 state | system 예시 |
|------|-----------|---------------|-------------|
| `_spread()` | `target_obj.states[Covered]._get_value` | `Covered` | `melted__butter` |
| `_draw()` | **monkey-patch 미사용** — 일반 `Covered.set_value(ink_system, True)` 호출 | `Covered` | `ink` |

**검증 완료**: 실험 `20260320_160702` — SPREAD SUCCESS → goal 2/2 달성 → `final_reward: 1.0`, 5 step/14.5초 완료

---

#### 방식 선택 가이드

| 조건 | 권장 방식 |
|------|-----------|
| GPU dynamics 사용 가능 + 물리적 파티클 시각화 필요 | 방식 A (`_freeze_particle_physics`) |
| GPU dynamics 불가 또는 불안정 + symbolic만으로 충분 | **방식 B (monkey-patch)** |
| 새 태스크에서 Covered/Saturated 상태 변경 필요 | 방식 B 권장 (코드 1~10줄, side effect 없음) |

---

#### SPREAD의 완전한 symbolic 흐름 (방식 B)

```
_spread(fluid_container, target_obj):
  1. _check_proximity(target_obj)         ← 로봇 거리 체크
  2. 좌표 기반 rubber_mat 체크             ← OnTop.get_value() 미사용 (물리 의존 제거)
     - target_pos vs rubber_mat_pos
     - xy_dist < 0.15 and 0 < z_diff < 0.15 → stabilized
     - 미충족 시: "SPREAD failed: toast slid during spreading."
  3. fluid system resolve                  ← BaseSystem이면 직접 사용, 아니면 get_contained_systems
  4. monkey-patch Covered._get_value       ← 핵심: 파티클 없이 True 반환
  5. yield from _settle_robot()            ← 1 physics step (형식상)
```

#### rubber_mat precondition의 좌표 기반 체크

`OnTop.get_value(rubber_mat)` 대신 좌표 근접 체크를 사용하는 이유:
- `OnTop.get_value()`는 PhysX 접촉 판정에 의존 → symbolic teleport 후 접촉이 미감지될 수 있음
- 좌표 체크: `xy_dist < 0.15 and 0 < z_diff < 0.15` → PLACE_ON_TOP 성공 후 위치가 보장됨
- 실패 시 에러 메시지에 가장 가까운 surface 이름을 포함 (LLM이 rubber_mat을 사용하도록 유도)

### 7.6 OPEN/CLOSE 자체 물리 보호

OPTION-B와 별개로 자체 보호 로직 보유:
- 내부 물체 위치 사전 저장 (`saved_poses`)
- `_no_op()` 사용 (`_settle_robot()` 대신) — CUDA error 방지
- 물리 step 후 내부 물체 원위치 복원
- 로봇 위치도 별도 재핀 (문 물리가 로봇을 밀 수 있음)

### 7.7 새 액션 작성 시 물리 적용 가이드

- **물체를 이동시키는 액션** (grasp, place 류): `_settle_robot()` + `_restore_from_snapshot(exclude={조작물체})` 사용
- **순수 symbolic 액션** (pierce 류 — 플래그만 변경, 물리적 이동 없음): `_settle_robot()`과 `_restore_from_snapshot()`을 **넣지 않는다**. `apply_ref` 마지막의 `_settle_robot()`이 대신 처리. 아래 7.9 참조.
- **상태만 변경하는 액션** (toggle, fill 류): `_settle_robot()` 또는 `_no_op()`만 사용, restore 불필요
- **파티클 상태 변경 액션** (spread, draw 류): 방식 A (`_freeze_particle_physics()`, GPU dynamics 필요) 또는 방식 B (monkey-patch `_get_value`, GPU dynamics 불필요). 섹션 7.5 참조
- **관절 조작 액션** (open/close 류): `_no_op()` + 자체 위치 저장/복원

### 7.8 전체 흐름

```
apply_ref(action, args)
  │
  ├─ try:
  │    └─ action 실행
  │         ├─ _settle_robot()                     ← 1 physics step
  │         └─ _restore_from_snapshot(exclude=...)  ← 일부 액션만 (GRASP, RELEASE, PLACE)
  │
  ├─ finally:
  │    └─ _post_action_snapshot = _save_scene_positions()
  │         ↑ 현재 씬 전체 상태 저장 (다음 액션의 restore 기준점)
  │
  └─ _settle_robot()    ← 마무리 settle (restore 없음)
       ↑ 이 drift는 다음 액션의 _restore_from_snapshot()이 보정
```

### 7.9 순수 symbolic 액션의 NaN 문제와 해결 (2026-03-20, _pierce 사례)

#### 문제 상황

`_pierce()`에서 `_settle_robot()` (1 physics step) 실행 시, 대상 오브젝트(carton)의 orientation이 NaN으로 오염됨. 이후 `_restore_from_snapshot(exclude={carton, nail})`에서 carton은 exclude이므로 NaN이 복원되지 않고 유지. `apply_ref`의 `finally`에서 `_save_scene_positions()`가 NaN을 snapshot에 저장 → 이후 모든 action이 NaN AssertionError로 영구 실패.

```
_pierce() 실행 흐름 (수정 전):
  1. Pierced state = True 설정 (symbolic)
  2. _release_ag() (변수만 None)
  3. yield from _settle_robot()  ← 1 physics step에서 carton NaN 발생
  4. _restore_from_snapshot(exclude={carton, nail})  ← carton은 exclude → NaN 유지

apply_ref finally:
  5. _save_scene_positions()  ← carton의 NaN orientation이 snapshot에 저장됨

다음 action:
  6. _restore_from_snapshot(exclude={...})  ← snapshot 자체에 NaN이 있으므로 복구 불가
```

#### 해결 방법 A: 순수 symbolic 액션에서 settle/restore 제거 (현재 적용)

`_pierce()`는 파이썬 변수(Pierced state, `_grasped_obj`)만 변경하는 순수 symbolic 액션이므로 physics step이 필요 없음. `_settle_robot()`과 `_restore_from_snapshot()`을 주석처리.

**부작용**: `_pierce()`가 아무것도 yield하지 않는 빈 generator가 됨 → `apply_ref`의 `yield from` 처리 과정에서 **TypeError: 'NoneType' object is not iterable** 발생. 단, Pierced state는 이미 설정된 상태이므로 symbolic 효과는 정상 작동.

**부작용 해결**: `planner.py`의 `_execute_action()`에서 `except Exception` 블록에 PIERCE 후처리 추가 — action이 PIERCE이고 piercing_tool의 Pierced state가 True이면 에러를 무시하고 SUCCESS로 처리 + custom feedback 정상 출력.

#### 해결 방법 B: `_restore_scene_positions()` NaN 가드 (미적용, 대안)

방법 A 대신 또는 추가로 적용할 수 있는 방어적 안전장치. `_restore_scene_positions()`에서 exclude 오브젝트의 orientation을 검사해서, NaN이면 snapshot의 정상값으로 복원.

```python
def _restore_scene_positions(self, saved, exclude=None):
    exclude = set(exclude or [])
    for obj, (pos, ori) in saved.items():
        if obj in exclude:
            # NaN 가드: physics step이 exclude 오브젝트를 오염시킨 경우 복원
            try:
                _, cur_ori = obj.get_position_orientation()
                if th.isnan(cur_ori).any():
                    obj.set_position_orientation(position=pos, orientation=ori)
                    obj.keep_still()
            except Exception:
                pass
            continue
        try:
            obj.set_position_orientation(position=pos, orientation=ori)
            obj.keep_still()
        except Exception:
            pass
```

이 방법의 동작 원리:
- **정상 상황**: exclude 오브젝트는 현재 physics 결과를 유지 (기존과 동일 동작)
- **NaN 상황**: exclude 오브젝트의 orientation이 NaN이면, snapshot에 저장된 이전 정상값(position, orientation)으로 복원
- **symbolic 상태에 영향 없음**: position/orientation만 복원하므로 Pierced state, `_grasped_obj` 등 symbolic 변수는 유지됨

이 방법의 한계:
- `_restore_from_snapshot()`은 action 내부에서 호출되지만, `_save_scene_positions()`는 `apply_ref`의 `finally`에서 호출됨
- NaN 가드가 action 내부에서 NaN을 복원해도, `finally`의 snapshot 저장 시점은 action generator의 모든 yield가 완료된 후 → action 내부의 마지막 `yield from _settle_robot()`이 또다시 NaN을 만들면 그것이 snapshot에 저장됨
- 따라서 **`_save_scene_positions()`에도 NaN 가드를 추가**해야 완전한 방어가 됨 (NaN orientation인 오브젝트는 저장하지 않고 이전 snapshot 값을 유지)

방법 A와 B의 비교:
- **방법 A** (settle 제거): 원인 자체를 제거. 단순하지만 빈 generator 부작용 처리 필요
- **방법 B** (NaN 가드): 방어적. pierce 외의 다른 action에서 NaN이 발생해도 보호. 하지만 `_save_scene_positions`까지 가드해야 완전함

---

## 8. 주요 버그/함정 기록 (향후 참고)

| 증상 | 원인 | 해결 |
|------|------|------|
| `FileNotFoundError` 씬 로딩 실패 | scene template JSON 미생성 | 생성 스크립트로 JSON 생성 |
| Progress `[TODO] 0`, `[TODO] 1` | `_body_to_text()` 예외 → `str(idx)` fallback | terms 속성 우선 사용 + tuple→list 변환 |
| `NameError: name 'self' is not defined` | `@staticmethod`에서 `self` 참조 | `@staticmethod` 제거 → 인스턴스 메서드 |
| Goal `sheet1` ≠ Scene `sheet.n.02_1` | goal text가 BDDL natural language에서 생성 | goal text도 `_body_to_text()`로 생성하여 synset 이름 통일 |
| `"is has a straight line"` 문법 오류 | `_fmt()`의 `"is {pred}"` + pred가 `"has..."` | VERB_PREDS에 해당 pred 추가 |
| result.json에 커스텀 피드백 누락 | `_build_full_action_history()`가 feedback 미반영 | SUCCESS 케이스에서 `execution.get("feedback")` 확인 |
| LLM이 커스텀 피드백을 못 봄 | planner가 eib_action.py를 거치지 않고 직접 `apply_ref()` 호출 | planner의 `_execute_action()`에 직접 피드백 읽기 로직 추가 |
| DRAW 성공인데 goal 미달성, LLM 추론 불가 | DRAW가 무조건 SUCCESS만 반환, 피드백 없음 | `_custom_success_feedback`으로 "Drew a curvy line" 등 단서 제공 |
| 프롬프트에 항상 "Robot is not holding anything" 표시 | symbolic 모드에서 `_grasped_obj`만 사용하고 `_ag_obj_in_hand` 미설정 → `_get_robot_holding()`이 None 반환 | `planner.py`의 `_get_robot_holding()`에서 `controller._grasped_obj`를 최우선으로 확인하도록 수정 (2026-03-20) |
| LLM이 안 들고 있는데 PIERCE/PLACE 시도, 들고 있는데 GRASP 시도 | action 설명에 hand state 전제조건이 없어서 LLM이 판단 못함 | `prompt_utils.py`의 모든 action 설명에 `(Requires: ~)` 전제조건 추가 (2026-03-20) |
| `on top of carton.n.02_1` 등 spurious spatial relation 표시 | 시뮬레이터가 carton 같은 flat panel 위에 OnTop 판정 | `planner.py`의 OnTop 체크에도 `non_surface_cats` 필터 추가 (Inside 필터와 동일 패턴) |

---

## 9. Mock LLM (테스트용 하드코딩된 액션 시퀀스)

API 호출 없이 파이프라인을 빠르게 테스트할 때 사용. 각 태스크의 mock YAML에 적는 액션 시퀀스는 해당 태스크의 **oracle code (GT code)** 역할을 하며, 이상적인 정답 경로를 정의한다.

### 파일 위치

| 파일 | 역할 |
|------|------|
| `omnigibson/llm_agent/llm/mock_llm.py` | MockLLM 클래스 — `responses` 리스트를 순차적으로 반환 |
| `omnigibson/llm_agent/configs/llm_mock_{task_name}.yaml` | 태스크 전용 Mock 시퀀스 (예: `llm_mock_hammer_nail.yaml`) |
| `omnigibson/examples/llm_agent/run_llm_agent.py` (line 287-296) | `--model mock` 시 `llm_mock_{task_name}.yaml` 자동 감지 |

### 실행 방법

```bash
python -m omnigibson.examples.llm_agent.run_llm_agent \
  --model mock --task hammer_nail --scene house_single_floor --robot Fetch --symbolic
```

### 작동 원리

- `MockLLM.generate()`가 호출될 때마다 `responses[index % len]`을 반환하고 인덱스 +1
- `--model mock` 사용 시 먼저 `llm_mock_{task_name}.yaml` 파일을 찾고, 없으면 `llm_mock.yaml` (기본) 로드
- 새 태스크의 mock을 만들려면 `configs/llm_mock_{task_name}.yaml`에 `responses:` 리스트 정의

---

## 10. 액션별 특징 및 카메라 Tracking 규칙

카메라 코드: `omnigibson/envs/common/eib_camera.py` → `get_rgb()`
이미지 저장: `omnigibson/llm_agent/planner.py` → step 실행 전후 `_1.png` (before), `_2.png` (after)

### Tracking 결정 규칙

- **기본**: `apply_ref()`에서 `self._tracking_object = args[-1]` (마지막 인자)
- **내부 덮어쓰기**: PIERCE, HAMMER, WIPE, CUT, FILL_WITH, TEAR 등은 함수 내부에서 `self._tracking_object = target_obj` (첫번째 인자)로 재설정
- **RELEASE**: `self._tracking_object = self._grasped_obj` (놓는 물체)

### 카메라 전략 분류

| 카메라 전략 | 설명 |
|------------|------|
| **side view** | 로봇 옆에서 EEF 높이로 촬영. orientation-aware (left→right→overhead fallback). collision 체크 포함 |
| **overhead+topdown** | `anchored_pos` XY + `_CAM_Z_OFFSET`(1.5m) 높이에서, 바닥(Z=0) 방향으로 수직 하강 시선 |
| **overhead+topdown+높이추가** | 위와 동일하되 높이를 더 올림 (로봇 머리 넘기기 위해) |
| **overhead 기본** | `_CAM_Z_OFFSET` 높이에서, tracking 물체 상단(aabb_hi)을 비스듬히 내려다봄 |
| **surface cam** | `_get_rgb_surface()` — countertop 위를 로봇 쪽에서 내려다봄 |

### 액션별 카메라 매핑 (2026-03-24 기준)

| 액션 | Tracking 대상 | 카메라 전략 | 이미지 저장 |
|------|-------------|-----------|-----------|
| **GRASP[obj]** | obj (마지막 arg) | side view | `_2.png` |
| **PLACE_ON_TOP[countertop]** | countertop (surface) | side view | `_2.png` |
| **PLACE_ON_TOP[기타]** | target obj | side view + overhead 둘 다 | `_2_side.png` + `_2_top.png` |
| **PLACE_AGAINST[wall]** | wall (furniture) | overhead+topdown, 높이 +0.5 | `_2.png` |
| **PLACE_NEXT_TO[obj]** | obj | overhead+topdown | `_2.png` |
| **NAVIGATE_TO[countertop]** | countertop (surface) | overhead+topdown, 높이 +1.0 | `_2.png` |
| **NAVIGATE_TO[wall/기타]** | wall/기타 (furniture) | overhead+topdown | `_2.png` |
| **PIERCE[target, tool]** | target (내부 덮어쓰기) | overhead 기본 | `_2.png` |
| **HAMMER[nail, hammer]** | nail (내부 덮어쓰기) | overhead+topdown | `_2.png` |
| **SPREAD[fluid, target]** | target (마지막 arg) | overhead 기본 | `_2.png` |
| **DRAW[fluid, target]** | target (마지막 arg) | overhead 기본 | `_2.png` |
| **SWEEP[target]** | target (마지막 arg) | overhead 기본 | `_2.png` |
| **TEAR[target]** | target (내부 덮어쓰기) | overhead (PLACE_ON_TOP 스타일) | `_2.png` |
| **RELEASE** | grasped_obj | overhead 기본 | `_2.png` |

### _is_topdown 적용 액션

다음 액션은 look_target Z=0 (바닥 방향 수직 시선):
`GRASP`, `PLACE_NEXT_TO`, `PLACE_AGAINST`, `NAVIGATE_TO`

### Side View 동작 원리

1. EEF 위치 기준으로 로봇의 **왼쪽** 1m + 전방 0.3m에 카메라 배치 시도
2. collision 발생 시 → **오른쪽** 1m + 전방 0.3m으로 fallback
3. 양쪽 다 collision → 기본 overhead로 fallback
4. `_cam_collides()`: fixed object AABB, 천장 높이, 방 경계 체크

### PLACE_ON_TOP 이중 캡처 (`_force_overhead` 플래그)

- `planner.py`에서 PLACE_ON_TOP + non-countertop 감지 시:
  1. 기본 `get_rgb()` → side view → `_2_side.png`
  2. `_force_overhead = True` 설정 → `get_rgb()` → overhead → `_2_top.png`
  3. `_force_overhead = False` 복원
- `_force_overhead=True`일 때 `_side_view_actions`에서 PLACE_ON_TOP 제외, GRASP만 남음

---

## Legacy 기록 (과거 기재 → 수정된 내용)

> 이 섹션은 과거 가이드에 기재되었으나 코드 검증 결과 부정확했던 내용을 보존합니다.
> 삭제하지 않고 기록으로 남겨 향후 참고합니다.

### [2026-03-24 수정] _sweep()의 proximity 체크

- **과거 기재**: 섹션 6.5 "navigate 필수" 테이블에 `SWEEP | target_obj`로 기재
- **실제 코드**: `_sweep()`에는 `_check_proximity()` 호출이 **없음**
- **수정**: "navigate 권장" 테이블로 이동 (proximity 체크는 없지만 근처에 있어야 정상 동작)

### [2026-03-24 수정] _draw()의 monkey-patch 사용 여부

- **과거 기재**: 섹션 7.5 적용 사례 테이블에서 `_draw()` | `target_obj.states[Covered]._get_value` | `Covered` | `ink` — `_spread()`와 동일한 monkey-patch 방식으로 기재
- **실제 코드**: `_draw()`는 monkey-patch를 사용하지 않고 일반 `Covered.set_value(ink_system, True)`를 호출. monkey-patch는 `_spread()`만 사용
- **수정**: 테이블에 "monkey-patch 미사용" 명시

### [2026-03-24 수정] run_llm_agent.py mock 감지 라인 번호

- **과거 기재**: 섹션 9에서 `run_llm_agent.py (line 269-278)`
- **실제 코드**: mock LLM 감지 로직은 line 287-296에 위치
- **수정**: 라인 번호 287-296으로 정정
