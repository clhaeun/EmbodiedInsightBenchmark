# Scenario Flexibility (SF) 평가 프레임워크 — Dinner Table Setting Task 확정 사양서

---

# Part 1: SF 파이프라인 (Cake Task에서 계승)

---

## 1. 측정 대상

**Scenario Flexibility (SF):** 시나리오가 전개될 수 있는 다양한 방식을 고려하여 가능한 우발 상황(contingencies)을 파악하는 능력.

핵심은 **실행 전에** 다양한 결과 가능성을 예측하는 것 (Prospection).

## 2. SF 파이프라인

```
Phase 0: 비파괴 관찰 (NAVIGATE_TO + 외부 관찰)
         — time_step 미소모, 환경 불변
         — 에이전트가 IsaacSim 카메라 이미지를 받음
         — ReAct 방식, 히스토리 누적
    ↓
SF Prediction 1: 초기 시나리오 예측 (verbal)
         — Part A: 변수 식별
         — Part B: 시나리오 생성
         — 개수 자유, F1으로 평가
    ↓
Phase 2: 비가역적 탐사 (OPEN, CLOSE, NAVIGATE_TO)
         — time_step 소모, 환경 변화 (문 열림 등)
         — GRASP/PLACE 차단
         — 에이전트가 열린 container 내부 이미지를 받음
         — ReAct 방식, 최대 4 step
    ↓
SF Prediction 2: 확장 시나리오 예측 + Plan 5개
         — Part A: 변수 업데이트
         — Part B: 시나리오 업데이트 + 외삽
         — Part C: Plan 5개 (action sequence, one-shot)
    ↓
Phase 4: One-shot 실행
         — 시스템이 Plan 5개를 각각 Case별로 기계적 실행
         — LLM 호출 0회
         — sim.save/restore는 시스템만 사용
    ↓
[평가]
```

## 3. 실험 조건 (Conditions)

| Condition | 구조 | 측정 대상 |
|---|---|---|
| **Condition 1: Full SF** | Phase 0 → SF Pred 1 → Phase 2 → SF Pred 2 → One-shot 실행 | **순수 SF** |
| **Condition 3: No Prediction** | Phase 0/2 없이, 바로 ReAct 실행 (사전 예측 없음) | 순수 reactive baseline |
| **Condition 4: Oracle** (선택) | 모든 Case 정보를 사전에 제공 → Plan 작성 → One-shot 실행 | 이론적 ceiling |

**핵심 비교:** Condition 1 vs Condition 3의 delta = SF prediction의 기여분.
- delta가 크면: SF가 태스크 성공에 중요 → 벤치마크가 SF를 유의미하게 측정
- delta가 작으면: 태스크 재설계 필요

---

# Part 2: Dinner Table Setting Task (정전 없는 테이블 세팅)

---

## 4. 태스크 개요

| 항목 | 내용 |
|---|---|
| 측정 대상 | Scenario Flexibility (SF) |
| 씬 | BEHAVIOR-1K — Dining Room |
| 로봇 | Tiago (dual-arm mobile manipulator) |
| Instruction | "You need to set the dining table for 4 guests as elegantly as possible. Guests arrive soon. Everything you need is somewhere in this dining room." |
| 시간 시스템 | Symbolic — 매 action 1 step, 총 15 step |

### Instruction 설계 의도

- "as elegantly as possible" → 고급 옵션이 더 좋다는 것을 상식적으로 추론 가능
- "Guests arrive soon" → 시간 제약 존재 (15 step으로 전부 불가)
- "Everything you need is somewhere in this dining room" → 물건 탐색의 동기 부여
- 구체적 점수표는 미공개

---

## 5. 씬 구성 및 오브젝트

| 오브젝트 | 위치 | 초기 상태 | 역할 | 비고 |
|---|---|---|---|---|
| dining_table | 방 중앙 | 비어있음 | 세팅 대상 | 4인용 |
| chair × 4 | 테이블 주변 | 배치됨 | 좌석 | 하나를 옮기면 좌석 부족 |
| **cabinet_A** | 벽면 왼쪽, 상단 | 문 닫힘 | 안: fancy_plate × 4 + serving_bowl(앞쪽) | 상단 = 고급 물건 힌트 |
| **cabinet_B** | 벽면 왼쪽, 하단 | 문 닫힘 | 안: regular_plate × 4 | 바로 접근 가능 |
| **drawer_C** | 사이드보드 상단 | 닫힘 | 안: silver_cutlery set | 열면 drawer_D와 간섭 |
| **drawer_D** | 사이드보드 하단 | 닫힘 | 안: regular_cutlery + napkin × 4 | drawer_C 열려있으면 열 수 없음 |
| **shelf_E** | 벽면 오른쪽, 높은 위치 | 보임 (열려있음) | wine_glass × 4 | 로봇 직접 도달 불가, 의자 필요 |
| **countertop** | 벽면 오른쪽 | 보임 | water_glass × 4 + candle | 바로 접근 가능 |
| **floor_box** | 바닥 구석 | 뚜껑 닫힘 | 안: tablecloth + flower_vase | 열어야 내용물 보임 |

### 오브젝트 배치도 (개략)

