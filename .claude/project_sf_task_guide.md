---
name: SF 평가 프레임워크 총 정리
description: SF 평가 프레임워크 — 논문 정의, 5 Phase 파이프라인, Symbolic 시간 시스템, 숨겨진 변수, 외삽 측정, 구현 가이드(time_system.py, planner_sf.py, task_config, 케이크 태스크 상세)
type: project
---

# Scenario Flexibility (SF) 평가 프레임워크 총 정리
## Embodied LLM 환경에서의 SF 측정을 위한 태스크 설계 및 구현 가이드

---

## 1. 이론적 배경: Scenario Flexibility란?

### 1.1. 논문에서의 정의

> **Scenario Flexibility:** 시나리오가 전개될 수 있는 다양한 방식을 고려하여 가능한 우발 상황(contingencies)을 파악하는 능력
> — Johnson, Karimi, Bengio et al., "Imagining and building wise machines" (Trends in Cognitive Sciences, 2026)

### 1.2. Ron 사례

Ron(정치 컨설턴트)은 후보의 승리 시나리오뿐 아니라 **패배 시나리오까지 상상**하고, 패배의 원인까지 사전에 분석한다. 핵심은 **실행 전에** 다양한 결과 가능성을 예측하는 것.

### 1.3. CA와의 구분

| | CA | SF |
|---|---|---|
| 축 | 유사성 (현재 ↔ 참조) | 시간 (현재 → 미래들) |
| 질문 | "이 상황이 무엇과 비슷한가?" | "이 상황이 어떻게 전개될 수 있는가?" |
| 정보 소스 | Demo 영상 (외부) | 관찰 + rollout (자체) |
| 제약 | One-shot | Time budget |
| 핵심 인지 | 구조적 매핑 | 미래 예측 + 외삽 |

### 1.4. SF ≠ Reactive Adaptation

| | Reactive Adaptation | SF |
|---|---|---|
| 시점 | 실패 **후** | 행동 **전** |
| 방향 | 과거 → 현재 (retrospection) | 현재 → 미래 (prospection) |
| 핵심 | "왜 실패했지?" | "앞으로 뭐가 벌어질 수 있지?" |

---

## 2. 5 Phase 파이프라인

### 전체 흐름

```
Phase 0: 환경 관찰 (exploration, time_step 미소모)
    ↓
Phase 1: 초기 시나리오 예측 (verbal — SF baseline)
    ↓
Phase 2: 확인 rollout 1회 (sim.save/restore, time_step 소모)
    ↓
Phase 3: 확장 시나리오 예측 + 계획 수정 (verbal — SF 핵심 측정)
    ↓
Phase 4: 최종 전략 수립 + 실행 (리셋 없음, time_step 진행)
    ↓
Phase 5: 시스템 검증 (에이전트 모르게)
    ↓
[평가]
```

### Phase별 요약

| Phase | 에이전트 활동 | 시간 소모 | 핵심 측정 |
|---|---|---|---|
| 0 | NAVIGATE_TO, TOUCH (외부만) | ❌ | 물리 변수 추정 능력 |
| 1 | Verbal 시나리오 생성 | ❌ | 사전 예측 범위, 최선+최악 균형 |
| 2 | OPEN, TOUCH 등 1회 rollout | ✅ (rollout 내) | 부수 효과 발견, rollout 목적성 |
| 3 | Verbal 시나리오 업데이트 | ❌ | **★ 외삽 범위·정확도** |
| 4 | ReAct 루프 실행 | ✅ | 태스크 완성도, contingency 발동 |
| 5 | (시스템이 수행) | N/A | 예측 정확도 검증 |

---

## 3. 정보의 3가지 층위

| 층위 | 발견 방법 | 예시 | Phase |
|---|---|---|---|
| **Layer 1 — Verbal** | LLM 상식 | "정전이면 오븐 꺼진다" | Phase 1 |
| **Layer 2 — 물리 관찰** | Exploration | 오븐 외벽 172°C, -3.2°C/step | Phase 0 |
| **Layer 3 — Rollout** | 실제 행동 | "열면 -30°C/step 급락" | Phase 2 |
| **외삽 (SF 핵심)** | Layer 3에서 일반화 | "오븐이 그러면 냉장고도" | Phase 3 |

**정답 전략 = Layer 1+2+3+외삽의 종합.**
어떤 Layer가 빠지면 다른 종류의 함정으로 빠진다.

---

## 4. 숨겨진 변수 설계

### 설계 원칙

태스크에 N개의 숨겨진 변수를 설계자가 미리 배치. 각 변수는 세 가지 발견 방법 중 하나로 분류:

| 발견 방법 | 역할 | 평가 기여 |
|---|---|---|
| Phase 0 관찰 | Baseline 정보 | 물리 추론 능력 |
| Phase 2 rollout | 부수 효과 발견 | rollout의 가치 |
| **Phase 3 외삽** | **SF 핵심** | **경험→미경험 일반화** |

**최소 1개 이상의 변수가 "외삽으로만 도달 가능"해야** SF를 유의미하게 측정 가능.

### 케이크 태스크 숨겨진 변수 (구체 예시)

| # | 변수 | 발견 방법 | 분기 |
|---|---|---|---|
| V1 | 케이크 익힘도 (70%) | OPEN[oven] + TOUCH[cake] | 추가 익힘 가능 여부 |
| V2 | 오븐 급랭 (문 열면 -30°C/step) | **rollout으로만 발견** | 잔열 보존 전략 결정 |
| V3 | 냉장고 급온 (문 열면 +5°C/step) | **V2에서 외삽** | 크림 시간 창 관리 |
| V4 | 정전 복구 (35분, step 7) | 기다려봐야 발견 | 오븐 재가동 가능성 |
| V5 | 뜨거운 케이크 + 크림 = 녹음 | 물리 추론 또는 rollout | 크림 도포 시점 결정 |
| V6 | 오븐 예열 시간 (10분, 2 step) | 정전 복구 후 발견 | 시간 예산 계산 |

