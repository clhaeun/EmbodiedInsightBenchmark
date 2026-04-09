# Scenario Flexibility (SF) 평가 프레임워크 및 Cake Task 확정 사양서

---

# Part 1: SF 프레임워크

---

## 1. 이론적 배경

### 1.1. 논문 정의

> **Scenario Flexibility:** 시나리오가 전개될 수 있는 다양한 방식을 고려하여 가능한 우발 상황(contingencies)을 파악하는 능력
> — Johnson, Karimi, Bengio et al., "Imagining and building wise machines" (Trends in Cognitive Sciences)

### 1.2. Ron 사례

Ron(정치 컨설턴트)은 후보의 승리 시나리오뿐 아니라 패배 시나리오까지 상상하고, 패배의 원인까지 사전에 분석한다. 핵심은 **실행 전에** 다양한 결과 가능성을 예측하는 것.

Ron의 상황이 SF 측정에 적합한 이유:
- **독립적 변수가 여러 개:** 경제 상황, 스캔들 발생, 상대 후보 전략 등이 독립적
- **각 변수 조합에서 최적 전략이 다름:** "경제 좋고 스캔들 없으면 A전략, 경제 나쁘고 스캔들 있으면 B전략"
- **사전에 다양한 가능성을 고려해야 robust한 전략이 나옴**

### 1.3. SF의 핵심 특성: Prospection

- **Prospection (SF):** "앞으로 무슨 일이 벌어질 수 있는가?" — 현재 → 미래
- **Retrospection (반성):** "왜 실패했는가?" — 과거 → 현재

기존 "실패 후 반성"(Reflexion, REFLECT)은 retrospection이지 SF가 아님.

### 1.4. CA와의 구분

| | CA (CATS) | SF |
|---|---|---|
| 축 | 유사성 (현재 ↔ 참조) | 시간 (현재 → 미래들) |
| 질문 | "이 상황이 무엇과 비슷한가?" | "이 상황이 어떻게 전개될 수 있는가?" |
| 정보 소스 | Demo 영상 (외부) | 관찰 + 비가역적 탐사 (자체) |
| 제약 | One-shot tool 선택 | Time budget + 비가역적 환경 변화 |
| 핵심 인지 | 구조적 매핑 | 미래 예측 + 외삽 + trade-off 추론 |

---

## 2. 정보의 3가지 층위

| 층위 | 발견 방법 | 예시 | Phase |
|---|---|---|---|
| **Layer 1 — Verbal** | LLM 상식 | "정전이면 오븐 꺼진다" | SF Prediction 1 |
| **Layer 2 — 비파괴 관찰** | NAVIGATE_TO, TOUCH(외벽) | 오븐 외벽 172°C, 냉각률 -2.0°C/3min (door closed) | Phase 0 |
| **Layer 3 — 비가역적 탐사** | OPEN, TOUCH(내부) | "열면 급랭한다!" | Phase 2 |
| **외삽 (SF 핵심)** | Layer 3에서 일반화 | "오븐이 그러면 냉장고도" | SF Prediction 2 |

**정답 전략 = Layer 1+2+3+외삽의 종합.** 어떤 Layer가 빠지면 다른 종류의 함정으로 빠진다.

---

## 3. SF 파이프라인 (확정)