```
        [shelf_E: wine_glass×4 (높음)]
        [countertop: water_glass×4, candle]

[cabinet_A (상단)]           [dining_table]           [사이드보드]
[cabinet_B (하단)]           [chair×4]                [drawer_C (상)]
                                                      [drawer_D (하)]

                    [floor_box (바닥 구석)]
```

---

## 6. 숨겨진 변수 (5개 축)

### 축 1: Plate 선택 (cabinet_A vs cabinet_B)

| # | 변수 | 발견 방법 | 핵심 |
|---|---|---|---|
| V1 | cabinet_A 안에 fancy_plate가 있지만, 앞에 serving_bowl이 막고 있음 | Phase 2에서 OPEN[cabinet_A] → 이미지로 확인 | POMDP — 열어야 보임 |
| V2 | serving_bowl을 꺼내면 countertop 공간을 차지 | V1 발견 후 추론 | 공간 점유 부수효과 |

**시각적 단서 (Phase 0):**
- cabinet_A가 상단에, cabinet_B가 하단에 있는 것이 이미지에서 보임
- "상단 캐비닛 = 더 좋은 물건"은 LLM 상식으로 추론 가능
- 문이 닫혀있으므로 안의 구체적 상태는 모름

**Phase 2에서 발견 시 이미지:**
- cabinet_A를 열면: serving_bowl이 앞에, fancy_plate가 뒤에 있는 것이 보임
- cabinet_B를 열면: regular_plate 4개가 바로 접근 가능한 것이 보임

### 축 2: Cutlery 선택 (drawer_C vs drawer_D)

| # | 변수 | 발견 방법 | 핵심 |
|---|---|---|---|
| V3 | drawer_C에 silver_cutlery가 있음 | Phase 2에서 OPEN[drawer_C] → 이미지로 확인 | POMDP |
| V4 | drawer_C를 열면 drawer_D가 물리적으로 열리지 않음 | Phase 2에서 경험 또는 시각적 추론 | 물리적 간섭 |

**시각적 단서 (Phase 0):**
- 두 서랍이 같은 사이드보드에 위아래로 있는 것이 보임
- 서랍 간 간격이 좁은 것이 보임 → "하나를 열면 다른 하나에 영향"을 추론 가능

**물리적 간섭 구현 (scripted):**
```python
def open_drawer_C(self):
    self.drawer_C_open = True
    self.drawer_D_accessible = False  # 간섭

def close_drawer_C(self):
    self.drawer_C_open = False
    self.drawer_D_accessible = True  # 복원
```

### 축 3: Glass 선택 (shelf_E vs countertop)

| # | 변수 | 발견 방법 | 핵심 |
|---|---|---|---|
| V5 | shelf_E의 wine_glass에 도달하려면 의자가 필요 | Phase 0에서 이미지로 높이 비교 → 추론 | 시각적 추론 |
| V6 | 의자를 옮기면 테이블 좌석이 3개로 감소 | V5에서 추론 | 자원 trade-off |

**시각적 단서 (Phase 0):**
- shelf_E가 높은 위치에 있고 wine_glass가 보이는 이미지
- 로봇(Tiago)의 높이와 선반 높이의 차이가 이미지에서 판단 가능
- "의자를 가져오면 닿을 수 있다"는 LLM 추론

**이미지로 자명한 이유:** wine_glass가 선반 위에 **보이지만 닿을 수 없다**는 것은 이미지에서 명확함. 텍스트 피드백 불필요.

### 축 4: Centerpiece + Tablecloth (floor_box)

| # | 변수 | 발견 방법 | 핵심 |
|---|---|---|---|
| V7 | floor_box 안에 tablecloth + flower_vase가 있음 | Phase 2에서 OPEN[floor_box] → 이미지로 확인 | POMDP |
| V8 | tablecloth를 깔려면 테이블이 비어있어야 함 | V7 발견 후 추론 | 순서 의존성 |

**시각적 단서 (Phase 0):**
- floor_box가 바닥 구석에 닫혀있는 것이 보임
- 안은 보이지 않음

**SF 핵심 — 순서 의존성:**
- tablecloth를 나중에 발견하면 "이미 테이블에 놓은 물건을 전부 치우고 → 깔고 → 다시 놓아야 함" → step 낭비
- **가장 먼저** floor_box를 열어보고 tablecloth를 깔아야 추가 비용 없음
- 이 순서 추론이 SF의 핵심 측정 포인트

### 축 5: 순서 전략 (cross-axis)

| # | 변수 | 발견 방법 | 핵심 |
|---|---|---|---|
| V9 | cabinet_A의 "앞 물건이 뒤 물건을 막는" 패턴 | Phase 2에서 cabinet_A 열어서 경험 | 패턴 학습 |
| V10 | floor_box도 같은 패턴 (위 물건이 아래를 막음) | **V9에서 외삽** | **SF 핵심 (외삽)** |

**외삽 구조:**
- Phase 2에서 cabinet_A를 열어서 "serving_bowl이 fancy_plate를 막고 있다"를 경험
- floor_box는 열어보지 않았다면, "여기도 안에 물건이 겹쳐있을 수 있다 → 위의 것을 먼저 꺼내야 아래에 접근 가능"을 외삽
- 시각적 유사성 기반: "닫힌 container 안에 물건이 겹쳐있는" 패턴