---

## 5. Symbolic 시간 시스템

### 5.1. 기본 구조

```
매 action → time_step += 1 (= 5분 경과)
WAIT action → 아무것도 안 하고 5분 경과
총 12 step (60분) 후 태스크 종료
```

### 5.2. 상태 변화 수식 (케이크 태스크)

```
오븐 온도 (문 닫힘): oven_temp(t) = max(23, 180 - 12*t)
오븐 온도 (문 열린 후): oven_temp(t) = max(23, oven_temp(t_open) - 30*(t - t_open))

냉장고 온도 (문 닫힘): fridge_temp(t) = min(30, 5 + 1.5*t)
냉장고 온도 (문 열린 후): fridge_temp(t) = min(30, fridge_temp(t_open) + 5*(t - t_open))

케이크 익힘: doneness(t) = min(100, 70 + Σ(max(0, oven_temp(i) - 100) * 0.04))
크림 사용 가능: cream_usable = (fridge_temp < 15)
크림 도포 성공: cake_temp < 50 AND cream_usable

정전 복구: power_restored = (t >= 7)
오븐 예열: 복구 후 2 step에서 180°C 도달
```

### 5.3. CA와의 패턴 일치

CA에서 확립된 "symbolic 과정 + 물리적 결과" 패턴과 동일:

```
CA:  NEW_ACTION[PRESS_AND_PICK, potato, shards]
     → symbolic: (potato, shards) → SUCCESS
     → 물리적: 파편 제거, 깨끗한 바닥 렌더링

SF:  OPEN[oven] at time_step 3
     → symbolic: oven_temp=144°C, cake=76%
     → 물리적: 오븐 문 열림, 케이크 렌더링
```

---

## 6. 측정 지표

### 6.1. 주 지표

| 지표 | 가중치 | Phase | 공식 |
|---|---|---|---|
| **시나리오 커버리지** | 0.25 | 1+3 | 매칭된 변수 수 / N |
| **예측 정확도** | 0.25 | 5 | 정확한 예측 / 총 예측 |
| **외삽 비율** | 0.20 | 3 | 정확한 외삽 / (N - D) |
| **태스크 완성도** | 0.20 | 4 | 태스크별 점수 (0~1) |
| **최선+최악 균형** | 0.10 | 1+3 | 실패 시나리오 비율 (0.3~0.7 이상적) |

### 6.2. 보조 지표

| 지표 | Phase | 설명 |
|---|---|---|
| 변수 조합 사고 | 1+3 | V1×V3, V2×V4 등 교차 시나리오 |
| 시간 추정 정확도 | 1+3 | "잔열 15분" 등의 수치 추정 정확성 |
| contingency 포함 | 3+4 | "만약 X이면 Y" 대비책 |
| 관찰 비용 인식 | 1+3 | "열면 잔열 손실" 트레이드오프 |
| rollout 목적성 | 2 | 탐색 vs 검증 |
| Phase 1→3 개선도 | 1 vs 3 | rollout 후 시나리오 풍부화 정도 |

---

## 7. 함정 구조 (케이크 태스크)

| 함정 | 행동 | 결과 | SF 결핍 |
|---|---|---|---|
| **즉시 확인** | 0분에 오븐+냉장고 모두 열기 | 잔열 급소실, 크림 일찍 녹음 | 관찰 비용 미인식 |
| **정전 복구 대기** | 35분까지 아무것도 안 함 | 크림 녹음, 시간 부족 | 단일 시나리오(최선)만 고려 |
| **크림 먼저** | 뜨거운 케이크에 바로 크림 | 크림 녹아내림 | 변수 조합 미고려 (V1×V3) |
| **잔열 과신** | 30분까지 대기 | 크림 시간 창 놓침 | 비선형 시간 추정 실패 |
| **포기** | 초콜릿만 장식 | 잔열/크림/복구 미활용 | SF 부재 |

### 함정별 예상 점수 (케이크 100점 만점)

| 전략 | 점수 | SF 수준 |
|---|---|---|
| 정답 (잔열 보존 + 크림 타이밍 + 정전 복구 활용) | 100 | 높음 |
| 잔열 보존 + 크림 타이밍 (복구 미활용) | 80 | 중~높음 |
| 포기 (초콜릿만) | 50 | 없음 |
| 함정1: 즉시 확인 | 40 | 낮음 |
| 함정4: 잔열 과신 | 40 | 중간 |
| 함정3: 크림 먼저 | 30 | 낮음 |
| 함정2: 대기 | 20 | 매우 낮음 |

---

## 8. SF 수준별 에이전트 프로파일

### SF = 0 (포기)

```
Phase 1: "정전이라 오븐 안 됨. 불가능."
Phase 2: rollout 안 함
Phase 3: "초콜릿이라도."
Phase 4: 초콜릿 장식만.
결과: 50점. 미래 가능성 미탐색.
```

### SF = 낮음 (즉시 확인)

```
Phase 1: "오븐 확인해봐야지."
Phase 2: OPEN[oven] → V2 발견 (급랭)
Phase 3: "오븐 안 열어야겠다." (외삽 없음 — V2에만 대응)
Phase 4: 냉장고는 바로 열어버림 → 크림 녹음
결과: 40점. V2만 대응, V3 외삽 실패.
```

### SF = 중간 (개별 변수 인식, 조합 미고려)

```
Phase 1: 잔열/크림/정전 개별 인식
Phase 2: V2 발견
Phase 3: V3 외삽 시도 ✅, 하지만 V5 (뜨거운 케이크+크림) 미고려
Phase 4: 15분에 오븐+크림 동시 → 뜨거운 케이크에 크림 → 녹아내림
결과: 40~60점. 외삽은 했지만 변수 조합 실패.
```

### SF = 높음 (정답)

