---
name: CATS retrieve_egg_from_gap 구현 상세 분석 (v1 설계)
description: retrieve_egg_from_gap (v1 설계) — 자연어 피드백, demo 라벨 있음, CUT 없음. 이후 glass_shard에서 v2로 진화 (raw 센서, 라벨 제거, CUT 추가)
type: project
---

# CATS retrieve_egg_from_gap 구현 상세 분석

## 1. 파일 구조 (총 7개 핵심 파일)

| # | 파일 | 역할 |
|---|------|------|
| 1 | `omnigibson/llm_agent/cats_tasks/retrieve_egg_from_gap.py` | TASK_CONFIG dict (task 정의의 중심) |
| 2 | `omnigibson/llm_agent/cats_tasks/__init__.py` | CATS_TASK_REGISTRY에 task 등록 |
| 3 | `bddl3/bddl/activity_definitions/retrieve_egg_from_gap/problem0.bddl` | BDDL 오브젝트·goal 정의 |
| 4 | `datasets/.../house_single_floor_task_retrieve_egg_from_gap_0_0_template.json` | Scene template (오브젝트 배치·물리 상태) |
| 5 | `datasets/.../create_retrieve_egg_from_gap_template.py` | Scene template 생성 스크립트 |
| 6 | `omnigibson/llm_agent/configs/llm_mock_cats_retrieve_egg_from_gap.yaml` | Mock LLM 응답 시퀀스 |
| 7 | `omnigibson/llm_agent/planner_ca.py` | CATSPlanner — 4단계 파이프라인 엔진 |
| 8 | `omnigibson/examples/cats/run_cats_agent.py` | 실행 진입점 |

---

## 2. Primitive & Action 구성

### Stage 1: Exploration Primitives (5종)

task_config의 `exploration_primitives_desc`와 `exploration_feedbacks`로 정의.

| Primitive | Valid Arguments | 반환 정보 | 카메라 변경 |
|-----------|----------------|-----------|------------|
| `NAVIGATE_TO[target]` | `gap`, `gap, low_angle`, `countertop`, `fridge` | 위치 이동 후 시각 정보 | **O** (teleport + 이미지) |
| `TOUCH[surface]` | `gap_walls`, `egg`, `countertop_surface`, `fridge_surface` | 물리 속성 (폭, 재질, 온도) | X (텍스트만) |
| `PUSH[object, target]` | `hand, gap`, `fridge` | 고정/진입 가능 여부 | X (텍스트만) |
| `LOOK_CLOSER[target]` | `egg`, `gap`, `objects_on_countertop` | 확대 관찰 | **O** (줌 이미지) |
| `OPEN[object]` | `cabinet` | 내부 상태 | X (텍스트만) |

**핵심**: exploration_feedbacks는 `"ACTION_NAME[arg]": "feedback text"` 형식의 dict.
- planner_ca.py의 `_resolve_feedback_key()`가 action+arg를 key로 조합하여 feedback 조회
- 콤마 구분 arg는 whitespace 정규화 처리 (`", ".join(p.strip() for p in arg.split(","))`)

**종료 조건**: `DONE_EXPLORING[]` — LLM이 스스로 탐색 종료 선언

### Stage 2: Demo Observation (비실행, 관찰만)

- LLM에 exploration history + demo labels + demo 영상/이미지를 전달
- LLM은 관찰 소감만 응답 (action 없음)
- 이후 Metacognitive Probe 2에서 각 데모와 현재 상황의 유사점/차이점 설명

### Tool Selection Step (4항목 출력)

별도 LLM 호출로 수행. 출력 형식:
```
(1) 참조 데모: 어떤 데모를 참고했고 왜
(2) 선택 도구: 어떤 도구를 선택하는지
(3) 적합 근거: 현재 상황의 어떤 특성이 적합하게 만드는지
(4) 실행 계획: base action 시퀀스 + NEW_ACTION 포함
```

`_extract_tool_from_response()`가 GRASP[tool_name] 또는 "I select <tool>" 패턴으로 선택된 도구 추출.

### Stage 3: Adaptive Execution (2종 action)

#### Base Actions (7종, OmniGibson 물리 엔진)
`_ACTION_PRIMITIVE_MAP`에 정의:
- `NAVIGATE_TO`, `GRASP`, `RELEASE`, `PLACE_ON_TOP`, `PUSH`, `PULL`, `OPEN`, `CLOSE`
- `_execute_base_action()`에서 `controller.apply_ref(primitive, *objs)` 호출 → 실제 물리 시뮬레이션