---

## 7. Case 변수 (시스템이 바꿔가며 실행)

에이전트가 Phase 2에서 열어보지 않은 container의 상태를 시스템이 Case별로 변경.

### cabinet_A 내부 상태

| Case | 상태 | 영향 |
|---|---|---|
| Case A1 | fancy_plate 4개 + 앞에 serving_bowl이 막음 | bowl 치워야 접근 → +2 step |
| Case A2 | fancy_plate 4개, 바로 접근 가능 | 추가 비용 없음 |
| Case A3 | fancy_plate 2개만 (나머지 없음) | 불완전 세팅 → cabinet_B 보충 필요 |

### floor_box 내부 상태

| Case | 상태 | 영향 |
|---|---|---|
| Case B1 | tablecloth(위) + flower_vase(아래) | tablecloth 먼저 꺼내야 vase 접근 |
| Case B2 | tablecloth만 (vase 없음) | 센터피스를 candle로 대체해야 함 |

### Phase 4 실행 매트릭스

```python
for plan in [Plan_A, Plan_B, Plan_C, Plan_D, Plan_E]:
    for cabinet_case in [A1, A2, A3]:
        for box_case in [B1, B2]:
            sim.restore(post_investigation)
            config.cabinet_A_state = cabinet_case
            config.floor_box_state = box_case
            execute(plan.steps)  # 기계적 실행, LLM 호출 0회
            record_score()

# 총: 5 plans × 3 cabinet × 2 box = 30 시뮬레이션
```

---

## 8. 시간 시스템

```
step_budget = 15
Phase 0: step 미소모 (관찰만)
Phase 2: step 소모 (최대 4 step) → Phase 4에서 남은 step = 15 - Phase 2 사용분

Action별 step 비용:
  OPEN[container]:     1 step
  CLOSE[container]:    1 step
  GRASP[object]:       1 step
  PLACE[object, loc]:  1 step
  NAVIGATE_TO[loc]:    Phase 0에서는 0 step, Phase 4에서는 1 step

Phase 2 예시 (3 step 사용):
  Step 1: OPEN[cabinet_A]         → 내부 이미지 제공
  Step 2: OPEN[floor_box]         → 내부 이미지 제공
  Step 3: OPEN[drawer_C]          → 내부 이미지 제공
  → Phase 4 남은 step: 12

Phase 2 예시 (1 step 사용):
  Step 1: OPEN[cabinet_A]         → 내부 이미지 제공
  → Phase 4 남은 step: 14
```

---

## 9. 점수 구조

### 기본 세팅 점수

| 요소 | 기본 옵션 | 점수 | 고급 옵션 | 점수 |
|---|---|---|---|---|
| Plate (4인분) | regular_plate × 4 | 10점 | fancy_plate × 4 | 20점 |
| | | | fancy_plate × 2 + regular × 2 (혼합) | 13점 |
| Cutlery (4인분) | regular_cutlery | 8점 | silver_cutlery | 15점 |
| Glass (4인분) | water_glass × 4 | 8점 | wine_glass × 4 | 18점 |
| Napkin (4인분) | 없음 0점 | 0점 | napkin × 4 | 5점 |
| Centerpiece | candle | 5점 | flower_vase | 8점 |
| Tablecloth | 없음 | 0점 | tablecloth 깔려있음 | 10점 |
| 좌석 | 의자 4개 제자리 | 5점 | 의자 3개 (1개 옮겨서 안 돌려놓음) | 0점 |

### 점수 요약

| 구성 | 합계 |
|---|---|
| 전부 기본 (plate + cutlery + glass + candle + 좌석) | 36점 |
| 전부 고급 (fancy + silver + wine + napkin + tablecloth + vase + 좌석) | 81점 |
| 15 step으로 전부 고급은 **불가능** | → 조합 선택이 전략 |

### 감점 사항

| 상황 | 감점 |
|---|---|
| Plan의 action이 존재하지 않는 object를 참조 (Case 불일치) | 해당 step 이후 전부 실패 |
| 의자를 옮기고 안 돌려놓음 | 좌석 점수 0 |
| 4인분 미달 (plate 3개 등) | 비례 감점 |

---

## 10. Step 비용 분석

### 각 축별 action sequence와 step 비용

**축 1a: Regular plate (cabinet_B)**
```
OPEN[cabinet_B] → GRASP[plate] → PLACE[plate, table] × 4 → CLOSE[cabinet_B]
= 1 + (1+1)×4 + 1 = 10 step
```

**축 1b: Fancy plate (cabinet_A, Case A1 — blocked)**
```
OPEN[cabinet_A] → GRASP[serving_bowl] → PLACE[bowl, countertop] →
GRASP[plate] → PLACE[plate, table] × 4 → CLOSE[cabinet_A]
= 1 + 1+1 + (1+1)×4 + 1 = 12 step
```

**축 1c: Fancy plate (cabinet_A, Case A2 — accessible)**
```
OPEN[cabinet_A] → GRASP[plate] → PLACE[plate, table] × 4 → CLOSE[cabinet_A]
= 1 + (1+1)×4 + 1 = 10 step
```

