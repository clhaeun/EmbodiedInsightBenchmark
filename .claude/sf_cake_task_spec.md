# SF Task: 정전 시 케이크 완성하기
## "Completing a Cake During Power Outage"
### Scenario Flexibility 측정을 위한 확정 사양서

---

## 1. 이론적 배경

### Scenario Flexibility (SF) 정의

> "Considering diverse ways in which a scenario might unfold to identify possible contingencies."
> — Johnson, Karimi, Bengio et al., "Imagining and building wise machines" (Trends in Cognitive Sciences, 2026)

**Ron 사례:** 정치 컨설턴트 Ron은 후보의 승리 시나리오뿐 아니라 패배 시나리오도 상상하고, 패배의 원인까지 사전에 분석한다. SF의 핵심은 **행동 전에** 다양한 가능성을 예측하고, 특히 실패/최악의 시나리오까지 고려하여 robust한 전략을 수립하는 것이다.

### CA vs SF 구분

| | CA (Context Adaptability) | SF (Scenario Flexibility) |
|---|---|---|
| 핵심 질문 | "이 상황이 무엇과 비슷한가?" | "이 상황이 앞으로 어떻게 전개될 수 있는가?" |
| 축 | 유사성 축 (현재 vs 참조 상황) | 시간 축 (현재 → 미래 가능성들) |
| 에이전트 활동 | Demo 비교 → 도구 선택 | 시나리오 예측 → robust 전략 수립 |
| 정보 소스 | Demo 영상 (외부 제공) | 환경 관찰 + 제한적 rollout (자체 수집) |
| 실행 횟수 | 1회 (one-shot) | 1회 rollout (관찰 확장) + 1회 최종 실행 |
| 핵심 능력 | 구조적 매핑 | 미래 예측 + 외삽 + 연쇄 추론 |

---

## 2. 태스크 기본 정보

| 항목 | 내용 |
|---|---|
| 측정 대상 | Scenario Flexibility (SF) |
| 씬 | house_single_floor (BEHAVIOR-1K) — Kitchen |
| Instruction | "주방에서 케이크를 만들고 있었는데 정전이 됐다. 1시간 내에 손님이 도착한다. 케이크를 최대한 완성하라." |
| 로봇 | Tiago (dual-arm mobile manipulator) |
| LLM 아키텍처 | ReAct (Think → Act → Observe) |
| 시간 시스템 | Symbolic — 매 action마다 5분 경과, 총 12 step (60분) |

---

## 3. Symbolic 시간 시스템

### 기본 구조

- 매 action을 실행할 때마다 내부 time_step이 1 증가 (= 5분 경과)
- WAIT[] action: 아무것도 하지 않고 5분 경과
- 총 12 step (60분) 후 태스크 종료 (손님 도착)
- 에이전트에게 "매 행동마다 약 5분이 소요된다"고 사전 고지

### 시간에 따른 내부 상태 변화 (에이전트는 직접 관찰해야만 앎)

```
t = time_step (0~12)

오븐 내부 온도 (문 닫힘 유지 시):
  oven_temp(t) = max(23, 180 - 12*t)
  → 0분: 180°C, 15분: 144°C, 30분: 108°C, 45분: 72°C, 60분: 36°C

오븐 내부 온도 (문 열린 이후):
  oven_temp(t) = max(23, oven_temp(t_open) - 30*(t - t_open))
  → 문 열면 매 step -30°C로 급격 하강
  → 예: 15분(step 3)에 열면 144°C → 다음 step 114°C → 84°C → 54°C...

케이크 익힘도 (%):
  doneness(t) = min(100, 70 + Σ(max(0, oven_temp(i) - 100) * 0.04))
  → 오븐 온도가 100°C 이상일 때만 추가 익힘
  → 문 닫힘 유지: 0분 70% → 15분 76% → 이후 온도 100°C 이하라 정지
  → 문 0분에 열면: 70% → 71%에서 거의 정지 (잔열 급소실)

냉장고 내부 온도 (문 닫힘 유지 시):
  fridge_temp(t) = min(30, 5 + 1.5*t)
  → 0분: 5°C, 10분: 8°C, 20분: 11°C, 30분: 14°C, 40분: 17°C

냉장고 내부 온도 (문 열린 이후):
  fridge_temp(t) = min(30, fridge_temp(t_open) + 5*(t - t_open))
  → 문 열면 매 step +5°C로 급격 상승

크림 상태:
  cream_usable = (fridge_temp < 15)
  → 냉장고 닫힘 유지: 약 step 6 (30분)까지 사용 가능
  → 냉장고 0분에 열면: 약 step 2 (10분)에 녹기 시작

케이크 위 크림 도포 가능 여부:
  cream_apply_success = (cream_usable AND cake_temp < 50)
  → 크림이 사용 가능하고, 케이크가 충분히 식어야 성공
  → 뜨거운 케이크(>50°C)에 크림 바르면 녹아내림

정전 복구:
  power_restored = (t >= 7)  # step 7 = 35분
  → 35분 후 전력 복구
  → 복구 후 오븐 재가동 가능 (예열에 2 step = 10분 소요)
```

---

## 4. 씬 구성 및 오브젝트

### 씬 내 오브젝트