#### NEW_ACTION (symbolic handler)
- 형식: `NEW_ACTION[name, tool, target]: "description"`
- task_config의 `new_action_handlers` dict에서 `(tool, target, context)` 키로 매칭
- 매칭 방식: tool_name과 target_name의 substring 매칭 (대소문자 무시)
- 결과: `outcome` (SUCCESS/FAILURE) + `aux_text` (설명) + `og.sim.step()`

retrieve_egg_from_gap의 new_action_handlers:
| tool | outcome | 설명 |
|------|---------|------|
| spatula | SUCCESS | spatula가 egg 아래로 미끄러져 들어감 |
| fork | FAILURE | fork가 egg를 찔러서 깨짐 (Broken) |
| tongs | FAILURE | gap에서 열 수 없음 |
| spoon | FAILURE | 곡면이라 바닥을 미끄러져 들어갈 수 없음 |
| towel | FAILURE | 매끈한 egg를 잡을 수 없음 |

#### One-Shot CA Tool Selection 제약
- `_check_ca_tool_grasp()`: 첫 GRASP 시 `_committed_tool` 확정
- 이후 다른 CA tool GRASP 시도 → "This tool is no longer available" 에러로 차단
- trial-and-error 방지 → CA 능력만 순수 측정

#### DONE 선언
- `Action: DONE[]` → Stage 3 종료

---

## 3. Camera 시스템 (3중 메커니즘)

### 3.1. _CameraHelper (기본)
- `CameraMixin` 래퍼 — `get_rgb()` → numpy (H,W,3) uint8 → PIL PNG 저장
- `_anchored_pos/ori` 기준으로 카메라 위치 결정
- `_tracking_object` 설정 시 해당 오브젝트를 바라보도록 자동 조정

### 3.2. NAVIGATE_TO 시 카메라 처리 (3단계 우선순위)

```
1. exploration_direct_camera 확인 → 있으면 _setup_direct_camera() 사용
2. 없으면 exploration_nav_targets + exploration_nav_tracking 조회
3. _teleport_to_face(nav_obj, tracking_obj) 호출
```

#### _teleport_to_face(target_obj, tracking_obj)
- 로봇을 target_obj에서 1m 떨어진 위치로 텔레포트
- XY 평면에서 target 방향 계산 → yaw = atan2(dy, dx) → quaternion
- `controller._anchored_pos/ori` 갱신 → CameraMixin이 자동으로 카메라 이동
- `controller._tracking_object = tracking_obj` → 카메라가 해당 오브젝트를 바라봄

#### _setup_direct_camera(robot_pos, cam_pos, cam_look_at)
- viewer_camera의 위치/방향을 **절대 좌표로 직접 지정**
- `_look_at_quat(eye, target)` 함수로 orientation 계산
- 10 render frame으로 안정화
- retrieve_egg_from_gap에서는 `exploration_direct_camera: {}` (비어있음) → 사용 안 함

#### exploration_nav_tracking (이 task의 핵심 카메라 설정)
```python
"exploration_nav_tracking": {
    "gap":            "fridge_dszchb_0",   # fridge+gap 전체가 보이도록
    "gap, low_angle": "egg_601",           # 바닥의 egg를 내려다보도록
}
```
- "gap"으로 navigate → fridge 방향 1m에서 fridge를 바라봄
- "gap, low_angle"로 navigate → fridge 방향 1m에서 egg를 내려다봄

### 3.3. LOOK_CLOSER 줌 시스템

```python
"exploration_look_targets": {
    "egg":                    "egg_601",
    "gap":                    "fridge_dszchb_0",
    "objects_on_countertop":  "countertop_kelzer_0",
}
"look_closer_focal_length": 50.0  # 기본값 (viewer 기본 18.0 → ~2.8x 줌)
```

`_capture_zoomed()` 구현:
1. `_settle_head_for_capture()` — CameraMixin 헤드 안정화
2. `viewer_camera.focalLength = 50.0` (줌)
3. 10 render frame
4. `get_obs()` → RGB 캡처
5. `viewer_camera.focalLength = 18.0` (원복)

### 3.4. Stage별 이미지 캡처 시점

| Stage | 캡처 함수 | 시점 |
|-------|----------|------|
| Stage 1 init | `_capture_image("stage1_init")` | 파이프라인 시작 |
| Stage 1 NAVIGATE_TO | `_capture_image()` 또는 `_capture_direct_camera()` | 텔레포트 후 |
| Stage 1 LOOK_CLOSER | `_capture_zoomed()` | 줌 적용 후 |
| Stage 1 TOUCH/PUSH/OPEN | 없음 (None 반환) | 텍스트만 |
| Stage 3 매 step | `_capture_image("stage3_step{N}_after")` | action 실행 후 |

