# Decorative Pattern CA Tasks — 장식적 패턴 기반 맥락 적응 태스크 설계
## "시각적 단서가 잘못된 행동을 유도하고, 실제 메커니즘은 다르다"는 구조의 CA 평가

---

## 1. 설계 철학: 왜 장식적 패턴인가?

### 1.1. 기존 CA 태스크의 한계

기존 CATS 태스크(retrieve_egg_from_gap, micro_glass_shard_pickup 등)는 **"여러 도구 중 어떤 것을 고를까?"**가 핵심 판단이었다. 이 구조의 문제:

- 정답 도구-태스크 조합(예: potato로 유리 파편 줍기)이 인터넷 상식으로 존재 → LLM이 데모 없이도 recall로 정답 도달
- 도구 선택이 binary(맞다/틀리다)라서 CA 측정의 해상도가 낮음
- 함정 도구의 부적합성이 물리적 속성 차이에만 의존 → LLM의 물리 상식으로 우회 가능

### 1.2. 장식적 패턴(Decorative Pattern) 접근

**핵심 아이디어:** 물체의 시각적 외관에 특정 action primitive를 강하게 연상시키는 패턴이 있지만, 실제 메커니즘은 다른 action primitive를 요구하는 상황을 설계한다.

이것이 CA를 더 정밀하게 측정하는 이유:
1. **시각적 유혹이 데모의 매력적 오답을 강화한다** — 데모를 본 에이전트가 시각 패턴과 일치하는 데모에 확신을 갖고 오답을 선택할 위험
2. **탐색이 필수가 된다** — 시각과 실제 메커니즘이 다르므로, 물리적 탐색 없이는 올바른 기법을 판별 불가
3. **파라미터 적응까지 측정 가능** — 기법 선택 후, 데모의 수치를 현재 인스턴스에 맞게 조정하는 능력까지 평가

### 1.3. 세 가지 보강 장치

모든 장식적 패턴 태스크에 다음 세 장치를 겹쳐서 적용한다:

| 장치 | 역할 | 막는 우회 경로 |
|---|---|---|
| **장치 1: 매력적 오답 유도** | 데모 중 시각 패턴과 가장 잘 매칭되는 데모가 오답 | 데모를 보고 시각적 매칭만으로 선택하는 경우 |
| **장치 2: 연속 파라미터 공간** | 기법 선택뿐 아니라 힘/각도/타이밍 등의 연속값 적응 요구 | 기법을 맞혀도 데모 수치를 그대로 복사하면 실패 |
| **장치 3: 물성 불일치** | 시각적 외관과 실제 물리 메커니즘이 다름 | 시각 기반 물리 추론으로 우회하는 경우 |

---

## 2. 기존 CATS 프레임워크와의 관계

### 2.1. 유지되는 것

- **3단계 구조**: Exploration → Demo Observation & Comparison → Adaptive Execution
- **Metacognitive Probe**: 각 단계 후 반성 질문
- **One-shot 제약**: 기법 선택 후 변경 불가
- **Exploration primitive 제한**: tool/technique 후보를 직접 시도 금지
- **데모 1회 시청**: Probe 0에서만 데모 영상 전달

### 2.2. 확장/변경되는 것

| 요소 | 기존 | 장식적 패턴 태스크 |
|---|---|---|
| 선택 대상 | 물리적 도구 (potato, sponge 등) | 조작 기법/technique (push-and-turn, slide 등) |
| 정답 구조 | `correct_tool: "potato"` (단일 값) | `correct_technique` + `correct_parameters` (범위) |
| 함정 메커니즘 | 도구의 물리적 속성 불일치 | 시각적 패턴이 잘못된 기법으로 유도 |
| 탐색 대상 | 환경 및 도구 후보의 물성 | 대상 물체(뚜껑, 문, 서랍)의 실제 메커니즘 |
| 성공 판정 | 도구 선택 binary + 실행 성공 | 기법 선택 + 파라미터 범위 내 + 실행 성공 (3단계) |
| 데모 구성 | 도구별 1개씩, cross-domain | 기법별 1개씩, 같은 도메인(가정환경)도 가능 |

### 2.3. 난이도 레벨 매핑

장식적 패턴 태스크는 기존 난이도 체계의 **Level 2.3 (Insight 기반 선택)**에 해당한다:
- 데모가 보여주는 기법의 핵심 원리를 추출해야 함
- 시각적 패턴(표면)과 실제 메커니즘(구조)의 분리가 필수
- 비자명한 적용이 요구됨 (나사산 홈이 보여도 돌리면 안 됨)

Level 2.4 확장 가능: 같은 집 안에서 여러 개의 용기/문/서랍을 연속으로 열되, 각각 다른 메커니즘인 경우.

### 2.4. 탐색/실행 분리 원칙 (Exploration–Execution Separation)

기존 CATS의 핵심 제약 — "Exploration 단계에서 tool 후보를 직접 사용 금지" — 을 장식적 패턴 태스크에 적용하면:

> **탐색에서는 물리적 속성(properties)만 발견할 수 있고, 정답 기법의 실행(solution)은 Stage 3에서만 가능해야 한다.**

#### "조합이 해법" 원칙

이 원칙이 자연스럽게 성립하려면, **모든 태스크의 정답이 2개 이상 동작의 조합**이어야 한다. 그러면 개별 동작은 탐색(속성 발견)이 되고 조합만이 해법이 된다.

| 태스크 | 개별 탐색 (속성) | 조합 실행 (해법) | 조합 유형 |
|---|---|---|---|
| A (Container) | PRESS → 스프링, TWIST → 걸림 | PRESS_AND_TWIST 동시 | 동시 결합 |
| B (Squeeze Drawer) | SQUEEZE → 클릭, PULL → 잠김 | SQUEEZE+PULL 동시 | 동시 결합 |
| C (Window) | TWIST[handle, 45°] → 스윙 발견, TWIST[135°] → 틸트 발견, PUSH[window] → 테이블 충돌 발견 | TWIST[handle, 135°] HOLD + PULL[window_top] 동시 | 모드 선택 + 동시 hold |
| D (Safety Sliding Door) | PRESS[lever] → 해제음, PUSH[door] → 잠김 | PRESS[lever] 후 3초 내 SLIDE | 순차 + 타이밍 |
| E (Magnetic Box) | PULL[lid, light] → 자력 감지 | 강한 PULL + 가장자리 위치 | 파라미터 적응 |
| F (Push-Turn-Pull Knob Drawer) | TWIST → 회전 불가(핀 차단), PRESS[center] → 클릭(서랍 미개방), PULL → 잠김 | PRESS[center] 유지 + TWIST + PULL 3단계 홀드 | 3-step sequential hold |
| G (Tilt-to-Release Bench) | PRESS[rear] → 앞 올라감, TOUCH → 래치 핀 | PRESS[rear] → 래치 해제 → LIFT[front] | 간접적 힘 전달 |

#### 조합 유형 분류

- **동시 결합** (A, B): 두 동작을 동시에 수행해야 성공
- **모드 선택 + 동시 hold** (C): 다중 모드 중 맥락에 적합한 모드를 선택하고, 스프링 복귀 핸들을 hold하면서 동작 수행
- **3-step sequential hold** (F): 3개 동작을 순차적으로 추가하며 이전 동작을 유지해야 성공 (동시 결합 + 순차 결합의 복합)
- **순차 + 타이밍** (D): 시간 제약 내 연속 수행
- **간접 전달** (G): 직접이 아닌 간접적 경로로 목표 달성
- **파라미터 적응** (E): 동작은 단순하지만 힘/위치 조정이 핵심

이 분류는 논문에서 "CA는 단일 동작 선택이 아니라, 동작 조합의 구성을 판단하는 능력"이라는 주장을 뒷받침한다.

---

## 3. 공통 task_config 구조 (Python dict)

기존 `TASK_CONFIG`를 확장하여 다음 필드를 추가한다:

```python
TASK_CONFIG = {
    # === 기존 필드 (유지) ===
    "task_name": "container_opening_push_turn",
    "level": "2.3",
    "instruction": "Open the container on the table and retrieve the item inside.",
    "ca_tool_names": [],  # 이 태스크에서는 물리적 도구 후보 없음 (기법 선택이므로)

    # === 장식적 패턴 태스크 신규 필드 ===

    # 기법 후보 목록 (데모와 1:1 대응)
    "technique_candidates": [
        "screw_turn",         # Demo 1: 나사식 회전
        "vacuum_seal_release", # Demo 2: 진공 밀봉 해제
        "push_and_turn",       # Demo 3: 아동 안전 push-and-turn
        "bayonet_quarter",     # Demo 4: 바요넷 1/4 회전
        "cork_rocking",        # Demo 5: 코르크 좌우 흔들기
    ],

    # 정답 기법
    "correct_technique": "push_and_turn",

    # 정답 파라미터 범위 (기법에 종속)
    "correct_parameters": {
        "downward_force_N": {"min": 2.5, "max": 4.5},
        "rotation_degrees": {"min": 100, "max": 140},
        "timing_delay_s": {"min": 0.2, "max": 0.6},
    },

    # 시각적 함정 기법 (시각 패턴이 이 기법으로 유도)
    "visual_trap_technique": "screw_turn",

    # 물성 불일치 설명 (평가용 메타데이터, 에이전트에게 미제공)
    "physical_mismatch": {
        "visual_cue": "나사산 모양의 세로 홈이 뚜껑에 분명하게 보임",
        "actual_mechanism": "장식적 홈, 실제는 push-and-turn 래치",
        "mismatch_type": "decorative_pattern",
    },

    # 기법별 실행 결과 매핑 (new_action_handlers 대체/확장)
    "technique_outcomes": {
        "screw_turn": {
            "success": False,
            "observation": "The lid rotates but does not rise. No threading engagement detected. At certain angles, internal catching is felt.",
            "physical_consequence": "no_change",  # 상태 변화 없음
        },
        "push_and_turn": {
            # 파라미터 범위에 따라 분기
            "param_conditions": [
                {
                    "condition": "downward_force_N in [2.5, 4.5] AND rotation_degrees in [100, 140]",
                    "success": True,
                    "observation": "The lid clicks, depresses, and rotates freely. The lid separates from the container.",
                    "physical_consequence": "lid_opened",
                },
                {
                    "condition": "downward_force_N > 6.0",
                    "success": False,
                    "observation": "Excessive force causes the internal latch mechanism to jam. The lid is now stuck.",
                    "physical_consequence": "mechanism_jammed",
                },
                {
                    "condition": "downward_force_N < 2.0",
                    "success": False,
                    "observation": "The lid barely depresses. The latch does not disengage. Rotation is still blocked.",
                    "physical_consequence": "no_change",
                },
            ],
        },
        "vacuum_seal_release": {
            "success": False,
            "observation": "No vacuum seal detected. Inserting a tool at the edge finds no gap or air resistance. This is not a vacuum-sealed container.",
            "physical_consequence": "no_change",
        },
        "bayonet_quarter": {
            "success": False,
            "observation": "Rotating exactly 90 degrees does not release the lid. No bayonet tabs detected internally.",
            "physical_consequence": "no_change",
        },
        "cork_rocking": {
            "success": False,
            "observation": "Rocking the lid side to side does not loosen it. The lid is rigid and does not flex. This is not a friction-fit closure.",
            "physical_consequence": "no_change",
        },
    },

    # === 탐색 피드백 (v2 raw 센서 데이터 형식) ===
    "exploration_feedbacks": {
        "TWIST[lid, counterclockwise]": (
            "=== Torque Sensor Data ===\n"
            "Applied torque: 2.1 Nm\n"
            "Lid angular displacement: 15 degrees\n"
            "Lid vertical displacement: 0.0 mm\n"
            "Resistance pattern: smooth rotation with periodic catch every ~60 degrees\n"
            "Note: No progressive vertical rise detected during rotation\n"
            "=== Internal Contact Sensor ===\n"
            "At 45-degree rotation: internal protrusion contact detected\n"
            "Contact force: 3.2 N (radial direction)"
        ),
        "PRESS[lid, downward]": (
            "=== Force-Displacement Sensor ===\n"
            "Applied force: 3.5 N\n"
            "Vertical displacement: 2.1 mm\n"
            "Spring constant (estimated): 1667 N/m\n"
            "Displacement at 2.0 N: 1.2 mm\n"
            "Displacement at 4.0 N: 2.4 mm (linear response)\n"
            "Max displacement before hard stop: 3.0 mm (at ~5.0 N)\n"
            "=== Release behavior ===\n"
            "Upon release: lid returns to original position (spring-loaded)"
        ),
        "PRESS_AND_TWIST[lid, down+counterclockwise]": (
            "=== Combined Sensor Data ===\n"
            "Downward force applied: 3.5 N\n"
            "Lid depressed: 2.1 mm\n"
            "Rotation attempted while depressed:\n"
            "  Angular displacement: continuous (no periodic catch)\n"
            "  Resistance: significantly reduced (0.3 Nm vs 2.1 Nm uncompressed)\n"
            "  Internal catch: NOT detected during depressed rotation\n"
            "Note: Rotation becomes free when lid is sufficiently depressed"
        ),
        "TOUCH[lid_surface]": (
            "=== Tactile Sensor Array (4x4, kPa) ===\n"
            "[[  0.0,  0.0,  0.0,  0.0],\n"
            " [  0.0, 12.3, 11.8,  0.0],\n"
            " [  0.0, 11.5, 12.1,  0.0],\n"
            " [  0.0,  0.0,  0.0,  0.0]]\n"
            "Surface temperature: 22.3°C\n"
            "Surface material: metallic, smooth finish\n"
            "=== Visual-Tactile Discrepancy ===\n"
            "Vertical grooves visible on surface: present (8 grooves, evenly spaced)\n"
            "Groove depth (tactile): 0.3 mm (shallow, decorative)\n"
            "Thread pitch detection: NONE (grooves do not follow helical pattern)"
        ),
        "PULL[lid, upward]": (
            "=== Force Sensor Data ===\n"
            "Applied upward force: 8.0 N\n"
            "Lid vertical displacement: 0.0 mm\n"
            "The lid does not separate from the container body.\n"
            "Internal locking mechanism engaged."
        ),
    },

    # === 데모 관련 ===
    "demo_image_paths": [
        # 각 기법별 데모 영상 경로 또는 YouTube URL
        # Demo 1~5 (technique_candidates와 순서 대응)
    ],
    "demo_labels": [],  # v2: 라벨 미제공

    # === 카메라/네비게이션 ===
    "exploration_nav_targets": {
        "container": "container_001",
        "container, close_up": "container_001",
        "table": "table_001",
    },
    "exploration_nav_tracking": {
        "container": "container_001",
        "container, close_up": "container_001",
    },
    "exploration_look_targets": {
        "lid": "container_001",
        "lid_grooves": "container_001",
    },

    # === Probe ===
    "probes": {
        "stage1": (
            "What did you discover about this container's opening mechanism? "
            "Did the physical properties match what you expected from the visual appearance? "
            "What specific sensor readings informed your understanding?"
        ),
        "stage3": (
            "Did you apply the technique exactly as shown in the demo, or did you modify any parameters? "
            "If you modified parameters, what observations led you to make those adjustments?"
        ),
    },

    # === 기존 호환 필드 ===
    "correct_tool": "push_and_turn",  # 기존 파싱 호환용 (correct_technique와 동일값)
    "new_action_handlers": {},  # technique_outcomes로 대체되지만 호환용 유지
}
```

---

## 4. 태스크 상세 설계

### 4.1. Task A: 용기 뚜껑 열기 (Container Opening)

#### 상황
주방 테이블 위에 뚜껑이 닫힌 용기가 있다. 내부 물품을 꺼내야 한다.

#### 물성 불일치
- **시각**: 뚜껑에 나사산 모양의 세로 홈이 분명하게 보임 → **screw-turn** 연상
- **실제**: 홈은 장식적 패턴. 내부 메커니즘은 **push-and-turn** (아동 안전 방식)

#### 데모 세트 (5개)

| Demo | 기법 | 영상 내용 | 역할 |
|---|---|---|---|
| 1 | screw_turn | 일반 병뚜껑을 반시계로 돌려서 열기 | **시각적 함정** (나사산 홈과 매칭) |
| 2 | vacuum_seal_release | 잼 병 뚜껑 가장자리에 나이프 삽입, 공기 유입 후 열기 | 부분 관련 (다른 메커니즘) |
| 3 | push_and_turn | 약병 뚜껑을 누르면서 돌려서 열기 | **정답** |
| 4 | bayonet_quarter | 카메라 렌즈 마운트를 90도 돌려서 분리 | Distractor |
| 5 | cork_rocking | 와인 코르크를 좌우로 흔들면서 빼기 | Distractor |