| 오브젝트 | 위치 | 초기 상태 | 역할 |
|---|---|---|---|
| oven | kitchen | 꺼져있음, 문 닫힘, 내부 180°C | 케이크가 들어있음 |
| cake (inside oven) | oven 내부 | 70% 익음, 보이지 않음 (문 닫혀서) | 주요 태스크 대상 |
| fridge | kitchen | 꺼져있음, 문 닫힘, 내부 5°C | 크림이 들어있음 |
| cream (inside fridge) | fridge 내부 | 5°C, 사용 가능, 보이지 않음 | 케이크 장식 재료 |
| chocolate | countertop | 상온, 안정 | 대안 장식 재료 |
| decoration_tools | countertop | 상온 | 장식 도구 |
| towel | countertop | 마른 상태 | 다용도 (쿠션, 단열 등) |
| plate | countertop | 상온 | 케이크 놓을 곳 |

### 오븐/냉장고 OPEN 시 시각적 변화

- OPEN[oven]: 문이 물리적으로 열림 + 내부 cake이 보이는 IsaacSim 렌더링
- OPEN[fridge]: 문이 물리적으로 열림 + 내부 cream이 보이는 IsaacSim 렌더링
- CLOSE[oven]: 문이 물리적으로 닫힘

---

## 5. 숨겨진 변수 (설계자만 앎)

| # | 변수 | 초기값 | 시간 의존성 | 발견 방법 | 에이전트 관점 |
|---|---|---|---|---|---|
| V1 | 케이크 익힘도 | 70% | 오븐 온도 > 100°C일 때 증가 | OPEN[oven] + TOUCH[cake] | POMDP — 열어봐야 앎 |
| V2 | 오븐 잔열 감쇠율 | -12°C/step (닫힘) | 문 열면 -30°C/step으로 급변 | rollout에서 OPEN 후 온도 변화 관찰 | rollout으로만 발견 가능한 부수 효과 |
| V3 | 크림 유효기간 | ~30분 (닫힘) | 냉장고 열면 급격 단축 (~10분) | V2에서 외삽 가능 | SF 외삽 대상 |
| V4 | 정전 복구 시점 | 35분 (step 7) | 고정 | 시간이 지나면 자연 발견 | 예측 불가, 대비만 가능 |
| V5 | 뜨거운 케이크+크림 상호작용 | N/A | cake_temp > 50 → 크림 녹음 | rollout 또는 물리 추론 | 변수 조합 시나리오 |
| V6 | 정전 복구 후 오븐 예열 시간 | 10분 (2 step) | 고정 | 정전 복구 후 발견 | 시간 예산 계산에 영향 |

---

## 6. SF 파이프라인

### 전체 흐름

```
Phase 0: 환경 관찰 (exploration, 행동 없이 외부만 관찰)
    ↓
Phase 1: 초기 시나리오 예측 (verbal, 행동 전) — SF baseline
    ↓
Phase 2: 확인 rollout (1회, sim.save/restore) — 관찰 확장
    ↓
Phase 3: 확장 시나리오 예측 + 계획 수정 (verbal) — SF 핵심 측정
    ↓
Phase 4: 최종 전략 수립 + 실행 (리셋 없음, time_step 진행)
    ↓
Phase 5: 시스템 검증 (에이전트 모르게, IsaacSim에서 예측 검증)
    ↓
[평가]
```

---

### Phase 0 — 환경 관찰

에이전트가 행동 없이 외부만 관찰. 오븐/냉장고를 열지 않음. **time_step은 아직 진행되지 않음** (관찰은 시간 소모 없음).

```
사용 가능한 Exploration Primitives:

NAVIGATE_TO[oven]:
  → [IsaacSim 렌더링: 오븐 문 닫혀있음, 꺼져있음]

TOUCH[oven_door]:
  → "Surface temperature: 172°C. Temperature gradient: -3.2°C per 5 minutes."

NAVIGATE_TO[fridge]:
  → [IsaacSim 렌더링: 냉장고 문 닫혀있음, 꺼져있음]

TOUCH[fridge_door]:
  → "Surface temperature: 8°C. Temperature gradient: +0.5°C per 5 minutes."

NAVIGATE_TO[countertop]:
  → [IsaacSim 렌더링: chocolate, decoration_tools, towel, plate 보임]

TOUCH[countertop]:
  → "Room temperature: 23°C"
```

**Phase 0에서 관찰 가능한 정보:**
- 오븐 외벽 172°C, 매 5분 -3.2°C 하강 중 → "잔열이 있고 점점 식고 있다"
- 냉장고 외벽 8°C, 매 5분 +0.5°C 상승 중 → "냉기가 빠지고 있다"
- 오븐/냉장고 내부는 안 보임 (POMDP)
- 초콜릿, 장식 도구는 countertop에 바로 있음

**Phase 0에서 관찰 불가능한 정보:**
- 케이크가 정확히 몇 % 익었는지
- 크림의 정확한 현재 온도/상태
- 오븐을 열면 잔열이 얼마나 빨리 빠지는지
- 정전이 언제 복구되는지
- 뜨거운 케이크에 크림을 바르면 어떻게 되는지

---

### Phase 1 — 초기 시나리오 예측 (verbal, SF baseline)

```
System Prompt:
"당신은 아직 아무 행동도 하지 않았다.
관찰한 정보만을 바탕으로, 이 태스크를 수행할 때
어떤 일들이 벌어질 수 있는지 예측하라.

다음을 포함하라:
(1) 성공 시나리오 — 어떻게 하면 케이크를 완성할 수 있는가?
(2) 실패 시나리오 — 어떤 것들이 잘못될 수 있는가?
(3) 시간에 따라 상황이 어떻게 변할 수 있는가?
(4) 아직 확인하지 못한 불확실한 요소는 무엇인가?"
```

**SF가 높은 에이전트의 Phase 1 출력 예시:**