### 3.5. 이미지 → LLM 전달 흐름

```python
# 단일 이미지
prompt = [("system", sys_prompt), ("user", text, image_path)]
# 복수 이미지 (Stage 2 데모)
messages = [("system", sys_prompt), ("user", text, current_img)]
for img in demo_images:
    messages.append(("user", "", img))
response = self.llm.generate(messages)
```

---

## 4. Mock LLM 응답 구조 (13개 response)

```
Stage 1 Exploration (7 responses):
  1. NAVIGATE_TO[gap]
  2. NAVIGATE_TO[gap, low_angle]
  3. TOUCH[gap_walls]
  4. PUSH[hand, gap]
  5. LOOK_CLOSER[egg]
  6. NAVIGATE_TO[countertop]
  7. DONE_EXPLORING[]

Probe 1 (1 response): 맥락 특성 요약

Stage 2 (1 response): 데모 관찰 소감

Probe 2 (1 response): 5개 데모 각각의 유사점/차이점

Tool Selection (1 response): 4항목 (spatula 선택)

Stage 3 (6 responses):
  1. NAVIGATE_TO[countertop_kelzer_0]
  2. GRASP[spatula_602]
  3. NAVIGATE_TO[fridge_dszchb_0]
  4. NEW_ACTION[SLIDE_UNDER, spatula_602, egg_601]
  5. PULL[spatula_602]
  6. PLACE_ON_TOP[countertop_kelzer_0]

Probe 3 (1 response): 적응 설명
```

---

## 5. Scene Template 생성 스크립트 핵심

- **base template**: cook_bacon template에서 시작 → 기존 task 오브젝트 제거 → 새 오브젝트 추가
- **INST_TO_NAME**: BDDL scope name ↔ scene object name 매핑 (11개)
- **NEW_OBJECTS**: 6개 (egg_601, spatula_602, tablefork_603, tongs_604, tablespoon_605, dishtowel_606)
  - 각각 category, model ID, scale, in_rooms 지정
- **NEW_OBJECT_STATES**: 초기 위치 (egg: gap 바닥, tools: countertop 위)
- **REPOSITION**: fridge와 cabinet의 위치를 조정하여 2.5cm gap 생성
  - fridge Z -12cm (다리를 바닥 아래로) + X 조정
  - cabinet Z -12cm + X +0.015 (4cm gap)

---

## 6. BDDL 정의

```
(:objects
    egg.n.02_1 - egg.n.02
    spatula.n.01_1 - spatula.n.01
    tablefork.n.01_1 - tablefork.n.01
    tongs.n.01_1 - tongs.n.01
    tablespoon.n.02_1 - tablespoon.n.02
    dishtowel.n.01_1 - dishtowel.n.01
    electric_refrigerator.n.01_1 - electric_refrigerator.n.01
    cabinet.n.01_1 - cabinet.n.01
    countertop.n.01_1 - countertop.n.01
    floor.n.01_1 - floor.n.01
    agent.n.01_1 - agent.n.01
)
(:init
    (ontop egg.n.02_1 floor.n.01_1)         # egg은 바닥 위
    (ontop spatula/fork/tongs/spoon/towel countertop.n.01_1)  # 도구들은 countertop 위
)
(:goal
    (ontop egg.n.02_1 countertop.n.01_1)    # egg이 countertop 위에 있으면 성공
)
```

---

## 7. Run Script (run_cats_agent.py) 핵심 흐름

1. `CATS_TASK_REGISTRY`에서 task_config 로드
2. LLM config 결정 (mock / gemini / bedrock)
3. `available_tasks.yaml`에서 scene_model 자동 결정
4. OmniGibson Environment 생성 (BehaviorTask)
5. `CATSPlanner` 생성 → `planner.run()` 실행
6. 결과 출력 (tool_selection_correct, committed_tool 등)

실행 예시:
```bash
# Mock
python -m omnigibson.examples.cats.run_cats_agent --model mock --task retrieve_egg_from_gap
# Gemini
python -m omnigibson.examples.cats.run_cats_agent --model gemini-2.5-pro --task retrieve_egg_from_gap
# YouTube 데모 오버라이드
python -m omnigibson.examples.cats.run_cats_agent --model gemini-2.5-pro --task retrieve_egg_from_gap --demo-urls URL1 URL2 URL3
```