```
Phase 1: 모든 변수 + 시간 추정 + 조합 + 불확실성 + 관찰 비용
Phase 2: V2 발견 → V3 외삽 ✅ + V5 예측 ✅
Phase 3: 시간별 분기 전략 + contingency + 변수 조합 시나리오
Phase 4: 잔열 보존 → 최적 시점에 꺼냄 → 크림 타이밍 → 정전 복구 활용
결과: 80~100점.
```

---

## 9. OmniGibson 구현 가이드

### 9.1. 반드시 생성해야 하는 파일

#### A. BDDL 정의 파일 (필수)
- **경로**: `bddl3/bddl/activity_definitions/{task_name}/problem0.bddl`
- CA와 동일한 방식. 오븐, 냉장고, 케이크, 크림, 초콜릿 등 정의.
- goal condition: 케이크가 완성된 상태 (장식 포함)

#### B. Scene Template JSON (필수)
- **경로**: `datasets/.../scenes/{scene}/json/{scene}_task_{task_name}_0_0_template.json`
- 주방 씬. 오븐(문 닫힘), 냉장고(문 닫힘), countertop에 초콜릿/장식 도구 배치.
- 케이크는 오븐 내부, 크림은 냉장고 내부에 배치.

#### C. available_tasks.yaml 엔트리 (필수)
- CA와 동일. scene_model, robot 위치 등.

#### D. SF Task Config (Python dict) (필수)
- **경로**: `omnigibson/llm_agent/sf_tasks/{task_name}.py`
- `SF_TASK_REGISTRY`에 등록.
- CA의 `TASK_CONFIG`과 구조적으로 유사하지만, 시간 시스템 설정이 추가됨.

#### E. time_system.py (필수 — SF 전용)
- **경로**: `omnigibson/llm_agent/time_system.py`
- TimeState 클래스: 상태 관리 + 시간 진행 + 관찰 가능 상태 반환
- 태스크별 상태 수식은 task_config에서 파라미터로 주입.

#### F. planner_sf.py (필수 — SF 전용)
- **경로**: `omnigibson/llm_agent/planner_sf.py`
- CA의 `planner_ca.py`와 별도. 5 Phase 파이프라인 구현.
- sim.save/restore 호출, 시간 시스템 연동.

---

### 9.2. CA의 planner_ca.py와의 차이

| 요소 | planner_ca.py | planner_sf.py |
|---|---|---|
| 데모 | Probe 0에서 영상 시청 | **없음** — 외부 정보 없이 자체 관찰/예측 |
| Exploration | Stage 1 ReAct (symbolic feedback) | Phase 0 (동일 방식) |
| 핵심 단계 | Stage 2 (Demo 비교) + Tool Selection | **Phase 1+3 (시나리오 예측)** |
| Rollout | 없음 | **Phase 2 — sim.save/restore** |
| 시간 | 없음 | **time_system.py 연동** |
| 실행 | Stage 3 ReAct | Phase 4 ReAct (**time_step 소모**) |
| 검증 | 없음 (success rate로 판정) | **Phase 5 — 시스템이 예측 검증** |
| One-shot 제약 | CA tool GRASP 시 확정 | 없음 — time budget으로 대체 |
| NEW_ACTION handler | (tool, target, context) → outcome | **(action, target, time_state) → outcome** |

---

### 9.3. 파이프라인 전체 흐름

```
Phase 0 (Exploration)
  ↓
Phase 1 (Initial Scenario Prediction — verbal)
  ↓
Phase 2 (Confirmation Rollout — sim.save/restore)
  ↓
Phase 3 (Extended Scenario Prediction — verbal, SF 핵심)
  ↓
Phase 4 (Final Execution — ReAct with time_step)
  ↓
Phase 5 (System Verification — 에이전트 모르게)
```

#### LLM 호출 횟수

| 단계 | 호출 수 |
|---|---|
| Phase 0 | N회 (exploration steps) |
| Phase 1 | 1회 (시나리오 예측) |
| Phase 2 | M회 (rollout steps) |
| Phase 3 | 1회 (확장 예측) |
| Phase 4 | K회 (실행 steps) |
| **총합** | **N + M + K + 2회** |

---

### 9.4. Phase 0 — Exploration 구현

CA의 Stage 1과 동일한 구조. 차이점: **time_step을 소모하지 않음.**

```python
# Phase 0에서는 time_system.advance_time() 호출 안 함
# NAVIGATE_TO → 카메라 이동 + 렌더링 이미지
# TOUCH[외부 표면] → 센서 피드백 텍스트 (v2 raw 수치)
# 오브젝트를 열거나 잡지 않음
```

Exploration feedback 형식 (v2, raw 센서):
```
TOUCH[oven_door]:
  "Surface temperature: 172°C. Temperature gradient: -3.2°C per 5 minutes."

TOUCH[fridge_door]:
  "Surface temperature: 8°C. Temperature gradient: +0.5°C per 5 minutes."
```

---

### 9.5. Phase 1 — 시나리오 예측 프롬프트

```
┌─ System ──────────────────────────────────────────────────────┐
│ "You are a robot agent in a kitchen during a power outage.    │
│  You have observed the environment but have not yet acted.    │
│  Before taking any action, think about what could happen."    │
├─ User ────────────────────────────────────────────────────────┤
│ === Your Exploration Findings ===                              │
│ (Phase 0의 전체 탐색 히스토리)                                 │
│                                                               │
│ Now predict:                                                  │
│ (1) Success scenarios — how can you complete the task?        │
│ (2) Failure scenarios — what could go wrong?                  │
│ (3) How might the situation change over time?                 │
│ (4) What uncertain factors remain that you haven't confirmed? │
├─ Image: Phase 0 마지막 카메라 이미지 ─────────────────────────┤
└───────────────────────────────────────────────────────────────┘
```

---

### 9.6. Phase 2 — Rollout 구현

```python
# 1. 상태 저장
og.sim.save("sf_rollout_checkpoint")
time_system.save_state()

# 2. Rollout 실행 (ReAct 루프, 제한된 step)
#    매 action마다:
#      time_system.advance_time()
#      결과를 symbolic으로 판정
#      IsaacSim에 물리적 결과 반영
#      렌더링 이미지 캡처

# 3. 상태 복원
og.sim.restore("sf_rollout_checkpoint")
time_system.restore_state()
```