```
(1) 성공 시나리오:
  - 잔열로 케이크가 더 익을 수 있다.
  - 크림이 녹기 전에 사용하면 장식 가능.
  - 정전이 복구되면 오븐을 다시 켤 수 있다.

(2) 실패 시나리오:
  - 잔열이 부족하면 케이크가 덜 익은 채로 끝난다.
  - 크림이 녹으면 장식할 수 없다.
  - 정전이 복구되지 않으면 오븐 사용 불가.
  - 오븐을 열면 잔열이 빠질 수 있다.
  - 뜨거운 케이크에 크림을 바르면 녹아내릴 수 있다.

(3) 시간 변화:
  - 오븐 외벽이 -3.2°C/5min이면, 약 30~40분 후 상온.
    잔열 효과는 초반 15~20분이 핵심일 것이다.
  - 냉장고 외벽이 +0.5°C/5min이면, 내부는 더 빨리 올라갈 것.
    크림은 20~30분 내에 사용해야 할 것이다.

(4) 불확실한 요소:
  - 케이크가 정확히 얼마나 익었는지
  - 오븐을 열면 잔열이 정확히 얼마나 빨리 빠지는지
  - 정전이 언제 복구되는지
  - 냉장고를 열면 냉기가 얼마나 빨리 빠지는지
```

**Phase 1 측정 항목:**

| 항목 | 측정 |
|---|---|
| 시나리오 수 | 성공 + 실패 시나리오 총 몇 개? |
| 변수 커버리지 | V1~V6 중 몇 개를 언급? |
| 최선+최악 균형 | 성공만? 실패도 포함? |
| 시간 추정 | "잔열 15~20분", "크림 20~30분" 등 수치 추정 여부 |
| 불확실성 인식 | "모르는 것"을 명시적으로 나열했는가? |
| 변수 조합 | "뜨거운 케이크 + 크림 = 녹음" 같은 조합 시나리오? |
| 관찰 비용 인식 | "오븐 열면 잔열 빠질 수 있다" 예측? |

---

### Phase 2 — 확인 Rollout (1회, 관찰 확장)

**목적: "시도"가 아니라 "관찰의 확장"** — Ron이 여론 조사를 돌리는 것에 해당.

에이전트에게 1회 rollout 기회를 줌. sim.save/restore로 초기 상태로 복원됨.
Rollout 동안의 action도 time_step을 소모함 (rollout 내에서 시간이 흐름).

```
System Prompt:
"1회 시뮬레이션 기회가 주어진다. 
이 시뮬레이션에서 행동하고 결과를 관찰할 수 있다.
시뮬레이션이 끝나면 초기 상태로 되돌아간다.
이 기회를 사용하여 불확실한 정보를 확인하라."

sim.save(S₀)

에이전트의 rollout (예시):
  
  Step 1: OPEN[oven]
    → [IsaacSim: 오븐 문 열림, 케이크 보임]
    → 보조 텍스트: "Oven door opened."
  
  Step 2: TOUCH[cake]  
    → "Internal temperature: 155°C. 
       Surface elasticity: 0.62 (1.0=fully done).
       Estimated doneness: ~72%"
  
  Step 3: TOUCH[oven_interior]
    → "Temperature: 118°C" 
       (열기 전 추정 144°C였는데, 2 step만에 118°C로!)
    → 에이전트: "문을 열었더니 온도가 급격히 떨어졌다!"
       (V2 발견: 문 열면 -30°C/step)

  Step 4: CLOSE[oven]
    → 오븐 문 닫힘. 하지만 이미 잔열 상당량 손실.

sim.restore(S₀) — 초기 상태로 복원

rollout 종료.
```

**Phase 2에서 발견한 핵심 정보:**
- 케이크가 약 70~72% 익었다 (V1 확인)
- **오븐을 열면 온도가 -30°C/step으로 급락한다** (V2 발견 — rollout으로만 알 수 있었던 부수 효과)
- 2 step 열어두었더니 144°C → 118°C (26°C 손실)

**Phase 2 측정 항목:**

| 항목 | 측정 |
|---|---|
| rollout 목적성 | "일단 해보자" vs "불확실한 것을 확인하겠다" |
| 발견한 변수 | rollout에서 직접 경험한 숨겨진 변수 수 |
| 부수 효과 인식 | "문 열면 잔열 급락"을 인식했는가? |

---

### Phase 3 — 확장 시나리오 예측 + 계획 수정 (SF 핵심)

```
System Prompt:
"시뮬레이션에서 새로운 정보를 얻었다. 
이제 예측을 업데이트하라:
(1) 시뮬레이션에서 새로 발견한 것은?
(2) 이 발견을 바탕으로, 아직 확인하지 않았지만
    추가로 존재할 수 있는 위험은?
(3) 처음 예측(Phase 1)에서 수정이 필요한 부분은?
(4) 모든 시나리오를 고려한 시간별 전략은?"
```

**SF가 높은 에이전트의 Phase 3 출력 예시:**