**축 2a: Regular cutlery + napkin (drawer_D)**
```
OPEN[drawer_D] → GRASP[cutlery_set] → PLACE[cutlery, table] →
GRASP[napkin_set] → PLACE[napkin, table] → CLOSE[drawer_D]
= 1 + 1+1 + 1+1 + 1 = 6 step
```
참고: cutlery_set과 napkin_set은 각각 4인분을 한 번에 잡을 수 있는 묶음으로 처리.

**축 2b: Silver cutlery + napkin (drawer_C → drawer_D)**
```
OPEN[drawer_C] → GRASP[silver_set] → PLACE[silver, table] → CLOSE[drawer_C] →
OPEN[drawer_D] → GRASP[napkin_set] → PLACE[napkin, table] → CLOSE[drawer_D]
= 1+1+1+1 + 1+1+1+1 = 8 step
```

**축 2c: Silver cutlery만, napkin 포기 (drawer_C)**
```
OPEN[drawer_C] → GRASP[silver_set] → PLACE[silver, table] → CLOSE[drawer_C]
= 4 step
```

**축 3a: Water glass (countertop)**
```
GRASP[glass] → PLACE[glass, table] × 4
= (1+1)×4 = 8 step
```
참고: countertop은 열려있으므로 OPEN 불필요.

**축 3b: Wine glass (shelf_E, 의자 이동 필요)**
```
GRASP[chair] → PLACE[chair, shelf_E앞] →
GRASP[wine_glass] → PLACE[glass, table] × 4 →
GRASP[chair] → PLACE[chair, table]
= 2 + (1+1)×4 + 2 = 12 step
```

**축 4a: Candle (countertop)**
```
GRASP[candle] → PLACE[candle, table]
= 2 step
```

**축 4b: Tablecloth + candle (floor_box, Case B2)**
```
OPEN[floor_box] → GRASP[tablecloth] → PLACE[tablecloth, table] →
GRASP[candle] → PLACE[candle, table] → CLOSE[floor_box]
= 1+1+1 + 1+1 + 1 = 6 step
```

**축 4c: Tablecloth + flower_vase (floor_box, Case B1)**
```
OPEN[floor_box] → GRASP[tablecloth] → PLACE[tablecloth, table] →
GRASP[flower_vase] → PLACE[vase, table] → CLOSE[floor_box]
= 1+1+1 + 1+1 + 1 = 6 step
```

### GRASP 단순화 규칙

- cutlery_set: 포크+나이프+스푼을 4인분 묶음으로 1회 GRASP
- napkin_set: 4장을 1회 GRASP
- plate: 개별 GRASP (1개씩, 4회)
- glass: 개별 GRASP (1개씩, 4회)
- 이유: plate와 glass는 "깨질 수 있는" 물건이므로 개별 운반이 자연스러움. cutlery와 napkin은 묶어서 운반 가능.

---

## 11. 경쟁 전략 분석

### 전략 A: "기본 빠른 세팅"

```
목표: regular plate + regular cutlery + napkin + water glass + candle
Step sequence:
  1-6:   OPEN[drawer_D] → cutlery_set → napkin_set → CLOSE → (6 step)
  7-8:   GRASP[candle] → PLACE[table] (2 step)
  9-12:  (GRASP[water_glass] → PLACE[table]) × 2 (4 step, 2개만)
  ...시간 부족으로 glass 4개 중 2개만, plate 세팅 불가

문제: 15 step으로도 "전부 기본"이 빡빡함
→ step 비용 재조정 필요 (아래 Section 12 참조)
```

**⚠️ Step 비용이 현재 설계로는 너무 높습니다. 조정이 필요합니다.**

---

## 12. Step 비용 조정

### 문제

현재 설계에서 plate 4개만 세팅해도 OPEN + GRASP×4 + PLACE×4 + CLOSE = 10 step.
Glass 4개도 GRASP×4 + PLACE×4 = 8 step.
총 기본 세팅만 24+ step → 15 step 예산 초과.

### 해결: 묶음 처리 확대 + step 예산 증가

**Option A: 묶음 처리 확대**

| 오브젝트 | 처리 | step 비용 |
|---|---|---|
| plate (regular or fancy) | 4개 스택으로 1회 GRASP, 1회 PLACE | 2 step |
| cutlery_set | 4인분 묶음 1회 | 2 step (GRASP + PLACE) |
| napkin_set | 4장 묶음 1회 | 2 step |
| glass (water or wine) | 2개씩 GRASP 가능 | 2회 × 2 step = 4 step |
| candle / flower_vase | 1개 | 2 step |
| tablecloth | 1개, PLACE = 테이블에 깔기 | 2 step |
| serving_bowl | 1개 | 2 step (치우기) |
| chair | 1개 | 2 step (옮기기) + 2 step (돌려놓기) |

**Option B: step 예산 증가 (20 step)**

케이크 태스크와 동일한 20 step으로 하면 여유가 생김.

### **결정: Option A(묶음 처리) + step 예산 20 step**

묶음 처리를 적용하되, 기본 세팅이 ~12 step, 풀 고급 세팅이 ~25 step이 되도록 조정.
step 예산 20으로 "전부 고급은 불가능하지만 2-3개 축 업그레이드는 가능"한 구간을 만듦.