Rollout 중 에이전트에게:
```
"This is a simulation. After this simulation, the environment 
will be reset to its initial state. Use this opportunity to 
gather information about uncertain factors."
```

---

### 9.7. Phase 3 — 확장 예측 프롬프트 (SF 핵심)

```
┌─ System ──────────────────────────────────────────────────────┐
│ "The simulation has ended and the environment has been reset. │
│  Use what you learned to update your predictions."            │
├─ User ────────────────────────────────────────────────────────┤
│ === Your Exploration Findings (Phase 0) ===                   │
│ (탐색 히스토리)                                                │
│                                                               │
│ === Your Initial Predictions (Phase 1) ===                    │
│ (Phase 1에서 LLM이 작성한 시나리오 텍스트)                     │
│                                                               │
│ === Simulation Results (Phase 2) ===                          │
│ (rollout의 각 step과 관찰 결과)                                │
│                                                               │
│ Now update your predictions:                                  │
│ (1) What new information did the simulation reveal?           │
│ (2) Based on this, what OTHER risks might exist that you      │
│     have NOT yet confirmed?                                   │
│ (3) What changes to your initial predictions are needed?      │
│ (4) Provide a time-based strategy with contingencies.         │
│                                                               │
│ Each action takes about 5 minutes. You have 60 minutes total. │
│ Plan your actions by time step.                               │
├─ Image: Phase 0 마지막 카메라 이미지 (rollout 전 상태) ────────┤
└───────────────────────────────────────────────────────────────┘
```

---

### 9.8. Phase 4 — 최종 실행

CA의 Stage 3과 동일한 ReAct 루프. 차이점:

1. **time_step이 매 action마다 진행:** `time_system.advance_time()` 호출
2. **시간 기반 이벤트 발생:** 정전 복구 등이 특정 step에서 자동 발생
3. **상태 변화가 관찰에 반영:** TOUCH[oven_door] → 현재 time_step 기준 온도 반환
4. **WAIT action 가능:** 아무것도 안 하고 5분 경과

Phase 4 system prompt에 포함되는 컨텍스트:
- Phase 0 탐색 결과 (요약)
- Phase 1 초기 예측 (요약)
- Phase 2 rollout 결과 (요약)
- Phase 3 확장 예측 + 시간별 전략 (전문)
- Available Objects 리스트
- Available Actions (NAVIGATE_TO, GRASP, OPEN, CLOSE, TOUCH, PLACE_ON_TOP, WAIT, NEW_ACTION 등)
- "Each action takes about 5 minutes. You have {remaining_steps} steps remaining."

---

### 9.9. Phase 5 — 시스템 검증

에이전트의 Phase 1+3 예측 텍스트를 파싱하여, 각 예측을 IsaacSim에서 자동 검증.

```python
# 예측 파싱 예시:
predictions = parse_predictions(phase1_text, phase3_text)
# [
#   {"claim": "오븐 열면 잔열 급락", "type": "causal"},
#   {"claim": "냉장고도 마찬가지", "type": "extrapolation"},
#   {"claim": "뜨거운 케이크에 크림 녹음", "type": "combination"},
# ]

# 각 예측을 sim에서 검증:
for pred in predictions:
    og.sim.restore("initial_state")
    result = simulate_prediction(pred)  # 해당 조건을 실행
    pred["verified"] = compare_with_ground_truth(result)
```

**자동화 수준:** 초기에는 수동 파싱, 이후 자동 파싱 스크립트 개발.

---

### 9.10. time_system.py 핵심 구현

```python
class TimeState:
    def __init__(self, config):
        self.config = config  # task_config에서 주입
        self.time_step = 0
        self.oven_door_open = False
        self.oven_door_opened_at = None
        self.fridge_door_open = False
        self.fridge_door_opened_at = None
        self.power_restored = False
        self._saved_state = None
    
    def advance_time(self):
        """매 action 실행 시 호출"""
        self.time_step += 1
        if self.time_step >= self.config["power_restore_step"]:
            if not self.power_restored:
                self.power_restored = True
                return {"event": "power_restored"}
        return {}
    
    def get_oven_temp(self):
        t = self.time_step
        c = self.config
        base = max(c["room_temp"], 
                   c["oven_initial_temp"] - c["oven_cooling_closed"] * t)
        if self.oven_door_open and self.oven_door_opened_at is not None:
            dt = t - self.oven_door_opened_at
            loss = c["oven_cooling_opened"] * dt
            return max(c["room_temp"], base - loss)
        return base
    
    def get_fridge_temp(self):
        t = self.time_step
        c = self.config
        base = min(c["room_temp"],
                   c["fridge_initial_temp"] + c["fridge_warming_closed"] * t)
        if self.fridge_door_open and self.fridge_door_opened_at is not None:
            dt = t - self.fridge_door_opened_at
            gain = c["fridge_warming_opened"] * dt
            return min(c["room_temp"], base + gain)
        return base
    
    def get_cake_doneness(self):
        doneness = self.config["cake_initial_doneness"]
        threshold = self.config["cake_cooking_threshold"]
        for i in range(self.time_step):
            temp_at_i = self._get_oven_temp_at_step(i)
            if temp_at_i > threshold:
                doneness += (temp_at_i - threshold) * 0.04
        return min(100, doneness)
    
    def get_cake_temp(self):
        """케이크가 오븐 안이면 oven_temp, 밖이면 상온으로 식어감"""
        if self.cake_in_oven:
            return self.get_oven_temp()
        else:
            # 꺼낸 이후 매 step -15°C씩 식어감
            dt = self.time_step - self.cake_removed_at
            return max(self.config["room_temp"],
                       self.cake_temp_when_removed - 15 * dt)
    
    def is_cream_usable(self):
        return self.get_fridge_temp() < self.config["cream_melt_threshold"]
    
    def can_apply_cream(self):
        cake_temp = self.get_cake_temp()
        return (self.is_cream_usable() and 
                cake_temp < self.config["cream_apply_max_cake_temp"])
    
    def open_oven(self):
        self.oven_door_open = True
        self.oven_door_opened_at = self.time_step
    
    def open_fridge(self):
        self.fridge_door_open = True
        self.fridge_door_opened_at = self.time_step
    
    def save_state(self):
        """Phase 2 rollout 전 상태 저장"""
        self._saved_state = {
            "time_step": self.time_step,
            "oven_door_open": self.oven_door_open,
            "oven_door_opened_at": self.oven_door_opened_at,
            "fridge_door_open": self.fridge_door_open,
            "fridge_door_opened_at": self.fridge_door_opened_at,
            "power_restored": self.power_restored,
        }
    
    def restore_state(self):
        """Phase 2 rollout 후 상태 복원"""
        for k, v in self._saved_state.items():
            setattr(self, k, v)
```