```
(1) 새 발견:
  - 오븐을 열면 잔열이 -30°C/step으로 급락한다.
    문 닫힌 상태(-12°C/step)보다 2.5배 빠르다.
  - 케이크는 약 70~72% 익었다.

(2) 외삽 — 아직 확인하지 않은 위험:
  - ★ 냉장고도 마찬가지일 수 있다. 
    냉장고를 열면 냉기가 급격히 빠져 
    크림이 예상보다 훨씬 빨리 녹을 수 있다.
    → 외벽 기준 +0.5°C/step이지만, 
      열면 +5°C/step 이상일 수 있다.
    → 크림 유효기간이 30분 → 10분으로 단축될 수 있다.
  
  - 정전이 복구되더라도, 그 시점에 오븐 잔열이 
    이미 없으면 예열부터 다시 해야 한다. 
    예열에 10분이면 남은 시간이 빠듯하다.
  
  - 케이크를 오븐에서 꺼낸 직후 크림을 바르면
    케이크 온도(100°C 이상)에 의해 크림이 녹아내릴 것.
    → 케이크를 꺼낸 후 충분히 식힌 뒤 크림을 발라야.

(3) 계획 수정:
  기존 Phase 1: "오븐 열고 확인 → 판단"
  수정: "오븐을 열지 않고 잔열을 최대한 보존한다.
        외벽 온도로 내부 상태를 추정한다.
        냉장고도 최대한 안 열고, 크림이 필요한 
        마지막 순간에만 연다."

(4) 시간별 분기 전략:
  0~15분 (step 0~3): 
    오븐/냉장고 안 열고 잔열/냉기 보존.
    이 동안 초콜릿 장식 준비.
    
  15분 (step 3): 
    오븐 외벽 온도 재확인.
    → 외벽 130°C 이상이면 → 5분 더 대기 (잔열 효과 지속)
    → 외벽 100°C 이하이면 → 잔열 효과 거의 끝. 오븐 열고 케이크 꺼냄.
    
  15~20분 (step 3~4):
    오븐에서 케이크 꺼냄.
    케이크를 plate 위에 놓고 식힘.
    
  20분 (step 4):
    냉장고 열고 크림 상태 확인.
    → 크림 사용 가능 → 케이크가 50°C 이하로 식었는지 확인.
      → 식었으면 → 크림 장식.
      → 아직 뜨거우면 → 5분 더 식힌 후 크림 장식.
    → 크림 이미 녹았으면 → 초콜릿만으로 마무리.
    
  35분 (step 7): 정전 복구 가능성.
    → 복구되면 → 오븐 재가동하여 케이크 추가 굽기 가능.
      하지만 잔열 보존했다면 예열 시간 단축 가능.
    → 복구 안 되면 → 현재 상태로 마무리.
    
  50~60분 (step 10~12):
    → 정전 복구 + 추가 굽기 완료 → 크림/초콜릿 장식 마무리.
    → 정전 미복구 → 76% 케이크에 가능한 장식으로 최선의 결과.
    
  만약의 contingency:
    - 크림이 예상보다 빨리 녹았으면 → 초콜릿 장식으로 전환.
    - 정전 복구가 예상보다 늦으면 → 현재 케이크로 마무리.
    - 케이크가 예상보다 덜 익었으면 → 정전 복구를 기다리는 쪽에 무게.
```

**Phase 3 측정 항목 (SF 핵심):**

| 항목 | 측정 |
|---|---|
| **외삽 정확도** | "오븐 열면 급락" → "냉장고도 마찬가지" 외삽 성공? |
| **외삽 범위** | rollout에서 경험하지 않은 변수(V3, V5, V6)를 몇 개 예측? |
| **변수 조합** | V1×V3 (뜨거운 케이크 + 크림), V4×V2 (정전 복구 + 잔열) 등 |
| **계획 수정 질** | Phase 1 대비 구체적으로 어떻게 수정? |
| **시간별 분기** | 시점별 조건 분기가 포함됐는가? |
| **contingency** | "만약 X이면 Y" 대비책이 포함됐는가? |
| **비용-이득 인식** | "관찰(열기) = 환경 악화"라는 트레이드오프 반영? |

---

### Phase 4 — 최종 전략 수립 + 실행

```
System Prompt:
"모든 시나리오를 고려하여 최종 전략을 수립하고 실행하라.
시간이 제한되어 있다 (매 행동 약 5분 소요, 총 60분).
매 행동 후 현재 상태를 관찰할 수 있다."

sim.restore(S₀) — 초기 상태로 최종 복원
time_step = 0
```

**정답 전략 실행 예시:**

```
Step 0 (0분): NAVIGATE_TO[countertop]
  → 초콜릿, 장식 도구 확인
  → time_step = 1

Step 1 (5분): NEW_ACTION[PREPARE_DECORATION, chocolate, decoration_tools]
  → "초콜릿 장식 요소를 준비했다"
  → IsaacSim: 초콜릿이 장식 형태로 변환됨
  → time_step = 2

Step 2 (10분): TOUCH[oven_door]
  → "Surface temperature: 148°C, gradient: -3.2°C/5min"
  → 에이전트: "아직 잔열 충분. 더 기다린다."
  → time_step = 3

Step 3 (15분): TOUCH[oven_door]
  → "Surface temperature: 136°C, gradient: -3.2°C/5min"
  → 에이전트: "내부 온도가 100°C 근처일 것. 
    잔열 효과가 거의 끝나가니 이제 꺼내자."
  → time_step = 4

Step 4 (20분): OPEN[oven]
  → [IsaacSim: 오븐 열림, 케이크 보임]
  → TOUCH[cake]: "Temperature: 108°C, doneness: ~76%"
  → time_step = 5

Step 5 (25분): GRASP[cake] → PLACE_ON_TOP[cake, plate]
  → [IsaacSim: 케이크가 plate 위에 놓임]
  → time_step = 6

Step 6 (30분): OPEN[fridge]
  → TOUCH[cream]: "Temperature: 14°C — still usable"
  → GRASP[cream]
  → time_step = 7
  → ★ 이 step에서 정전 복구됨! (에이전트에게 알림)
  → "The power has been restored."

Step 7 (35분): TOUCH[cake]
  → "Temperature: 62°C — still too hot for cream"
  → 에이전트: "케이크가 아직 뜨겁다. 크림은 나중에. 
    정전이 복구됐으니 오븐을 다시 켜자."
  → NEW_ACTION[TURN_ON, oven, 180]
  → "Oven is preheating."
  → time_step = 8

Step 8 (40분): TOUCH[cake]
  → "Temperature: 48°C — cool enough for cream"
  → NEW_ACTION[APPLY_CREAM, cream, cake]
  → 판정: cake_temp(48) < 50 AND cream_temp(14) < 15 → ✅ 성공!
  → [IsaacSim: 크림이 예쁘게 발라진 케이크 렌더링]
  → time_step = 9

Step 9 (45분): TOUCH[oven_interior]
  → "Temperature: 175°C — almost preheated"
  → time_step = 10

Step 10 (50분): PLACE_INSIDE[cake, oven]
  → "Cake placed in preheated oven for final baking"
  → time_step = 11

Step 11 (55분): GRASP[cake] from oven
  → TOUCH[cake]: "doneness: 92%"
  → NEW_ACTION[APPLY_CHOCOLATE_DECORATION, chocolate, cake]
  → [IsaacSim: 완성된 케이크 렌더링]
  → time_step = 12

Step 12 (60분): 손님 도착. 태스크 종료.
  최종 결과: 케이크 92% + 크림 장식 + 초콜릿 장식 = 최상
```