```
Phase 0: 비파괴 관찰 (NAVIGATE_TO + TOUCH 외벽)
         — time_step 미소모, 환경 불변
         — ReAct 방식, 히스토리 누적
    ↓
SF Prediction 1: 초기 시나리오 예측 (verbal)
         — Part A: 변수 식별 (불확실한 요인 나열)
         — Part B: 시나리오 생성 (변수 조합, 조건부 IF~THEN)
         — 개수 자유, F1(정밀도×재현율)로 평가
    ↓
Phase 2: 비가역적 탐사 (OPEN, CLOSE, TOUCH, NAVIGATE_TO)
         — time_step 소모, 환경 변화, 되돌릴 수 없음
         — GRASP/PLACE/WAIT/NEW_ACTION 차단
         — ReAct 방식, Phase 0 + SF Pred 1 히스토리 포함
         — 최대 4 step
    ↓
SF Prediction 2: 확장 시나리오 예측 (verbal — SF 핵심 측정)
         — Part A: 변수 업데이트 (CONFIRMED/REVISED/STILL UNKNOWN + NEW)
         — Part B: 시나리오 업데이트 (CONFIRM/REVISE/DELETE + NEW, 외삽)
         — Part C: 구체적 Plan 5개를 action sequence로 출력
         — 각 plan이 "어떤 시나리오를 커버하는지" 명시
         — "Plans will be executed EXACTLY as written, NO mid-execution adjustment"
    ↓
Phase 4: One-shot 실행 (시스템이 plan들을 각각 실행)
         — 에이전트 추가 판단 없음 (LLM 호출 0회)
         — sim.save/restore는 시스템이 사용 (에이전트는 모름)
         — 불확실한 변수(power, cream 상태 등)의 각 Case에 대해 반복 실행
    ↓
Phase 5: 시스템 검증 (태스크 종료 후 별도 session)
    ↓
[평가]
```

### 핵심 설계 원칙

**1. sim.save/restore는 에이전트에게 없음**
- 에이전트 관점에서 모든 행동은 비가역적
- "관찰의 비용"이 진짜임 (오븐 열면 잔열 진짜 빠짐)
- sim.save/restore는 Phase 4에서 **시스템만** 사용 (여러 plan 실행용)

**2. Phase 4는 one-shot (ReAct 아님)**
- SF Prediction 2에서 만든 plan을 기계적으로 실행
- 중간에 분기/수정 없음
- SF(예측 능력)만 순수하게 측정, reactive adaptation 배제

**3. 불확실한 변수에 대해 Case별 실행**
- 에이전트가 모르는 변수(power 복구, cream 상태 등)를 시스템이 Case별로 바꿔가며 각 plan 실행
- 에이전트의 plan이 "어떤 Case에서든 괜찮은가" = robustness 측정

---

## 4. SF Prediction 형식

### SF Prediction 1 — 조건부 시나리오 (Phase 0 후)

Phase 0에서 얻은 정보는 외벽 온도/변화율뿐. 내부 상태를 모르므로 **구체적 action sequence 없이** "IF ~ THEN ~" 조건부 예측.

```
프롬프트 구조:

=== Part A: Variable Identification ===
"List ALL uncertain or hidden factors. For each:
 - VARIABLE: Name
 - CURRENT KNOWLEDGE: What you know / don't know
 - POSSIBLE VALUES: What it could be
 - IMPACT: How it affects the task
 - HOW TO DISCOVER: How to confirm"

=== Part B: Scenario Generation ===
"Combine variables into scenarios. For each:
 - SCENARIO: What happens
 - VARIABLES INVOLVED: Which from Part A
 - TRIGGER: What condition causes this
 - CONSEQUENCE: Impact on task
 - LIKELIHOOD: High / Medium / Low

Focus on scenarios where variables COMBINE to create 
unexpected outcomes.
List as many as you think are relevant."
```

### SF Prediction 2 — 시나리오 업데이트 + 구체적 Plan (Phase 2 후)

Phase 2에서 숨겨진 변수와 부수 효과를 경험함. SF Prediction 1의 시나리오를 **명시적으로 보여주고** 업데이트 요구.

```
프롬프트 구조:

=== Part A: Variable Updates ===
"For each variable from SF Prediction 1:
 CONFIRMED / REVISED / STILL UNKNOWN
 Are there NEW variables?"

=== Part B: Scenario Updates ===
"For each scenario from SF Prediction 1:
 CONFIRM / REVISE / DELETE — explain why.
 
 What NEW scenarios should be added?
 Did any observation reveal effects that might apply 
 to OTHER parts of the environment?"

=== Part C: Execution Plans (exactly 5) ===
"Create 5 plans as complete action sequences.
 Each plan should address DIFFERENT scenarios from Part B.

 CRITICAL: Plans will be executed EXACTLY as written 
 with NO opportunity to adjust mid-execution.

 Format per plan:
 Plan [A-E]: [strategy name]
   Addresses scenarios: [which scenarios]
   Step 1: ACTION[args]
   Step 2: ACTION[args]
   ...
   Expected outcome: [specific result]
   Key risk: [what could go wrong]

 RANKING: best to worst"
```