#### 탐색에서 발견해야 할 critical context features

| Feature | Primitive | 발견 내용 |
|---|---|---|
| 홈이 나사산이 아닌 장식임 | TOUCH[lid_surface] | groove depth 0.3mm (얕음), helical pattern 없음 |
| 회전 시 상승 없음 | TWIST[lid] | angular displacement 있지만 vertical displacement 0mm |
| 스프링 기반 래치 존재 | PRESS[lid] | 2mm 눌림, 스프링 저항, 릴리즈 시 복귀 |
| 눌린 상태에서 회전 자유로움 | PRESS_AND_TWIST[lid] | 저항 0.3Nm (비압축 시 2.1Nm 대비 대폭 감소) |

#### 파라미터 정답 범위

| 파라미터 | 정답 범위 | Demo 3 수치 | 과도 시 결과 |
|---|---|---|---|
| Downward force | 2.5~4.5 N | 5~8 N | >6N: 래치 잼 |
| Rotation | 100~140° | ~180° | >160°: 재잠금 |
| Timing delay | 0.2~0.6 s | ~0.2 s | 동시성 문제 없으면 범위 내 허용 |

#### 채점 (3단계)

| 단계 | 측정 | 배점 비중 |
|---|---|---|
| 1차: 기법 선택 | push_and_turn 선택 여부 | 50% |
| 2차: 파라미터 적응 | 3개 파라미터 모두 정답 범위 내 | 30% |
| 3차: 물리적 성공 | 뚜껑이 실제로 열렸는가 | 20% |

---

### 4.2. Task B: 쥐어짜서 여는 서랍 (Squeeze-Handle Drawer)

#### 상황
주방 서랍에서 도구를 꺼내야 한다. 서랍 전면에 D-handle 손잡이가 달려 있다.

#### 물성 불일치
- **시각**: 서랍에 일반적인 D-handle 손잡이 → **잡고 당기기** 연상
- **실제**: Squeeze-handle 방식. 손잡이를 서랍 면 쪽으로 **쥐어짜야(squeeze)** 내부 캠 래치가 해제되고, 그 상태에서 **동시에 당겨야** 열린다. 일부 현대 주방 캐비닛과 어린이 안전 캐비닛에 실제 존재하는 메커니즘 (브레이크 레버와 유사한 작동).

#### 데모 세트 (4개)

| Demo | 기법 | 영상 내용 | 역할 |
|---|---|---|---|
| 1 | handle_pull | 일반 서랍 손잡이를 잡고 앞으로 당겨서 열기 | **시각적 함정** |
| 2 | squeeze_and_pull | 손잡이를 쥐어짜면서 당겨서 열기 (캠 래치 해제 + 당기기 동시) | **정답** |
| 3 | push_to_open | 서랍 면을 눌러서 스프링 해제 | Distractor |
| 4 | lift_and_pull | 서랍을 약간 들어올리면서 당겨서 안전장치 해제 후 열기 | 부분 관련 |

#### 탐색에서 발견해야 할 critical context features

| Feature | Primitive | 발견 내용 |
|---|---|---|
| 당기면 안 열림 | PULL[handle] | displacement 0mm, 내부 걸림 감지 (래치 잠김) |
| 손잡이에 안쪽 유격 있음 | SQUEEZE[handle] | 클릭 감지, 하지만 서랍은 안 열림 (squeeze만으로 불충분) |
| 손잡이 촉각 | TOUCH[handle] | D-handle, 안쪽 방향으로 약간의 유격 감지 (property) |
| 수평 레일 존재 | TOUCH[drawer_frame] | 상하단 수평 레일 감지, 경첩 없음 |

**개별 탐색은 속성만 발견:** PULL → 잠김 상태, SQUEEZE → 클릭(하지만 열리지 않음), TOUCH → 유격 감지
**정답은 조합:** SQUEEZE+PULL 동시 수행 (동시 결합 유형)

#### 파라미터 정답 범위

| 파라미터 | 정답 범위 | Demo 2 수치 | 주의사항 |
|---|---|---|---|
| Squeeze force | 3~8 N | ~5 N | <2N: 캠 래치 미해제, >12N: 손잡이 손상 |
| Pull force (while squeezing) | 5~15 N | ~8 N | squeeze 없이 pull → 잠김 |
| Simultaneity | squeeze 유지 중 pull | 동시 | squeeze 해제 후 pull → 래치 재잠금 |

#### 탐색 피드백 (raw 센서 데이터)

```python
"exploration_feedbacks": {
    "PULL[handle]": (
        "=== Force Sensor Data ===\n"
        "Applied pull force: 12.0 N\n"
        "Drawer displacement: 0.0 mm\n"
        "Handle displacement: 0.0 mm (outward direction)\n"
        "Internal mechanism status: LOCKED\n"
        "Note: rigid resistance felt, internal latch engaged"
    ),
    "SQUEEZE[handle]": (
        "=== Force Sensor Data ===\n"
        "Applied inward force (handle → drawer face): 5.0 N\n"
        "Handle inward displacement: 8.2 mm\n"
        "At 6.5 mm: audible click detected\n"
        "Post-click: handle holds in depressed position\n"
        "Drawer displacement: 0.0 mm (drawer did NOT open)\n"
        "=== Release behavior ===\n"
        "Upon release: handle returns to original position, click resets"
    ),
    "TOUCH[handle]": (
        "=== Tactile Sensor Array (4x4, kPa) ===\n"
        "Standard D-handle shape detected\n"
        "Material: brushed metal, cylindrical grip\n"
        "Handle-to-face connection: pivoted, inward play ~8 mm\n"
        "Grip circumference: ~95 mm\n"
        "Spring resistance felt when pressing handle toward face"
    ),
    "TOUCH[drawer_frame]": (
        "=== Tactile Sensor Array ===\n"
        "Frame material: solid wood\n"
        "No hinges detected on sides\n"
        "Top/bottom edges: linear rail guides detected (2 rails)\n"
        "Rail orientation: horizontal (front-to-back)"
    ),
    "TOUCH[drawer_face]": (
        "=== Tactile Sensor Array (4x4, kPa) ===\n"
        "Surface: flat panel, laminated wood finish\n"
        "Contact stiffness: high (no compliance)\n"
        "Temperature: 22.1°C"
    ),
}
```

---

### 4.3. Task C: 틸트앤턴 창문 (Tilt-and-Turn Window)

#### 상황
침실 창문을 환기를 위해 열어야 한다. 창문 앞 ~0.65m에 커피 테이블이 있고, 위에 화분과 꽃병이 놓여 있어서 풀 스윙으로 열면 물건을 쓸어버린다.

#### 물성 불일치
- **시각**: 일반적인 레버 손잡이 하나 → 손잡이를 돌리고 **밀거나 당기면** 열릴 것으로 예상
- **실제**: 비표준 다중 모드 창문. 손잡이 각도에 따라 완전히 다른 모드 작동. **45°** = 옆으로 풀 스윙 (측면 경첩), **135°** = 위쪽만 안쪽으로 기울어짐(tilt, 상단 경첩). 핸들은 **스프링 복귀식**으로 ~3초 내 0°(잠금)로 돌아감.

**비표준 각도 사용 이유:** 표준 유럽식 tilt-and-turn (90°=swing, 180°=tilt) 지식을 LLM이 recall하는 것을 방지. 45°/135° 비표준 매핑 + 표준 대비 역전된 모드 할당.

#### 데모 세트 (4개)

| Demo | 기법 | 영상 내용 | 역할 |
|---|---|---|---|
| 1 | swing_open | 빈 방의 창문. 핸들을 돌려 창을 활짝 열어 환기. 장애물 없음 | **맥락적 함정** (기법은 작동하지만 환경이 부적합) |
| 2 | partial_recline | **리클라이닝 의자** (벽 앞). 두 단계 레버 — 풀 리클라인은 벽에 부딪힘 → 부분 리클라인 선택 (cross-domain) | **정답** (다중 모드 + 환경 제약 원리) |
| 3 | sliding_push | 슬라이딩 창문을 옆으로 밀어서 열기 | Distractor |
| 4 | crank_open | 크랭크 핸들을 돌려서 여닫이 창문 열기 | Distractor |