---

### Phase 5 — 시스템 검증 (에이전트 모르게)

평가자가 에이전트의 Phase 1 + Phase 3 예측을 IsaacSim에서 검증.

```
검증 1: "오븐을 열면 잔열이 급격히 빠진다" 예측
  → sim에서 step 0에 OPEN[oven] → 온도 급락 확인
  → 예측 정확 ✅

검증 2: "냉장고도 열면 냉기가 급격히 빠진다" 예측 (외삽)
  → sim에서 step 0에 OPEN[fridge] → 크림 온도 급상승 확인
  → 외삽 정확 ✅

검증 3: "뜨거운 케이크에 크림 바르면 녹는다" 예측
  → sim에서 step 4에 OPEN[oven] → GRASP[cake] → APPLY_CREAM
  → cake_temp 108°C > 50°C → 크림 녹음
  → 예측 정확 ✅

검증 4: "정전이 복구될 수 있다" 예측
  → sim에서 step 7에 정전 복구 확인
  → 예측 정확 ✅ (시점 예측은 불가능했으므로 존재 예측만 평가)

검증 5: "잔열 효과는 15~20분이 핵심" 예측
  → sim에서 문 닫힘 유지 시 doneness 변화:
    step 0: 70%, step 3: 76%, step 4: 76% (변화 없음)
  → 약 15분(step 3)까지만 효과 → 예측 정확 ✅
```

---

## 7. 성공/실패 판정 — 케이크 완성도 점수

### 완성도 요소별 점수

| 요소 | 조건 | 점수 |
|---|---|---|
| **익힘도** | doneness ≥ 90% | 30점 |
| | 80% ≤ doneness < 90% | 20점 |
| | 70% ≤ doneness < 80% | 10점 |
| | doneness < 70% (악화) | 0점 |
| **크림 장식** | cream 성공적으로 도포 | 30점 |
| | cream 녹아내림 (뜨거운 케이크) | 0점 |
| | cream 미사용 (녹았거나 시간 부족) | 0점 |
| **초콜릿 장식** | chocolate 장식 완료 | 20점 |
| | 미완성 | 0점 |
| **시간 내 완료** | 60분 내 모든 작업 완료 | 20점 |
| | 일부 작업 미완 | 10점 |
| | 거의 미완 | 0점 |

**최대 점수: 100점**

---

## 8. 함정 시나리오별 예상 점수

| 전략 | 익힘 | 크림 | 초콜릿 | 시간 | 총점 | SF 수준 |
|---|---|---|---|---|---|---|
| **정답 (잔열 보존 + 크림 타이밍 + 정전 복구 활용)** | 30 (92%) | 30 | 20 | 20 | **100** | 높음 |
| 잔열 보존 + 크림 타이밍 (정전 복구 미활용) | 10 (76%) | 30 | 20 | 20 | **80** | 중~높음 |
| 함정1: 즉시 확인 (0분에 모두 열기) | 10 (71%) | 0 (녹음) | 20 | 10 | **40** | 낮음 |
| 함정2: 정전 복구 대기 (아무것도 안 함) | 10 (76%) | 0 (녹음) | 0 | 10 | **20** | 매우 낮음 |
| 함정3: 크림 먼저 (뜨거운 케이크에 도포) | 0 (70%) | 0 (녹아내림) | 20 | 10 | **30** | 낮음 |
| 함정4: 잔열 과신 (30분까지 대기) | 10 (76%) | 0 (녹음) | 20 | 10 | **40** | 중간 |
| 함정5: 포기 (초콜릿만) | 10 (76%) | 0 | 20 | 20 | **50** | 없음 |

---

## 9. SF 평가 지표

### 주 지표

| 지표 | 가중치 | 측정 Phase | 공식/방법 |
|---|---|---|---|
| **시나리오 커버리지** | 0.25 | Phase 1+3 | 예측한 시나리오 중 V1~V6과 매칭되는 수 / 6 |
| **예측 정확도** | 0.25 | Phase 5 검증 | 시스템 검증에서 정확한 예측 수 / 총 예측 수 |
| **외삽 비율** | 0.20 | Phase 3 | Phase 3에서 추가한 정확한 시나리오 수 / (V_total - V_rollout에서 발견한 수) |
| **케이크 완성도** | 0.20 | Phase 4 종료 | 위 점수 체계 (0~100점 → 0~1로 정규화) |
| **최선+최악 균형** | 0.10 | Phase 1+3 | 실패 시나리오 수 / 총 시나리오 수 (0.3~0.7이 이상적) |

