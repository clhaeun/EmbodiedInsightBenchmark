# Scenario Flexibility (SF) 평가 프레임워크 총 정리
## Embodied LLM 환경에서의 SF 측정을 위한 태스크 설계

---

## 1. 이론적 배경: Scenario Flexibility란?

### 1.1. 논문에서의 정의

"Imagining and building wise machines: The centrality of AI metacognition" (Johnson, Karimi, Bengio et al.)에서 Scenario Flexibility(SF)는 **perspectival metacognition**의 핵심 구성 요소 중 하나로 정의된다.

> **Scenario Flexibility:** 시나리오가 전개될 수 있는 다양한 방식을 고려하여 가능한 우발 상황(contingencies)을 파악하는 능력

SF는 논문의 Table 2에서 6개 메타인지 전략 중 유일하게 **학술적 인용이 없는** 항목으로, 저자들의 독자적 합성으로 보인다. Grossmann (2017)의 Wise Reasoning Model의 "flexibility" 요소에서 파생된 것으로 추정.

### 1.2. SF의 기능적 역할

SF는 메타인지의 세 가지 기능 중 특히 **input-seeking(정보 탐색)**과 **outcome monitoring(결과 점검)**에 핵심적으로 기여한다:

- **Input-seeking:** "이 상황이 앞으로 어떻게 전개될 수 있는가?"를 묻고, 다양한 미래 가능성을 탐색하여 의사결정에 필요한 정보를 사전에 확보
- **Outcome monitoring:** "최선의 시나리오에만 의존하고 있지 않은가?"를 점검하여, 최악의 시나리오까지 대비하는 robust한 전략을 수립
- **Conflict resolution:** 복수의 시나리오가 서로 다른 전략을 요구할 때, 어떤 전략이 가장 다양한 시나리오에서 작동하는지 판별

### 1.3. 논문 내 사례 (Ron)

Ron 사례가 SF의 대표적 예시이다:
- Ron(정치 컨설턴트)은 후보의 **최선 시나리오(승리)뿐 아니라 최악 시나리오(패배)까지 상상**하고, 패배의 원인까지 분석한다.
- 핵심은 **"실행 전에"** 다양한 결과 가능성을 예측하고, 각 시나리오의 원인-결과 메커니즘을 이해하여, robust한 전략을 사전에 수립하는 것이다.
- Ron은 선거를 **실제로 치러보지 않고**, 순수하게 "만약 이렇게 되면?" "만약 저렇게 되면?"을 상상한다.

### 1.4. SF의 핵심 특성: Prospection (미래 예측)

SF의 본질은 **prospection(전향적 인지)**이다:
- **Prospection (SF):** "앞으로 무슨 일이 벌어질 수 있는가?" — 현재 → 미래 방향
- **Retrospection (반성):** "왜 실패했는가?" — 과거 → 현재 방향

기존의 "실패 후 반성"(Reflexion, REFLECT 등)은 retrospection이지 SF가 아니다. SF는 **아직 일어나지 않은 일의 다양한 가능성을 미리 고려**하는 것이다.

### 1.5. 인접 개념과의 구분

| 메타인지 전략 | 핵심 질문 | SF와의 차이 |
|---|---|---|
| Context Adaptability | "이 상황이 무엇과 비슷한가?" | 유사성 축 — 현재 vs 참조 상황 비교. SF는 시간 축 — 미래 전개 가능성 |
| Intellectual Humility | "내가 모르는 것은 무엇인가?" | 자기 지식의 한계 인식 — SF는 미래의 불확실성을 다양하게 탐색 |
| Planning | "어떤 순서로 행동할 것인가?" | 행동 시퀀스 최적화 — SF는 "각 행동의 결과가 어떻게 전개될 수 있는가"의 다양성 |
| Reactive Adaptation | "실패했으니 어떻게 고칠 것인가?" | 사후 대응 — SF는 **사전 예측** (행동 전에 실패 가능성을 상상) |

본 프레임워크는 SF만을 순수하게 측정하기 위해, 위 인접 개념들과 겹치지 않도록 태스크를 설계한다.

### 1.6. SF 측정의 핵심: "경험에서 미경험으로의 외삽"

SF가 높은 에이전트의 핵심 행동 패턴:
1. **물리적 관찰**로 환경의 기본 변수를 파악 (Layer 2)
2. **제한된 rollout**으로 숨겨진 변수와 부수 효과를 발견 (Layer 3)
3. rollout에서 발견한 것을 **아직 경험하지 않은 상황에까지 일반화(외삽)** — 이것이 SF의 핵심
4. 외삽 결과를 종합하여 **다양한 시나리오에 대비하는 robust한 전략**을 수립

예: "오븐을 열면 잔열이 급격히 빠진다" (rollout에서 발견) → **"냉장고도 열면 냉기가 급격히 빠질 것이다"** (외삽) → 두 자원의 시간 창을 동시에 관리하는 전략 수립.

---

## 2. 평가 프레임워크: Embodied SF Pipeline

### 2.1. 프레임워크 개요

**한 줄 정의:** 에이전트가 POMDP + non-stationary 환경에서 물리적 관찰과 제한된 rollout을 통해 숨겨진 변수를 발견하고, 발견한 것에서 미발견 변수까지 외삽하여, 다양한 시나리오(최선~최악)를 예측하고, 그 예측에 기반한 robust한 시간별 분기 전략을 수립·실행하는 평가 프레임워크.

**핵심 측정 대상:** 에이전트가 제한된 경험(1회 rollout)에서 미경험 시나리오까지 외삽하여, 다양한 결과 가능성을 사전에 예측하고, 그에 기반한 contingency를 포함한 전략을 수립할 수 있는가?

### 2.2. 환경 및 기술 스택

| 구성 요소 | 선택 |
|---|---|
| 시뮬레이터 | NVIDIA IsaacSim (OmniGibson) |
| 에셋 | BEHAVIOR-1K dataset |
| 로봇 | Tiago (dual-arm mobile manipulator) |
| 시간 시스템 | **Symbolic** — 매 action마다 고정 시간 경과 (예: 5분/step) |
| Rollout | `sim.save()` / `sim.restore()` 네이티브 활용 |
| 평가 방식 | 복합: 시나리오 커버리지 + 예측 정확도 + 외삽 비율 + 태스크 점수 + 균형 |

### 2.3. CA와의 핵심 구조 차이

| | CA (CATS) | SF (본 프레임워크) |
|---|---|---|
| 정보 소스 | 외부 제공 (Demo 영상) | 자체 수집 (관찰 + rollout) |
| 핵심 인지 | 구조적 매핑 (현재 ↔ 참조) | 미래 예측 + 외삽 (현재 → 미래들) |
| 시간 | 없음 (정적 상황) | **핵심** (시간에 따라 환경 변화) |
| 실행 제약 | One-shot (1회 선택) | Time budget (N step 내 완수) |
| 환경 특성 | 정적 (변하지 않음) | **Non-stationary** (시간 경과 + 행동의 부수 효과) |
| 관찰 | 물리적 탐색 | 물리적 탐색 + **rollout** |
| 평가 초점 | "올바른 도구를 골랐는가" | "다양한 시나리오를 예측했는가 + robust한 전략인가" |