---

## 5. Phase별 프롬프트 상세

### Phase 0 — 비파괴 관찰

```
System:
"You are a robot agent in a kitchen during a power outage.
 [task instruction]
 
 This is the OBSERVATION phase. You may look around and 
 touch external surfaces to gather information.
 You may NOT open, grab, or manipulate any objects yet.

 Available actions:
 - NAVIGATE_TO[location]: Move to look at something
 - TOUCH[surface]: Measure surface temperature/properties
 - LOOK_CLOSER[object]: Zoom in for details
 - DONE_OBSERVING[]: Finish observation phase

 Respond: Thought: <reasoning> / Action: <ACTION>[<args>]"

User (매 step 누적):
"=== Observation History ===
 Step 1:
   Thought: ...
   Action: NAVIGATE_TO[kitchen]
   Result: (image only)
 Step 2:
   Thought: ...
   Action: TOUCH[oven_door]
   Result: Surface temperature: 172°C.
           Cooling rate (door closed): -2.0°C per 3 minutes.
           Power indicator LED: OFF.
 ..."
```

**TOUCH 피드백에서 "(door closed)" 명시** — Phase 2에서 열었을 때의 변화율과 비교 가능하게.

### Phase 2 — 비가역적 탐사

```
System:
"This is the INVESTIGATION phase.
 You may now interact with the environment to verify 
 your predictions and resolve uncertainties.

 IMPORTANT:
 - Actions in this phase PERMANENTLY change the environment 
   and CANNOT be undone.
 - Each action takes [step_duration] minutes.
 - Maximum 4 steps in this phase.
 - After this phase, you will create your final execution plans. 
   You will NOT be able to adjust plans mid-execution.

 Allowed: NAVIGATE_TO, OPEN, CLOSE, TOUCH
 NOT allowed: GRASP, PLACE, WAIT, NEW_ACTION

 When done: Action: DONE_INVESTIGATING[]"

User (매 step 누적):
"=== Your Observation Findings (Phase 0) ===
 [Phase 0 전체 히스토리]

 === Your Predictions (SF Prediction 1) ===
 [SF Prediction 1 전문]

 === Investigation History ===
 Step 1: OPEN[oven] → Oven door opened.
   Thought: ...
 Step 2: TOUCH[cake] → Temperature: 93°C, elasticity: 0.75...
   Thought: ...
 
 Current time: Step 2 of investigation
 (2 steps used of 4 maximum. X steps elapsed, Y remaining.)"
```

**Phase 2에서 GRASP를 차단하는 이유:**
- GRASP → APPLY_CREAM 하면 V5(뜨거운 cake+cream)를 **직접 경험**
- Phase 2에서 직접 경험하면 SF Prediction 2에서 **외삽할 필요 없음**
- GRASP 차단 → V5는 외삽으로만 도달 가능 → SF 측정 보존

---

## 6. 태스크 설계 원칙

### 6.1. 독립적 변수 축

SF가 유의미하게 측정되려면, 숨겨진 변수들이 **서로 독립적**이어야 한다.

```
나쁜 설계 (하나의 인과 체인):
  V2 → V1 → V5 → V3 → 결과 (일직선)
  → 최적 경로가 하나뿐
  → "다양한 시나리오"의 의미 없음

좋은 설계 (독립적 축):
  축1: cream 관련 (fridge 온도, whisk 상태, 수도 가용)
  축2: chocolate 관련 (kettle 온도, 녹이기 시간)
  축3: presentation 관련 (cabinet, 떨어질 위험)
  축4: baking 관련 (power 복구, 예열 시간)
  → 각 축이 독립 → 2^4 = 16가지 조합
  → 각 조합에서 최적 전략이 다름
  → 시나리오 다양성이 진짜 의미를 가짐
```

### 6.2. "보너스 트랙" 구조

```
[기본] cake 꺼내기 + 기본 완성 = base 점수
[트랙A] cream 장식 = +보너스 (fridge 관리 + whisk 필요)
[트랙B] chocolate 장식 = +보너스 (kettle로 녹이기 필요)
[트랙C] presentation = +보너스 (cabinet 접근 필요)
[트랙D] extra baking = +보너스 (power 복구 필요)

각 트랙이 2-4 step 소모.
총 가용 step에서 2-3개 트랙만 선택 가능, 전부는 불가.
→ "어떤 트랙 조합을 선택하느냐"가 전략.
→ 어떤 변수를 발견하고 고려했느냐에 따라 최적 조합 달라짐.
```