### 보조 지표

| 지표 | 측정 Phase | 설명 |
|---|---|---|
| 변수 조합 사고 | Phase 1+3 | 단일 변수만? V1×V3, V2×V4 등 조합 시나리오도? |
| 시간 추정 정확도 | Phase 1+3 | "잔열 15분", "크림 20분" 등의 추정이 실제와 얼마나 가까운가 |
| 계획 수정 질 | Phase 3 | Phase 1 → Phase 3에서 구체적으로 어떻게 수정? |
| contingency 포함 | Phase 3+4 | "만약 X이면 Y" 대비책이 최종 전략에 있는가 |
| 관찰 비용 인식 | Phase 1+3 | "열면 잔열/냉기 손실"이라는 트레이드오프를 언급? |
| rollout 목적성 | Phase 2 | 무작위 시도 vs 불확실한 것을 확인하려는 목적적 행동 |
| Phase 1→3 개선도 | Phase 1 vs 3 비교 | rollout 후 시나리오가 얼마나 풍부/정확해졌는가 |
| 과대/과소 예측 | Phase 5 검증 | false positive(헛다리) vs false negative(놓침) 비율 |

---

## 10. SF 수준별 에이전트 행동 프로파일

### SF = 0 (포기)

```
Phase 1: "정전이라 오븐 안 됨. 불가능."
Phase 2: rollout 안 함
Phase 3: "초콜릿 장식이라도."
Phase 4: 초콜릿 장식만 함.
결과: 50점. 잔열/크림/정전 복구 전부 미활용.
```

### SF = 낮음 (즉시 확인)

```
Phase 1: "오븐 확인해봐야지."
Phase 2: OPEN[oven] → 케이크/온도 확인 → V2 발견
Phase 3: "오븐 안 열어야겠다." (V2에만 대응, 외삽 없음)
Phase 4: 0분에 냉장고도 열어버림 → 크림 일찍 녹음
결과: 40점.
```

### SF = 중간 (개별 변수 인식, 조합 미고려)

```
Phase 1: 잔열/크림/정전 개별 인식
Phase 2: V2 발견
Phase 3: V3 외삽 시도, 하지만 V5(뜨거운 케이크+크림) 미고려
Phase 4: 15분에 오븐 열고 바로 크림 → 크림 녹아내림
결과: 40~60점.
```

### SF = 높음 (정답)

```
Phase 1: 모든 변수 + 시간 추정 + 조합 + 불확실성
Phase 2: V2 발견 → V3 외삽 + V5 예측
Phase 3: 시간별 분기 전략 + contingency
Phase 4: 잔열 보존 → 최적 시점에 꺼냄 → 크림 타이밍 → 정전 복구 활용
결과: 80~100점.
```

---

## 11. Embodiedness 보장 사항

### 최소 기준

> **에이전트가 받는 observation은 텍스트가 아니라 IsaacSim의 실제 렌더링 상태이다.**

| 단계 | Embodiedness 수준 | 구체적 구현 |
|---|---|---|
| Phase 0 Exploration | TOUCH: 텍스트 데이터 / NAVIGATE: IsaacSim 렌더링 | 오븐 외벽 온도 = 텍스트, 씬 관찰 = 렌더링 이미지 |
| Phase 1 시나리오 예측 | Verbal (텍스트 출력) | 에이전트의 예측을 텍스트로 기록 |
| Phase 2 Rollout | **물리적** | OPEN[oven] → 오븐 문이 실제로 열림, 케이크 렌더링 |
| Phase 3 확장 예측 | Verbal (텍스트 출력) | 에이전트의 외삽/수정을 텍스트로 기록 |
| Phase 4 최종 실행 | **물리적** | 모든 action의 결과가 IsaacSim에서 물리적으로 구현 |
| Phase 5 시스템 검증 | **물리적** | 에이전트 예측을 IsaacSim에서 실행하여 검증 |
| Observation | **물리적** | IsaacSim 카메라 렌더링 이미지가 primary |
| 성공/실패 판정 | **Symbolic + 물리적** | 상태 테이블 기반 판정 + IsaacSim 렌더링으로 시각 확인 |

### Embodiedness가 텍스트 게임과 구별되는 핵심

1. **시각 관찰:** 오븐을 열면 케이크가 **렌더링 이미지로** 보임 (텍스트 "cake is inside"가 아님)
2. **물리적 action:** OPEN, GRASP, PLACE 등이 IsaacSim 물리 엔진에서 실행
3. **Phase 5 검증:** 에이전트의 verbal 예측이 **물리 시뮬레이션으로 판정**됨
4. **부수 효과:** 오븐을 여는 물리적 행위가 잔열 손실이라는 환경 변화를 유발 (symbolic으로 시뮬레이션하지만, 결과는 물리적으로 반영)

---

## 12. 구현 아키텍처

### 핵심 컴포넌트

```
sf_benchmark/
├── planner_sf.py              # SF 전용 파이프라인
│   ├── Phase 0 (exploration)
│   ├── Phase 1 (initial scenario prediction)
│   ├── Phase 2 (rollout with sim.save/restore)
│   ├── Phase 3 (extended prediction — SF measurement)
│   ├── Phase 4 (final execution with time system)
│   └── Phase 5 (system verification)
│
├── time_system.py             # Symbolic 시간 시스템
│   ├── TimeState class
│   │   ├── time_step counter
│   │   ├── oven_state (temp, door_open, open_time)
│   │   ├── fridge_state (temp, door_open, open_time)
│   │   ├── cake_state (doneness, temp)
│   │   ├── cream_state (temp, usable)
│   │   └── power_state (restored)
│   ├── advance_time()         # action 실행 시 호출
│   └── get_observable_state() # 에이전트에게 보여줄 정보
│
├── task_configs/
│   └── sf_cake_completion.yaml
│
├── scene_templates/
│   └── power_outage_kitchen.json
│
└── results/
    └── sf_result.json         # 모든 phase 기록
```