---

## 3. 태스크 구조: 5 Phase + 시스템 검증

### 정보의 3가지 층위

SF 태스크에서 에이전트가 접근하는 정보는 세 계층으로 구분된다:

| 층위 | 발견 방법 | 예시 | 에이전트에게 요구되는 능력 |
|---|---|---|---|
| **Layer 1 — Verbal** | LLM 상식으로 추론 가능 | "정전이면 오븐이 꺼진다", "크림은 온도가 오르면 녹는다" | 기본 상식 추론 |
| **Layer 2 — 물리적 관찰** | Exploration primitive (행동 없이 관찰만) | 오븐 외벽 172°C/-3.2°C per step, 냉장고 외벽 8°C/+0.5°C per step | **센서 데이터에서 시간 변수를 추정** |
| **Layer 3 — Rollout** | 실제 행동 후 결과 관찰 | "오븐을 열면 -30°C/step으로 급락" (관찰의 부수 효과) | **행동의 비의도적 부수 효과를 인식** |
| **외삽 (SF 핵심)** | Layer 3 경험에서 미경험으로 일반화 | "오븐 급락 → 냉장고도 마찬가지일 것" | **경험→미경험 일반화 추론** |

**정답 전략은 Layer 1+2+3+외삽의 종합을 요구한다.** 어떤 Layer가 빠지면 다른 종류의 함정으로 빠진다.

---

### Phase 0 — 환경 관찰 (Exploration)

**목적:** 에이전트가 행동 없이 환경의 기본 물리 상태를 관찰하여 핵심 변수의 존재와 대략적 수치를 파악.

**핵심 제약:**
- 오브젝트를 직접 조작(OPEN, GRASP 등)하지 않고 **외부에서만** 관찰
- NAVIGATE_TO, TOUCH(외부 표면) 등만 허용
- **time_step은 아직 진행되지 않음** (관찰은 시간 소모 없음)

**Exploration Primitives:**

| Primitive | 반환 형식 | 발견 가능한 정보 |
|---|---|---|
| NAVIGATE_TO[object] | IsaacSim 렌더링 이미지 | 오브젝트 위치, 외형, 배치 |
| TOUCH[surface] | 센서 수치 (온도, gradient 등) | 외벽 온도, 변화율 (내부 상태 추정의 근거) |

**핵심:** 내부 상태(오븐 안 케이크, 냉장고 안 크림)는 관찰 불가 → POMDP. 외벽 온도/gradient에서 내부를 **추정**해야 함.

---

### Phase 1 — 초기 시나리오 예측 (Verbal, SF Baseline)

**목적:** 에이전트가 **아직 아무것도 실행하지 않은 상태에서** Phase 0의 관찰만으로 다양한 시나리오를 생성.

**프롬프트:**
```
"아직 아무 행동도 하지 않았다. 관찰한 정보만을 바탕으로:
(1) 성공 시나리오 — 어떻게 하면 목표를 달성할 수 있는가?
(2) 실패 시나리오 — 어떤 것들이 잘못될 수 있는가?
(3) 시간에 따라 상황이 어떻게 변할 수 있는가?
(4) 아직 확인하지 못한 불확실한 요소는 무엇인가?"
```

**측정 항목:**
- 시나리오 수 (성공 + 실패)
- 변수 커버리지 (설계자가 심어놓은 숨겨진 변수 중 몇 개를 언급했는가)
- 최선+최악 균형 (성공만? 실패도 포함?)
- 시간 추정 여부 (Layer 2 데이터에서 수치적 추정을 했는가)
- 불확실성 인식 ("모르는 것"을 명시적으로 나열했는가)

**Ron 대응:** 선거 전에 여론 조사만 보고 "이길 수도 있고, 이런 이유로 질 수도 있다"를 상상하는 단계.

---

### Phase 2 — 확인 Rollout (1회, 관찰 확장)

**목적:** "시도"가 아니라 **"관찰의 확장"** — Ron이 여론 조사를 돌리는 것에 해당. 물리적 상호작용으로만 알 수 있는 정보를 획득.

**구현:**
```
sim.save(S₀)
에이전트가 행동 실행 (OPEN, TOUCH 등)
→ 결과 관찰 (숨겨진 변수 발견 + 행동의 부수 효과 발견)
→ 반성
sim.restore(S₀) — 초기 상태로 복원
```

**핵심:** Rollout 동안의 action도 **time_step을 소모**한다 (rollout 내에서 시간이 흐름). 하지만 `sim.restore()`로 초기 상태로 복원되므로 최종 실행에는 영향 없음.

**Rollout의 의도적 제한: 1회만 허용.** 모든 변수를 rollout으로 직접 발견할 수 없도록 하여, **Phase 3에서의 외삽을 강제**한다.

**측정 항목:**
- rollout 목적성: "일단 해보자" (탐색) vs "불확실한 것을 확인하겠다" (검증)
- 발견한 변수: rollout에서 직접 경험한 숨겨진 변수 수
- 부수 효과 인식: "문 열면 잔열 급락" 같은 행동의 비의도적 결과를 인식했는가

---

### Phase 3 — 확장 시나리오 예측 + 계획 수정 (SF 핵심 측정)

**목적:** Rollout 경험을 바탕으로 시나리오를 업데이트하고, **경험하지 않은 변수까지 외삽.** 이것이 SF의 핵심 측정 지점이다.

**프롬프트:**
```
"시뮬레이션에서 새로운 정보를 얻었다. 예측을 업데이트하라:
(1) 새로 발견한 것은?
(2) 이 발견을 바탕으로, 아직 확인하지 않았지만
    추가로 존재할 수 있는 위험은?
(3) 처음 예측(Phase 1)에서 수정이 필요한 부분은?
(4) 모든 시나리오를 고려한 시간별 분기 전략은?"
```

**핵심 측정 — 외삽:**

"경험한 것에서 미경험 시나리오까지 외삽하는 능력"

```
SF 공식:
  D = rollout에서 직접 발견한 변수 수
  E = verbal 외삽으로 정확히 예측한 미경험 변수 수
  N = 총 숨겨진 변수 수

  SF_extrapolation = E / (N - D)
  = "경험하지 않은 변수 중 몇 개를 외삽했는가"
```

**측정 항목:**
- 외삽 범위: rollout에서 경험하지 않은 변수를 몇 개 추가 예측했는가
- 외삽 정확도: 외삽한 것 중 실제 변수와 일치하는 비율
- 변수 조합 사고: 단일 변수만? V2+V4 같은 조합 시나리오도?
- 계획 수정 질: Phase 1 대비 구체적으로 어떻게 수정?
- 시간별 분기: 시점별 조건 분기가 포함됐는가
- contingency: "만약 X이면 Y" 대비책이 포함됐는가
- 관찰 비용 인식: "열면 잔열/냉기 손실"이라는 트레이드오프 반영

**Ron 대응:** 여론 조사 결과를 보고 "그러면 이런 것도 가능하겠네?"를 추가 상상 + 각 시나리오에 대한 contingency plan 수립.

---

### Phase 4 — 최종 전략 수립 + 실행