### 6.3. 관찰 비용 (Observation Cost)

환경을 관찰하기 위해 열면, 그 행위 자체가 환경을 악화시킨다:
- OPEN[oven] = 케이크 확인 (의도) + 잔열 급격 손실 (부수 효과)
- OPEN[fridge] = 크림 확인 (의도) + 냉기 급격 손실 (부수 효과)
- OPEN[wall_cabinet] = plate 접근 (의도) + 물건 낙하 위험 (부수 효과)

에이전트에게 **구체적으로 뭐가 변하는지 알려주지 않음.** "Actions permanently change the environment and cannot be undone."만 알림. 구체적 부수 효과 예측은 에이전트 몫.

### 6.4. 시나리오 개수: 자유 + F1 평가

```
시나리오 수 = 자유 (에이전트가 relevant하다고 판단하는 만큼)

평가:
  정밀도 = 실제 변수와 매칭되는 시나리오 수 / 총 뽑은 수
  재현율 = 실제 변수와 매칭되는 시나리오 수 / 총 숨겨진 변수 수
  SF_scenario = F1(정밀도, 재현율)

→ 20개 뽑고 3개 맞으면: F1 낮음
→ 5개 뽑고 3개 맞으면: F1 높음
→ 핵심을 정확히 짚어야 유리
```

---

## 7. 측정 지표

### 7.1. 주 지표

| 지표 | 가중치 | 측정 |
|---|---|---|
| **Robust score** | 0.25 | min(각 Plan의 최악 Case 점수) — worst-case |
| **Best plan SR** | 0.15 | 1순위 plan의 평균 점수 |
| **시나리오 커버리지 F1** | 0.20 | 변수 식별 + 시나리오 매칭의 F1 |
| **외삽 비율** | 0.20 | SF Pred 2 새 시나리오 중 정확한 것 / 미경험 변수 |
| **Plan 다양성** | 0.10 | 5개 plan이 서로 다른 변수 조합을 커버하는가 |
| **Ranking 정확도** | 0.10 | 1순위 plan이 실제로 가장 robust한가 |

### 7.2. 보조 지표

| 지표 | 측정 |
|---|---|
| 변수 조합 사고 | 단일 변수만? 교차 시나리오도? |
| 시간 추정 정확도 | 수치적 추정이 실제와 가까운가 |
| 관찰 비용 인식 | "열면 환경 악화"를 Phase 1에서 이미 예측했는가 |
| Phase 1→2 개선도 | 탐사 후 시나리오가 얼마나 풍부/정확해졌는가 |
| Investigation 효율성 | 최소 step으로 핵심 변수를 발견했는가 |

---

## 8. Symbolic 시간 시스템

### 8.1. 기본 구조

- 매 action → time_step += 1 (= step_duration_minutes 경과)
- WAIT action: 아무것도 안 하고 시간 경과
- Phase 0: time_step 미소모 (비파괴 관찰)
- Phase 2~4: time_step 소모 (환경 변화)
- 총 max_steps 후 태스크 종료

### 8.2. CA와의 패턴 일치

CA에서 확립된 "symbolic 과정 + 물리적 결과" 패턴과 동일:
- 내부 판정: lookup table / 수식 (에이전트는 모름)
- 에이전트 관찰: IsaacSim 렌더링 이미지 + 센서 피드백 텍스트
- 결과: 계산된 상태를 IsaacSim에서 물리적으로 반영

### 8.3. CLOSE 누적 손실 보존

spec 규칙: "닫아도 이미 빠진 열은 돌아오지 않음"

```python
def close_oven(self):
    self.oven_door_open = False
    self.oven_door_closed_at = self.time_step

def get_oven_temp(self):
    t = self.time_step
    base = max(room_temp, initial_temp - cooling_closed * t)
    if self.oven_door_open:
        loss = cooling_opened * (t - self.oven_door_opened_at)
        return max(room_temp, base - loss)
    elif self.oven_door_opened_at is not None:
        open_duration = self.oven_door_closed_at - self.oven_door_opened_at
        accumulated_loss = cooling_opened * open_duration
        return max(room_temp, base - accumulated_loss)
    return base
```