---

## 13. 조정된 Step 비용표

```
OPEN[container]:              1 step
CLOSE[container]:             1 step
GRASP[object(s)]:             1 step (묶음 가능한 경우 묶어서)
PLACE[object(s), location]:   1 step
NAVIGATE_TO[location]:        0 step (단일 방이므로)
```

### 축별 조정된 step 비용

**축 1: Plate**

| 옵션 | Action Sequence | Step |
|---|---|---|
| Regular plate | OPEN[B] → GRASP[plate_stack] → PLACE[table] → CLOSE[B] | 4 |
| Fancy plate (Case A1, blocked) | OPEN[A] → GRASP[bowl] → PLACE[bowl, counter] → GRASP[plate_stack] → PLACE[table] → CLOSE[A] | 6 |
| Fancy plate (Case A2, accessible) | OPEN[A] → GRASP[plate_stack] → PLACE[table] → CLOSE[A] | 4 |
| Fancy plate (Case A3, 2개만) | OPEN[A] → GRASP[plate×2] → PLACE[table] → CLOSE[A] → OPEN[B] → GRASP[plate×2] → PLACE[table] → CLOSE[B] | 8 |

**축 2: Cutlery + Napkin**

| 옵션 | Action Sequence | Step |
|---|---|---|
| Regular cutlery + napkin | OPEN[D] → GRASP[cutlery_set] → PLACE[table] → GRASP[napkin_set] → PLACE[table] → CLOSE[D] | 6 |
| Silver cutlery만 (napkin 포기) | OPEN[C] → GRASP[silver_set] → PLACE[table] → CLOSE[C] | 4 |
| Silver + napkin (둘 다) | OPEN[C] → GRASP[silver] → PLACE[table] → CLOSE[C] → OPEN[D] → GRASP[napkin] → PLACE[table] → CLOSE[D] | 8 |

**축 3: Glass**

| 옵션 | Action Sequence | Step |
|---|---|---|
| Water glass | GRASP[glass×2] → PLACE[table] → GRASP[glass×2] → PLACE[table] | 4 |
| Wine glass (의자 이동) | GRASP[chair] → PLACE[chair, shelf앞] → GRASP[glass×2] → PLACE[table] → GRASP[glass×2] → PLACE[table] → GRASP[chair] → PLACE[chair, table] | 8 |
| Wine glass (의자 안 돌려놓음) | GRASP[chair] → PLACE[shelf앞] → GRASP[glass×2] → PLACE → GRASP[glass×2] → PLACE | 6 (좌석 -5점) |

**축 4: Centerpiece / Tablecloth**

| 옵션 | Action Sequence | Step |
|---|---|---|
| Candle만 | GRASP[candle] → PLACE[table] | 2 |
| Tablecloth + candle (Case B2) | OPEN[box] → GRASP[cloth] → PLACE[table] → CLOSE[box] → GRASP[candle] → PLACE[table] | 6 |
| Tablecloth + vase (Case B1) | OPEN[box] → GRASP[cloth] → PLACE[table] → GRASP[vase] → PLACE[table] → CLOSE[box] | 6 |

**※ Tablecloth 순서 페널티:** 이미 테이블에 물건을 올린 상태에서 tablecloth를 깔면, 기존 물건을 임시로 치우고 다시 올려야 함 → **+4 step 추가** (GRASP[기존물건] → PLACE[임시] → GRASP[cloth] → PLACE[table] → GRASP[기존물건] → PLACE[table]).

---

## 14. 조정된 경쟁 전략 (20 step 예산)

### 전략 A: "기본 안전" (14 step)

```
Regular plate(4) + Regular cutlery + napkin(6) + Water glass(4) + Candle(2)
= 4 + 6 + 4 + 2 = 16 step... 여전히 빡빡
```

**⚠️ 재조정: CLOSE를 선택적으로 만들기**

CLOSE[container]를 하지 않아도 됨 (시간 절약). 단, 열어둔 문이 동선을 방해할 수 있음.
→ cabinet/drawer를 닫지 않으면 -1~2점 감점 (미관) + 동선 영향은 axis별로 다름.

### 최종 step 비용 (CLOSE 선택적)

| 옵션 | CLOSE 포함 | CLOSE 생략 |
|---|---|---|
| Regular plate | 4 | 3 |
| Fancy plate (blocked) | 6 | 5 |
| Regular cutlery + napkin | 6 | 5 |
| Silver + napkin | 8 | 6 |
| Water glass | 4 | 4 (CLOSE 없음) |
| Wine glass (의자 복원) | 8 | 6 (의자 안 돌려놓음, 좌석 -5) |
| Candle | 2 | 2 |
| Tablecloth + vase | 6 | 5 |

### 전략 A: "기본 안전" (~14 step, CLOSE 생략)

```
Step 1-3:   Regular plate (OPEN[B] + GRASP + PLACE) = 3
Step 4-8:   Regular cutlery + napkin (OPEN[D] + GRASP + PLACE + GRASP + PLACE) = 5
Step 9-12:  Water glass (GRASP×2 + PLACE×2) × 2 = 4
Step 13-14: Candle (GRASP + PLACE) = 2
Total: 14 step (6 여유)

점수: 10 + 8 + 5 + 8 + 5 + 5 - 2(cabinet_B 안 닫음) = 39점
모든 Case에서 동일 (regular 옵션만 사용하므로 Case 무관)
```