**목적:** 모든 시나리오를 종합하여 robust한 전략을 수립하고, 실제로 실행.

**핵심 제약:**
- **리셋 없음** — `sim.restore()` 사용 불가. 행동의 결과가 영구적.
- **Time budget** — 매 action이 시간을 소모하고, 총 시간 내에 완수해야 함.
- 시간에 따라 환경이 변화 (**non-stationary**) — 잔열 감소, 크림 녹음, 정전 복구 등.

**실행 방식:** CA의 Stage 3과 동일한 ReAct 루프. 기존 action primitive + NEW_ACTION.

**측정 항목:**
- 태스크 완성도 점수 (태스크별 채점 기준에 따라)
- Phase 3의 시나리오 분석이 실제 전략에 반영되었는가
- contingency가 실행 중 실제로 발동되었는가 (예: 정전 복구 시 오븐 재가동)

---

### Phase 5 — 시스템 검증 (에이전트 모르게)

**목적:** 에이전트의 Phase 1+3 예측을 IsaacSim에서 물리적으로 검증. **에이전트는 이 Phase의 존재를 모른다.**

**방법:** 평가자(시스템)가 에이전트가 예측한 각 시나리오에 해당하는 조건을 IsaacSim에서 실행하고, 에이전트의 예측과 실제 물리 결과를 비교.

```
예: 에이전트 예측 "오븐을 열면 잔열이 급격히 빠진다"
→ sim에서 step 0에 OPEN[oven] → 온도 급락 확인 → 예측 정확 ✅

예: 에이전트 예측 "냉장고도 열면 냉기가 급격히 빠진다" (외삽)
→ sim에서 step 0에 OPEN[fridge] → 크림 온도 급상승 확인 → 외삽 정확 ✅
```

**측정 항목:**
- 예측 정확도: 시스템 검증에서 정확한 예측 수 / 총 예측 수

---

## 4. 태스크 설계 원칙

### 4.1. POMDP — 부분 관찰 가능성

핵심 변수는 **직접 행동해야만 발견 가능**해야 한다:
- 오븐 안 케이크 상태 → 열어봐야 앎
- 냉장고 안 크림 온도 → 열어봐야 앎
- 정전 복구 시점 → 기다려봐야 앎

Phase 0에서 외부 관찰(TOUCH 외벽)로 **추정은 가능하지만 정확한 값은 알 수 없는** 구조.

### 4.2. Non-stationary — 시간에 따른 환경 변화

환경이 시간에 따라 자동으로 변화해야 한다:
- 에이전트의 행동과 무관하게: 오븐 잔열 감소, 냉장고 온도 상승, 정전 복구
- 에이전트의 행동에 의해: 문 열면 감쇠율 급변 (부수 효과)

이것이 **시간별 분기 전략**을 강제한다 — "언제 행동하느냐"가 결과를 바꿈.

### 4.3. 행동의 부수 효과 (Side Effects)

에이전트의 행동이 **의도하지 않은 환경 변화**를 유발해야 한다:
- OPEN[oven] = 케이크 확인 (의도) + 잔열 급격 손실 (부수 효과)
- OPEN[fridge] = 크림 확인 (의도) + 냉기 급격 손실 (부수 효과)

**관찰의 비용:** 정보를 얻기 위해 환경을 열어보면, 그 행위 자체가 환경을 악화시킨다. 이 트레이드오프를 인식하는 것이 SF의 중요한 요소.

### 4.4. 숨겨진 변수의 다층 구조

설계자가 심어놓은 숨겨진 변수는 세 가지 발견 방법으로 구분된다:

| 발견 방법 | 역할 | 예시 |
|---|---|---|
| Phase 0 관찰로 발견 가능 | Baseline 정보 | 바닥 재질, 외벽 온도 |
| Phase 2 rollout으로만 발견 가능 | 행동의 부수 효과 | "열면 급락" |
| **Phase 3 외삽으로만 도달 가능** | **SF 핵심 측정** | "오븐이 그러면 냉장고도" |

**최소 1개 이상의 변수가 "외삽으로만 도달 가능"해야** SF를 유의미하게 측정할 수 있다.

### 4.5. 시간 창(Time Window)의 교차

정답 전략이 **복수의 시간 창을 동시에 관리**하는 것을 요구해야 한다:

```
시간 창 1: 잔열 효과 (0~15분에만 유효)
시간 창 2: 크림 유효기간 (0~30분에 녹기 시작)
시간 창 3: 정전 복구 (35분에 복구)
→ 최적 전략은 이 세 시간 창의 교차점에서 결정됨
```

이것이 SF를 단순 planning과 구분짓는다 — planning은 "어떤 순서로 할까"이지만, SF는 "미래에 어떤 시간 창들이 존재하고, 그것들이 어떻게 상호작용하는가"를 예측하는 것.

### 4.6. 함정 구조

각 함정은 **SF의 특정 결핍**에 대응한다:

| 함정 | SF 결핍 | Ron 비유 |
|---|---|---|
| 즉시 확인 (모두 열기) | 관찰 비용 미인식 | "여론 조사 결과를 언론에 유출해서 역효과" |
| 정전 복구 대기 | 단일 시나리오(최선)만 고려 | "이길 것이라 확신하고 대비 안 함" |
| 크림 먼저 | 변수 조합 미고려 (V1×V3) | "한 정책만 보고 부작용 미고려" |
| 잔열 과신 | 시간 추정 실패 | "지지율이 계속 오를 것으로 과신" |
| 포기 | SF 부재 — 미래 가능성 미탐색 | "지는 것 같으니 캠페인 중단" |

---

## 5. 측정 지표

### 5.1. 주 지표

| 지표 | 가중치 | 측정 Phase | 설명 |
|---|---|---|---|
| **시나리오 커버리지** | 0.25 | Phase 1+3 | 예측한 시나리오 중 숨겨진 변수와 매칭되는 수 / N |
| **예측 정확도** | 0.25 | Phase 5 검증 | 시스템 검증에서 정확한 예측 수 / 총 예측 수 |
| **외삽 비율** | 0.20 | Phase 3 | Phase 3에서 추가한 정확한 시나리오 수 / (N - D) |
| **태스크 완성도** | 0.20 | Phase 4 종료 | 태스크별 채점 기준 (0~100 → 0~1 정규화) |
| **최선+최악 균형** | 0.10 | Phase 1+3 | 실패 시나리오 수 / 총 시나리오 수 (0.3~0.7이 이상적) |

### 5.2. 보조 지표 (참고용)

| 지표 | 측정 Phase | 설명 |
|---|---|---|
| 변수 조합 사고 | Phase 1+3 | V1×V3, V2×V4 등 교차 시나리오 포함 여부 |
| 시간 추정 정확도 | Phase 1+3 | "잔열 15분", "크림 30분" 등의 추정이 실제와 가까운가 |
| 계획 수정 질 | Phase 3 | Phase 1 → Phase 3에서 구체적 수정 내용 |
| contingency 포함 | Phase 3+4 | "만약 X이면 Y" 대비책의 유무 |
| 관찰 비용 인식 | Phase 1+3 | "열면 잔열/냉기 손실"이라는 트레이드오프 반영 |
| rollout 목적성 | Phase 2 | 무작위 시도 vs 목적적 확인 |
| Phase 1→3 개선도 | Phase 1 vs 3 비교 | rollout 후 시나리오가 얼마나 풍부/정확해졌는가 |
| 과대/과소 예측 비율 | Phase 5 검증 | false positive(헛다리) vs false negative(놓침) |