---

## 9. Embodiedness

| 단계 | Embodiedness |
|---|---|
| Phase 0 관찰 | NAVIGATE: IsaacSim 렌더링 / TOUCH: 센서 텍스트 |
| SF Prediction 1, 2 | Verbal (텍스트 출력) |
| Phase 2 탐사 | **물리적** — OPEN[oven]으로 문 실제 열림 |
| Phase 4 실행 | **물리적** — action 결과가 IsaacSim에서 구현 |
| Phase 5 검증 | **물리적** — 예측을 IsaacSim에서 실행 검증 |
| Observation | IsaacSim 카메라 렌더링이 primary |

---

# Part 2: Cake Completion Task (정전 시 케이크 완성)

---

## 10. 태스크 개요

| 항목 | 내용 |
|---|---|
| 측정 대상 | Scenario Flexibility (SF) |
| 씬 | house_single_floor (BEHAVIOR-1K) — Kitchen |
| 로봇 | Tiago (dual-arm mobile manipulator) |
| Instruction | "You were making a cake in the kitchen when the power went out. Guests arrive in 60 minutes. Complete the cake as best you can — the guests are expecting a decorated cake." |
| 시간 시스템 | Symbolic — 매 action 3분, 총 20 step (60분) |

---

## 11. 씬 구성 및 오브젝트

| 오브젝트 | 위치 | 초기 상태 | 역할 |
|---|---|---|---|
| oven | kitchen | 꺼짐, 문 닫힘, 내부 180°C | 케이크 들어있음 |
| cake (casserole) | oven 내부 | ~73% 익음, 보이지 않음 | 주요 대상 |
| fridge | kitchen | 꺼짐, 문 닫힘, 내부 5°C | cream 들어있음 |
| cream_carton | fridge 내부 | 5°C, 액상 | 장식 재료 (휘핑 필요) |
| chocolate_bar | countertop | 고체 상태 | 장식 재료 (녹이기 필요) |
| kettle | countertop | 75°C 뜨거운 물 | 초콜릿 녹이기용 |
| bowl | countertop 또는 cabinet | 상온 | 초콜릿 녹이기용 용기 |
| whisk | sink 위 | 더러움 (잔여물) | cream 휘핑용 |
| sink | kitchen | 수도 — 물 나올 수도 안 나올 수도 | whisk 세척용 |
| plate (일반) | countertop | 상온 | 기본 plate |
| presentation_plate | wall_cabinet 안 | 보이지 않음 | 보너스 plate |
| wall_cabinet | kitchen 벽면 | 문 닫힘 | 열면 물건 낙하 위험 |
| dishtowel | countertop | 마른 상태 | 다용도 |

---

## 12. 숨겨진 변수 (독립적 축별 분류)

### 축 1: Oven / Cake (잔열 + 익힘)

| # | 변수 | 발견 방법 | 핵심 |
|---|---|---|---|
| V1 | 케이크 익힘도 (~73%) | OPEN[oven] + TOUCH[cake] | POMDP — 열어봐야 앎 |
| V2 | 오븐 급랭 (열면 냉각률 급증) | Phase 2에서 OPEN 후 TOUCH[oven_interior] 비교 | 부수 효과 |

### 축 2: Fridge / Cream (냉기 + 크림 상태)

| # | 변수 | 발견 방법 | 핵심 |
|---|---|---|---|
| V3 | 냉장고 급온 (열면 승온률 급증) | **V2에서 외삽** | SF 핵심 (외삽) |
| V5 | 뜨거운 cake + cream = 녹음 | 물리 추론 또는 V1에서 외삽 | 변수 조합 |
| V9 | cream은 휘핑 필요 (whisk) | NAVIGATE_TO[sink] + TOUCH[whisk] → 더러움 | 추가 준비 |
| V10 | 수도 불가 (펌프 정전) | NEW_ACTION[WASH, whisk, sink] 시도 시 발견 | whisk 경로 차단 가능 |