---

### 9.11. SF task_config 전체 필드 목록

| 필드 | 필수 | 설명 |
|------|------|------|
| `task_name` | ✅ | 태스크 식별자 (예: `cake_completion_power_outage`) |
| `measurement_target` | ✅ | `"Scenario Flexibility"` |
| `instruction` | ✅ | 에이전트에게 주어지는 태스크 지시문 **(영어)** |
| `time_system` | ✅ | 시간 시스템 설정 dict |
| `time_system.step_duration_minutes` | ✅ | 매 step당 경과 시간 (분) |
| `time_system.max_steps` | ✅ | 총 step 수 |
| `time_system.power_restore_step` | | 정전 복구 step (없으면 복구 없음) |
| `initial_state` | ✅ | 초기 물리 상태 (오븐 온도, 냉장고 온도, 케이크 익힘도 등) |
| `hidden_variables` | ✅ | 숨겨진 변수 목록 (V1~VN, 각각 name, discovery method) |
| `scoring` | ✅ | 태스크 완성도 채점 기준 |
| `sf_metrics` | ✅ | SF 주 지표 가중치 설정 |
| `phases` | ✅ | 각 Phase의 시스템 프롬프트 |
| `exploration_feedbacks` | ✅ | Phase 0 exploration feedback (v2 raw 수치) |
| `action_outcomes` | ✅ | 각 action의 물리적 결과 + symbolic 상태 변화 |
| `exploration_nav_targets` | ✅ | NAVIGATE_TO target → scene object 매핑 |
| `exploration_nav_tracking` | | 카메라 tracking 설정 |
| `rollout_max_steps` | | Phase 2 rollout 최대 step 수 (기본 4) |

---

### 9.12. 주요 버그/함정 (SF 전용)

| 증상 | 원인 | 해결 |
|------|------|------|
| time_step이 rollout 후에도 진행됨 | restore_state() 누락 | time_system.restore_state() 반드시 호출 |
| 에이전트가 Phase 2를 "시도"로 인식 | 프롬프트가 "simulation"임을 강조 안 함 | "This is a simulation. Environment will be reset." 명시 |
| Phase 5 검증이 Phase 4 결과와 충돌 | 같은 sim session에서 실행 | Phase 5는 별도 session 또는 Phase 4 완료 후 실행 |
| 오븐을 닫으면 잔열이 회복된다고 에이전트 오해 | 물리적으로 비현실적 | CLOSE[oven] 후에도 cooling_rate_opened 유지 (잃은 열은 돌아오지 않음) |
| WAIT action이 등록되지 않음 | _ACTION_PRIMITIVE_MAP에 없음 | WAIT을 별도 핸들러로 구현 (time_system.advance_time()만 호출) |
| 정전 복구 이벤트를 에이전트에게 안 알림 | advance_time()의 반환값 무시 | event == "power_restored"이면 observation에 알림 추가 |

---

### 9.13. Run Script 진입점

```bash
# Mock LLM으로 파이프라인 테스트
python -m omnigibson.examples.sf.run_sf_agent --model mock --task cake_completion_power_outage

# Gemini로 실제 실행
python -m omnigibson.examples.sf.run_sf_agent --model gemini-2.5-pro --task cake_completion_power_outage
```

---

### 9.14. Mock LLM (SF용)

| 순서 | 응답 |
|------|------|
| 1~N | Phase 0 exploration steps |
| N+1 | Phase 0 DONE_EXPLORING |
| N+2 | Phase 1 시나리오 예측 |
| N+3~N+3+M | Phase 2 rollout steps |
| N+3+M+1 | Phase 2 DONE (rollout 종료) |
| N+3+M+2 | Phase 3 확장 예측 |
| N+3+M+3~끝 | Phase 4 실행 steps |
| 마지막 | Phase 4 DONE |

---

## 10. 정답 전략 시간표 (케이크 태스크)

| Step | 시간 | Action | 오븐°C | 케이크% | 냉장고°C | 크림 | 비고 |
|---|---|---|---|---|---|---|---|
| 0 | 0분 | (Phase 0 완료) | 180 | 70 | 5 | ✅ | |
| 1 | 5분 | PREPARE_DECORATION | 168 | 73 | 6.5 | ✅ | 초콜릿 준비 |
| 2 | 10분 | TOUCH[oven_door] | 156 | 75 | 8 | ✅ | "아직 잔열 충분" |
| 3 | 15분 | TOUCH[oven_door] | 144 | 76 | 9.5 | ✅ | "잔열 효과 거의 끝" |
| 4 | 20분 | OPEN[oven]+TOUCH[cake] | 144→114 | 76 | 11 | ✅ | 꺼냄 준비 |
| 5 | 25분 | GRASP[cake]→PLACE | - | 76 | 12.5 | ✅ | plate 위 |
| 6 | 30분 | OPEN[fridge]+GRASP[cream] | - | ~72°C | 14 | ✅(14<15) | 크림 꺼냄! |
| 7 | 35분 | TURN_ON[oven] | 예열 | ~62°C | - | 대기 | ★정전 복구 |
| 8 | 40분 | APPLY_CREAM | 예열 중 | ~48°C | - | ✅도포 | 48<50 성공! |
| 9 | 45분 | TOUCH[oven] | ~175 | - | - | - | 예열 거의 완료 |
| 10 | 50분 | PLACE[cake,oven] | 180 | 추가굽기 | - | - | 재투입 |
| 11 | 55분 | GRASP[cake]+DECORATE | - | ~92 | - | - | 완성! |
| 12 | 60분 | 태스크 종료 | - | 92 | - | - | 손님 도착 |