#### 탐색에서 발견해야 할 critical context features

| Feature | Primitive | 발견 내용 |
|---|---|---|
| 테이블+물건 존재 (모호) | NAVIGATE_TO[window] | 0.65m에 물체 감지, 상면에 3개 물체 — 충돌 여부는 미명시 |
| 핸들 45° 첫 클릭 | TWIST[handle, 45] | 45°에서 detent, 스프링 장력 1.2N |
| 핸들 135° 두 번째 클릭 | TWIST[handle, 135] | 135°에서 detent, 다른 음향, hard stop |
| **45°에서 스윙 → 충돌!** | PUSH[window] | 스윙 시작, **32°에서 0.65m 물체와 contact** — 여기서 맥락 제약 발견 |
| 135°에서 틸트 → 안전 | PULL[window_top] | 상단만 85mm 기울어짐, 테이블과 충돌 없음. 릴리즈 시 스프링 복귀 2.8s |

**NAVIGATE_TO는 테이블 존재만 보여주고, PUSH[window]로 탐색해야 충돌을 확인 → embodied exploration 필수**

#### 파라미터 정답 범위

| 파라미터 | 정답 범위 | Demo 2 수치 | 주의사항 |
|---|---|---|---|
| Handle rotation | 130~140° (second detent) | 135° | 40~50°: 스윙 모드 (테이블 충돌!), 중간: 스프링 복귀 |
| hold_handle_while_pull | True | True | False: 스프링 복귀 ~3초 → 재잠금 |
| Pull force | 2~5 N | ~3.5 N | >8N: 경첩 손상 |
| Target tilt angle | 10~25° | ~15° | >30°: restrictor arm 한계 |

#### 맥락 제약이 데모 선택을 결정하는 구조

이 태스크의 핵심은 **Demo 1도 Demo 2도 물리적으로 "작동"하지만, 현재 맥락(테이블 위 물건)이 Demo 1을 기각하게 만든다**는 점이다. 기존 태스크(F, G)에서 함정은 "물리적으로 안 되는 기법"이었지만, 여기서 함정은 **"물리적으로 되지만 맥락적으로 부적합한 기법"**이다.

이것은 CA 정의 — "상황의 어떤 특징이 다른 상황과 구별되게 만드는지 식별" — 에 가장 정확하게 부합한다. 테이블의 존재가 Demo 1의 적용 가능성을 제한한다.

#### LLM recall 차단 장치 (3중)

1. **비표준 각도**: 45°/135° (표준 90°/180° 대신) — 기존 tilt-and-turn 지식 적용 불가
2. **탐색 필수 충돌 발견**: NAVIGATE_TO에서는 충돌 미명시, PUSH[window]로 직접 시도해야 확인
3. **스프링 복귀 핸들**: hold 필수 — 단순 "모드 선택 후 동작"이 아닌 동시 수행 요구

#### 조합 구조 (모드 선택 + 동시 hold)

F, G와 동등한 조합 깊이를 확보:
- **F**: PRESS(hold) → TWIST(hold) → PULL (3-step sequential hold)
- **G**: PRESS[rear](hold) → LIFT[front] (동시 hold)
- **C**: TWIST[handle, 135°](hold) → PULL[window_top] (동시 hold + 모드 판단)

---

### 4.4. Task D: 안전 잠금 슬라이딩 도어 (Safety-Release Sliding Door)

#### 상황
방문을 열고 다른 방으로 이동해야 한다. 문에 D-handle이 달려 있고, 문 하단 프레임에 작은 풋 레버가 있다.

#### 물성 불일치
- **시각**: D-handle → **당기거나 밀어서** 여닫이로 열릴 것으로 예상. 풋 레버의 존재를 인지하더라도 문과의 연관성을 파악하기 어려움.
- **실제**: 어린이 안전 슬라이딩 도어 잠금장치. 풋 레버를 밟거나 누르면 내부 래치가 **3초간 해제**되고, 그 시간 내에 문을 옆으로 밀어야 열린다.

#### 데모 세트 (4개)

| Demo | 기법 | 영상 내용 | 역할 |
|---|---|---|---|
| 1 | pull_swing | 일반 문 손잡이를 잡고 앞으로 당겨서 여닫이로 열기 | **시각적 함정** |
| 2 | press_lever_then_slide | 하단 레버를 밟고 3초 내에 문을 옆으로 밀어서 열기 | **정답** |
| 3 | push_swing | 문을 앞으로 밀어서 열기 | Distractor |
| 4 | pocket_fold | 접이식 문을 접어서 열기 | Distractor |

#### 탐색에서 발견해야 할 critical context features

| Feature | Primitive | 발견 내용 |
|---|---|---|
| 당겨도 안 열림 | PULL[handle] | displacement 0mm, 잠금 상태 |
| 밀어도 안 열림 | PUSH[door] | displacement 0mm (전후 방향 + 좌우 방향 모두) |
| 풋 레버 존재 | NAVIGATE_TO[door, low_angle] | 하단 프레임에 작은 레버 시각적 발견 |
| 레버 누르면 무언가 해제 | PRESS[floor_lever] | 클릭, 문 프레임에서 기계적 움직임 감지, ~3초 후 복귀 |
| 경첩 없음 | TOUCH[door_frame] | 경첩/피벗 없음, 수평 레일 감지 |

**개별 탐색은 속성만 발견:** PUSH[door] → 잠김, PRESS[lever] → 3초간 무언가 해제(하지만 문은 안 열림)
**정답은 조합:** PRESS[lever] 후 3초 내에 SLIDE[door] (순차 + 타이밍 유형)

#### 파라미터 정답 범위

| 파라미터 | 정답 범위 | Demo 2 수치 | 주의사항 |
|---|---|---|---|
| Lever press force | 3~8 N | ~5 N | <2N: 래치 미해제 |
| Slide timing | lever 해제 후 3초 이내 | ~1초 | >3초: 래치 재잠금 |
| Slide direction | left (인스턴스 종속) | left | 반대 방향: 이동 불가 |
| Slide force | 5~15 N | ~8 N | <3N: 마찰 미극복 |

#### 탐색 피드백 (raw 센서 데이터)

```python
"exploration_feedbacks": {
    "PULL[handle]": (
        "=== Force Sensor Data ===\n"
        "Applied pull force: 15.0 N\n"
        "Door displacement: 0.0 mm\n"
        "No hinge or pivot detected.\n"
        "Internal mechanism status: LOCKED"
    ),
    "PUSH[door]": (
        "=== Force Sensor Data ===\n"
        "Applied force: 12.0 N (perpendicular to door surface)\n"
        "Door displacement: 0.0 mm\n"
        "Applied force: 12.0 N (lateral direction)\n"
        "Door displacement: 0.0 mm\n"
        "Note: door is locked in all directions"
    ),
    "PRESS[floor_lever]": (
        "=== Force-Displacement Sensor ===\n"
        "Applied downward force: 5.0 N\n"
        "Lever displacement: 12 mm (downward)\n"
        "At 10 mm: click detected\n"
        "Brief mechanical engagement sound from door frame area\n"
        "Lever returns to original position after ~3 s"
    ),
    "TOUCH[door_frame]": (
        "=== Tactile Sensor Array ===\n"
        "Frame material: aluminum\n"
        "No hinges detected\n"
        "Top/bottom edges: horizontal rail guides detected (2 rails)\n"
        "Small lever mechanism at bottom frame (foot-operated)"
    ),
    "TOUCH[handle]": (
        "=== Tactile Sensor Array (4x4, kPa) ===\n"
        "Standard D-handle shape\n"
        "Material: brushed metal\n"
        "Handle-to-door connection: rigid, no play\n"
        "Grip circumference: ~95 mm"
    ),
}
```

---

### 4.5. Task E: 자기 잠금 뚜껑 (Magnetic Closure with Fake Latch)

#### 상황
테이블 위 보석함을 열어서 내부 물품을 꺼내야 한다.

#### 물성 불일치
- **시각**: 상자 전면에 금속 래치(걸쇠)가 달려 있음 → **래치를 올려서** 해제할 것으로 예상
- **실제**: 래치는 장식(고정, 움직이지 않음). 실제 잠금은 **자석**. 뚜껑을 충분한 힘으로 들어올리면 자력을 이기고 열림.

#### 데모 세트 (4개)