### 축 3: Chocolate (녹이기)

| # | 변수 | 발견 방법 | 핵심 |
|---|---|---|---|
| V7 | chocolate은 녹여야 장식 가능 | Phase 0에서 chocolate_bar 관찰 (고체) | 추가 준비 필요 |
| V8 | kettle 물이 시간이 지나면 식음 | TOUCH[kettle] → 온도 확인 + 시간 경과 관찰 | 시간 창 |

### 축 4: Presentation (접시)

| # | 변수 | 발견 방법 | 핵심 |
|---|---|---|---|
| V11 | 예쁜 plate가 wall_cabinet 안 | NAVIGATE_TO[wall_cabinet] → 관찰 | 보너스 옵션 |
| V12 | cabinet 열면 물건 낙하 위험 | OPEN[wall_cabinet] 시 발생 | 부수 효과 + 시간 손실 |

### 축 5: Power (정전 복구)

| # | 변수 | 발견 방법 | 핵심 |
|---|---|---|---|
| V4 | 정전 복구 시점 | 기다려봐야 발견 | 불확실 — Case A/B/C |
| V6 | 오븐 예열 시간 | 복구 후 발견 | 시간 예산에 영향 |

---

## 13. 시간 시스템 수식

```
step_duration_minutes = 3
max_steps = 20 (60분)

=== 축 1: Oven ===
oven_temp (closed):  max(23, 180 - 8*t)
oven_temp (opened):  max(23, oven_temp(t_open) - 20*(t - t_open))
  → "(door closed)" 피드백에서 -2.0°C/3min 제시
  → 열면 급격히 빨라짐 → V2
  → CLOSE해도 누적 손실 보존

cake_doneness: min(100, 73 + Σ(max(0, oven_temp(i) - 100) * 0.02))
cake_temp_when_removed: oven_temp at removal step
cake_cooling_on_plate: -10°C/step

=== 축 2: Fridge ===
fridge_temp (closed): min(30, 5 + 1.0*t)
fridge_temp (opened): min(30, fridge_temp(t_open) + 3.5*(t - t_open))
cream_melt_threshold: 21°C
cream_warming_outside: +0.5°C/step (꺼낸 후)

=== 축 3: Chocolate ===
kettle_temp: max(23, 75 - 3*t)
chocolate_melt_possible: kettle_temp > 50°C
  → step ~9 이후 불가 (75-27=48°C < 50°C)

=== 축 4: Presentation ===
cabinet_fall_risk: True (열면 glass 낙하)
cleanup_cost: 1 step

=== 축 5: Power ===
power_restore: 불확실 (시스템이 Case별 실행)
  Case A: step 6 (빠른 복구)
  Case B: step 12 (중간 복구)
  Case C: 복구 없음
oven_preheat_steps: 3 (복구 후 180°C까지)
```

---

## 14. TOUCH 피드백 형식

```
TOUCH[oven_door]:
  "Surface temperature: 172°C. 
   Cooling rate (door closed): -2.0°C per 3 minutes.
   Power indicator LED: OFF."

TOUCH[fridge_door]:
  "Surface temperature: 8°C.
   Warming rate (door closed): +0.3°C per 3 minutes.
   Compressor: silent. Power indicator: OFF."

TOUCH[cake]:
  "Internal temperature: 93°C.
   Surface elasticity coefficient: 0.73 on 0-1 scale 
   (0=raw batter, 1=fully baked).
   The cake is structurally stable and edible at this level."

TOUCH[kettle]:
  "Surface temperature: 72°C. Contains hot water.
   Cooling rate: -3°C per 3 minutes."

TOUCH[whisk]:
  "Surface: sticky residue from previous use. Needs washing."

TOUCH[countertop]:
  "Surface temperature: 23°C (room temperature)."

TOUCH[oven_interior] (Phase 2에서만, OPEN 후):
  "Temperature: {current_temp}°C"
```

---

## 15. 점수 구조

### 기본 점수

| 요소 | 조건 | 점수 |
|---|---|---|
| doneness ≥ 90% | power 복구 + 추가 baking 필요 | 35점 |
| 80% ≤ doneness < 90% | 잔열 보존 잘하면 도달 | 25점 |
| 70% ≤ doneness < 80% | 기본 (잔열만) | 15점 |
| 시간 내 완료 | 20 step 이내 | 20점 |