---

## 6. CA와의 관계

### 6.1. 완전 독립적 프레임워크

CA와 SF는 동일 논문(Johnson et al.)의 6개 메타인지 전략 중 **서로 다른 축**을 측정하며, **태스크 설계·실행·평가가 완전히 독립적**이다:
- **CA:** 유사성 축 — "이 상황이 저 상황과 어떻게 다른가?" → 현재를 과거/참조와 비교
- **SF:** 시간 축 — "이 상황이 앞으로 어떻게 전개될 수 있는가?" → 현재에서 미래를 예측

CA 태스크와 SF 태스크는 동시에 측정하지 않으며, 각각 별도의 태스크·플래너·평가 파이프라인으로 운영된다.

### 6.2. 구조적 대응

| 설계 요소 | CA (CATS) | SF |
|---|---|---|
| 설계자가 미리 정의 | Tool 후보 5개 + 정답 1개 | 숨겨진 변수 N개 + 각 변수의 분기 |
| 에이전트의 과제 | 5개 중 정답 tool 선택 | N개 변수를 관찰/rollout/외삽으로 발견 |
| 정보 소스 | Demo 영상 (외부 제공) | 환경 관찰 + rollout (자체 수집) |
| 실행 제약 | One-shot (1회 선택) | Time budget (N step 내 완수) |
| 주 지표 | Tool 선택 정확도 | 시나리오 커버리지 + 예측 정확도 + 태스크 점수 |
| 핵심 인지 능력 | 구조적 매핑 | 미래 예측 + 외삽 |

### 6.3. 동일 에이전트에서의 독립 측정

동일 LLM 에이전트가 CA에서 높은 점수를 받지만 SF에서 낮은 점수를 받을 수 있다 (또는 그 반대). 예:
- **CA 높고 SF 낮음:** 참조 상황과의 구조적 매핑은 잘하지만, 미래 가능성의 다양성을 고려하지 않음
- **CA 낮고 SF 높음:** 미래 시나리오는 다양하게 생성하지만, 현재 상황의 고유 맥락을 정확히 파악하지 못함

이 독립성이 두 프레임워크를 별도로 운영하는 정당성을 제공한다.

---

## 7. IsaacSim 활용 정당성

| 설계 요소 | IsaacSim 없이 가능한가? | IsaacSim이 필요한 이유 |
|---|---|---|
| POMDP (내부 상태 숨기기) | 텍스트로 가능하지만 VQA와 구별 불가 | 오븐을 **물리적으로 열어야** 내부가 보이는 렌더링 |
| Non-stationary (시간 변화) | 텍스트로 가능 | Symbolic 시간 시스템이지만, **결과는 IsaacSim 렌더링으로 표현** |
| Rollout (sim.save/restore) | 불가능 | **IsaacSim 네이티브 기능** — 상태 저장/복원으로 "상상" 구현 |
| 부수 효과 검증 | 불가능 | "열면 급락"의 ground truth를 물리 시뮬레이션으로 판정 |
| Phase 5 시스템 검증 | 불가능 | 에이전트 예측을 IsaacSim에서 **실제로 실행하여 검증** |

**결론:** `sim.save/restore`를 통한 rollout + Phase 5의 물리적 검증이 IsaacSim 사용의 필수적 정당성을 제공한다.

---

## 8. Symbolic 시간 시스템

### 8.1. 왜 Symbolic인가

OmniGibson의 물리 엔진은 실시간 물리 step만 지원하고, "분 단위 시간 경과"나 "연속 온도 감쇠"를 네이티브로 시뮬레이션하지 않는다. 따라서:

- **시간 경과:** 매 action마다 time_step += 1 (= 고정 분 수)
- **상태 변화:** lookup table / 수식으로 계산 (에이전트는 모름)
- **결과 표현:** 계산된 상태를 IsaacSim에서 물리적으로 반영 (렌더링)

### 8.2. CA와의 패턴 일치

CA에서 확립된 **"symbolic 과정 + 물리적 결과"** 패턴과 동일:

```
CA: NEW_ACTION[PRESS_AND_PICK, potato_half, glass_shards]
    → symbolic 판정: (potato, glass_shards, spill_area) → SUCCESS
    → 물리적 결과: 파편 제거, 깨끗한 바닥 렌더링

SF: OPEN[oven] at time_step 3
    → symbolic 판정: oven_temp = 144°C, cake = 76%
    → 물리적 결과: 오븐 문 열림, 케이크가 보이는 렌더링
```

### 8.3. 구현 컴포넌트

```
time_system.py:
  - TimeState 클래스: time_step, oven/fridge/cake/cream 상태 관리
  - advance_time(): action 실행 시 호출, 모든 상태 업데이트
  - get_observable_state(): 에이전트에게 보여줄 정보 반환
  - 내부 수식은 에이전트가 접근 불가 (POMDP)
```

---

## 9. 난이도 스케일링 (3.1 → 3.4)

CA와 동일하게 4단계로 구성하되, SF의 핵심 축인 **"미래 예측의 깊이"**를 기준으로 스케일링한다. CA가 2.x 넘버링이므로 SF는 3.x로 구분.

### Level 3.1 — 단일 시간 창 + 관찰 가능한 변화 (Basic Prospection)

**구조:** 환경에 **1개의 시간 변수**만 존재하고, 그 변수는 Phase 0 관찰로 변화율을 추정 가능. Rollout으로 직접 확인 가능.

**SF 측정 초점:** "시간이 흐르면 환경이 변한다"는 기본 인식 + 단일 time window 관리.

**예시:** 냉장고에서 꺼낸 아이스크림이 녹고 있다. 외벽 TOUCH로 온도 상승률 관찰 → "N분 후 완전히 녹는다" 예측 → 시간 내 서빙 완료.

**외삽 요구:** 없음 (직접 관찰 가능)

---

### Level 3.2 — 복수 시간 창 + 관찰 비용 (Observation Cost Awareness)

**구조:** **2개 이상의 시간 변수**가 존재하고, 관찰 행위 자체가 **환경을 악화**시킨다 (부수 효과). Phase 2 rollout에서 부수 효과를 발견해야 함.

**SF 측정 초점:** "정보를 얻기 위해 환경을 열면, 그 행위가 환경을 망친다"는 트레이드오프 인식.

**예시:** 오븐(잔열 감소 중) + 냉장고(온도 상승 중). 오븐을 열어 케이크를 확인하면 잔열이 급락. 관찰의 비용을 인식하고 최적 타이밍에 행동.

**외삽 요구:** 없음 (두 변수 모두 rollout에서 직접 경험 가능)

---

### Level 3.3 — 외삽 필수 + 시간 창 교차 (Extrapolation-Required Prospection)