### 전략 B: "Fancy plate + 기본 나머지" (~17 step)

```
Step 1-5:   Fancy plate, blocked 가정 (OPEN[A] + GRASP[bowl] + PLACE[counter] + GRASP[plate] + PLACE[table]) = 5
Step 6-10:  Regular cutlery + napkin = 5
Step 11-14: Water glass = 4
Step 15-16: Candle = 2
Total: 16 step (4 여유)

점수:
  Case A1: 20 + 8 + 5 + 8 + 5 + 5 = 51점
  Case A2: 20 + 8 + 5 + 8 + 5 + 5 = 51점 (bowl 치우기 step이 낭비되지만 성공)
  Case A3: 13 + 8 + 5 + 8 + 5 + 5 = 44점 (plate 2개만이라 보충 필요한데 Plan에 없음)
```

### 전략 C: "Tablecloth 먼저 + fancy plate" (~18 step)

```
Step 1-3:   Tablecloth (OPEN[box] + GRASP[cloth] + PLACE[table]) = 3
Step 4-8:   Fancy plate (Case A1 가정) = 5
Step 9-13:  Regular cutlery + napkin = 5
Step 14-17: Water glass = 4
Step 18:    GRASP[vase 또는 candle] → PLACE[table] = 2... 총 20 step으로 빡빡
Total: 19-20 step

점수:
  Case A1 + B1: 20 + 8 + 5 + 8 + 10 + 8 + 5 = 64점
  Case A1 + B2: 20 + 8 + 5 + 8 + 10 + 5 + 5 = 61점 (vase 없음)
  Case A2 + B1: 20 + 8 + 5 + 8 + 10 + 8 + 5 = 64점
  Case A3 + B1: 13 + 8 + 5 + 8 + 10 + 8 + 5 = 57점
```

### 전략 D: "Wine glass + silver cutlery" (~18 step)

```
Step 1-3:   Regular plate = 3
Step 4-9:   Silver cutlery + napkin (drawer_C → close → drawer_D) = 6
Step 10-15: Wine glass (의자 이동 + 복원) = 6 (의자 안 돌려놓으면)
Step 16-17: Candle = 2
Total: 17 step

점수 (좌석 안 돌려놓음):
  모든 Case: 10 + 15 + 5 + 18 + 5 + 0(좌석) = 53점
점수 (좌석 복원, +2 step):
  모든 Case: 10 + 15 + 5 + 18 + 5 + 5 = 58점 (19 step)
```

### 전략 E: "올인 — tablecloth + fancy + wine" (~24 step 필요)

```
Tablecloth(3) + Fancy plate blocked(5) + Silver+napkin(6) + Wine glass+복원(8) + vase(2)
= 24 step → 20 step 예산 초과 → **실행 불가능**

→ 무언가를 포기해야 함.
→ 에이전트가 "전부는 불가능"을 사전에 인식하는 것이 SF
```

### 전략 요약

| 전략 | Step | Case A1+B1 | Case A2+B1 | Case A3+B2 | 최악 Case | Robust |
|---|---|---|---|---|---|---|
| A: 기본 안전 | 14 | 39 | 39 | 39 | 39 | ✅ |
| B: Fancy plate | 16 | 51 | 51 | 44 | 44 | 중 |
| C: Cloth+Fancy | 19 | 64 | 64 | 57 | 57 | 중 |
| D: Wine+Silver | 17 | 53 | 53 | 53 | 53 | ✅ |
| E: 올인 | 24+ | 불가 | 불가 | 불가 | 0 | ✗ |

---

## 15. 함정 구조

| 함정 | SF 결핍 | 어떤 변수를 놓치면 빠지는가 |
|---|---|---|
| "전부 고급"으로 Plan 작성 | step 예산 미계산 | 모든 축의 step 합산 |
| cabinet_A에 bowl blocking을 모르고 바로 GRASP[plate] | Case A1에서 실패 | V1 (POMDP) |
| tablecloth를 나중에 발견하고 깔려다 step 낭비 | 순서 의존성 미인식 | V8 |
| drawer_C를 열어두고 drawer_D 접근 시도 | 물리적 간섭 미인식 | V4 |
| 의자를 옮기고 돌려놓지 않음 | 자원 trade-off 미인식 | V6 |
| plate가 2개뿐인 Case를 고려하지 않음 | 불확실성 미고려 | Case A3 |
| 모든 Plan이 같은 전략의 변종 | Plan 다양성 부족 | 전반적 SF 부족 |

---

## 16. 변수-전략 매트릭스

```
           │ V1  V2  V3  V4  V5  V6  V7  V8  V9  V10
───────────┼───────────────────────────────────────────
전략A 기본 │
전략B 접시 │  ✅  ✅
전략C 천접 │  ✅  ✅                  ✅  ✅  ✅  ✅
전략D 와은 │          ✅  ✅  ✅  ✅
전략E 올인 │  ✅  ✅  ✅  ✅  ✅  ✅  ✅  ✅  ✅  ✅
```