### 트랙별 보너스

| 트랙 | 최고 보너스 | 조건 | 차선 | step 소요 |
|---|---|---|---|---|
| Cream (휘핑) | 25점 | 깨끗한 whisk + 휘핑 | 15점(더러운 whisk) / 10점(액상) | 1-3 step |
| Chocolate (녹임) | 25점 | kettle로 녹여서 장식 | 10점(고체 조각 올리기) | 1-3 step |
| Presentation | 10점 | presentation_plate 사용 | 0점(일반 plate) | 2-3 step |

**최대 가능 점수: 35+20+25+25+10 = 115점 (cap 100)**
→ 전부 다 하는 건 시간적으로 불가능. 조합 선택 필수.

---

## 16. 경쟁 전략들

```
전략 1: "Cream + Chocolate" (장식 극대화)
  cake 즉시 꺼내기 + 식히기
  kettle로 chocolate 녹이기
  whisk로 cream 휘핑 + 도포
  → 15+20+25+25 = 85점
  핵심 변수: V3(fridge), V7(kettle), V9(whisk), V8(kettle 시간)

전략 2: "Cream + Presentation" (크림 + 예쁜 접시)
  presentation plate 꺼내기
  cake 꺼내서 예쁜 plate에 놓기
  cream 휘핑 + 도포
  chocolate는 조각만
  → 15+20+25+10+10 = 80점
  핵심 변수: V3(fridge), V9(whisk), V11(cabinet), V12(낙하)

전략 3: "Power Gamble + Bake + Chocolate" (추가 baking)
  power 복구 기다리기 + 추가 baking
  kettle로 chocolate 녹이기
  cream은 액상
  → Case A: 35+20+10+25 = 90점 / Case C: 15+20+10+25 = 70점
  핵심 변수: V4(power), V7(kettle)

전략 4: "안전 올라운드" (위험 최소화)
  cake 즉시 꺼내기
  chocolate 조각만 (녹이기 생략)
  cream 액상 (휘핑 생략)
  일반 plate
  → 15+20+10+10 = 55점 (안전하지만 낮음)
  핵심 변수: 거의 없음

전략 5: "All-in Decoration" (장식 + 접시)
  presentation plate + cream 휘핑 + chocolate 녹이기
  cake는 잔열만
  → 15+20+25+25+10 = 95점 (시간 안에 되면)
  핵심 변수: 거의 전부 (V3,V7,V8,V9,V11,V12)
  리스크: step 부족, 하나라도 실패하면 와르르
```

---

## 17. 변수-전략 매트릭스

```
           │ V2  V3  V4  V5  V7  V8  V9  V10 V11 V12
───────────┼──────────────────────────────────────────
전략1 크초 │  ✅  ✅          ✅  ✅  ✅  ✅
전략2 크접 │  ✅  ✅              ✅  ✅  ✅  ✅
전략3 파초 │  ✅      ✅      ✅  ✅
전략4 안전 │  ✅
전략5 올인 │  ✅  ✅      ✅  ✅  ✅  ✅  ✅  ✅  ✅
```

각 전략이 **다른 변수 조합에 의존** → 어떤 변수를 발견하고 고려했느냐에 따라 최적 전략 달라짐.

---

## 18. Case별 실행 구조 (Phase 4)

```
시스템 동작:
  Phase 2 종료 시점의 환경 상태 저장
  
  for plan in [A, B, C, D, E]:
    for case in [Case_A(power@6), Case_B(power@12), Case_C(no_power)]:
      for cream_state in [fresh, spoiled]:  # cream 불확실성
        sim.restore(post_investigation)
        config.power_restore = case
        config.cream_spoiled = cream_state
        execute(plan.steps)  # 기계적 실행, LLM 호출 없음
        record_score()

결과: 5 plans × 3 power cases × 2 cream states = 30개 시뮬레이션
```

---

## 19. 함정 구조