**구조:** **숨겨진 변수 N개** 중 일부는 rollout 1회로는 경험 불가. Phase 2 rollout에서 발견한 패턴을 **미경험 변수에까지 외삽**해야 정답 전략 도출 가능. 복수 시간 창이 교차.

**SF 측정 초점:** "경험한 것에서 미경험으로의 일반화" — SF의 핵심.

**예시:** 오븐 급락 rollout 경험 → 냉장고도 열면 급락할 것이라 외삽 → 정전 복구 시점까지 고려하여 3개 시간 창의 교차점에서 전략 수립.

**외삽 요구:** 필수 (최소 1개 변수가 외삽으로만 도달 가능)

---

### Level 3.4 — 연쇄 효과 + Contingency 필수 (Cascading Scenarios)

**구조:** 하나의 사건이 **연쇄적으로 다른 변수에 영향**을 미치며, "만약 X이면 Y, 그러면 Z" 형태의 다단계 시나리오 추론이 필요. **Contingency plan이 없으면 실패**.

**SF 측정 초점:** 연쇄 시나리오 추론 + if-then 분기 전략 수립 + 실행 중 contingency 발동.

**예시:** 정전 → 오븐 꺼짐 → 케이크 정지 + 냉장고 온도 상승 가속 → 정전 복구 시 오븐 재가동 가능 but 크림은 이미 녹았을 수도 → "정전이 언제 복구되느냐"에 따라 완전히 다른 전략 필요.

**외삽 요구:** 다단계 (A→B→C 연쇄)

---

### 난이도 간 관계

```
Level 3.1: SF 기본 — "시간이 흐르면 환경이 변한다"
    ↓ (관찰 비용 + 부수 효과 인식 추가)
Level 3.2: SF + 관찰 비용 — "열어보면 정보를 얻지만 환경이 악화된다"
    ↓ (외삽 필수화)
Level 3.3: SF + 외삽 — "오븐이 그러면 냉장고도 그럴 것이다" (핵심)
    ↓ (연쇄 추론 + contingency 필수)
Level 3.4: SF + 연쇄 — "A가 B를 유발하고, B가 C를 유발한다면?"
```

논문 관점에서, **3.1~3.3이 SF의 core evaluation**이고, **3.4는 extended evaluation**으로 위계를 둔다.

---

## 10. 구체적 태스크 예시: 정전 케이크 완성 (Level 3.3)

### 10.1. 태스크 개요

| 항목 | 내용 |
|------|------|
| task_name | `power_outage_cake_completion` |
| Level | 3.3 (외삽 필수 + 시간 창 교차) |
| 로봇 | Tiago (dual-arm) |
| 씬 | house_single_floor 주방 |
| 목표 | 케이크에 크림을 올려서 countertop에 제출 |

### 10.2. 환경 초기 상태

- **오븐**: 170°C, 안에 케이크 (80% 완성, 100%에 꺼내야 함)
- **냉장고**: 4°C, 안에 생크림 (15°C 이상이면 녹아서 사용 불가)
- **정전 상태**: time_step 0에서 정전 발생. 오븐은 잔열만, 냉장고는 보온만.
- **정전 복구**: time_step 7에 자동 복구 (에이전트에게 알려지지 않음)
- **countertop**: 제출 위치, 장식 도구, 접시

### 10.3. 숨겨진 변수 (N=6)

| # | 변수 | 발견 Layer | 발견 방법 | 에이전트 미발견 시 결과 |
|---|------|-----------|----------|----------------------|
| V1 | 오븐 잔열 감쇠율 (닫힌 상태: -3°C/step) | Layer 2 | Phase 0 TOUCH[oven 외벽] | 시간 추정 실패 → 너무 늦게 꺼냄 |
| V2 | 냉장고 온도 상승률 (닫힌 상태: +0.5°C/step) | Layer 2 | Phase 0 TOUCH[fridge 외벽] | 크림 시간 창 과소평가 |
| V3 | 오븐 문 열면 감쇠 급변 (-30°C/step) | Layer 3 | Phase 2 rollout — OPEN[oven] | 잔열 과신 → 관찰 비용 미인식 |
| V4 | **냉장고 문 열면 상승 급변 (+5°C/step)** | **외삽** | V3에서 일반화 | **크림을 일찍 꺼내면 녹음** — SF 핵심 |
| V5 | 정전 복구 시점 (step 7) | Layer 3 | Phase 2 rollout — 기다려보면 전기 복구 | 오븐 재사용 가능성 놓침 |
| V6 | 케이크 완성도 임계값 (100% = step 3에서 꺼내야) | Layer 3 | Phase 2 rollout — OPEN[oven] 후 관찰 | 덜 익힘 or 과열 |

### 10.4. 시간 진행표 (에이전트에게 비공개)

```
Step 0: 정전 발생. 오븐 170°C, 케이크 80%, 냉장고 4°C, 크림 OK
Step 1: 오븐 167°C, 케이크 87%, 냉장고 4.5°C
Step 2: 오븐 164°C, 케이크 93%, 냉장고 5.0°C
Step 3: 오븐 161°C, 케이크 100% ★꺼내야★, 냉장고 5.5°C
Step 4: 오븐 158°C, 케이크 과열 시작, 냉장고 6.0°C
Step 5: 오븐 155°C, 냉장고 6.5°C
Step 6: 오븐 152°C, 냉장고 7.0°C
Step 7: ★정전 복구★ 오븐 재가동 가능, 냉장고 7.5°C → 냉각 시작
...
(문을 열면 각각 -30°C/step, +5°C/step으로 급변)
```

### 10.5. 정답 전략 (oracle)

```
Phase 0: TOUCH[oven 외벽] → 172°C, -3°C/step 추정
         TOUCH[fridge 외벽] → 8°C, +0.5°C/step 추정
Phase 1: "잔열이 약 15 step 후 소멸, 냉장고는 약 20 step 후 15°C 도달"
Phase 2 (rollout): OPEN[oven] → 케이크 87% 확인 + 잔열 -30°C 급락 관찰
         → sim.restore()
Phase 3: "오븐을 열면 급락한다. 냉장고도 열면 급상승할 것이다(외삽).
         따라서: step 3까지 기다려 케이크 100% → OPEN[oven] → GRASP[cake]
         → 그 직후에 OPEN[fridge] → GRASP[cream] (노출 최소화)
         → 즉시 크림 올리고 제출. 정전 복구를 기다릴 여유는 없다."
Phase 4: Step 0-2 대기 → Step 3 OPEN[oven]+GRASP[cake] → OPEN[fridge]+GRASP[cream]
         → 크림 올리기 → PLACE_ON_TOP[countertop] → DONE
```

### 10.6. 함정별 결과

| 함정 전략 | 실패 원인 | SF 결핍 유형 |
|----------|----------|-------------|
| Step 0에서 바로 오븐+냉장고 열기 | 잔열 급락 → 케이크 미완성 + 크림 시간 창 단축 | 관찰 비용 미인식 |
| 정전 복구 기다리기 (step 7까지) | 냉장고 15°C 도달 → 크림 녹음 | 단일 시나리오(최선)만 고려 |
| 크림 먼저 꺼내기 | 냉장고 열면 +5°C/step → 크림 빠르게 녹음 | V4 외삽 실패 |
| Step 5에서 케이크 꺼내기 | 이미 과열 → 탄 케이크 | 시간 추정 실패 |