---

## 17. SF 수준별 에이전트 프로파일

### SF = 낮음

```
Phase 0: 테이블과 countertop만 관찰
SF Pred 1: "접시와 컵을 놓으면 된다" (변수 1-2개)
Phase 2: cabinet_B만 열어봄
SF Pred 2: Plan 5개 모두 "기본 세팅" 변종. 고급 옵션 모름.
결과: 39점 (모든 Case)
```

### SF = 중간

```
Phase 0: 캐비닛들, 서랍, shelf 확인
SF Pred 1: 변수 4-5개, "상단 캐비닛에 좋은 것이 있을 수 있다"
Phase 2: cabinet_A + drawer_C 열어봄 → V1, V3 발견
SF Pred 2: Fancy plate + Silver cutlery 전략 포함. 하지만 tablecloth 미발견.
         drawer 간섭은 인식했지만 floor_box 미탐사.
결과: 51-58점 (Case에 따라)
```

### SF = 높음

```
Phase 0: 모든 가구 위치, shelf 높이, floor_box 존재 확인
SF Pred 1: 변수 8-10개, 순서 의존성 추론, step 예산 계산
Phase 2: cabinet_A + floor_box 열어봄 → V1, V7 발견 → V10 외삽
SF Pred 2: 5개 Plan이 각각 다른 Case 조합 커버.
         tablecloth를 먼저 까는 전략 포함.
         plate 부족 Case에 대한 contingency 포함.
         step 예산을 고려한 trade-off 반영.
결과: 57-64점 (최적 조합 + robust)
```

---

## 18. 측정 지표

### 주 지표

| 지표 | 가중치 | 측정 |
|---|---|---|
| **Robust score** | 0.25 | min(각 Plan의 최악 Case 점수) |
| **Best plan score** | 0.15 | 1순위 Plan의 평균 점수 |
| **시나리오 커버리지 F1** | 0.20 | 변수 식별 + 시나리오 매칭의 F1 |
| **외삽 비율** | 0.20 | 미경험 변수에 대한 정확한 예측 비율 |
| **Plan 다양성** | 0.10 | 5개 Plan이 서로 다른 Case 조합을 커버하는가 |
| **Ranking 정확도** | 0.10 | 1순위 Plan이 실제 가장 robust한가 |

### 보조 지표

| 지표 | 측정 |
|---|---|
| Step 예산 인식 | Plan이 20 step 이내인가 |
| 순서 의존성 인식 | tablecloth를 먼저 까는 Plan이 있는가 |
| 물리적 간섭 인식 | drawer_C/D 간섭을 고려한 Plan이 있는가 |
| Investigation 효율성 | Phase 2에서 최소 step으로 핵심 변수 발견 |
| Condition 1 vs 3 delta | SF prediction의 기여분 |

---

## 19. Phase별 프롬프트 상세

### Phase 0 — 비파괴 관찰

```
System:
"You are a robot agent in a dining room.
 Your task: Set the dining table for 4 guests as elegantly 
 as possible. Guests arrive soon. Everything you need is 
 somewhere in this dining room.

 This is the OBSERVATION phase. You may look around to 
 gather information about what is available and where.
 You may NOT open, grab, or manipulate any objects yet.

 Available actions:
 - NAVIGATE_TO[location]: Move to look at something
 - DONE_OBSERVING[]: Finish observation phase

 You receive camera images showing what you see.
 Respond: Thought: <reasoning> / Action: <ACTION>[<args>]"
```

### SF Prediction 1

```
"Based on your observations, analyze the situation:

=== Part A: Variable Identification ===
List ALL uncertain or hidden factors. For each:
 - VARIABLE: Name
 - CURRENT KNOWLEDGE: What you know / don't know
 - POSSIBLE VALUES: What it could be
 - IMPACT: How it affects the task
 - HOW TO DISCOVER: What action would reveal it

=== Part B: Scenario Generation ===
Combine variables into scenarios. For each:
 - SCENARIO: What might happen
 - VARIABLES INVOLVED: Which from Part A
 - TRIGGER: What condition causes this
 - CONSEQUENCE: Impact on task
 - LIKELIHOOD: High / Medium / Low

Focus on scenarios where variables COMBINE to create 
unexpected outcomes.
List as many as you think are relevant."
```

### Phase 2 — 비가역적 탐사

```
System:
"This is the INVESTIGATION phase.
 You may now open containers to see what is inside.

 IMPORTANT:
 - Opening containers counts toward your step budget.
 - You have a maximum of 4 investigation steps.
 - After this phase, you will create execution plans.
   Plans will be executed EXACTLY as written with 
   NO opportunity to adjust mid-execution.

 Allowed: NAVIGATE_TO, OPEN, CLOSE
 NOT allowed: GRASP, PLACE

 You receive camera images showing container contents.
 When done: Action: DONE_INVESTIGATING[]"
```

### SF Prediction 2