| Demo | 기법 | 영상 내용 | 역할 |
|---|---|---|---|
| 1 | latch_flip | 금속 래치를 위로 올려서 해제 후 뚜껑 열기 | **시각적 함정** |
| 2 | magnetic_lift | 자석 잠금 상자의 뚜껑을 수직으로 들어올려서 열기 | **정답** |
| 3 | clasp_slide | 슬라이드식 걸쇠를 옆으로 밀어서 해제 후 열기 | Distractor |
| 4 | combination_dial | 다이얼을 특정 숫자에 맞춰서 잠금 해제 | Distractor |

#### 탐색에서 발견해야 할 critical context features

| Feature | Primitive | 발견 내용 |
|---|---|---|
| 래치가 안 움직임 | PUSH[latch, upward] | displacement 0mm, 완전 고정 |
| 뚜껑에 자기력 | PULL[lid, slight] | 미세 들림 후 자력으로 다시 닫힘, 인력 감지 |
| 자력 세기 추정 | PULL[lid, measured] | 분리에 필요한 힘 ~4N, 거리에 따라 급감 |
| 경첩 위치 | TOUCH[box_back] | 후면에 작은 경첩 감지 (뚜껑 열림 방향 결정) |

#### 파라미터 정답 범위

| 파라미터 | 정답 범위 | Demo 2 수치 | 주의사항 |
|---|---|---|---|
| Lift force | 4~8 N | ~5 N | <3N: 자력 미극복, >12N: 내용물 튀어나감 |
| Lift position | 자석 반대쪽 가장자리 | 가장자리 | 자석 바로 위: 최대 저항, 가장자리: 지렛대 효과 |
| Lift speed | 느리게 (1~3 cm/s) | ~2 cm/s | 빠르게: 내용물 흔들림 |

---

### 4.6. Task F: 눌러-돌려-당기기 서랍 (Push-Turn-Pull Knob Drawer)

#### 상황
주방 캐비닛 서랍에 둥근 노브(knob) 손잡이가 달려 있다. 서랍을 열어 내부 스크루드라이버를 꺼내 조리대 위에 놓아야 한다.

#### 물성 불일치
- **시각**: 둥근 노브 → **잡고 당기기** 연상
- **실제**: 3-step sequential hold 메커니즘. 노브 중앙에 숨겨진 버튼이 있으며, 이 버튼을 **누른 상태를 유지하면서 시계방향 90° 회전** → **회전 상태를 유지하면서 당기기** 해야 열린다. 가스 레인지 점화 노브(push-and-turn)와 유사한 원리이지만 pull까지 추가된 3단계.

#### 데모 세트 (4개)

| Demo | 기법 | 영상 내용 | 역할 |
|---|---|---|---|
| 1 | knob_pull | 서류 캐비닛 노브를 잡고 당기지만 열리지 않음 | **시각적 함정** (당기기만으로는 실패) |
| 2 | press_turn_ignite | 가스 레인지 노브를 안쪽으로 누르고 유지하면서 왼쪽으로 돌려 점화 | **정답** (press+turn 원리 — cross-domain) |
| 3 | push_to_open | 주방 캐비닛 패널을 밀어 클릭 후 열기 | Distractor |
| 4 | twist_then_pull | 책상 서랍 노브를 90° 돌린 후 당겨서 열기 (버튼 없이) | **교묘한 distractor** (button 단계 누락) |

#### 탐색에서 발견해야 할 critical context features

| Feature | Primitive | 발견 내용 |
|---|---|---|
| 당기면 안 열림 | PULL[knob] | displacement 0mm, 잠금 상태 |
| 노브 회전 불가 | TWIST[knob, clockwise] | **0° — 내부 핀이 회전 차단** |
| 중앙 버튼 존재 | TOUCH[knob_center] | D=7.8mm 오목 영역, compliance 0.10 mm/N |
| 버튼 누르면 클릭 | PRESS[knob_center] | 0.5mm 눌림, 릴리즈 시 복귀, 서랍 미개방 |
| 수평 레일 | TOUCH[drawer_frame] | U-shaped 채널 2개, 수평 방향 |

**개별 탐색은 속성만 발견:** PULL → 잠김, TWIST → 회전 불가(핀 차단), PRESS[center] → 클릭(서랍 미개방)
**정답은 조합:** PRESS[center] 유지 + TWIST 유지 + PULL (3-step sequential hold 유형)

**핵심 CA 판단:** "twist가 막혀 있고, center 버튼을 누르면 클릭이 나지만 서랍은 안 열림 → 버튼이 회전 잠금을 해제하는 것인가?" 데모 2(가스 레인지)에서 "누르면서 돌리기"라는 **동시 수행 원리**를 추출하고, 추가로 "회전 유지 + 당기기"까지 확장해야 함. 데모 4(단순 twist+pull)는 버튼 단계가 빠져 있어 함정.

#### 파라미터 정답 범위

| 파라미터 | 정답 범위 | Demo 2 수치 | 주의사항 |
|---|---|---|---|
| press_center | True | True | 미누름 → 회전 불가 |
| hold_press_while_twist | True | True | 릴리즈 → 핀 재잠금 |
| Rotation angle | 85~95° (시계방향) | ~90° | 반시계: 5°에서 hard stop |
| hold_twist_while_pull | True | True | 릴리즈 → 스프링 복귀 (~2초 내 재잠금) |
| Pull force | 5~15 N | ~10 N | <3N: 미이동, >20N: 과도 |

#### 탐색 피드백 (raw 센서 데이터)

```python
"exploration_feedbacks": {
    "NAVIGATE_TO[drawer]": (
        "=== Spatial Scan (depth + RGB point cloud) ===\n"
        "Object: rectangular unit against wall\n"
        "Bounding box: 0.69 x 2.35 x 0.81 m (W x D x H)\n"
        "Material: wood, painted white\n"
        "=== Target panel (top-left, 0.30 x 0.25 m) ===\n"
        "  Cylindrical protrusion at center: D=35 mm, H=20 mm\n"
        "    Material: brushed metal\n"
        "    Protrusion from face: 22 mm\n"
        "  Seam around panel: 3 mm gap, uniform"
    ),
    "NAVIGATE_TO[drawer, close_up]": (
        "=== Close-Range Scan (30 cm distance) ===\n"
        "=== Cylindrical protrusion detail ===\n"
        "  Outer ring: D=35.2 mm, H=19.8 mm, brushed metal\n"
        "  Center shaft: D=6 mm, into panel face\n"
        "  Center face region: D=8 mm\n"
        "    Recess depth: 0.5 mm below outer ring surface\n"
        "    Surface texture: smoother than outer ring\n"
        "=== Panel face ===\n"
        "  Material: painted MDF, smooth\n"
        "  Seam: 3.0 mm gap to frame, uniform all sides"
    ),
    "PULL[knob]": (
        "=== Force Sensor Data ===\n"
        "Applied force: 12.0 N (outward)\n"
        "Displacement (knob): 0.0 mm\n"
        "Displacement (panel): 0.0 mm\n"
        "Reaction force: 12.0 N (equal to applied)"
    ),
    "TWIST[knob, clockwise]": (
        "=== Torque Sensor Data ===\n"
        "Applied torque: 1.5 Nm (clockwise)\n"
        "Angular displacement: 0 degrees\n"
        "Reaction torque: 1.5 Nm (equal to applied)\n"
        "=== Accelerometer ===\n"
        "No transient events detected\n"
        "Background noise: 0.04 m/s^2"
    ),
    "TWIST[knob, counterclockwise]": (
        "=== Torque Sensor Data ===\n"
        "Applied torque: 1.5 Nm (counterclockwise)\n"
        "Angular displacement: 0 degrees\n"
        "Reaction torque: 1.5 Nm (equal to applied)\n"
        "=== Accelerometer ===\n"
        "No transient events detected"
    ),
    "PRESS[knob_center]": (
        "=== Force-Displacement Sensor ===\n"
        "Applied force: 5.0 N (inward, on D=8 mm center region)\n"
        "Center displacement: 0.5 mm (inward)\n"
        "Outer ring displacement: 0.0 mm\n"
        "=== Accelerometer ===\n"
        "No transient events detected\n"
        "Background noise: 0.04 m/s^2\n"
        "=== Release (force removed) ===\n"
        "Center returns to 0.0 mm within 0.4 s\n"
        "Panel displacement: 0.0 mm"
    ),
    "TOUCH[knob]": (
        "=== Tactile Sensor Array (4x4, kPa) ===\n"
        "Shape: cylindrical, D=35 mm\n"
        "Material: brushed metal, circumferential grain\n"
        "Rotational play: 0 degrees\n"
        "Axial play: 0.0 mm\n"
        "Temperature: 22.0 C\n"
        "Center region (D~8 mm): recess 0.5 mm, different texture"
    ),
    "TOUCH[knob_center]": (
        "=== Tactile Sensor Array (1x1, kPa) ===\n"
        "Contact area: circular, D=7.8 mm\n"
        "Surface: smooth metal, recessed 0.5 mm\n"
        "Compliance: 0.10 mm/N (inward)\n"
        "Material: brushed metal (same as outer ring)"
    ),
    "TOUCH[drawer_frame]": (
        "=== Tactile Sensor Array ===\n"
        "Frame material: solid wood\n"
        "Top/bottom edges: 2 horizontal channels detected\n"
        "  Channel profile: U-shaped, width 12 mm, depth 5 mm\n"
        "  Orientation: front-to-back\n"
        "  Surface: smooth, low friction coefficient"
    ),
}
```