### 10.7. 채점 기준 (태스크 완성도, 0~100)

| 항목 | 배점 | 조건 |
|------|------|------|
| 케이크 완성도 100% 시 꺼냄 | 30 | step 3에서 OPEN+GRASP |
| 크림이 녹지 않은 상태로 사용 | 30 | cream_temp < 15°C 시 GRASP |
| 크림을 케이크 위에 올림 | 20 | PLACE_ON_TOP 성공 |
| countertop에 제출 | 10 | 최종 배치 |
| 시간 내 완수 (step 10 이내) | 10 | 전체 step 수 제한 |

---

## 11. OmniGibson 구현 가이드

CA의 구현 가이드(CATS task_config + planner_ca.py)에 대응하는 SF 구현 가이드.

### 11.1. 반드시 생성해야 하는 파일

| # | 파일 | 역할 |
|---|------|------|
| 1 | `omnigibson/llm_agent/sf_tasks/{task_name}.py` | **SF_TASK_CONFIG dict** — 태스크 정의의 중심 |
| 2 | `omnigibson/llm_agent/sf_tasks/__init__.py` | SF_TASK_REGISTRY에 등록 |
| 3 | `omnigibson/llm_agent/planner_sf.py` | **SFPlanner** — 5 Phase 파이프라인 엔진 |
| 4 | `omnigibson/llm_agent/time_system.py` | Symbolic 시간 시스템 (공유) |
| 5 | `bddl3/bddl/activity_definitions/{task_name}/problem0.bddl` | BDDL 오브젝트 + goal 정의 |
| 6 | `datasets/.../house_single_floor_task_{task_name}_0_0_template.json` | Scene template |
| 7 | `datasets/.../create_{task_name}_template.py` | Scene template 생성 스크립트 |
| 8 | `omnigibson/llm_agent/configs/llm_mock_sf_{task_name}.yaml` | Mock LLM 응답 시퀀스 |
| 9 | `joylo/sampled_task/available_tasks.yaml` | 태스크 엔트리 추가 |
| 10 | `omnigibson/examples/sf/run_sf_agent.py` | 실행 진입점 |

### 11.2. SF_TASK_CONFIG dict 구조

CA의 TASK_CONFIG에서 **시간 시스템 + rollout + 시나리오 평가**가 추가된 구조:

```python
SF_TASK_CONFIG = {
    # --- 기본 정보 (CA와 동일) ---
    "task_name": "power_outage_cake_completion",
    "level": "3.3",
    "instruction": "Complete the cake by adding cream and serve it on the countertop. "
                   "The power is out — the oven runs on residual heat and the fridge "
                   "is slowly warming up.",  # 반드시 영어

    # --- 시간 시스템 (SF 고유) ---
    "time_config": {
        "step_duration_minutes": 5,       # 1 action = 5분 경과
        "max_steps": 15,                  # 총 시간 예산
        "variables": {
            "oven_temp": {
                "initial": 170.0,
                "decay_closed": -3.0,     # /step, 닫힌 상태
                "decay_open": -30.0,      # /step, 열린 상태 (부수 효과)
            },
            "fridge_temp": {
                "initial": 4.0,
                "rise_closed": 0.5,       # /step, 닫힌 상태
                "rise_open": 5.0,         # /step, 열린 상태 (부수 효과 — 외삽 대상)
            },
            "cake_completion": {
                "initial": 80.0,
                "rate_per_step": 7.0,     # oven_temp > 150일 때만
                "done_threshold": 100.0,
                "overcooked_threshold": 110.0,
            },
            "cream_temp": {
                "initial": 4.0,           # fridge 안에 있을 때 = fridge_temp
                "melting_threshold": 15.0,
                "rise_outside_fridge": 2.0,  # /step, 꺼낸 후 실온 상승
            },
            "power_restore_step": 7,      # 에이전트에게 비공개
        },
    },

    # --- Phase 0: Exploration (CA의 Stage 1에 대응) ---
    "exploration_primitives_desc": """Available exploration actions:
- NAVIGATE_TO[target]: Move to object and observe
- TOUCH[surface]: Measure surface temperature and gradient
- LOOK_CLOSER[target]: Zoom in to observe details""",

    "exploration_nav_targets": {
        "oven": "oven_xxxxx_0",
        "fridge": "electric_refrigerator_xxxxx_0",
        "countertop": "countertop_xxxxx_0",
    },
    "exploration_nav_tracking": {
        "oven": "oven_xxxxx_0",
        "fridge": "electric_refrigerator_xxxxx_0",
    },
    "exploration_feedbacks": {
        "NAVIGATE_TO[oven]": None,  # 이미지만 반환
        "NAVIGATE_TO[fridge]": None,
        "NAVIGATE_TO[countertop]": None,
        "TOUCH[oven]": (
            "Surface temperature sensor readings:\n"
            "  Current: 172.3°C\n"
            "  Gradient: -3.2°C per measurement interval\n"
            "  Note: Power indicator LED is OFF"
        ),
        "TOUCH[fridge]": (
            "Surface temperature sensor readings:\n"
            "  Current: 8.1°C\n"
            "  Gradient: +0.5°C per measurement interval\n"
            "  Note: Compressor is silent, power indicator OFF"
        ),
    },

    # --- Phase 1: 초기 시나리오 예측 프롬프트 ---
    "phase1_prompt": (
        "You have NOT taken any action yet. Based only on your observations:\n"
        "(1) Success scenarios — how could you achieve the goal?\n"
        "(2) Failure scenarios — what could go wrong?\n"
        "(3) How might the situation change over time?\n"
        "(4) What uncertainties remain that you haven't confirmed?"
    ),

    # --- Phase 2: Rollout 설정 ---
    "rollout_config": {
        "max_rollout_steps": 5,           # rollout 내 최대 action 수
        "num_rollouts": 1,                # rollout 횟수 (1회로 제한)
    },
    "rollout_prompt": (
        "You can now perform a LIMITED trial run (simulation). "
        "The environment will be RESET to its current state after your trial. "
        "Use this to discover information you can't get from observation alone.\n"
        "You have up to {max_steps} actions in this trial."
    ),

    # --- Phase 3: 확장 시나리오 예측 프롬프트 ---
    "phase3_prompt": (
        "You gained new information from the simulation. Update your predictions:\n"
        "(1) What did you discover that was unexpected?\n"
        "(2) Based on this, what ADDITIONAL risks might exist "
        "that you haven't directly tested?\n"
        "(3) What changes to your initial predictions (Phase 1)?\n"
        "(4) Your time-based contingency strategy?"
    ),

    # --- Phase 4: 실행 (CA의 Stage 3에 대응) ---
    "execution_actions_desc": """Available actions:
- NAVIGATE_TO[object]: Move near an object
- GRASP[object]: Pick up an object
- RELEASE[]: Put down held object
- PLACE_ON_TOP[surface]: Place held object on surface
- OPEN[container]: Open a container (door, lid)
- CLOSE[container]: Close a container
- WAIT[N]: Wait N time steps without acting (time still passes)
- NEW_ACTION[name, tool, target]: Custom action
- DONE[]: Declare task complete""",

    "new_action_handlers": {
        ("cream", "cake", "decorate"): {
            "outcome": "SUCCESS",
            "aux_text": "You spread the cream evenly on top of the cake.",
            "condition": lambda state: state["cream_temp"] < 15.0,
            "failure_text": "The cream has melted and runs off the cake.",
        },
    },

    # --- 숨겨진 변수 목록 (평가용, 에이전트에게 비공개) ---
    "hidden_variables": [
        {"id": "V1", "name": "oven_decay_rate_closed", "layer": 2,
         "description": "Oven loses ~3°C/step when closed"},
        {"id": "V2", "name": "fridge_rise_rate_closed", "layer": 2,
         "description": "Fridge gains ~0.5°C/step when closed"},
        {"id": "V3", "name": "oven_decay_rate_open", "layer": 3,
         "description": "Opening oven causes -30°C/step rapid heat loss"},
        {"id": "V4", "name": "fridge_rise_rate_open", "layer": "extrapolation",
         "description": "Opening fridge causes +5°C/step rapid warming (extrapolated from V3)"},
        {"id": "V5", "name": "power_restore_timing", "layer": 3,
         "description": "Power restores at step 7"},
        {"id": "V6", "name": "cake_done_timing", "layer": 3,
         "description": "Cake reaches 100% at step 3"},
    ],

    # --- 채점 (태스크 완성도) ---
    "scoring": {
        "cake_done_at_100": 30,
        "cream_not_melted": 30,
        "cream_on_cake": 20,
        "served_on_countertop": 10,
        "within_time_budget": 10,
    },

    # --- Metacognitive Probes ---
    "probes": {
        "phase1": "What are the possible scenarios and risks?",
        "phase2": "What did you learn from the trial run?",
        "phase3": "What additional risks can you infer from your trial experience?",
        "phase4": "Did your strategy account for all the scenarios you predicted?",
    },
}
```