```
"Based on your investigation:

=== Your Previous Predictions ===
[SF Prediction 1 전문]

=== Your Investigation Results ===
[Phase 2 히스토리 + 이미지 설명]

=== Part A: Variable Updates ===
For each variable from SF Prediction 1:
 CONFIRMED / REVISED / STILL UNKNOWN
 Are there NEW variables discovered?

=== Part B: Scenario Updates ===
For each scenario from SF Prediction 1:
 CONFIRM / REVISE / DELETE — explain why.
 What NEW scenarios should be added?
 Did any observation reveal patterns that might apply 
 to OTHER containers you did NOT open?

=== Part C: Execution Plans (exactly 5) ===
You have {remaining_steps} steps remaining.

Create 5 plans as complete action sequences.
Each plan should address DIFFERENT scenarios from Part B.

CRITICAL: Plans will be executed EXACTLY as written
with NO opportunity to adjust mid-execution.
If a plan tries to GRASP an object that doesn't exist
in that scenario, the plan fails from that point.

Format per plan:
Plan [A-E]: [strategy name]
  Addresses scenarios: [which scenarios/cases]
  Assumes: [what this plan assumes about unknown containers]
  Step 1: ACTION[args]
  Step 2: ACTION[args]
  ...
  Expected score: [estimated points]
  Key risk: [what case would make this plan fail]

RANKING: best to worst, explain why"
```

---

## 20. 확정된 설계 결정 요약

| 항목 | 결정 |
|---|---|
| 측정 대상 | **Scenario Flexibility (SF)** |
| 태스크 | Dinner Table Setting (4인, 단일 방) |
| 시간 시스템 | Symbolic — 매 action 1 step, 총 20 step |
| Phase 0 | step 미소모. NAVIGATE_TO만. 이미지 관찰 |
| Phase 2 | step 소모. 최대 4 step. OPEN/CLOSE/NAVIGATE_TO만. GRASP 차단 |
| Phase 4 | **One-shot** (ReAct 아님). Plan을 기계적으로 실행 |
| sim.save/restore | **에이전트에게 없음.** 시스템만 Phase 4에서 사용 |
| Plan 수 | 5개 고정 |
| Case 변수 | cabinet_A (3 Case) × floor_box (2 Case) = 6 조합 |
| 총 시뮬레이션 | 5 plans × 6 cases = 30회 |
| 관찰 방식 | **이미지 기반** (IsaacSim 카메라 렌더링). 텍스트 센서 피드백 없음 |
| 부수효과 구현 | **Scripted/deterministic** (PhysX 물리 의존 없음) |
| 점수 기준 | 이미지에서 자명 — "우아한 테이블 세팅" |
| Instruction 언어 | **영어** |
| 실험 조건 | Condition 1 (Full SF) + Condition 3 (No Prediction baseline) |
| 외삽 구조 | cabinet_A의 "blocking" 패턴 → floor_box에 외삽 |
| GRASP 단순화 | cutlery/napkin은 묶음 GRASP, plate/glass는 개별 (2개씩 가능) |
| CLOSE 선택성 | 생략 가능, 미관 감점 있음 |

---

## 21. 구현 우선순위

```
Phase 1: 씬 구성
  - BEHAVIOR-1K dining room에서 필요한 오브젝트 확인
  - 없는 오브젝트는 유사 asset으로 대체
  - articulated joint (cabinet, drawer) 정상 작동 확인

Phase 2: 파이프라인 skeleton
  - Phase 0 (NAVIGATE_TO + 이미지 캡처) 구현
  - SF Prediction 1 프롬프트 + LLM 호출
  - Phase 2 (OPEN + 이미지 캡처) 구현
  - SF Prediction 2 프롬프트 + LLM 호출

Phase 3: Phase 4 실행 엔진
  - Plan 파싱 (action sequence 추출)
  - Case별 config 적용
  - 기계적 실행 + 결과 기록

Phase 4: 평가 시스템
  - 테이블 위 오브젝트 검사 → 자동 채점
  - SF Prediction 질 평가 (변수 매칭, F1)
  - Condition 1 vs 3 비교

Phase 5: 실험
  - 여러 LLM (GPT-4V, Claude, Gemini 등) 비교
  - SF 수준별 행동 패턴 분석
```

---

## 22. 미결 사항 (구현 시 확인 필요)

| 항목 | 질문 | 결정 시점 |
|---|---|---|
| BEHAVIOR-1K 씬 | dining room에 필요한 가구가 모두 있는가? | Phase 1 |
| 오브젝트 asset | fancy_plate vs regular_plate를 시각적으로 구별 가능한 asset이 있는가? | Phase 1 |
| Articulated joint | drawer_C/D의 물리적 간섭을 OmniGibson에서 어떻게 구현하는가? | Phase 1 |
| shelf_E 높이 | Tiago 로봇이 실제로 닿을 수 없는 높이로 배치 가능한가? | Phase 1 |
| 이미지 품질 | cabinet 내부를 열었을 때 내용물이 이미지에서 식별 가능한가? | Phase 1 |
| plate 스택 | 4개 plate를 스택으로 쌓아놓는 것이 OmniGibson에서 안정적인가? | Phase 1 |
| GRASP 묶음 | Tiago가 plate 스택을 한 번에 잡을 수 있는가? | Phase 1 |
| tablecloth | OmniGibson에서 tablecloth를 "깐다"는 것을 어떻게 구현하는가? (soft body? 또는 scripted state 변경?) | Phase 1 |