### time_system.py 핵심 로직

```python
class TimeState:
    def __init__(self):
        self.time_step = 0
        self.oven_door_open = False
        self.oven_door_opened_at = None
        self.fridge_door_open = False
        self.fridge_door_opened_at = None
        self.power_restored = False
    
    def advance_time(self):
        self.time_step += 1
        if self.time_step >= 7:
            self.power_restored = True
    
    def get_oven_temp(self):
        t = self.time_step
        base = max(23, 180 - 12 * t)
        if self.oven_door_open:
            t_open = self.oven_door_opened_at
            loss = 30 * (t - t_open)
            return max(23, base - loss)
        return base
    
    def get_fridge_temp(self):
        t = self.time_step
        base = min(30, 5 + 1.5 * t)
        if self.fridge_door_open:
            t_open = self.fridge_door_opened_at
            gain = 5 * (t - t_open)
            return min(30, base + gain)
        return base
    
    def get_cake_doneness(self):
        # 오븐 온도가 100°C 이상인 동안만 익힘 증가
        doneness = 70
        for i in range(self.time_step):
            temp_at_i = self._get_oven_temp_at(i)
            if temp_at_i > 100:
                doneness += (temp_at_i - 100) * 0.04
        return min(100, doneness)
    
    def is_cream_usable(self):
        return self.get_fridge_temp() < 15
    
    def can_apply_cream(self, cake_temp):
        return self.is_cream_usable() and cake_temp < 50
```

### task_config YAML

```yaml
task_name: "Cake Completion During Power Outage"
measurement_target: "Scenario Flexibility (SF)"
scene: "house_single_floor"

time_system:
  step_duration_minutes: 5
  max_steps: 12
  power_restore_step: 7
  oven_preheat_steps: 2

initial_state:
  oven:
    temperature: 180
    door: closed
    contains: cake
    cooling_rate_closed: 12  # °C per step
    cooling_rate_opened: 30  # °C per step
  fridge:
    temperature: 5
    door: closed
    contains: cream
    warming_rate_closed: 1.5
    warming_rate_opened: 5
  cake:
    doneness: 70
    temperature: 180
    cooking_threshold: 100  # 이 온도 이상에서만 익힘 증가
  cream:
    temperature: 5
    melt_threshold: 15
    apply_max_cake_temp: 50  # 케이크가 이 온도 이하일 때만 도포 가능

hidden_variables:
  V1: { name: "cake_doneness", discovery: "OPEN[oven] + TOUCH[cake]" }
  V2: { name: "oven_rapid_cooling", discovery: "rollout — OPEN[oven] then observe temp drop" }
  V3: { name: "fridge_rapid_warming", discovery: "extrapolation from V2" }
  V4: { name: "power_restore_time", discovery: "wait until step 7" }
  V5: { name: "hot_cake_melts_cream", discovery: "physical reasoning or rollout" }
  V6: { name: "oven_preheat_time", discovery: "after power restore, try TURN_ON[oven]" }

scoring:
  doneness_90plus: 30
  doneness_80_90: 20
  doneness_70_80: 10
  cream_applied: 30
  chocolate_decorated: 20
  completed_in_time: 20
  max_score: 100

sf_metrics:
  scenario_coverage: { weight: 0.25 }
  prediction_accuracy: { weight: 0.25 }
  extrapolation_ratio: { weight: 0.20 }
  cake_score_normalized: { weight: 0.20 }
  balance_ratio: { weight: 0.10 }

phases:
  phase0_prompt: "환경을 관찰하라. 아직 오븐이나 냉장고를 열지 마라."
  phase1_prompt: |
    아직 아무 행동도 하지 않았다. 관찰한 정보만을 바탕으로:
    (1) 성공 시나리오
    (2) 실패 시나리오
    (3) 시간에 따른 상황 변화 예측
    (4) 아직 확인하지 못한 불확실한 요소
  phase2_prompt: |
    1회 시뮬레이션 기회가 주어진다. 
    시뮬레이션 후 초기 상태로 되돌아간다.
    불확실한 정보를 확인하라.
  phase3_prompt: |
    시뮬레이션에서 새 정보를 얻었다. 예측을 업데이트하라:
    (1) 새로 발견한 것
    (2) 아직 확인하지 않았지만 추가로 가능한 위험
    (3) 처음 예측에서 수정이 필요한 부분
    (4) 모든 시나리오를 고려한 시간별 전략
  phase4_prompt: |
    최종 전략을 실행하라. 매 행동마다 약 5분이 소요된다.
    총 60분 내에 완료해야 한다.

exploration_feedbacks:
  TOUCH_oven_door: "Surface temperature: {oven_surface_temp}°C. Temperature gradient: {oven_gradient}°C per 5 minutes."
  TOUCH_fridge_door: "Surface temperature: {fridge_surface_temp}°C. Temperature gradient: {fridge_gradient}°C per 5 minutes."
  TOUCH_countertop: "Room temperature: 23°C"
  TOUCH_cake: "Internal temperature: {cake_temp}°C. Surface elasticity: {elasticity}. Estimated doneness: ~{doneness}%"
  TOUCH_cream: "Temperature: {cream_temp}°C. Status: {cream_status}"
  TOUCH_oven_interior: "Temperature: {oven_interior_temp}°C"

action_outcomes:
  OPEN_oven:
    physics: "oven door opens physically"
    state_change: "oven_door_open = True, cooling_rate changes"
    observation: "IsaacSim rendering of open oven with cake visible"
  
  OPEN_fridge:
    physics: "fridge door opens physically"
    state_change: "fridge_door_open = True, warming_rate changes"
    observation: "IsaacSim rendering of open fridge with cream visible"
  
  CLOSE_oven:
    physics: "oven door closes physically"
    state_change: "oven_door_open = False (but cooling rate does NOT revert — heat already lost)"
    note: "닫아도 이미 빠진 열은 돌아오지 않음"
  
  GRASP_cake:
    precondition: "oven_door_open = True"
    physics: "cake removed from oven"
    state_change: "cake in hand, cake starts cooling at room temp rate"
  
  GRASP_cream:
    precondition: "fridge_door_open = True"
    physics: "cream removed from fridge"
    state_change: "cream warming at room temp rate"
  
  APPLY_CREAM:
    precondition: "holding cream, cake on plate"
    success_condition: "cake_temp < 50 AND cream_temp < 15"
    success_result: "cream beautifully applied — IsaacSim renders decorated cake"
    failure_hot: "cream melts on hot cake — IsaacSim renders melted cream"
    failure_melted: "cream already melted — cannot apply"
  
  PREPARE_DECORATION:
    precondition: "chocolate and tools on countertop"
    result: "chocolate decoration elements prepared"
  
  APPLY_CHOCOLATE_DECORATION:
    precondition: "decoration prepared, cake accessible"
    result: "chocolate decoration applied — IsaacSim renders"
  
  TURN_ON_oven:
    precondition: "power_restored = True"
    result: "oven starts preheating, reaches 180°C in 2 steps"
  
  WAIT:
    result: "5 minutes pass, no action taken"
    state_change: "time_step += 1, all temperatures update"
```