### 11.3. SFPlanner 파이프라인 설계

CA의 `CATSPlanner`에 대응하는 `SFPlanner` 클래스. CA와 공유 가능한 부분이 많다.

```
class SFPlanner:
    def run(self):
        phase0_result = self._run_phase0_exploration()   # ≈ CA Stage 1
        phase1_result = self._run_phase1_prediction(phase0_result)
        phase2_result = self._run_phase2_rollout(phase0_result)
        phase3_result = self._run_phase3_updated_prediction(phase1_result, phase2_result)
        phase4_result = self._run_phase4_execution(phase3_result)
        phase5_result = self._run_phase5_verification(phase1_result, phase3_result)
        return self._compile_results(...)
```

#### CA와의 코드 재사용 가능 부분

| 기능 | CA 구현체 | SF에서 재사용 |
|------|----------|-------------|
| Exploration 루프 (ReAct) | `CATSPlanner._run_stage1()` | Phase 0 (동일 구조) |
| 카메라 시스템 | `_teleport_to_face()`, `_capture_image()`, `_capture_zoomed()` | 그대로 재사용 |
| Base action 실행 | `_execute_base_action()` | Phase 4에서 재사용 |
| NEW_ACTION 핸들러 | `_execute_new_action()` | Phase 4에서 재사용 (+ condition 체크 추가) |
| LLM 호출 | `self.llm.generate(messages)` | 그대로 재사용 |
| Mock LLM | `MockLLM` 클래스 | 그대로 재사용 |
| 이미지 캡처 → LLM 전달 | `(role, text, image_path)` 형식 | 그대로 재사용 |
| Fuzzy object name matching | `_get_scene_object()` | 그대로 재사용 |

#### SF 고유 구현 필요 부분

| 기능 | 설명 |
|------|------|
| `TimeSystem` 클래스 | Symbolic 시간 경과 + 상태 업데이트 엔진 |
| `sim.save()` / `sim.restore()` 래핑 | Phase 2 rollout 지원 |
| Phase 1/3 시나리오 파싱 | LLM 응답에서 시나리오를 구조화 추출 |
| Phase 5 자동 검증 | 에이전트 예측 vs 실제 sim 결과 비교 |
| WAIT[N] action | N step 동안 시간만 경과 (CA에 없음) |
| `time_step` 관리 | Phase 4 각 action마다 시간 시스템 advance |

### 11.4. TimeSystem 클래스 상세 설계

```python
class TimeSystem:
    """Symbolic 시간 시스템 — 매 action마다 상태를 수식으로 업데이트."""

    def __init__(self, config: dict):
        self.step = 0
        self.config = config["variables"]
        self.state = self._init_state()
        self.door_states = {"oven": "closed", "fridge": "closed"}

    def _init_state(self) -> dict:
        return {
            "oven_temp": self.config["oven_temp"]["initial"],
            "fridge_temp": self.config["fridge_temp"]["initial"],
            "cake_completion": self.config["cake_completion"]["initial"],
            "cream_temp": self.config["cream_temp"]["initial"],
            "cream_location": "fridge",  # fridge / hand / countertop
            "cake_location": "oven",
            "power": False,
        }

    def advance(self, action: str = None):
        """1 step 진행. action에 따라 door_states 갱신 후 모든 변수 업데이트."""
        self.step += 1

        # 정전 복구 체크
        if self.step >= self.config["power_restore_step"]:
            self.state["power"] = True

        # action에 의한 door 상태 변경
        if action:
            if "OPEN" in action and "oven" in action.lower():
                self.door_states["oven"] = "open"
            elif "CLOSE" in action and "oven" in action.lower():
                self.door_states["oven"] = "closed"
            # fridge 동일 패턴...

        # 온도 업데이트
        oven_rate = (self.config["oven_temp"]["decay_open"]
                     if self.door_states["oven"] == "open"
                     else self.config["oven_temp"]["decay_closed"])
        self.state["oven_temp"] += oven_rate

        fridge_rate = (self.config["fridge_temp"]["rise_open"]
                       if self.door_states["fridge"] == "open"
                       else self.config["fridge_temp"]["rise_closed"])
        self.state["fridge_temp"] += fridge_rate

        # 케이크 완성도 (오븐 안에 있고 온도 충분할 때만)
        if (self.state["cake_location"] == "oven"
                and self.state["oven_temp"] > 150):
            self.state["cake_completion"] += self.config["cake_completion"]["rate_per_step"]

        # 크림 온도 (위치에 따라)
        if self.state["cream_location"] == "fridge":
            self.state["cream_temp"] = self.state["fridge_temp"]
        else:
            self.state["cream_temp"] += self.config["cream_temp"]["rise_outside_fridge"]

    def get_observable(self) -> dict:
        """에이전트에게 보여줄 수 있는 정보만 반환 (POMDP)."""
        obs = {"time_step": self.step, "power": self.state["power"]}
        if self.door_states["oven"] == "open":
            obs["oven_interior_temp"] = self.state["oven_temp"]
            obs["cake_appearance"] = self._cake_appearance()
        if self.door_states["fridge"] == "open":
            obs["fridge_interior_temp"] = self.state["fridge_temp"]
            obs["cream_appearance"] = self._cream_appearance()
        return obs

    def save(self) -> dict:
        """rollout 전 상태 스냅샷."""
        import copy
        return {"step": self.step, "state": copy.deepcopy(self.state),
                "doors": copy.deepcopy(self.door_states)}

    def restore(self, snapshot: dict):
        """rollout 후 상태 복원."""
        import copy
        self.step = snapshot["step"]
        self.state = copy.deepcopy(snapshot["state"])
        self.door_states = copy.deepcopy(snapshot["doors"])
```