---

### 4.7. Task G: 기울여서 여는 수납 벤치 (Tilt-to-Release Storage Bench)

#### 상황
거실의 cedar chest(수납 벤치)를 열어서 내부 목걸이를 꺼내야 한다.

#### 물성 불일치
- **시각**: 전면에 스크롤 무늬 금속 판(장식 래치)이 보임 → **래치를 올려서 열기** 연상. 뒤에 경첩이 보임 → **앞을 들어올리기** 연상.
- **실제**: 금속 판은 장식(용접 고정, 0mm gap). 경첩은 실재하지만, 뚜껑 앞쪽 밑면에 숨겨진 **자중 래치 핀(gravity latch pin, D=5mm, L=8mm)**이 있어서 바로 들어올릴 수 없다. 뚜껑의 **뒤쪽 끝을 아래로 눌러서**(tilt) 앞쪽이 올라오게 하면, 자중 래치 핀이 중력으로 떨어져 해제된다. 그 상태를 유지하면서 앞쪽을 들어올리면 열린다. 일부 빈티지 수납 벤치와 피아노 벤치에 실제 존재하는 메커니즘.

#### 데모 세트 (4개)

| Demo | 기법 | 영상 내용 | 역할 |
|---|---|---|---|
| 1 | latch_flip_and_lift | 금속 공구함의 스프링 걸쇠를 엄지로 올려서 뚜껑 열기 | **시각적 함정** |
| 2 | see_saw_leverage | 놀이터 시소 — 한쪽 끝을 밟으면 반대쪽이 올라감 (cross-domain) | **정답** (간접 전달 원리) |
| 3 | slide_forward | 나무 장난감 상자의 뚜껑을 홈을 따라 앞으로 밀어서 열기 | Distractor |
| 4 | full_lift | 선물 상자의 뚜껑을 양손으로 수직 분리 | Distractor |

#### 탐색에서 발견해야 할 critical context features

| Feature | Primitive | 발견 내용 |
|---|---|---|
| 앞을 들어올리면 걸림 | LIFT[lid, front] | 안 열림, 앞쪽에 걸림 감지 (래치 존재) |
| 래치가 안 움직임 | PUSH[latch, upward] | displacement 0mm, 고정 (장식) |
| 뒤를 누르면 피벗 동작 | PRESS[lid, rear_end] | rear -3.2mm, front +0.5mm, 1180Hz transient event (래치 핀 클리어 소리), 릴리즈 시 복귀 + 재클릭 |
| 중앙 누르면 효과 없음 | PRESS[lid, center] | 0.4mm 미세 변형, 피벗 없음 (대조군) |
| 앞 밑면에 래치 핀 | TOUCH[lid_front_edge] | 밑면에 금속 원통형 돌출물 (D=5.1mm, L=7.8mm), 수직 하향, slight vertical play |
| 경첩 존재 | TOUCH[hinge] | 후면 steel brackets 2개, 300mm 간격, 회전 저항 0.12 Nm, 110° 범위 |

**개별 탐색은 속성만 발견:** LIFT → 걸림, PRESS[rear] → 피벗(앞 올라감), TOUCH → 래치 핀 감지
**정답은 조합:** PRESS[rear] → 자중 래치 해제 → LIFT[front] (간접적 힘 전달 유형)

**3단계 인과 체인:** "뒤를 누름 → 앞이 올라감 → 래치 핀이 중력으로 빠짐 → 잠금 해제"
이 체인을 데모에서 관찰하고 현재 상황에 매핑해야 하며, 1:1 역산이 불가능하다.

#### 파라미터 정답 범위

| 파라미터 | 정답 범위 | Demo 2 수치 | 주의사항 |
|---|---|---|---|
| Rear press force | 최적 8~20 N (허용 5~25 N) | ~12 N | <5N: 래치 핀 미클리어, >25N: 경첩 손상 |
| Press position | "rear" 포함 (뒤쪽 끝) | 뒤쪽 끝 | 중앙/앞: 피벗 효과 불충분 |
| hold_while_lift | True (rear press 유지 중 lift) | 동시 | False: rear 릴리즈 → 핀 중력 복귀 → 재잠금 |
| Front lift force | 최적 3~15 N (허용 2~20 N) | ~8 N | <2N: 미이동, >20N: 경첩 스트레스 |

#### 탐색 피드백 (raw 센서 데이터)

```python
"exploration_feedbacks": {
    "NAVIGATE_TO[chest]": (
        "=== Spatial Scan (depth + RGB point cloud) ===\n"
        "Object detected: rectangular solid against wall\n"
        "Bounding box: 0.40 x 0.53 x 0.26 m (W x D x H)\n"
        "Material: wood (cedar), dark brown finish\n"
        "=== Front face ===\n"
        "  Metal plate: center, 85 x 40 x 4 mm, scroll/ornamental, oxidized iron\n"
        "  Mounting: flush to surface, no visible gap or hinge\n"
        "=== Top surface (lid) ===\n"
        "  Seam: 2 mm gap along front, left, right edges (no seam at rear)\n"
        "=== Rear edge ===\n"
        "  Two steel brackets, zinc-plated, spacing 300 mm"
    ),
    "LIFT[lid, front]": (
        "=== Force-Displacement Sensor ===\n"
        "Applied force: 15.0 N (upward, front edge)\n"
        "Displacement Z (front): 0.0 mm\n"
        "Displacement Z (rear): 0.0 mm\n"
        "Strain distribution: front 0.92, center 0.31, rear 0.04\n"
        "Net movement: none"
    ),
    "PUSH[latch, upward]": (
        "=== Force Sensor Data ===\n"
        "Applied force: 8.0 N (upward on metal plate)\n"
        "Displacement: 0.0 mm\n"
        "Stiffness: > 10000 N/m (rigid connection)\n"
        "Joint detection: none (welded to substrate)"
    ),
    "PRESS[lid, rear_end]": (
        "=== Force-Displacement Sensor ===\n"
        "Applied force: 12.0 N (downward, rear quadrant)\n"
        "Displacement Z (rear): -3.2 mm\n"
        "Displacement Z (center): -0.8 mm\n"
        "Displacement Z (front): +0.5 mm\n"
        "Stiffness (rear): 3750 N/m\n"
        "=== Accelerometer (lid-mounted, 3-axis) ===\n"
        "Transient event #1 at t=0.42 s:\n"
        "  Peak acceleration: 2.3 m/s^2\n"
        "  Dominant frequency: 1180 Hz\n"
        "  Duration: 4.2 ms\n"
        "=== Release (force removed) ===\n"
        "Return time to Z=0: 0.15 s\n"
        "Transient event #2 at t=0.58 s:\n"
        "  Peak acceleration: 2.1 m/s^2\n"
        "  Dominant frequency: 1210 Hz"
    ),
    "PRESS[lid, center]": (
        "=== Force-Displacement Sensor ===\n"
        "Applied force: 12.0 N (downward, center)\n"
        "Displacement Z: -0.4 mm (center only)\n"
        "Stiffness (center): 30000 N/m\n"
        "Accelerometer: 0.8 m/s^2, 980 Hz, 1.5 ms (weak)"
    ),
    "TOUCH[lid_front_edge]": (
        "=== Tactile Sensor Array ===\n"
        "Upper: uniform wood grain, 2.0 kPa\n"
        "=== Underside probe (fingertip) ===\n"
        "Geometry: cylindrical protrusion, D=5.1 mm, L=7.8 mm\n"
        "Orientation: vertical (pointing downward)\n"
        "Material: metal\n"
        "Mobility: slight vertical play under lateral force"
    ),
    "TOUCH[hinge]": (
        "=== Tactile Sensor Array ===\n"
        "Count: 2 brackets, spacing 300 mm\n"
        "Material: steel, zinc-plated\n"
        "Profile: continuous strip, width 25 mm\n"
        "Rotational resistance: 0.12 Nm (low)\n"
        "Rotational range: ~110 degrees"
    ),
    "TOUCH[latch]": (
        "=== Tactile Sensor Array ===\n"
        "Material: ferrous metal, oxidized, Ra 12.5 um\n"
        "Geometry: scroll-shaped plate, 85 x 40 x 4 mm\n"
        "Joint detection: none\n"
        "Gap to substrate: 0.0 mm\n"
        "Weld points: 4 (corners)"
    ),
}
```