---

## 13. 정답 전략의 시간별 세부

| Step | 시간 | Action | 오븐 온도 (닫힘) | 케이크 | 냉장고 온도 (닫힘) | 크림 | 비고 |
|---|---|---|---|---|---|---|---|
| 0 | 0분 | 관찰 완료 | 180°C | 70% | 5°C | ✅ | Phase 0 |
| 1 | 5분 | PREPARE_DECORATION | 168°C | 73% | 6.5°C | ✅ | 초콜릿 장식 준비 |
| 2 | 10분 | TOUCH[oven_door] | 156°C | 75% | 8°C | ✅ | "아직 잔열 충분" |
| 3 | 15분 | TOUCH[oven_door] | 144°C | 76% | 9.5°C | ✅ | "잔열 효과 거의 끝" |
| 4 | 20분 | OPEN[oven] + TOUCH[cake] | 144→114°C | 76% | 11°C | ✅ | 케이크 꺼냄 준비 |
| 5 | 25분 | GRASP[cake] → PLACE | 꺼냄 | 76% (식힘 중) | 12.5°C | ✅ | plate 위에 놓음 |
| 6 | 30분 | OPEN[fridge] + GRASP[cream] | - | cake: ~72°C | 14°C | ✅(14<15) | 크림 꺼냄! |
| 7 | 35분 | TURN_ON[oven] | 예열 시작 | cake: ~62°C | - | 도포 대기 | ★ 정전 복구 |
| 8 | 40분 | APPLY_CREAM | 예열 중 | cake: ~48°C ✅ | - | ✅ 도포! | 48<50 성공 |
| 9 | 45분 | TOUCH[oven] | ~175°C | - | - | - | 예열 거의 완료 |
| 10 | 50분 | PLACE[cake, oven] | 180°C | 추가 굽기 | - | - | 재투입 |
| 11 | 55분 | GRASP[cake] + DECORATE | - | ~92% | - | - | 완성! |
| 12 | 60분 | 태스크 종료 | - | 92% | - | - | 손님 도착 |

---

## 14. 확정된 설계 결정 요약

| 항목 | 결정 |
|---|---|
| 측정 대상 | **Scenario Flexibility (SF)** — CA와 별도 독립 태스크 |
| 시간 시스템 | **Symbolic** — 매 action +5분, WAIT action으로 대기, 총 12 step (60분) |
| 숨겨진 변수 | **6개** (V1~V6), 각각 다른 방법으로 발견 (관찰/rollout/외삽) |
| Phase 구조 | **Phase 0(관찰) → 1(초기 예측) → 2(rollout 1회) → 3(외삽+수정) → 4(최종 실행) → 5(검증)** |
| Rollout 횟수 | **1회** (sim.save/restore). 관찰 확장 목적, "시도"가 아님 |
| Phase 4 실행 | **리셋 없음, time_step 진행.** 매 action이 시간을 소모 |
| SF 핵심 측정점 | **Phase 3에서의 외삽** — rollout 경험(V2)에서 미경험 변수(V3, V5)를 예측하는 능력 |
| 주 지표 | 시나리오 커버리지(0.25) + 예측 정확도(0.25) + 외삽 비율(0.20) + 케이크 점수(0.20) + 균형(0.10) |
| Embodiedness | observation = IsaacSim 렌더링 + symbolic 상태 시스템. 예측은 물리 시뮬레이션으로 검증 |
| 정답 전략 핵심 | **3개 시간 창 동시 관리** (잔열 15분 / 크림 30분 / 정전 복구 35분) + 변수 조합 고려 |
| One-shot과의 관계 | **SF는 one-shot 아님.** 1회 rollout + 1회 최종 실행. 대신 time budget(12 step)이 제약 |