---

## 11. 확정된 설계 결정 요약

| 항목 | 결정 |
|---|---|
| 측정 대상 | **Scenario Flexibility (SF)** — CA와 별도 독립 태스크 |
| 핵심 정의 | "시나리오의 다양한 전개 가능성을 **사전에** 예측하는 능력" |
| Ron과의 대응 | Ron = verbal 예측, 에이전트 = 관찰+rollout+verbal 예측 |
| SF의 핵심 측정 | Phase 3 — rollout 경험에서 미경험 변수까지 **외삽** |
| 파이프라인 | 5 Phase (관찰→예측→rollout→확장예측→실행) + 시스템 검증 |
| 시간 시스템 | Symbolic — 매 action +5분, WAIT 가능, 총 12 step |
| Rollout | 1회, sim.save/restore, "관찰의 확장" 목적 |
| 숨겨진 변수 | 6개 (V1~V6), 관찰/rollout/외삽으로 분류 |
| 주 지표 | 커버리지(0.25) + 정확도(0.25) + 외삽(0.20) + 태스크(0.20) + 균형(0.10) |
| Embodiedness | observation=렌더링, rollout=sim.save/restore, 검증=IsaacSim |
| CA와의 관계 | **완전 독립** — 별도 태스크·플래너·평가 파이프라인으로 운영 |
| 구현 패턴 | CA와 동일: "symbolic 과정 + 물리적 결과" |
| 정답 전략 | 3개 시간 창 동시 관리 (잔열/크림/정전 복구) |
| instruction | **반드시 영어** (한국어 사용 시 LLM 혼동) |

---

## 12. 설계 원칙

### 12.1. POMDP — 부분 관찰 가능성

핵심 변수는 **직접 행동해야만 발견 가능**:
- 오븐 안 케이크 상태 → 열어봐야 앎
- 냉장고 안 크림 온도 → 열어봐야 앎
- 정전 복구 시점 → 기다려봐야 앎

Phase 0에서 외부 관찰(TOUCH 외벽)로 **추정은 가능하지만 정확한 값은 알 수 없는** 구조.

### 12.2. Non-stationary — 시간에 따른 환경 변화

환경이 에이전트의 행동 유무와 관계없이 시간에 따라 변화:
- **자동 변화**: 오븐 잔열 감소, 냉장고 온도 상승, 정전 복구
- **행동 유발 변화**: 문 열면 감쇠율 급변 (부수 효과)

### 12.3. 행동의 부수 효과 (Side Effects)

에이전트의 행동이 **의도하지 않은 환경 변화**를 유발:
- OPEN[oven] = 케이크 확인 (의도) + 잔열 급격 손실 (부수 효과)
- OPEN[fridge] = 크림 확인 (의도) + 냉기 급격 손실 (부수 효과)

**관찰의 비용:** 정보를 얻기 위해 환경을 열어보면, 그 행위 자체가 환경을 악화. 이 트레이드오프를 인식하는 것이 SF의 중요한 요소.

### 12.4. 외삽 가능 변수 최소 1개

설계자가 배치한 숨겨진 변수 중 **최소 1개는 rollout으로 직접 경험할 수 없고, 다른 변수에서 외삽으로만 도달 가능**해야 함. 이것이 SF를 단순 trial-and-error와 구분하는 핵심 장치.

### 12.5. 시간 창(Time Window)의 교차

정답 전략이 **복수의 시간 창을 동시에 관리**하는 것을 요구:
```
시간 창 1: 잔열 효과 (0~15분에만 유효)
시간 창 2: 크림 유효기간 (0~30분에 녹기 시작)
시간 창 3: 정전 복구 (35분에 복구)
→ 최적 전략은 세 시간 창의 교차점에서 결정
```

이것이 SF를 단순 planning과 구분 — planning은 "어떤 순서로 할까"이지만, SF는 "미래에 어떤 시간 창들이 존재하고, 어떻게 상호작용하는가"를 예측하는 것.

### 12.6. Exploration feedback → raw 센서 데이터

CA v2에서 확정된 방향과 동일. Phase 0의 TOUCH 피드백은 **raw 센서 수치**로 제공:
- 자연어 해석("뜨겁다") 대신 수치("172°C, -3.2°C/step")
- 센서 이름과 단위는 제공하되, 수치 해석은 에이전트 몫
- "reading comprehension이 아니라 sensor interpretation을 측정"

---

## 13. 난이도 스케일링 (3.1 → 3.4)

CA의 2.x에 대응하여 SF는 3.x 넘버링. **"미래 예측의 깊이"**를 기준으로 스케일링.

### Level 3.1 — 단일 시간 창 (Basic Prospection)

**구조:** 1개 시간 변수. Phase 0 관찰로 변화율 추정 가능. 외삽 불필요.

**예시:** 아이스크림 녹는 시간 추정 → 시간 내 서빙.

### Level 3.2 — 복수 시간 창 + 관찰 비용 (Observation Cost)

**구조:** 2개+ 시간 변수. 관찰 행위가 환경 악화. 외삽 불필요.

**예시:** 오븐(잔열) + 냉장고(온도). 열면 급변. 두 변수 모두 rollout에서 직접 경험 가능.

### Level 3.3 — 외삽 필수 + 시간 창 교차 (Extrapolation-Required)

**구조:** N개 변수 중 일부는 rollout으로 경험 불가. 외삽 필수. 시간 창 교차.