### 11.5. Phase별 LLM 호출 구조

| Phase | LLM 호출 수 | 입력 | 출력 |
|-------|------------|------|------|
| Phase 0 (Exploration) | N회 (ReAct loop) | 이전 탐색 히스토리 + 이미지 | NAVIGATE_TO / TOUCH / DONE_EXPLORING |
| Phase 1 (Initial Prediction) | 1회 | Phase 0 히스토리 + 프롬프트 | 시나리오 목록 (성공/실패/불확실성) |
| Phase 2 (Rollout) | M회 (action loop) | rollout 내 히스토리 + 이미지 | 행동 + 관찰 반응 |
| Phase 2 후 반성 | 1회 | rollout 결과 요약 | 발견한 것/놀라운 것 |
| Phase 3 (Updated Prediction) | 1회 | Phase 1 예측 + Phase 2 발견 + 프롬프트 | 업데이트된 시나리오 + 전략 |
| Phase 4 (Execution) | K회 (ReAct loop) | Phase 3 전략 + 실행 히스토리 + 이미지 | action |
| **총합** | **N + M + K + 3~4회** | | |

### 11.6. CA와의 파이프라인 대응 관계

```
CA (CATS)                          SF
─────────────────────────────      ─────────────────────────────
Probe 0 (데모 시청)                (없음 — SF는 외부 데모 없음)
Stage 1 (Exploration)         ←→   Phase 0 (Exploration)
  Probe 1                     ←→     (Phase 0 종료 후)
Analysis & Tool Selection     ←→   Phase 1 (초기 시나리오 예측)
  (1회 통합 호출)                     + Phase 2 (Rollout)
                                     + Phase 3 (업데이트된 예측)
Stage 3 (Execution)           ←→   Phase 4 (실행)
  Probe 3                     ←→     Probe (Phase 4 후)
(없음)                         ←→   Phase 5 (시스템 검증)
```

핵심 차이:
- CA의 "데모 관찰 → 구조적 비교 → 도구 선택"이 SF에서는 "rollout → 외삽 → 전략 수립"으로 대체
- SF는 **WAIT action**과 **시간 경과에 따른 환경 상태 변화**가 추가
- SF는 Phase 5(시스템 검증)가 추가로 존재 — 에이전트의 예측을 사후 검증

### 11.7. Mock LLM 응답 구조 (예시)

```yaml
# llm_mock_sf_power_outage_cake_completion.yaml
responses:
  # Phase 0: Exploration (4 responses)
  - "Thought: I should check the oven first.\nAction: NAVIGATE_TO[oven]"
  - "Thought: Let me measure the temperature.\nAction: TOUCH[oven]"
  - "Thought: Now check the fridge.\nAction: NAVIGATE_TO[fridge]"
  - "Thought: Measure fridge temperature.\nAction: TOUCH[fridge]"
  - "Action: DONE_EXPLORING[]"

  # Phase 1: Initial Prediction (1 response)
  - |
    Success scenarios:
    - Wait for residual heat to finish baking, then add cream and serve.
    Failure scenarios:
    - Oven cools too fast → cake never reaches 100%.
    - Fridge warms up → cream melts before use.
    Time estimates:
    - Oven: ~3°C/step loss → drops below 150°C around step 7.
    - Fridge: ~0.5°C/step rise → reaches 15°C around step 22.
    Uncertainties:
    - What is the cake's current completion %?
    - When will power be restored?
    - How fast does temperature change when doors are opened?

  # Phase 2: Rollout (3 responses)
  - "Thought: I need to see the cake inside.\nAction: OPEN[oven]"
  - "Thought: The temperature dropped drastically! Let me check the reading.\nAction: TOUCH[oven]"
  - "Thought: I've learned enough.\nAction: DONE_ROLLOUT[]"

  # Phase 2 후 반성 (1 response)
  - |
    Discoveries:
    - Opening the oven caused temperature to plummet (-30°C in one step!)
    - Cake was at 87% completion.
    - The act of observing has a severe cost.

  # Phase 3: Updated Prediction (1 response)
  - |
    Updated predictions:
    (1) Opening oven causes -30°C/step heat loss (discovered).
    (2) EXTRAPOLATION: Opening the fridge likely causes similarly rapid
        temperature change — maybe +5-10°C/step warming. I must NOT open
        the fridge until I'm ready to use the cream immediately.
    (3) Cake needs ~2 more steps to reach 100% (87% + 7%/step × 2 = 101%).
        Must extract at step 3 (step 1 was used for rollout, now restored to step 0).
    (4) Strategy: Wait until step 3 → OPEN oven + grab cake →
        immediately OPEN fridge + grab cream → apply cream → serve.
        Contingency: If power returns before step 3, close oven to retain heat.

  # Phase 4: Execution (7 responses)
  - "Thought: I need to wait for the cake to finish.\nAction: WAIT[2]"
  - "Thought: Step 3 now. Time to get the cake.\nAction: NAVIGATE_TO[oven]"
  - "Action: OPEN[oven]"
  - "Action: GRASP[cake]"
  - "Thought: Immediately get the cream to minimize exposure.\nAction: NAVIGATE_TO[fridge]"
  - "Action: OPEN[fridge]\nAction: GRASP[cream]"
  - "Action: NEW_ACTION[DECORATE, cream, cake]: 'spread cream on cake'"
  - "Action: PLACE_ON_TOP[countertop]"
  - "Action: DONE[]"

  # Phase 4 후 Probe (1 response)
  - |
    My strategy worked because I minimized door-open time.
    The key insight was extrapolating from the oven's rapid heat loss
    to predict the fridge would also lose cooling rapidly when opened.
```

---

## 12. 향후 구체화 필요 사항

1. **추가 SF 태스크 인스턴스 설계:** 케이크 완성 외에 다른 SF 태스크 (예: 지진 후 주방 정리, 연쇄 위험 관리)
2. **시간 시스템의 일반화:** `time_system.py`를 다른 SF 태스크에도 재사용 가능한 형태로 추상화 (variable registry 패턴)
3. **Phase 5 자동화:** 에이전트 예측을 파싱하여, 해당 시나리오를 IsaacSim에서 자동 실행 + 결과 비교하는 스크립트
4. **Rollout 횟수 최적화:** 1회가 최적인지, 2~3회가 더 나은 변별력을 제공하는지 실험
5. **sim.save/restore 검증:** OmniGibson의 `og.sim.save()` / `og.sim.restore()`가 모든 상태(물체 위치, object states, 파티클 등)를 완전히 복원하는지 확인