---

## 5. 평가 구조

### 5.1. 4가지 실험 조건 (모든 태스크 공통)

| 조건 | 데모 | 탐색 | 측정 대상 |
|---|---|---|---|
| A: Full Pipeline | ✅ | 에이전트 직접 | 전체 CA 능력 |
| B: Oracle Exploration | ✅ | 시스템이 물성 정보 텍스트 제공 | 순수 CA 추론 (탐색 능력 분리) |
| C: No-Demo | ❌ | 에이전트 직접 | 데모 기여도 검증용 baseline |
| D: No-Demo + Oracle | ❌ | 시스템이 물성 정보 텍스트 제공 | LLM 사전지식만으로 풀리는 정도 |

### 5.2. 측정 지표

**1차 지표 — 기법 선택 정확도 (Technique Selection Accuracy):**
- 올바른 기법(technique)을 선택했는가 (binary)
- 시각적 함정 기법을 선택하지 않았는가 (함정 회피율)

**2차 지표 — 파라미터 적응 정확도 (Parameter Adaptation Accuracy):**
- 각 파라미터가 정답 범위 내인가 (파라미터별 binary → 평균)
- 데모 수치와의 차이 방향이 올바른가 (예: 데모 8N → 현재 3.5N으로 줄임 = 올바른 방향)

**3차 지표 — 물리적 성공률 (Physical Success Rate):**
- 태스크 목표 달성 여부 (뚜껑 열림, 서랍 열림, 문 열림 등)

**CA Delta:**
- `CA_technique = Accuracy(A) - Accuracy(C)` → 기법 선택에서의 데모 기여도
- `CA_parameter = ParamAccuracy(A) - ParamAccuracy(C)` → 파라미터 적응에서의 데모 기여도
- `Pure_CA = Accuracy(B) - Accuracy(D)` → 탐색 능력 제거 후 순수 CA

### 5.3. 보조 지표 (Verbal, 참고용)

기존 CATS와 동일하게 metacognitive probe 응답을 보조적으로 평가:
- 시각-물성 불일치를 언급했는가
- 함정 기법을 기각한 근거가 탐색 결과에 기반하는가
- 파라미터 조정의 근거가 명시되어 있는가

---

## 6. OmniGibson/IsaacSim 구현 노트

### 6.1. 에셋 요구사항

| 태스크 | 필요 에셋 | BEHAVIOR-1K 존재 여부 | 비고 |
|---|---|---|---|
| A: Container Opening | 용기 + 뚜껑 | jar, bottle 등 존재 | push-and-turn 메커니즘은 joint constraint로 custom 구현 |
| B: Squeeze-Handle Drawer | 서랍 + D-handle | cabinet/drawer 존재 | squeeze-handle 캠 래치는 revolute joint로 구현 |
| C: Tilt-and-Turn Window | 창문 + 레버 핸들 | window 존재 여부 확인 필요 | dual-hinge 메커니즘은 conditional joint로 구현 |
| D: Safety-Release Sliding Door | 문 + D-handle + 풋 레버 | door 존재 | 래치 + prismatic joint + 타이머로 구현 |
| E: Magnetic Closure | 보석함 + 장식 래치 | box 존재 가능 | 자력은 spring joint + attraction force로 근사 |
| F: Rotate-Knob Drawer | 서랍 + 둥근 노브 | cabinet/drawer 존재 | revolute joint (90° cam lock) + prismatic joint |
| G: Tilt-to-Release Bench | 수납 벤치 + 장식 래치 | bench/ottoman 확인 필요 | revolute joint (경첩) + gravity latch (conditional) |

### 6.2. 메커니즘 구현 전략

모든 태스크의 핵심 메커니즘은 **OmniGibson의 joint system + state change**로 구현한다:

- **Push-and-turn (A)**: prismatic joint (수직) + revolute joint (회전), conditional activation (수직 변위 > threshold일 때 회전 자유도 해제)
- **Squeeze-handle (B)**: revolute joint (손잡이 안쪽 피벗) + prismatic joint (서랍 슬라이드), conditional activation (손잡이 변위 > threshold일 때 서랍 잠금 해제)
- **Tilt-and-turn (C)**: revolute joint 2개 (측면 경첩 + 하단 경첩), handle 각도에 따라 활성 경첩 전환
- **Safety-release sliding (D)**: prismatic joint (수평) + foot lever (래치 제어), 타이머 기반 conditional (lever press 후 3초간 해제)
- **Magnetic closure (E)**: prismatic joint (수직) + 거리 반비례 attraction force
- **Push-turn-pull knob (F)**: center button (spring-loaded pin) + revolute joint (90° cam) + prismatic joint (서랍), 3-step conditional (button press → rotation unlock → pull unlock). 구현은 symbolic param_checker 방식
- **Tilt-to-release (G)**: revolute joint (경첩) + gravity latch (핀이 중력으로 해제), 피벗 기반 conditional (뒤쪽 눌림 → 앞쪽 올라감 → 핀 해제)

### 6.3. Exploration Primitive 확장

기존 primitive (NAVIGATE_TO, TOUCH, PUSH, PULL, PICK_UP, OPEN)에 추가:

| Primitive | 용도 | 반환 데이터 |
|---|---|---|
| TWIST[object, direction] | 회전 시도 | torque, angular displacement, vertical displacement |
| PRESS[object, direction] | 수직으로 누르기 | force, displacement, spring constant, click detection |
| SQUEEZE[object] | 안쪽으로 쥐어짜기 | force, displacement, click detection |
| LIFT[object, position] | 들어올리기 시도 | force, displacement, obstruction detection |
| PRESS_AND_TWIST[object] | 누르면서 돌리기 | combined sensor data |
| SQUEEZE_AND_PULL[object] | 쥐어짜면서 당기기 | combined sensor data |

#### 탐색/실행 분류 (§2.4 "조합이 해법" 원칙)

**원칙:** 개별 동작은 탐색(속성 발견), 조합 동작은 실행(해법) 전용

| Primitive | A (Container) | B (Squeeze) | C (Window) | D (Safety Door) | E (Magnet) | F (Rotate) | G (Tilt Bench) |
|---|---|---|---|---|---|---|---|
| TWIST | ✅ 탐색 | — | ✅ 탐색 (45°/135° detent) | — | — | ✅ 탐색 | — |
| PRESS | ✅ 탐색 | — | — | ✅ 탐색 | — | ✅ 탐색 | ✅ 탐색 |
| SQUEEZE | — | ✅ 탐색 | — | — | — | — | — |
| PULL | ✅ 탐색 | ✅ 탐색 | ✅ 탐색 (틸트 확인) | ✅ 탐색 | ✅ 탐색 | ✅ 탐색 | — |
| PUSH | — | — | ✅ 탐색 (충돌 발견!) | ✅ 탐색 | ✅ 탐색 | — | ✅ 탐색 |
| LIFT | — | — | — | — | — | — | ✅ 탐색 |
| PRESS_AND_TWIST | ❌ 실행 | — | — | — | — | — | — |
| SQUEEZE_AND_PULL | — | ❌ 실행 | — | — | — | — | — |
| PRESS[center]+TWIST+PULL 3-step | — | — | — | — | — | ❌ 실행 | — |
| PRESS→SLIDE 타이밍 | — | — | — | ❌ 실행 | — | — | — |
| PRESS[rear]→LIFT 간접 | — | — | — | — | — | — | ❌ 실행 |