| 함정 | SF 결핍 | 어떤 변수를 놓치면 빠지는가 |
|---|---|---|
| 즉시 모두 열기 | 관찰 비용 미인식 | V2, V3 |
| 오븐만 집착 (추가 baking) | 시간 창 미관리 | V3, V8 (cream/kettle 시간) |
| 더러운 whisk 사용 | 품질 trade-off 미인식 | V9, V10 |
| Cabinet 열었다가 낙하 | 부수 효과 미예측 | V12 |
| 수도에서 물 안 나오는데 씻기 시도 | 정전 연쇄 효과 미예측 | V10 |
| kettle이 식은 후 초콜릿 녹이기 시도 | 시간 창 미관리 | V8 |
| Cream 상한 건 모르고 cream 전략 올인 | 불확실성 미고려 | cream 불확실성 |

---

## 20. SF 수준별 에이전트 프로파일

### SF = 낮음

```
Phase 0: oven과 fridge만 확인
SF Pred 1: "오븐에서 꺼내서 장식하면 된다" (변수 2개)
Phase 2: OPEN[oven] → TOUCH[cake] → "더 익혀야지"
SF Pred 2: Plan 5개 모두 "baking 시간" 변종. kettle/whisk/cabinet 모름.
결과: 50-60점 (chocolate 고체 조각만, cream 액상만)
```

### SF = 중간

```
Phase 0: oven, fridge, countertop 확인. kettle 발견.
SF Pred 1: 변수 5-6개, 기본 시나리오들
Phase 2: OPEN[oven] → V2 발견 → V3 외삽 시도
SF Pred 2: cream+chocolate 전략 포함, 하지만 whisk/cabinet 미고려
결과: 70-85점 (cream 액상 + chocolate 녹임)
```

### SF = 높음

```
Phase 0: 모든 오브젝트 확인. kettle, whisk, sink, cabinet 모두 발견.
SF Pred 1: 변수 8-10개, 조합 시나리오 포함, 시간 창 추정
Phase 2: V2 발견 → V3 외삽 성공 → V10 예측 ("수도도 정전?")
SF Pred 2: 5개 Plan이 각각 다른 변수 조합 커버.
         cream 불확실성에 대한 contingency 포함.
         kettle 시간 창 고려한 chocolate 타이밍 포함.
결과: 85-95점 (최적 조합 + robust 대비)
```

---

## 21. 확정된 설계 결정 요약

| 항목 | 결정 |
|---|---|
| 측정 대상 | **Scenario Flexibility (SF)** |
| sim.save/restore | **에이전트에게 없음.** 시스템만 Phase 4에서 사용 |
| Phase 4 | **One-shot** (ReAct 아님). Plan을 기계적으로 실행 |
| 시간 시스템 | Symbolic — 3분/step, 20 step, 60분 |
| Phase 0 | time_step 미소모. NAVIGATE_TO + TOUCH(외벽)만 |
| Phase 2 | time_step 소모, 비가역. 최대 4 step. GRASP/NEW_ACTION 차단 |
| 시나리오 개수 | 자유 (F1 평가). Plan은 5개 고정 |
| SF Prediction 형식 | Part A(변수) → Part B(시나리오) → Part C(Plan + 시나리오 연결) |
| 숨겨진 변수 | 5개 축, 12개 변수 (독립적) |
| 점수 구조 | 보너스 트랙 방식 — 2-3개 트랙 선택, 전부는 불가 |
| 경쟁 전략 | 최소 4-5개 (각 80-95점 범위) |
| 불확실 변수 | power 복구 (Case A/B/C), cream 상태 (fresh/spoiled) |
| Instruction | "the guests are expecting a decorated cake" (장식 중요 힌트, 구체적 점수 미공개) |
| TOUCH[cake] | "structurally stable and edible at this level" (먹을 수 있다는 물리적 사실) |
| Instruction 언어 | **영어** (CA v2와 동일) |
| Config 형식 | **Python dict** (CA와 동일) |
| CLOSE 후 온도 | **누적 손실 보존** (회복 없음) |
| Phase 2 피드백 | doneness% 미제공, elasticity는 스케일 설명만 |
| "(door closed)" 힌트 | Phase 0 TOUCH에 포함 — 열었을 때와 비교 가능 |
| Embodiedness | observation = IsaacSim 렌더링, 검증 = IsaacSim 물리 |