**예시:** 케이크 태스크 — 오븐 급랭 rollout → 냉장고도 급온할 것이라 외삽 + 정전 복구 시점 관리.

### Level 3.4 — 연쇄 효과 + Contingency 필수 (Cascading)

**구조:** A→B→C 연쇄. "만약 X이면 Y, 그러면 Z" 다단계 추론. Contingency 없으면 실패.

**예시:** 정전 → 오븐 멈춤 → 케이크 미완성 + 냉장고 가속 → 복구 시 재가동 vs 크림 녹음 분기.

### 난이도 간 관계

```
Level 3.1: SF 기본 — "시간이 흐르면 환경이 변한다"
    ↓ (관찰 비용 추가)
Level 3.2: SF + 관찰 비용 — "열어보면 환경이 악화된다"
    ↓ (외삽 필수)
Level 3.3: SF + 외삽 — "오븐이 그러면 냉장고도 그럴 것이다" (핵심)
    ↓ (연쇄 추론)
Level 3.4: SF + 연쇄 — "A→B→C 시나리오까지 추론"
```

---

## 14. 이미지 캡처 및 LLM 전달 시스템

CA와 동일한 시스템을 SF에서도 재사용. SF에서의 적용:

### 14.1. 기본 메커니즘 (CA와 동일)

```python
# CameraHelper 초기화
self._camera_helper = _CameraHelper(self.env, self.controller)

# RGB 캡처 → numpy (H, W, 3) uint8 → PNG 저장
rgb = self._camera_helper.get_rgb()
Image.fromarray(rgb).save(image_path)
```

LLM에 이미지 전달:
```python
full_prompt = [
    ("system", system_prompt),
    ("user", step_prompt_text, image_path),  # PNG 파일 경로
]
response = self.llm.generate(full_prompt)
```

### 14.2. Phase별 이미지 캡처 시점

| Phase | 캡처 시점 | LLM에 전달 |
|-------|----------|-----------|
| Phase 0 (Exploration) | NAVIGATE_TO 후 | 직전 after-action 이미지 |
| Phase 1 (Prediction) | 캡처 없음 | Phase 0 마지막 이미지 |
| Phase 2 (Rollout) | 매 action 후 | 직전 after-action 이미지 |
| Phase 3 (Extended Prediction) | 캡처 없음 | **Phase 0 마지막 이미지** (rollout 전 상태) |
| Phase 4 (Execution) | 매 action 후 | 직전 after-action 이미지 |

**핵심:** Phase 3에서는 **rollout 전 상태의 이미지**를 전달. `sim.restore()` 후이므로 Phase 0 마지막 이미지가 현재 환경 상태를 정확히 반영.

### 14.3. 카메라 Tracking 시스템

CA와 동일하게 `exploration_nav_tracking`으로 카메라 방향을 제어:

```python
"exploration_nav_tracking": {
    "oven":       "oven_xxxxx_0",      # 오븐 정면
    "fridge":     "electric_refrigerator_xxxxx_0",  # 냉장고 정면
    "countertop": "countertop_xxxxx_0",  # countertop 전체
}
```

- `_anchored_pos/ori`는 `NAVIGATE_TO` 실행 시 갱신
- navigate 없이 이미지를 캡처하면 카메라가 이전 위치에 머묾 → **Phase 0/2/4에서 NAVIGATE_TO 후 이미지 캡처가 기본 패턴**

### 14.4. LOOK_CLOSER 줌

```python
"exploration_look_targets": {
    "cake":  "cake_xxxxx_0",    # 오븐 문 통해 확대
    "cream": "cream_xxxxx_0",
}
"look_closer_focal_length": 50.0  # 약 2.8x 줌
```

### 14.5. Rollout 중 이미지 변화

Phase 2 rollout에서 **행동의 물리적 결과가 렌더링에 반영**:
- OPEN[oven] → 오븐 문 열림 + 케이크가 보이는 렌더링
- 이미지 변화 자체가 부수 효과의 시각적 단서를 제공

---

## 15. 수정이 필요할 수 있는 파일

CA와 동일한 패턴. **안전 원칙: 기존 파일은 "추가"만.**

### 위험도 중간 — 메타데이터/상태 등록

| 파일 | 수정이 필요한 경우 | 위험 |
|------|-------------------|------|
| `category_mapping.csv` | BDDL에서 사용하는 synset이 기존에 없을 때 | 행 추가는 안전 |
| `synsets.csv` | 새 오브젝트의 ability 정의 필요 시 | 행 추가는 안전 |
| `output_hierarchy_properties.json` | synset hierarchy에 새 노드 추가 시 | 기존 구조 미수정 |
| `domain_omnigibson.bddl` | 새 predicate 사용 시 | predicate 추가는 안전 |

### SF 전용 고려사항

- **오븐/냉장고 문 열림/닫힘 상태**: OmniGibson의 `Open` object state 사용. BDDL에서 `(not (open oven.n.01_1))` 등으로 초기 상태 정의.
- **Temperature state**: 케이크/크림의 온도 관련 state가 필요할 수 있음. 단, symbolic 시간 시스템으로 관리하므로 OG의 Temperature state를 직접 사용하지 않을 가능성 높음 → **time_system.py에서 자체 관리** 권장.
- **cake/cream 에셋**: BEHAVIOR-1K assets에 cake, cream 카테고리가 있는지 사전 확인 필요. 없으면 유사 에셋 대체 또는 custom.

---

## 16. Phase별 히스토리 포함 관계

각 Phase의 LLM 호출 시 포함되는 이전 컨텍스트:

| Phase | 포함하는 이전 컨텍스트 |
|-------|----------------------|
| Phase 0 각 step | Phase 0 내부 이전 step 전체 (thought + action + feedback) |
| Phase 1 | Phase 0 전체 탐색 히스토리 + 현재 이미지 |
| Phase 2 각 step | "This is a simulation" 안내 + Phase 2 내부 이전 step 전체 |
| Phase 3 | Phase 0 탐색 히스토리 + Phase 1 예측 텍스트 + Phase 2 rollout 히스토리 + 현재 이미지 |
| Phase 4 system prompt | Available Objects (정확한 이름) + Phase 0 요약 + Phase 3 전략 전문 + 시간 정보 |
| Phase 4 각 step | Phase 4 내부 이전 step (thought + action + result + time_step + 이벤트) |

**핵심:** Phase 3에서 **Phase 1 예측 + Phase 2 rollout 결과가 모두 포함**되어야 LLM이 자기 예측을 업데이트할 수 있음. CA의 Analysis & Tool Selection에서 Probe 0 + Stage 1을 모두 포함하는 것과 동일한 패턴.

### Phase 4 system prompt 상세 구조

```
┌─ System ──────────────────────────────────────────────────────┐
│ "You are a robot agent executing your strategy. Each action   │
│  takes 5 minutes. You have {remaining_steps} steps left."     │
├─ User ────────────────────────────────────────────────────────┤
│ === Available Objects ===                                      │
│ oven_xxxxx_0, electric_refrigerator_xxxxx_0, cake_601,        │
│ cream_602, countertop_xxxxx_0, chocolate_603, plate_604       │
│                                                               │
│ === Your Exploration Summary (Phase 0) ===                    │
│ - Oven exterior: 172°C, cooling at -3.2°C/step               │
│ - Fridge exterior: 8°C, warming at +0.5°C/step               │
│                                                               │
│ === Your Strategy (Phase 3) ===                               │
│ (Phase 3에서 LLM이 작성한 전략 전문)                           │
│                                                               │
│ === Available Actions ===                                     │
│ - NAVIGATE_TO[object]: Move near object                       │
│ - GRASP[object]: Pick up (Requires: hand empty)               │
│ - RELEASE[]: Put down (Requires: holding object)              │
│ - PLACE_ON_TOP[surface]: Place on surface (Requires: holding) │
│ - OPEN[container]: Open (Requires: hand empty)                │
│ - CLOSE[container]: Close (Requires: hand empty)              │
│ - TOUCH[surface]: Measure temperature                         │
│ - WAIT[]: Do nothing, 5 minutes pass                          │
│ - NEW_ACTION[name, tool, target]: Custom action               │
│ - DONE[]: Declare task complete                               │
│                                                               │
│ Current time: Step {N} ({N*5} minutes elapsed)                │
│ IMPORTANT: Use exact object names from Available Objects.     │
├─ Image: 직전 action의 after-action 이미지 ────────────────────┤
└───────────────────────────────────────────────────────────────┘
```

---

## 17. 오브젝트 이름 Fuzzy Matching

CA와 동일한 `_get_scene_object()` 패턴을 SF에서도 재사용:

| 순위 | 매칭 방식 | 예시 |
|------|----------|------|
| 1 | exact match (`obj.name == name`) | `"cake_601"` → `cake_601` |
| 2 | base name substring (`re.sub(r"_\d+$", "", obj.name)`) | `"cake"` → `cake_601` |

Phase 4에서 LLM이 `"oven"` 같은 자연어 이름을 사용할 수 있으므로, Available Objects 리스트 제공 + fuzzy matching이 필수.

---

## 18. WAIT action 구현 상세

CA에 없는 SF 전용 action. **시간만 경과시키고 아무 물리적 행동도 하지 않음.**

```python
# planner_sf.py 내 Phase 4 action dispatcher:
if action_name == "WAIT":
    events = self.time_system.advance_time()
    feedback = f"You waited. {self.time_system.step_duration_minutes} minutes passed."
    if events.get("event") == "power_restored":
        feedback += "\n⚡ The power has been restored! Appliances are coming back online."
    # 이미지는 현재 위치에서 다시 캡처 (변화가 있을 수 있음)
    image_path = self._capture_image(f"phase4_step{step}_after")
    return feedback, image_path
```

**설계 의도:**
- WAIT은 "아무것도 안 함"이 아니라 **"의도적으로 시간을 소비하는 전략적 선택"**
- 잔열로 케이크가 익을 때까지 기다리기, 정전 복구를 기다리기 등
- WAIT 중에도 환경은 변화 → 다음 step에서 TOUCH로 확인하면 다른 수치 반환

### CLOSE action의 물리적 효과

SF에서 CLOSE[oven]과 CLOSE[fridge]는 문을 닫지만, **이미 잃은 열/냉기는 돌아오지 않음**:
- CLOSE[oven] → `oven_door_open = False`로 설정하지만, 이미 급랭된 온도에서 closed rate(-12°C/step)으로 계속 감소
- CLOSE[fridge] → 동일. 이미 올라간 온도에서 closed rate(+1.5°C/step)으로 계속 상승
- 에이전트가 "닫으면 회복된다"고 오해할 수 있음 → **함정 중 하나**

---

## 19. 향후 구체화 필요 사항

1. **추가 SF 태스크 인스턴스 설계:** 케이크 외 다른 SF 태스크 (예: 연쇄 위험 관리, 화재 후 주방 정리)
2. **time_system.py 일반화:** 케이크 태스크의 수식을 다른 SF 태스크에도 재사용 가능한 형태로 추상화 (variable registry 패턴)
3. **Phase 5 자동화:** 예측 파싱 → sim 실행 → ground truth 비교 자동 스크립트
4. **Rollout 횟수 최적화:** 1회 vs 2~3회의 변별력 비교
5. **sim.save/restore 검증:** OmniGibson의 `og.sim.save()` / `og.sim.restore()`가 모든 상태를 완전히 복원하는지 확인
6. **cake/cream 에셋 확인:** BEHAVIOR-1K assets에 cake, whipped_cream 등 존재 여부 확인, 없으면 대체 에셋 결정
7. **NEW_ACTION handler에 time_state 조건 분기:** handler outcome이 현재 time_state에 따라 달라지는 구현 (예: `can_apply_cream()`이 False면 FAILURE)