기존 primitive와의 구분:
- PUSH: 물체를 수평으로 밀기 (이동 여부 확인)
- PRESS: 물체의 특정 면을 수직으로 누르기 (변위 + 스프링 확인)
- SQUEEZE: 손잡이를 안쪽으로 쥐어짜기 (캠/래치 작동 확인)
- TWIST: 물체를 회전 (토크 + 각변위 + 수직변위 확인)
- LIFT: 물체를 들어올리기 (걸림/저항 확인)

---

## 7. No-Demo Baseline 예상 분석

### 7.1. 각 태스크별 LLM 사전지식 수준

| 태스크 | 조합 유형 | LLM 사전지식 | No-Demo 예상 | 근거 |
|---|---|---|---|---|
| A: Container Opening | 동시 결합 | 중간 | 30~40% | child-proof는 상식이지만 시각 함정이 screw-turn으로 유도 |
| B: Squeeze-Handle Drawer | 동시 결합 | 낮음 | 15~25% | squeeze-handle은 매우 드묾. PULL 실패 후 "쥐면서 당기기"는 비자명 |
| C: Tilt-and-Turn Window | 순차 (모드) | 낮음 | 15~25% | tilt-and-turn은 북미 데이터에 적음, 각도별 모드 전환 비직관적 |
| D: Safety-Release Door | 순차 + 타이밍 | 낮음 | 10~20% | 풋 레버 + 3초 타이밍 + 슬라이드 조합은 매우 드묾 |
| E: Magnetic Closure | 파라미터 적응 | 중간 | 30~40% | 자석 잠금은 알려져 있지만 래치 함정이 유도 |
| F: Push-Turn-Pull Knob Drawer | 3-step sequential hold | 낮음 | 10~20% | 3단계 홀드(press center → twist while holding → pull while holding)는 매우 비자명. 가스 레인지 원리를 서랍에 적용하는 연결이 어려움 |
| G: Tilt-to-Release Bench | 간접 전달 | 매우 낮음 | 5~15% | "뒤를 눌러서 앞을 여는" 발상은 극히 비자명 |

### 7.2. Delta 예상

데모 + 탐색 조건(A)에서 기법 선택 정확도가 50~80%로 예상되므로, **CA Delta는 25~50%p 범위**로 통계적 유의성 확보가 가능할 것으로 예상된다.

**가장 높은 delta 예상 태스크:**
1. **G (Tilt-to-Release Bench)** — LLM 사전지식이 가장 적고, 간접적 힘 전달이 데모 없이는 도달 불가
2. **D (Safety-Release Door)** — 3초 타이밍 조건이 데모 없이는 파악 불가
3. **C (Tilt-and-Turn Window)** — 각도별 모드가 데모에서 직접적으로 보여짐

---

## 8. 구현 우선순위 및 로드맵

### 8.1. 조합 유형별 구현 순서

모든 태스크가 "조합이 해법" 원칙을 만족하므로, **조합 유형의 다양성**과 **구현 난이도**를 기준으로 순서를 정한다:

```
Phase 1: Task A (Container Opening) — 동시 결합                    ✅ 구현 완료
  ├─ full task_config 예시 존재 (§3)
  ├─ TWIST, PRESS 탐색 핸들러 추가
  └─ planner_ca.py: TWIST, PRESS 추가 (탐색 dispatch)

Phase 2: Task F (Push-Turn-Pull Knob Drawer) — 3-step sequential hold   ✅ 구현 완료
  ├─ Phase 1에서 구현한 TWIST 재사용
  ├─ 새 primitive: PRESS[center] (버튼 감지)
  ├─ 3-step 파라미터 체커 구현 (_check_press_twist_pull_params)
  ├─ cross-domain 데모: 가스 레인지 노브 (press-and-turn)
  └─ 기존 cabinet 에셋 활용 + 실험 완료 (6개 모델)

Phase 3: Task G (Tilt-to-Release Bench) — 간접 전달              ✅ 구현 완료
  ├─ 새 primitive: LIFT, PRESS[rear]
  ├─ gravity latch 메커니즘 (피벗 기반 conditional)
  ├─ cross-domain 데모: 시소 (see-saw leverage)
  ├─ cedar_chest + necklace 에셋
  └─ 실험 완료 (6개 모델)

Phase 4: Task C (Tilt-and-Turn Window) — 순차 (모드)
  ├─ CA delta 최고 예상
  ├─ Phase 1에서 구현한 TWIST 재사용
  └─ OmniGibson window 에셋 확인 필요

Phase 5: Task E (Magnetic Closure) — 파라미터 적응
  ├─ 새 primitive 불필요 (기존 PULL + TOUCH)
  └─ 자력 구현 (spring joint + attraction force)

Phase 6: Task B (Squeeze-Handle Drawer) — 동시 결합 (변형)
  ├─ 새 primitive: SQUEEZE, SQUEEZE_AND_PULL
  └─ 기존 cabinet 에셋 + 손잡이 커스텀

Phase 7: Task D (Safety-Release Door) — 순차 + 타이밍
  ├─ Phase 1의 PRESS 재사용
  ├─ 타이머 기반 conditional 구현 필요
  └─ 풋 레버 에셋 커스텀
```

### 8.2. 최소 논문 세트

**6개 조합 유형을 모두 커버하는 최소 세트 = 6개 태스크:**

| 조합 유형 | 대표 태스크 | 상태 | 비고 |
|---|---|---|---|
| 동시 결합 | A (Container) | ✅ 구현 완료 | |
| 3-step sequential hold | F (Push-Turn-Pull Knob) | ✅ 구현 완료 | 실험 완료 |
| 간접 전달 | G (Tilt-to-Release Bench) | ✅ 구현 완료 | 실험 완료, LLM 난이도 최고 |
| 순차 (모드) | C (Tilt-and-Turn Window) | ⬜ 미구현 | CA delta 최고 예상 |
| 파라미터 적응 | E (Magnetic Closure) | ⬜ 미구현 | |
| 동시 결합 (변형) 또는 순차+타이밍 | B 또는 D | ⬜ 미구현 | 6번째는 선택적 |

순차 + 타이밍(D)은 3-step hold(F)와 유사하므로 최소 세트에서 제외 가능.
동시 결합은 A로 커버되므로 B는 선택적.

---

## 9. 한계 및 향후 과제

### 9.1. 인정해야 할 한계

- **물성 불일치의 생태학적 타당성**: "장식적 나사산", "장식적 래치" 등은 현실에 존재하지만 흔하지는 않음. 다만 tilt-and-turn 창문, squeeze-handle 캐비닛, cam lock 서랍은 실제로 존재하는 제품.
- **LLM 사전지식 차단의 불완전성**: child-proof 뚜껑, 자석 잠금 등은 인터넷에 존재하는 지식. 완전 차단은 불가능하며, delta로 데모 기여도를 측정하는 것이 현실적 목표. 특히 Task G(tilt-to-release)와 D(safety-release)는 사전지식이 매우 낮아 delta가 클 것으로 예상.
- **파라미터 평가의 모호성**: 연속 파라미터의 "정답 범위"를 어디까지로 설정하느냐에 연구자 편향 가능성. 시뮬레이터의 물리 엔진이 자동으로 성공/실패를 판정하는 파이프라인으로 보완.
- **조합 동작의 복잡도 편차**: 동시 결합(A, B)은 비교적 단순한 반면, 간접 전달(G)은 3단계 인과 체인을 요구. 태스크 간 난이도 차이가 크므로, 난이도별 분석이 필수.

### 9.2. Level 2.4 확장 가능성

하나의 가정환경에서 여러 메커니즘을 연속으로 만나는 시나리오:
- Subtask 1: 약장 뚜껑 (push-and-turn, A) → 약 꺼내기
- Subtask 2: 서랍 (rotate-knob, F) → 도구 꺼내기
- Subtask 3: 수납 벤치 (tilt-to-release, G) → 물건 꺼내기

동일 데모 세트를 1회만 보여주고, subtask마다 다른 기법을 선택해야 한다. 이전 subtask에서 성공한 기법이 다음 subtask의 함정이 될 수 있다 (예: push-and-turn 성공 후 rotate-knob에서도 눌러보려 시도).
