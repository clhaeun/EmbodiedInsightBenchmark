---
name: CATS 평가 프레임워크 총 정리
description: CA 평가 프레임워크 — 논문 정의, CATS 3단계, 난이도 2.1~2.4, 지표, 구현 가이드 + §12 Decorative Pattern 구현 가이드(param_checker, no_image, text demo, technique naming, 버그/함정)
type: project
---

# Context Adaptability (CA) 평가 프레임워크 총 정리
## Embodied LLM 환경에서의 CA 측정을 위한 태스크 설계

---

## 1. 이론적 배경: Context Adaptability란?

### 1.1. 논문에서의 정의

"Imagining and building wise machines: The centrality of AI metacognition" (Johnson, Karimi, Bengio et al.)에서 Context Adaptability(CA)는 **perspectival metacognition**의 핵심 구성 요소 중 하나로 정의된다.

> **Context Adaptability:** 상황의 어떤 특징이 다른 상황과 비교 가능하게(comparable) 또는 구별되게(distinct) 만드는지를 식별하는 능력 (Baltes & Smith, 2008)

CA는 주로 인식론적(epistemic) 성격의 메타인지 전략으로 분류되며, 논문의 Figure 1에서 6개 메타인지 전략(Intellectual Humility, Epistemic Deference, Scenario Flexibility, Context Adaptability, Perspective Seeking, Viewpoint Balancing) 중 하나로 위치한다.

### 1.2. CA의 기능적 역할

논문에 따르면, CA는 메타인지의 세 가지 기능 중 특히 **전략 간 충돌 해소(conflict resolution)**에 핵심적으로 기여한다:

- **Input-seeking:** 현재 상황에서 어떤 정보를 추가로 확인해야 하는지 판단
- **Conflict resolution:** 복수의 object-level 전략이 충돌할 때, 현재 맥락의 특성에 기반하여 어떤 전략이 적합한지 판별
- **Outcome monitoring:** 선택된 전략의 결과가 현재 맥락에서 타당한지 점검

### 1.3. 논문 내 사례 (Daphne)

V4 및 V1에서 공통으로 제시되는 Daphne 사례가 CA의 대표적 예시이다:
- Daphne(심장전문의)가 동료의 전문지식을 참고할 때, **자신의 환자의 고유한 상황이 동료의 전문지식의 적용 가능성을 제한하는지** 고려하는 과정이 CA이다.
- 즉, 외부에서 주어진 전략/정보가 현재 상황에 얼마나 적용 가능한지를 **맥락 특성에 기반하여 판단**하는 것이 CA의 본질이다.

### 1.4. 인접 개념과의 구분

| 메타인지 전략 | 핵심 질문 | CA와의 차이 |
|---|---|---|
| Intellectual Humility | "내가 모르는 것은 무엇인가?" | 자기 지식의 한계 인식 — CA는 상황 특성의 유사/차이 판별 |
| Epistemic Deference | "누구의 판단을 따를 것인가?" | 타인의 전문성에 대한 의존 — CA는 외부 전략의 맥락 적합성 판단 |
| Scenario Flexibility | "이 상황이 어떻게 전개될 수 있는가?" | 다양한 시나리오 생성 — CA는 현재 vs 참조 상황의 구조적 비교 |

본 프레임워크는 CA만을 순수하게 측정하기 위해, 위 인접 개념들과 겹치지 않도록 태스크를 설계한다.

---

## 2. 평가 프레임워크: CATS (Context-Adaptive Tool Selection)

### 2.1. 프레임워크 개요

**한 줄 정의:** 에이전트가 embodied 환경에서 물리적 탐색을 통해 현재 상황의 고유 맥락 특성을 발견한 뒤, 복수의 도구 사용 데모와 현재 상황 간의 구조적 유사성/차이를 판별하여, 적절한 도구를 선택하고 현재 맥락에 맞게 조정하여 태스크를 수행하는 평가 프레임워크.

**핵심 측정 대상:** 에이전트가 참조 상황(데모)과 현재 상황 사이에서 관련된 구조적 유사점과 차이점을 정확히 식별하고, 그에 기반하여 도구를 선택·조정할 수 있는가?

### 2.2. 환경 및 기술 스택

| 구성 요소 | 선택 |
|---|---|
| 시뮬레이터 | NVIDIA IsaacSim (OmniGibson) |
| 에셋 | BEHAVIOR-1K dataset (5000+ objects, 50 scenes) |
| 로봇 | Tiago (dual-arm mobile manipulator) |
| 오브젝트 상태 | OmniGibson Object States (Temperature, Filled, Sliced, Stained, ToggledOn, Open, Inside, OnTop 등 34종) |
| 데모 형식 | 실제 사람이 촬영한 영상 |
| 평가 방식 | 주로 success rate (도구 선택 정확도 + 실행 성공/실패), verbal (근거 설명)은 보조적 참고 |

---

## 3. 태스크 구조: 3단계 + Metacognitive Probe

### Stage 1 — Exploration (맥락 발견)

**목적:** 에이전트가 현재 환경의 **critical context feature**를 물리적 탐색을 통해 스스로 발견.

**핵심 제약:**
- Critical context feature는 **텍스트로 직접 제공되지 않음**
- 에이전트는 **tool 후보를 사용하지 않은 상태**에서 탐색해야 함
- Tool 후보 외의 exploration primitive만 사용 가능

**Exploration Primitives (tool 후보 제외):**

| Primitive | 획득 가능한 정보 | Embodiedness |
|---|---|---|
| pick_up(object) | 무게, 무게중심 편향 | 들어봐야 아는 정보 |
| touch(surface) | 미끄러움, 끈적임, 온도, 재질 | 만져봐야 아는 정보 |
| push/pull(object) | 고정 여부, 관절 유무, 이동 가능성 | 움직여봐야 아는 정보 |
| open(container) | 내부 상태, 내용물, 공간 여유 | 열어봐야 아는 정보 |
| navigate_to(position) | 가려진 물체, 틈새 안쪽, 다른 각도의 시각 정보 | 이동해야 볼 수 있는 정보 |

**Tool 후보 사용 금지의 이유:**
- Tool 후보로 직접 시도하면 trial-and-error로 CA 없이도 정답에 도달 가능
- 이 제약이 있어야 "먼저 맥락을 파악하고 → 데모와 비교하고 → tool을 선택한다"는 **CA의 순서가 강제**됨
- Exploration primitive로 충분한 맥락 정보를 획득할 수 있되, 도구 선택 자체에 대한 정보는 직접 얻을 수 없음

**평가 지표:**
- **[주] 맥락 특성 식별 정확도:** 에이전트가 태스크 수행에 관련된 맥락 특성을 식별했는가
- **[보조] 탐색 전략의 질:** 어떤 primitive를 어떤 순서로 실행했는가

**Metacognitive Probe (Stage 1 후):**
- "이 환경에서 태스크 수행에 영향을 줄 수 있는 특이한 점을 발견했는가? 무엇인가?"
- "왜 그 탐색 행동을 수행했는가?"

---

### Stage 2 — Demo Observation & Comparison (비교 판단)

**목적:** 복수의 데모를 관찰하고, 각 데모의 맥락과 현재 자신의 맥락을 비교하여 어떤 도구가 적합한지 판단.

**데모 구성 원칙:**

(a) **각 데모는 하나의 tool 후보에 대한 사용 장면이다.** 에이전트가 어떤 데모를 선택하면 해당 데모의 tool을 선택하는 것과 동일하다.

(b) **데모의 도메인은 현재 태스크와 완전히 달라도 된다.** Cross-domain 데모(폭포, 낚시, 대장간, 인형뽑기 등)를 포함하여, 에이전트가 **표면적 유사성이 아닌 구조적 원리**를 추출해야 하는 상황을 만든다.

(c) **데모 세트 내에 세 종류의 구성 요소를 포함한다:**

| 데모 유형 | 역할 | 예시 |
|---|---|---|
| 핵심 구조 일치 데모 (1~2개) | 정답 도구의 핵심 원리를 제공 | 대장간 집게 → tongs의 "열 거리 + 파지" 원리 |
| 제약 인식 데모 (1~2개) | 현재 맥락의 제약 조건을 인식하도록 도움 | 유리잔 파손 슬로모션 → "충격 시 깨짐" 제약 |
| 함정 데모 (1~2개) | 표면적으로 관련 있어 보이지만 현재 맥락 feature와 충돌 | 파워워셔 세차 → "고압수" 전략이 전자기기 근처에서 위험 |

(d) **데모는 도구의 표준적 사용뿐 아니라 비자명한(non-obvious) 사용법도 포함할 수 있다** (난이도 2.3 참조).

**평가 지표:**
- **[주] 도구 선택 정확도:** 올바른 도구를 선택했는가 (success rate)
- **[주] 함정 회피율:** 표면 유사-구조 불일치 함정 데모를 선택하지 않았는가
- **[보조] 선택 근거의 구조적 정합성:** 에이전트가 데모 맥락과 현재 맥락 간의 관련 유사점/차이점을 정확히 식별했는가

**Metacognitive Probe (Stage 2 후):**
- "각 데모와 현재 상황은 어떤 점에서 유사하고 어떤 점에서 다른가?"
- "어떤 도구를 왜 선택하는가?"
- "선택하지 않은 도구들은 왜 부적합한가?"

---

### Stage 3 — Adaptive Execution (적응적 실행)

**목적:** 선택한 도구를 사용하여 태스크를 수행하되, 필요시 데모에서 본 방식을 현재 맥락에 맞게 조정.

**평가 방식 (이중):**
- **주 평가 — Success Rate:** 도구 선택의 정확도 및 실제 실행의 물리적 성공/실패
- **보조 평가 — Verbal:** 선택 근거의 질을 참고 지표로 활용 (CA의 process 측면 보완)

**Execution이 주 평가인 이유:**
- 올바른 도구를 선택했는지는 실행 결과로 가장 명확하게 검증됨
- 잘못된 선택은 물리적 실패(도구가 안 들어감, 물체가 깨짐, 미끄러짐 등)로 직결
- Verbal은 success rate만으로는 포착하기 어려운 **"왜 그 판단을 했는가"의 process 측면**을 보조적으로 확인하는 데 사용

**Metacognitive Probe (Stage 3 후):**
- "데모에서 본 방식과 다르게 수행한 부분이 있는가? 왜 그렇게 했는가?"
- "실행 결과가 예상과 달랐다면, 무엇이 원인인가?"

---

## 4. 난이도 스케일링 (2.1 → 2.4)

태스크 난이도를 4단계로 구성한다. 2.1→2.4로 갈수록 CA의 더 깊은 측면을 요구한다.

### Level 2.1 — 기본 도구 선택 (Basic Tool Selection)

**구조:** 데모 N개(각각 다른 tool의 사용 장면) → 현재 상황 특성과 구조적으로 가장 적합한 데모의 tool을 선택.

**CA 측정 초점:** 현재 상황의 맥락 특성과 데모 상황의 맥락 특성 간 유사/차이를 올바르게 판별하는 기본 능력.

**예시:** 5개의 도구별 데모(fork, ladle, tongs, spoon, spatula)를 보고, 현재 상황(좁은 병 입구 + 고체 내용물)에 적합한 도구를 선택.

---

### Level 2.2 — 환경 물체의 도구적 활용 (Affordance-Based Tool Selection)

**구조:** 데모들이 전용 도구의 사용 장면을 보여주지만, 현재 환경에는 전용 도구 외에 **도구로 활용 가능한 일반 물체**(textbook, cutting board 등)도 존재. 에이전트는 데모에서 추출한 원리를 환경 내 물체의 물리적 속성에 매핑하여, 전용 도구 또는 대체 물체를 선택.

**CA 측정 초점:** 데모의 도구가 가진 **기능적 속성(affordance)**을 추상화하고, 그 속성을 현재 환경의 다른 물체에서도 식별하는 능력. 즉, "hammer의 핵심은 '무겁고 단단한 표면으로 충격을 가하는 것'이다 → 무거운 textbook도 이 기능을 수행할 수 있다"는 추론.

**예시:** 데모에서 hammer, nailgun 등을 보여주지만, 현재 환경에는 hammer가 없고 두꺼운 textbook, 가벼운 물체 등이 있음. 에이전트가 textbook의 물리적 속성(무겁고 단단함)을 hammer의 기능적 속성과 매핑하여 선택.

---

### Level 2.3 — Insight 기반 선택 (Non-Obvious Usage Selection)

**구조:** 데모가 도구의 **비자명한(non-obvious), 창의적 사용법**을 보여줌. 표준 용도가 아닌 대안적 용도에서 추출한 insight가 현재 상황에 적용 가능한지 판단.

**CA 측정 초점:** 도구의 표면적 기능이 아닌 **추상적 속성**을 매칭하는 능력. "이 도구가 원래 이런 용도이지만, 이 데모에서 보여주는 이런 방식으로도 쓸 수 있구나 → 현재 상황에서 이 방식이 적합하다"는 판단.

**예시:** "spatula의 표준 용도는 뒤집기이지만, 데모에서 얇고 평평한 형태를 이용해 좁은 틈에 삽입하여 물체를 밀어내는 장면을 보여줌" → 현재 상황(좁은 틈에 빠진 물체)에 이 insight를 적용.

---

### Level 2.4 — 다중 Subtask + 맥락 변이 (Repeated CA with Context Shift)

**구조:** 하나의 태스크 안에 **유사하지만 미묘하게 다른 subtask 여러 개**가 존재. 동일한 도구 세트에서 매번 다른 선택을 해야 함.

**CA 측정 초점:** CA가 **일회성이 아니라 반복적으로 작동하는지**, 그리고 subtask 간 맥락 차이를 세밀하게 감지하여 **매번 적절히 재조정하는지**.

**예시:** 못 박기 태스크 3회 반복인데:
- Subtask A: 단단한 벽 + 넓은 공간 → hammer가 적합
- Subtask B: 무른 벽 + 좁은 공간 → 다른 도구가 적합
- Subtask C: 단단한 벽 + 위치가 높음 → 또 다른 도구/방식이 적합

동일 도구 세트, 동일 데모를 참조하되 **맥락이 미묘하게 달라질 때마다 CA가 작동하는지** 측정.

**주의:** 이 레벨에서 subtask 순서 결정은 CA 평가에 포함하지 않음. 순서 최적화는 CA보다 planning/scenario flexibility에 가까우며, CA와의 경계가 모호해질 수 있음.

---

### 난이도 간 관계

```
Level 2.1: CA의 기본 — "이 상황과 저 상황이 어떻게 다른가?"
    ↓ (환경 물체의 affordance 인식 추가)
Level 2.2: CA + affordance transfer — "이 물체가 저 도구와 기능적으로 유사한가?"
    ↓ (비자명한 용도까지 고려)
Level 2.3: CA + 창의적 전이 — "이 도구의 숨겨진 속성이 현재 상황에 적합한가?"
    ↓ (반복 적용으로 일관성 측정)
Level 2.4: CA의 반복 적용 — "맥락이 조금씩 달라질 때마다 매번 재판단하는가?"
```

논문 관점에서, **2.1~2.3이 CA의 core evaluation**이고, **2.4는 extended evaluation**으로 위계를 둔다.

---

## 5. 설계 원칙

### 5.1. 표면-구조 분리 (Surface-Structure Dissociation)

모든 태스크에서 반드시 포함해야 하는 핵심 설계 장치:
- **표면적으로 가장 유사한 데모가 구조적으로는 부적합한 경우** (함정)
- **표면적으로 완전히 달라 보이는 데모가 구조적으로 가장 적합한 경우** (정답)

이것이 단순 유사성 매칭(pattern matching)과 진정한 CA를 구분하는 핵심 장치이다.

### 5.2. Cross-Domain 데모 허용

데모는 현재 태스크와 **완전히 다른 도메인**에서 올 수 있다. 예:
- 주방에서 뜨거운 냄비의 고체를 건지는 태스크에, **대장간에서 뜨거운 쇳덩이를 집게로 꺼내는 영상**을 데모로 제공
- 에이전트는 "고온 환경 + 긴 집게형 도구 + 열원과의 거리 유지"라는 추상 원리를 추출하여 현재 상황에 매핑

이는 CA가 **도메인 특정적 지식이 아니라 구조적 매핑 능력**임을 반영한다.

### 5.3. Embodied Exploration의 필수성

Critical context feature는 반드시 **물리적 상호작용을 통해서만 발견 가능한 정보**를 포함해야 한다:
- 카메라 이미지만으로 알 수 있는 정보 (형태, 색상, 위치) → 불충분
- 들어보기, 만져보기, 밀어보기, 열어보기, 이동해서 보기 → 필수

이것이 본 프레임워크가 **IsaacSim/OmniGibson을 사용하는 정당성**을 제공한다. 물리적 상호작용 없이는 맥락 특성을 발견할 수 없으므로, 이미지+텍스트 기반 VLM 평가로는 대체 불가능하다.

### 5.4. Tool 후보 사용 금지 (Exploration 단계)

Exploration 단계에서 에이전트는 **선택해야 할 tool 후보를 직접 사용해볼 수 없다.** Tool 후보 외의 exploration primitive만 사용 가능하다.

이유:
- Tool 후보로 직접 시도하면 **trial-and-error로 CA 없이도 정답 도달 가능**
- 이 제약이 "맥락 파악 → 데모 비교 → tool 선택"이라는 **CA의 인지적 순서를 강제**

### 5.5. Success Rate 중심 + Process 보조 평가

논문이 강조하듯, 지혜(wisdom)의 평가는 outcome과 process를 모두 봐야 한다:
- **주 평가는 success rate** — 도구 선택 정확도, 실행 성공률 등 객관적 결과 지표
- **보조 평가로 verbal probe** — success rate만으로는 "운 좋게 맞춘 것"과 "맥락을 판단해서 적응한 것"을 구분하기 어려운 경우, "왜 그 도구를 선택했는가"의 근거를 참고
- 모든 단계(Exploration, Comparison, Execution)마다 metacognitive probe를 삽입하되, 이는 보조적 참고 자료로 활용

---

## 6. 측정 지표

### 6.1. 주 지표 (Success Rate 기반)

**Exploration 단계:**
- **맥락 특성 식별 정확도 (Context Feature Identification Accuracy):** 에이전트가 태스크 관련 critical context feature를 정확히 식별한 비율

**Comparison 단계:**
- **도구 선택 정확도 (Tool Selection Accuracy):** 올바른 도구를 선택한 비율 — 전체 프레임워크의 핵심 지표
- **함정 회피율 (Distractor Resistance Rate):** 표면 유사-구조 불일치 함정 데모를 선택하지 않은 비율

**Execution 단계:**
- **물리적 성공률 (Physical Success Rate):** 선택한 도구로 태스크를 실제 수행하여 성공한 비율
- **적응 적절성 (Adaptation Appropriateness):** 데모 방식을 현재 맥락에 맞게 올바르게 조정하여 성공한 비율

**Level 2.4 추가:**
- **재조정 적절성 (Re-adaptation Accuracy):** subtask 간 맥락 변이에 대해 도구 선택을 올바르게 변경/유지한 비율
- **변별 민감도 (Discrimination Sensitivity):** "이 subtask는 이전과 같으므로 같은 도구" vs "이 subtask는 달라졌으므로 다른 도구"를 올바르게 구분한 비율

### 6.2. 보조 지표 (Verbal, 참고용)

Success rate만으로는 **"운 좋게 맞춘 것"과 "맥락을 판단해서 적응한 것"을 구분하기 어려운 경우**에, 다음 지표를 보조적으로 참고한다:

- **설명 정합성 (Explanation Coherence):** 도구 선택 근거와 실제 맥락 특성 간의 일치도
- **구조적 추론 비율 (Structural Reasoning Ratio):** 설명에서 표면적 유사성 vs 구조적 원리에 기반한 근거의 비율
- **탐색 효율성 (Exploration Efficiency):** 관련 정보 획득에 사용한 primitive 수 / 전체 사용 primitive 수

---

## 7. 인접 개념과의 관계 정리

### 7.1. CA vs Epistemic Deference

- **Epistemic Deference:** 타인의 전문성에 의존하여 판단을 위임
- **본 프레임워크의 CA:** 에이전트가 스스로 맥락 특성을 판별하고 데모와 비교. 다른 에이전트나 전문가에 의존하지 않음
- **구분 방법:** 태스크에 "누구의 말을 따를 것인가" 선택이 없음. 데모는 정보 제공원이지 권위 있는 조언자가 아님

### 7.2. CA vs Planning

- **Planning:** 목표 달성을 위한 행동 시퀀스 최적화
- **본 프레임워크의 CA:** 현재 상황의 특성이 참조 상황과 어떻게 다른지를 판별하여 전략을 조정
- **구분 방법:** Subtask 순서 결정은 CA 평가에서 제외. 순서 최적화는 planning/scenario flexibility의 영역

### 7.3. CA vs Analogical Reasoning

- **Analogical Reasoning:** 두 도메인 간의 구조적 매핑을 수행하는 인지 능력
- **CA:** analogical reasoning을 포함하되, "현재 맥락의 고유 특성이 매핑을 제한하거나 수정하는가"까지 판단
- **관계:** CA는 analogical reasoning의 상위 집합. Analogical reasoning은 "이것과 저것이 구조적으로 유사하다"를 인식하는 것이고, CA는 거기에 "그 유사성이 현재 맥락에서 유효한가"라는 메타인지적 판단을 더함

---

## 8. IsaacSim 활용 정당성

| 설계 요소 | IsaacSim 없이 가능한가? | IsaacSim이 필요한 이유 |
|---|---|---|
| 물리적 탐색 (들기, 만지기, 밀기) | 불가능 | 무게, 온도, 재질, 고정 여부 등은 물리 시뮬레이션에서만 감지 가능 |
| Object states (Temperature, Filled, Sliced 등) | 불가능 | OmniGibson의 34종 object state로 맥락 특성 구현 |
| 도구 사용 실행 및 물리적 피드백 | 불가능 | 잘못된 도구 선택 시 물리적 실패(안 들어감, 깨짐, 흘림 등) 구현 |
| 시각적 관찰만으로 파악 가능한 정보 | 이미지로 대체 가능 | 이것만으로는 VQA와 구별 불가 |

**결론:** Exploration primitive를 통한 물리적 상호작용 + Execution의 물리적 피드백이 IsaacSim 사용의 필수적 정당성을 제공한다.

---

## 9. 향후 구체화 필요 사항

1. **구체적 태스크 인스턴스 설계:** BEHAVIOR-1K asset 기반으로 Level 2.1~2.4 각각에 대한 구체적 태스크 시나리오
2. **데모 영상 촬영 계획:** 각 태스크의 도구별 데모 영상 목록 및 촬영 프로토콜
3. **Exploration primitive의 API 설계:** OmniGibson 내에서 각 primitive가 반환하는 정보의 형식 및 범위
4. **Metacognitive probe의 표준화:** 각 단계별 질문의 정확한 문구 및 응답 평가 기준 (rubric)
5. **Custom asset 필요 여부 결정:** BEHAVIOR-1K 기존 asset만으로 충분한지, 추가 asset이 필요한지

---

## 10. OmniGibson 구현 가이드

Phase 1 태스크 생성 경험(`project_task_creation_guide.md`)에서 CATS에 적용 가능한 기술적 사항을 정리한다.

### 10.1. 반드시 생성해야 하는 파일 (3~4개)

#### A. BDDL 정의 파일 (필수)
- **경로**: `bddl3/bddl/activity_definitions/{task_name}/problem0.bddl`
- 디렉토리를 만들고 problem0.bddl만 넣으면 자동 등록
  - `bddl_utils.py`의 `BEHAVIOR_ACTIVITIES`가 디렉토리를 스캔하므로 별도 등록 불필요
- 오브젝트는 WordNet synset 이름 사용 (예: `egg.n.02_1`, `spatula.n.01_1`)
  - synset 이름은 `category_mapping.csv`에서 확인: `egg` 카테고리 → `egg.n.02` synset
- CATS 특이사항:
  - **tool 후보 전부 BDDL에 정의** — tool을 선택하지 않더라도 씬에 물리적으로 배치되어야 함
  - goal condition은 태스크 목표(예: egg가 countertop 위에 있음)로 정의

#### B. Scene Template JSON (필수)
- **경로**: `datasets/2025-challenge-task-instances/scenes/{scene}/json/{scene}_task_{task_name}_0_0_template.json`
- **이 파일이 없으면 `FileNotFoundError`로 씬 로딩 실패** — 가장 빠뜨리기 쉬운 파일
- 핵심 구조:
  - `metadata.task.inst_to_name`: BDDL scope name → scene object name 매핑
  - `objects_info.init_info`: 각 오브젝트의 class, model ID, category, in_rooms
  - `state.registry.object_registry`: 초기 위치(pos, ori), 물리 상태
- 모델 ID 확인: `datasets/behavior-1k-assets/objects/{category}/` 하위 디렉토리명
- CATS 특이사항:
  - **가구 간격 정밀 조절** 필요 (예: stove-countertop 사이 2-3cm 틈)
  - critical context feature를 구현하는 환경 배치가 이 파일에서 결정됨

#### C. available_tasks.yaml 엔트리 추가 (필수)
- **경로**: `joylo/sampled_task/available_tasks.yaml`
- scene_model, robot_start_position, robot_start_orientation 지정
- CATS 기본: `scene_model: house_single_floor`, `robot: Tiago`

#### D. Scene Template 생성 스크립트 (선택, 강력 권장)
- **경로**: `datasets/.../scenes/{scene}/json/create_{task}_task_template.py`
- 기존 template JSON 로드 → task 오브젝트 제거 → 새 오브젝트 추가
- 수작업으로 JSON을 편집하면 실수 가능성 높으므로 스크립트 권장
- **CATS에서 특히 중요**: 가구 간격, 물체 배치 위치 등 정밀한 수치가 필요하므로 스크립트화 필수

#### E. CATS Task Config (Python dict) (필수)
- **경로**: `omnigibson/llm_agent/cats_tasks/{task_name}.py`
- YAML이 아닌 **Python dict (`TASK_CONFIG`)**로 정의 — 코드 내에서 직접 import
- `cats_tasks/__init__.py`의 `CATS_TASK_REGISTRY`에 자동 등록:
  ```python
  CATS_TASK_REGISTRY = {
      "retrieve_egg_from_gap": retrieve_egg_from_gap.TASK_CONFIG,
  }
  ```
- `run_cats_agent.py`에서 `--task` 인자로 registry에서 조회

---

### 10.2. 수정이 필요할 수 있는 파일

CATS는 `planner_ca.py`를 별도로 만들므로 기존 planner.py를 수정하지 않는다. 하지만 다음 파일은 수정이 필요할 수 있다:

| 파일 | 수정이 필요한 경우 | 위험 |
|------|-------------------|------|
| `category_mapping.csv` | BDDL에서 사용하는 synset이 기존에 없을 때 | 행 추가는 안전 |
| `synsets.csv` | 새 오브젝트의 ability 정의 필요 시 | 행 추가는 안전 |
| `domain_omnigibson.bddl` | 새 predicate 사용 시 | predicate 추가는 안전 |

**안전 원칙** (Phase 1과 동일):
1. 기존 파일은 "추가"만 한다 (행 추가, elif 추가)
2. 기존 함수의 시그니처나 로직은 절대 변경하지 않는다
3. CSV/JSON은 기존 행/키를 수정하지 않고 새 행/키만 추가
4. synset 이름과 scene 오브젝트 이름의 일관성 유지

---

### 10.3. 이미지 캡처 및 LLM 전달 시스템

각 step에서 action 완료 직후의 이미지를 캡처하여 다음 step의 LLM 프롬프트에 함께 전달한다.

#### 기존 시스템 (planner.py) 흐름

```
Step N:
  1. 프롬프트 구성: (system_prompt) + (step_text + prev_image_path)
     → ("user", step_prompt_text, prev_image_path)
  2. LLM 호출 — 텍스트 + 이미지를 함께 수신
  3. before-action 이미지 캡처 → step_NNNN_1.png
  4. action 실행
  5. after-action 이미지 캡처 → step_NNNN_2.png
  6. prev_image_path = after-action 이미지 → 다음 step에 전달
```

#### 이미지 캡처 방법

```python
# CameraHelper 초기화
self._camera_helper = _CameraHelper(self.env, self.controller)

# RGB 캡처 → numpy (H, W, 3) uint8 → PNG 저장
rgb = self._camera_helper.get_rgb()
from PIL import Image
Image.fromarray(rgb).save(image_path)
```

#### LLM에 이미지 전달 형식

```python
# Message = (role, text) 또는 (role, text, image_path)
full_prompt = [
    ("system", system_prompt),
    ("user", step_prompt_text, image_path),  # image_path는 PNG 파일 경로 (string)
]
response = self.llm.generate(full_prompt)
```

- 이미지는 **파일 경로(string)**로 전달 — LLM 백엔드(Gemini 등)가 PNG를 자동 인코딩
- after-action 이미지가 **다음 step의 입력 이미지**가 됨

#### CATS planner_ca.py에서의 적용

| Stage | 이미지 캡처 시점 | LLM에 전달하는 이미지 |
|-------|----------------|---------------------|
| Probe 0 (Demo) | N/A | 데모 영상 (extra_images) — **유일한 데모 시청 시점** |
| Stage 1 (Exploration) | 각 exploration primitive 실행 후 | 직전 primitive의 after-action 이미지 |
| Analysis & Tool Selection | N/A | Stage 1 마지막 이미지 |
| Stage 3 (Execution) | 각 action 실행 후 | 직전 action의 after-action 이미지 |

#### 카메라 앵커와 Exploration의 관계

- `get_rgb()`는 `_anchored_pos` (로봇 위치) 기준으로 카메라 위치를 결정
- `_anchored_pos/ori`는 `navigate_to` 실행 시 갱신됨
- **Stage 1에서 `navigate_to(gap, low_angle)` 같은 exploration을 할 때, 텍스트 피드백만 반환하면 이미지는 바뀌지 않음**
- 따라서 exploration `navigate_to`에서는:
  1. 텍스트 피드백 반환 (symbolic)
  2. **로봇 위치를 실제로 텔레포트** (기존 `_navigate_to_obj()` 재사용)
  3. `_anchored_pos/ori` 갱신
  4. 갱신된 위치에서 `get_rgb()` 캡처 → 다른 시각 정보 제공
- 이것은 "물리 시뮬레이션"이 아니라 "카메라 위치 변경"이므로 symbolic 원칙과 충돌하지 않음

#### 카메라 Tracking 시스템

NAVIGATE_TO 실행 시 카메라가 **특정 오브젝트를 바라보도록** 설정할 수 있다:

- **`exploration_nav_tracking`**: action target별로 카메라가 추적할 오브젝트 지정
  ```python
  "exploration_nav_tracking": {
      "gap":            "fridge_dszchb_0",   # 카메라가 fridge+gap 방향을 향함
      "gap, low_angle": "egg_601",            # 카메라가 바닥의 egg을 내려다봄
  }
  ```
- tracking 대상이 지정되지 않으면 기본 `_navigate_to_obj()` 방향 사용
- 내부적으로 `_look_at_quat(eye, target)` 함수로 카메라 orientation 계산

#### LOOK_CLOSER 줌 시스템

- **`exploration_look_targets`**: LOOK_CLOSER action의 대상 오브젝트 매핑
  ```python
  "exploration_look_targets": {
      "egg":                    "egg_601",
      "gap":                    "fridge_dszchb_0",
      "objects_on_countertop":  "countertop_kelzer_0",
  }
  ```
- **`look_closer_focal_length`**: 줌 시 focal length (기본값 `50.0`, viewer 기본 `18.0` → 약 2.8x 줌)
- LOOK_CLOSER 실행 시 viewer_camera의 focal_length를 변경하여 확대 촬영 후 원복
- `eib_camera.py` 기본값: head_height `1.4m`, ceiling_height `2.4m`

#### exploration_direct_camera (직접 카메라 오버라이드)

- **`exploration_direct_camera`**: 특정 action에서 viewer_camera의 위치/방향을 **직접 수치로 지정**
- `exploration_nav_tracking`으로 충분하지 않은 경우(예: 매우 특수한 앵글)에 사용
- 비어있으면 (`{}`) tracking 시스템이 기본으로 동작

---

### 10.4. 파이프라인 전체 흐름 (v2)

```
Probe 0  →  Stage 1 (+ Probe 1)  →  Analysis & Tool Selection  →  Stage 3 (+ Probe 3)
```

#### 데모 있는 경우:
```
Probe 0 (데모 영상 시청 — 유일한 기회)
  │
Stage 1 (탐색 ReAct loop, 최대 10회)
  └─ Probe 1 (맥락 특성 식별)
  │
Analysis & Tool Selection (1회 LLM 호출)
  │  ← Probe 0 텍스트 + Stage 1 히스토리 + 도구 선택 지시
  │
Stage 3 (실행 ReAct loop, 최대 15회)
  └─ Probe 3 (적응 반성)
```

#### 데모 없는 경우:
```
Probe 0 → skip ({"skipped": True})
  │
Stage 1 (탐색 ReAct loop, 최대 10회)
  └─ Probe 1 (맥락 특성 식별)
  │
Analysis & Tool Selection (1회 LLM 호출)
  │  ← Stage 1 히스토리 + 도구 선택 지시 (데모 없음 분기)
  │
Stage 3 (실행 ReAct loop, 최대 15회)
  └─ Probe 3 (적응 반성)
```

#### 각 단계별 히스토리 포함 관계

| 단계 | 포함하는 이전 컨텍스트 |
|------|----------------------|
| Stage 1 각 step | Stage 1 내부 이전 step 전체 (thought + action + feedback) |
| Probe 1 | Available Tools + Stage 1 전체 |
| Analysis & Tool Selection | Available Tools + (데모 있으면) Probe 0 텍스트 + Stage 1 전체 + 선택 지시 |
| Stage 3 system prompt | Available Objects (정확한 이름) + Stage 1 요약 + Tool Selection 전문 |
| Stage 3 각 step | Stage 3 내부 이전 step 전체 (thought + action + result) |
| Probe 3 | Available Tools + Stage 1 전체 + Tool Selection 전문 + Stage 3 전체 |

#### LLM 호출 횟수

| 단계 | 호출 수 |
|------|--------|
| Probe 0 | 0~1회 (데모 있을 때만) |
| Stage 1 | N회 (탐색 step) + 1회 (Probe 1) |
| Analysis & Tool Selection | **1회** |
| Stage 3 | M회 (실행 step) + 1회 (Probe 3) |
| **총합** | **N + M + 3~4회** |

#### 설계 근거 — 왜 단일 호출로 통합했는가

이전 설계(Probe 1, Stage 2, Probe 2, Tool Selection = 4회 호출)의 문제:
- `keep_message_history=false`라서 매 호출이 **stateless** — 이전 분석을 텍스트로 복사하는 hack 필요
- 4회 중 3회가 "도구 적합성 분석"으로 실질적 중복
- 약한 모델(flash-lite)에서 별도 호출 간 추론 일관성 유지 불가

통합 후:
- 상황분석 → 도구분석 → 결정이 **하나의 reasoning chain**으로 연결
- 3배 빠른 API 호출
- 단일 응답에서 파싱으로 각 항목(지각/분석/결정) 별도 평가 가능

---

### 10.5. Stage 3 실행 방식: 물리적 Grounding

Stage 3에서는 기존 action과 NEW_ACTION을 조합하여 실행한다:

- **기존 action** (NAVIGATE_TO, GRASP 등): OmniGibson 물리 엔진으로 실행
- **NEW_ACTION**: 중간 과정은 symbolic, **결과 상태를 IsaacSim에서 물리적으로 구현** (teleport + state change + `og.sim.step()`)
- **Observation**: 항상 IsaacSim 카메라의 실제 렌더링 이미지 (텍스트가 아님)

**One-Shot CA Tool Selection 제약:**
- GRASP 시점에 CA tool 확정, 나머지 CA tool은 사용 불가
- `planner_ca.py`의 `_check_ca_tool_grasp()`에서 강제

**Stage 3 system prompt에 포함되는 컨텍스트:**
- Available Objects 리스트 (정확한 scene name — LLM이 올바른 이름 사용하도록)
- Stage 1 exploration findings (요약형: action → feedback)
- Tool Selection plan 전문 (LLM이 자기가 세운 계획을 참조)
- `"IMPORTANT: Use exact object names from the Available Objects list above."` 지시

---

### 10.6. 데모 영상 전달

**핵심 원칙: 데모는 Probe 0에서 1회만 보여주고, 이후로는 절대 재전송하지 않는다.**

- **Probe 0**: `extra_images`로 데모 영상 직접 전달 — 파이프라인 전체에서 **유일한** 데모 시청 시점
- **이후 단계**: Probe 0에서 LLM이 작성한 **텍스트 설명**만 전달 (영상 재전송 없음)
  - Analysis & Tool Selection의 user prompt에 `"=== Your Demo Observations (from Probe 0) ==="` 섹션으로 포함

**v2 변경**: `demo_labels: []` — 에이전트가 영상에서 직접 도구/원리를 식별해야 함 (라벨 미제공)

**데모가 없는 경우**: Probe 0이 skip되고, Analysis & Tool Selection에서 no-demo 분기로 진입

---

### 10.7. Mock LLM (CATS용)

API 호출 없이 파이프라인을 테스트할 때 사용.

- **파일 위치**: `omnigibson/llm_agent/configs/llm_mock_cats_{task_name}.yaml`
- **응답 순서**:
  1. (데모 있을 때) Probe 0 응답: 데모 설명
  2. Stage 1 응답: exploration primitive 호출 시퀀스 (N개)
  3. Stage 1 DONE_EXPLORING 응답
  4. Probe 1 응답
  5. Analysis & Tool Selection 응답: 분석 + 4항목 + `SELECTED_TOOL: <name>`
  6. Stage 3 응답: 실행 step들 (M개)
  7. Stage 3 DONE 응답
  8. Probe 3 응답
- 기존 MockLLM 클래스(`llm/mock_llm.py`)의 순차 반환 구조를 그대로 사용

---

### 10.8. 주요 버그/함정

| 증상 | 원인 | 해결 |
|------|------|------|
| `FileNotFoundError` 씬 로딩 실패 | scene template JSON 미생성 | 생성 스크립트로 JSON 생성 |
| synset 이름 불일치 | Goal text와 scene object name이 다름 | synset 이름을 모든 곳에서 일관되게 사용 |
| LLM이 hand state를 모름 | action 설명에 전제조건 없음 | 모든 action 설명에 `(Requires: ~)` 전제조건 추가 |
| 카메라 앵글이 안 바뀜 | navigate 없이 이미지 캡처 | navigate 시 `_anchored_pos/ori` 갱신 필수 |
| `selected_tool: null` | LLM이 "I will use the sponge" 형태로 출력 | `SELECTED_TOOL:` 구조화 출력 지시 + 파싱 강화 |
| Stage 3에서 오브젝트 이름 불일치 | "blue sponge" vs "sponge_705" | Available Objects 리스트 제공 + fuzzy matching |
| `instruction`이 한국어 | LLM이 영어 모델일 때 혼동 | **instruction은 반드시 영어로 작성** |

---

### 10.9. task_config 전체 필드 목록

`cats_tasks/{task_name}.py`의 `TASK_CONFIG` dict가 포함해야 하는 필드:

| 필드 | 필수 | 설명 |
|------|------|------|
| `task_name` | ✅ | 태스크 식별자 (예: `micro_glass_shard_pickup`) |
| `level` | | 난이도 레벨 (예: `"2.3"`) |
| `instruction` | ✅ | 에이전트에게 주어지는 태스크 지시문 **(영어)** |
| `correct_tool` | ✅ | 정답 도구 (평가용, base name: `"potato"`) |
| `ca_tool_names` | ✅ | CA tool 후보 목록 (scene object name, 순서가 프롬프트에 반영됨) |
| `exploration_primitives_desc` | ✅ | Stage 1 탐색 프리미티브 설명 텍스트 (system prompt에 포함) |
| `exploration_nav_targets` | ✅ | NAVIGATE_TO action target → scene object name 매핑 |
| `exploration_nav_tracking` | | NAVIGATE_TO 시 카메라가 바라볼 오브젝트 매핑 |
| `exploration_look_targets` | | LOOK_CLOSER action target → scene object name 매핑 |
| `exploration_direct_camera` | | 특정 action에서 viewer_camera 위치/방향 직접 지정 |
| `look_closer_focal_length` | | LOOK_CLOSER 줌 focal length (기본 50.0) |
| `exploration_feedbacks` | ✅ | exploration action별 센서 피드백 (v2: raw 수치) |
| `demo_image_paths` | ✅ | 데모 영상/이미지 경로 또는 YouTube URL 목록 (빈 리스트 = 데모 없음) |
| `demo_labels` | | 데모 라벨 목록 (v2: 빈 리스트 `[]` — 라벨 미제공) |
| `tool_selection_prompt` | | 데모 있을 때 Tool Selection 프롬프트 (기본값 있음) |
| `tool_selection_prompt_no_demo` | | 데모 없을 때 Tool Selection 프롬프트 (기본값 있음) |
| `new_action_handlers` | ✅ | NEW_ACTION symbolic 핸들러: `(tool, target, context)` → outcome/aux_text |
| `probes` | ✅ | metacognitive probe 질문 dict (`stage1`, `stage3` 키) |

---

### 10.10. Analysis & Tool Selection 프롬프트 구조

Stage 1 탐색 직후, **1회 LLM 호출**로 상황분석 + 도구분석 + 도구선택 + 실행계획을 통합 수행.

#### 데모 없는 경우 (no-demo 분기)

```
┌─ System ──────────────────────────────────────────────────────┐
│ "You are a robot agent. No reference demonstrations are       │
│  available. Reason from your exploration and the available    │
│  tools alone.                                                 │
│                                                               │
│  Based on your exploration, what are the key features of this │
│  situation that would affect how you approach the task? What   │
│  makes this situation unique or challenging? Select the tool   │
│  needed to solve this task."                                  │
├─ User ────────────────────────────────────────────────────────┤
│ === Available Tools ===                                        │
│ sponge_705, broccoli_703, vacuum_704, lettuce_702,            │
│ potato_701, broom_706                                         │
│                                                               │
│ === Stage 1: Your Exploration Findings ===                    │
│ Step 1:                                                       │
│   Thought: ...  Action: ...  Result: ...                      │
│ ... (전체 탐색 히스토리)                                       │
│                                                               │
│ (task_config["tool_selection_prompt_no_demo"] 또는 기본값):    │
│ Provide:                                                      │
│ (1) What physical principle guides your tool selection        │
│ (2) Which tool you select                                     │
│ (3) What sensor data or physical properties make it suitable  │
│ (4) Your action plan                                          │
│                                                               │
│ (base actions 설명: NAVIGATE_TO, GRASP, ..., NEW_ACTION)      │
│                                                               │
│ IMPORTANT: At the very end, write ONLY:                       │
│ SELECTED_TOOL: <tool_name>                                    │
│ where <tool_name> is one of: sponge, broccoli, vacuum,        │
│ lettuce, potato, broom                                        │
├─ Image: Stage 1 마지막 카메라 이미지 ─────────────────────────┤
└───────────────────────────────────────────────────────────────┘
```

#### 데모 있는 경우 (demo 분기)

```
┌─ System ──────────────────────────────────────────────────────┐
│ "You are a robot agent. You observed reference demonstrations │
│  earlier and explored the environment. Now analyze the        │
│  demonstrations in context of your current situation and      │
│  select the best tool to solve the task."                     │
├─ User ────────────────────────────────────────────────────────┤
│ === Available Tools ===                                        │
│ sponge_705, broccoli_703, vacuum_704, lettuce_702,            │
│ potato_701, broom_706                                         │
│                                                               │
│ === Your Demo Observations (from Probe 0) ===                 │
│ (Probe 0에서 LLM이 직접 작성한 데모 설명 텍스트)              │
│                                                               │
│ === Stage 1: Your Exploration Findings ===                    │
│ Step 1:                                                       │
│   Thought: ...  Action: ...  Result: ...                      │
│ ... (전체 탐색 히스토리)                                       │
│                                                               │
│ (task_config["tool_selection_prompt"] 또는 기본값):            │
│ Provide:                                                      │
│ (1) Which demo you referenced and why                         │
│ (2) Which tool you select                                     │
│ (3) What features of the current situation make it suitable   │
│ (4) Your action plan                                          │
│                                                               │
│ (base actions 설명: NAVIGATE_TO, GRASP, ..., NEW_ACTION)      │
│                                                               │
│ IMPORTANT: At the very end, write ONLY:                       │
│ SELECTED_TOOL: <tool_name>                                    │
│ where <tool_name> is one of: sponge, broccoli, vacuum,        │
│ lettuce, potato, broom                                        │
├─ Image: Stage 1 마지막 카메라 이미지 ─────────────────────────┤
└───────────────────────────────────────────────────────────────┘
```

#### Tool Selection 파싱 (`_extract_tool_from_response`)

LLM 응답에서 선택된 도구를 추출하는 우선순위:

| 순위 | 패턴 | 예시 |
|------|------|------|
| 0 | `SELECTED_TOOL: <name>` (구조화 출력) | `SELECTED_TOOL: potato` |
| 1 | `select/choose/pick/use the <tool>` (자연어) | `"I will use the sponge"` |
| 2 | `GRASP[<CA tool>]` (action plan에서) | `GRASP[potato_701]` |
| 3 | `GRASP[<any>]` (fallback) | `GRASP[knife]` |

모든 단계에서 **fuzzy matching** 적용: `"sponge"` → `sponge_705` (base name 비교, `_NNN` suffix 무시)

#### 오브젝트 이름 Fuzzy Matching (`_get_scene_object`)

Stage 3에서 LLM이 출력한 이름을 scene object로 resolve할 때:

| 순위 | 매칭 방식 | 예시 |
|------|----------|------|
| 1 | exact match (`obj.name == name`) | `"sponge_705"` → `sponge_705` |
| 2 | base name substring (`re.sub(r"_\d+$", "", obj.name)`) | `"sponge"` → `sponge_705` |

---

### 10.11. Run Script 진입점

- **경로**: `omnigibson/examples/cats/run_cats_agent.py`
- 주요 인자:
  - `--task`: CATS_TASK_REGISTRY에서 task 조회
  - `--model`: LLM 모델 (예: `mock`, `gemini-2.0-flash`)
  - `--robot`: 로봇 종류 (Tiago, R1, R1Pro, Fetch, Stretch)
  - `--exp-dir`: 실험 결과 저장 경로

```bash
# Mock LLM으로 파이프라인 테스트
python -m omnigibson.examples.cats.run_cats_agent --model mock --task retrieve_egg_from_gap

# Gemini로 실제 실행
python -m omnigibson.examples.cats.run_cats_agent --model gemini-2.0-flash --task retrieve_egg_from_gap
```

---

### 10.12. 데모 영상 YouTube URL 병합

Gemini API는 **요청당 YouTube URL 1개** 제한이 있으므로, 복수 YouTube 데모를 사용할 때:

- `planner_ca.py`의 `_merge_youtube_demos()` 가 자동 처리:
  1. `yt-dlp`로 각 YouTube URL을 mp4 다운로드
  2. `ffmpeg concat`으로 하나의 mp4로 병합
  3. 병합된 로컬 파일을 `from_data`로 LLM에 전달
- YouTube URL이 1개면 기존대로 `from_uri`로 직접 전달
- 의존성: `yt-dlp`, `ffmpeg` 필요 (`pip install yt-dlp`)

---

## 11. v2 설계 변경사항 (2026-03-28, micro_glass_shard_pickup에서 확정)

### 11.1. Exploration feedback → raw 센서 데이터

기존 (v1, retrieve_egg): 자연어 피드백 ("You feel tiny sharp pricks...")
신규 (v2, glass_shard~): **raw 센서 수치** — 에이전트가 데이터에서 의미를 직접 추론

| Primitive | 반환 형식 | 예시 |
|-----------|----------|------|
| NAVIGATE_TO | 이미지 + 짧은 시각 설명 | (기존과 동일) |
| TOUCH | tactile 4x4 pressure array (kPa) + force + temp | 대부분 0, 몇 셀에서 스파이크 |
| PUSH | pre/post tactile 비교 + displaced count | 전후 동일 → 제거 불가 |
| PICK_UP | mass, hardness(Shore A), friction, moisture | hardness 78, moisture 0.02 |

**설계 의도**: 센서 이름과 단위는 제공하되, 수치 해석은 에이전트 몫. "reading comprehension이 아니라 sensor interpretation을 측정"

### 11.2. Demo 라벨 제거

v1: `"Demo 1 — spatula"` 형태로 tool 라벨 제공
v2: `demo_labels: []` — 에이전트가 영상에서 직접 도구/원리를 식별

**이유**: 라벨이 있으면 "어떤 데모가 어떤 tool인지"를 공짜로 알게 됨 → CA의 구조적 매핑 능력 측정이 약화

### 11.3. 평가 2단계 분리

- **Tool Selection accuracy (1차 지표)**: `correct_tool` 필드와 에이전트 선택 비교 (예: "potato" 선택 = 정답)
- **Execution success (2차 지표)**: NEW_ACTION handler outcome (예: CUT 안 하고 통감자 사용 → FAILURE)
- 1차는 맞았지만 2차에서 실패할 수 있음 (전처리 insight 부족)

### 11.4. CUT 액션 추가

- `planner_ca.py`의 `_ACTION_PRIMITIVE_MAP`에 `"CUT": SymbolicSemanticActionPrimitiveSet.CUT` 전역 추가
- 형식: `CUT[target_object, cutting_tool]` (target 먼저, tool 나중)
- SlicingRule이 자동으로 `half_{name}_0`, `half_{name}_1` 생성
- sliceable 오브젝트가 없는 task에서는 자연 실패 → 기존 task에 영향 없음

### 11.5. 파이프라인 통합 (Probe 1 + Stage 2 + Probe 2 + Tool Selection → Analysis & Tool Selection)

이전: 4회 LLM 호출 (Probe 1, Stage 2 관찰, Probe 2 분석, Tool Selection 결정)
현재: **1회 LLM 호출** (`_run_analysis_and_selection`)

**통합 이유:**
- `keep_message_history=false`로 매 호출이 stateless → 이전 분석을 텍스트 복사하는 hack 필요
- 4회 호출에서 3회가 실질적으로 "도구 적합성 분석"으로 중복
- 단일 호출 내에서 자연스러운 reasoning chain (상황분석 → 도구분석 → 결정)

### 11.6. 데모 시청 시점 제한

이전: Probe 0 + Stage 2에서 데모 영상 2회 전달
현재: **Probe 0에서 1회만 전달**, 이후는 Probe 0의 텍스트 설명만 참조

### 11.7. instruction 영어 필수화

이전: 한국어 instruction (`"주방 바닥에 유리컵이 깨졌다..."`)
현재: 영어 instruction (`"A glass cup broke on the kitchen floor..."`)

### 11.8. 실행 명령어

```bash
# Mock LLM
python -m omnigibson.examples.cats.run_cats_agent --model mock --task micro_glass_shard_pickup

# Gemini
python -m omnigibson.examples.cats.run_cats_agent --model gemini-2.5-pro --task micro_glass_shard_pickup

# YouTube 데모 오버라이드
python -m omnigibson.examples.cats.run_cats_agent --model gemini-2.5-pro --task micro_glass_shard_pickup --demo-urls URL1 URL2 URL3 URL4 URL5 URL6
```

---

## 12. Decorative Pattern 태스크 구현 가이드 (2026-04-02, tilt_to_release_bench에서 확정)

기존 CATS 태스크(도구 선택)와 다른 **기법 선택 + 파라미터 적응** 태스크. 물체의 시각적 외관이 잘못된 기법을 유도하지만 실제 메커니즘은 다른 기법(동작 조합)을 요구.

상세 설계 문서: `.claude/decorative_pattern_ca_tasks.md`

### 12.1. 기존 CATS와의 구현 차이점

| 요소 | 기존 CATS (도구 선택) | Decorative Pattern (기법 선택) |
|------|----------------------|------------------------------|
| `ca_tool_names` | scene object 이름 (`potato_701`) | 기법 이름 (`technique_A`, `technique_B`) |
| `correct_tool` | 도구 base name (`potato`) | 기법 이름 (`technique_B`) |
| Stage 3 실행 | `new_action_handlers` 또는 `stage3_action_menu` | **`stage3_action_menu` + `param_checker`** |
| 정답 구조 | 도구 선택 binary | 기법 선택 + 파라미터 범위 + 물리적 성공 (3단계) |
| 이미지 | 카메라 이미지 전달 | `exploration_no_image: True` 가능 (수치 데이터만) |
| 데모 | YouTube 영상 / 로컬 mp4 | 영상 **또는** `demo_text_descriptions` (텍스트 전용) |

### 12.2. 기법 이름 규칙

기법 후보 이름에 정답 힌트가 포함되면 안 됨. `tilt_rear_then_lift`처럼 동작을 설명하는 이름은 no-demo baseline을 높이므로, **중립 이름** (`technique_A`, `technique_B`, ...) 사용:

```python
"ca_tool_names": [
    "technique_A",   # Demo 1에 대응
    "technique_B",   # Demo 2에 대응 (정답)
    "technique_C",   # Demo 3에 대응
    "technique_D",   # Demo 4에 대응
],
"correct_tool": "technique_B",
```

### 12.3. `stage3_action_menu`에서 `param_checker` 사용

기존 CATS의 `stage3_action_menu`는 `defn["outcome"]` + `defn["feedback"]`을 직접 참조했으나, Decorative Pattern에서는 **`param_checker` callable**로 동적 평가:

```python
"APPLY_TECHNIQUE[lid]": {
    "tool_key": "technique_B",
    "description": "Apply technique. Specify parameters in JSON: {...}",
    "param_checker": _check_params,  # callable
    # outcome, feedback 키 없음 — param_checker가 반환
},
```

`param_checker` 반환 형식:
```python
{
    "outcome": "SUCCESS" | "FAILURE",
    "aux_text": "설명 텍스트",
    "optimal": True | False,  # 최적 범위 여부 (보조 지표)
    "state_changes": [
        {"type": "set_flag", "flag": "lid_opened"},  # requires 체크용
    ],
}
```

**`state_changes`의 `set_flag`**: `completed_actions`에 flag를 추가하여 후속 메뉴 액션의 `requires` 조건을 충족시킴.

### 12.4. 메뉴 액션의 `requires` 필드

후속 액션(GRASP, PLACE_ON_TOP 등)은 이전 액션 완료를 전제:

```python
"GRASP[necklace]": {
    "requires": "lid_opened",     # param_checker의 set_flag로 추가됨
    "outcome": "SUCCESS",
    "feedback": "...",
},
"PLACE_ON_TOP[necklace, floor]": {
    "requires": "GRASP[necklace]",  # 메뉴 키 자체가 completed_actions에 추가됨
    "outcome": "SUCCESS",
    "feedback": "...",
    "task_success": True,
},
```

### 12.5. `exploration_no_image` — 텍스트 전용 탐색

3D 모델의 시각적 외관이 태스크 설계와 일치하지 않을 때 (예: 장식 래치가 모델에 없음, 뚜껑이 기본 열림 상태), 카메라 이미지를 비활성화하고 **수치 공간 데이터**만 제공:

```python
"exploration_no_image": True,
```

이 플래그가 True이면:
- `NAVIGATE_TO`: 텔레포트는 하지만 **이미지 캡처 스킵**, 텍스트 피드백만 반환
- `LOOK_CLOSER`: 줌 캡처 스킵, 텍스트 피드백만 반환
- `TOUCH/PRESS/LIFT/PUSH`: 원래대로 텍스트 전용

NAVIGATE_TO 피드백을 **객관적 수치 공간 데이터**로 작성:
```python
"NAVIGATE_TO[chest]": (
    "=== Spatial Scan (depth + RGB point cloud) ===\n"
    "Object detected: rectangular solid against wall\n"
    "Bounding box: 0.40 x 0.53 x 0.26 m (W x D x H)\n"
    "Material: wood (cedar), dark brown finish\n"
    "=== Front face ===\n"
    "  Metal plate: center, 85 x 40 x 4 mm, scroll pattern\n"
    "  Mounting: flush to surface, 4 weld points\n"
    "=== Top surface (lid) ===\n"
    "  Seam: 2 mm gap (front, left, right edges; no seam at rear)\n"
    "=== Rear edge ===\n"
    "  Two metal brackets: steel, 25 mm wide, spacing 300 mm"
),
```

### 12.6. `demo_text_descriptions` — 텍스트 전용 데모

영상 촬영 전에 텍스트 설명으로 데모를 제공. `demo_image_paths`가 비어있고 `demo_text_descriptions`가 있으면 Probe 0에서 텍스트 전용 모드로 실행:

```python
"demo_image_paths": [],
"demo_text_descriptions": [
    "A metal toolbox with a clasp. The person flips the clasp upward, then lifts the lid.",
    "A piano bench. The person presses one end down, then opens from the opposite side.",
    "A toy chest. The person slides the top forward along grooves.",
    "A gift box. The person lifts the lid straight up, separating it from the base.",
],
```

**Probe 0 동작**: 시스템이 텍스트 설명을 LLM에 전달하고, LLM이 각 데모의 물리 원리를 분석한 응답을 반환. 이 응답이 Analysis & Tool Selection에서 `"=== Your Demo Observations (from Probe 0) ==="`로 포함됨.

**`has_demos` 판정**: `demo_text_descriptions`가 있으면 `has_demos = True` → demo 분기 프롬프트 사용.

### 12.7. Tool Selection 파싱 — exact match 우선

기존 fuzzy matching (`rsplit("_", 1)`)은 `technique_A`와 `technique_B`를 구분하지 못함 (둘 다 base = `technique`):

```
SELECTED_TOOL: technique_B
→ fuzzy: "technique" in "technique_b" → technique_A가 먼저 매칭 (버그)
```

수정: **exact match를 먼저 시도**, fuzzy는 fallback:

```python
# Priority 0: exact match
for tool_name in self._ca_tool_names:
    if tool_name.lower() == candidate:
        return tool_name  # technique_B → technique_B (정확)

# Priority 1: fuzzy fallback (기존 도구명용)
for tool_name in self._ca_tool_names:
    base = tool_name.rsplit("_", 1)[0].lower()
    if base == candidate or base in candidate or candidate in base:
        return tool_name
```

### 12.8. `tool_key` 매칭 — 원본 이름 포함

기존 `rsplit("_", 1)`이 `tilt_rear_then_lift` → `tilt_rear_then`으로 잘못 분리하는 문제:

```python
# 수정: 원본 이름과 base 이름 둘 다로 매칭
self._selected_tool_keys = {selected_tool, selected_tool_base} - {""}
# tool_key 필터: tool_key not in self._selected_tool_keys
```

### 12.9. 메뉴 매칭 — action name prefix

LLM이 JSON 파라미터를 action 인자 안에 넣는 경우:
```
APPLY_TECHNIQUE[lid, {"force": 12.0, ...}]
```

기존 매칭은 `APPLY_TECHNIQUE[lid]`와 매칭 실패 (`lid]` ≠ `lid, {`). action name prefix 매칭 추가:

```python
# Fallback: action name prefix match
fa_name = fa.split("[")[0].lower()
for key in available:
    key_name = key.split("[")[0].lower()
    if fa_name == key_name:
        return key
```

### 12.10. JSON 파라미터 추출 — fallback regex

`_extract_6dof_json()`은 6-DOF 키(`linear_velocity` 등)만 찾음. Decorative Pattern의 키(`rear_press_force_N` 등)는 매칭 안 됨. fallback으로 일반 JSON dict 추출:

```python
if callable(defn.get("param_checker")):
    description = self._extract_6dof_json(response) or ""
    if not description:
        brace_match = re.search(r'\{[^{}]+\}', response)
        if brace_match:
            description = brace_match.group(0)
    result = defn["param_checker"](description)
```

### 12.11. 탐색 피드백 난이도 조절

**원칙**: 탐색 데이터가 해법을 직접 알려주면 no-demo baseline이 높아져서 CA delta가 사라짐.

**noise floor 기법**: 핵심 수치를 센서 노이즈 범위 안에 넣어서 신호/노이즈 모호성 부여:
```python
"Displacement Z (front): +0.2 mm (sensor noise floor: +/- 0.3 mm)"
```
데모가 있으면 "이게 시소 효과"로 해석, 없으면 노이즈로 무시.

**해석적 표현 금지**: "click detected from front edge", "pivot axis detected" 같은 해석 대신 raw 수치만:
```python
# Bad: "Brief metallic click from front edge area"
# Good: "Transient event: 2.3 m/s², 1180 Hz, 4.2 ms, Z-axis"
```

### 12.12. 구현된 태스크

| 태스크 | 파일 | 조합 유형 | 상태 |
|--------|------|----------|------|
| container_opening_push_turn (Task A) | `cats_tasks/container_opening_push_turn.py` | 동시 결합 (press + twist) | 구현 완료, mock 미검증 |
| tilt_to_release_bench (Task G) | `cats_tasks/tilt_to_release_bench.py` | 간접 전달 (rear press → lift) | 구현 완료, Pro 성공 확인 |

### 12.13. 주요 버그/함정 (Decorative Pattern 고유)

| 증상 | 원인 | 해결 |
|------|------|------|
| `SELECTED_TOOL: technique_B` → `technique_A` 추출 | fuzzy matching이 base name "technique"으로 첫 번째 후보 매칭 | exact match 우선 (§12.7) |
| `APPLY_TECHNIQUE[lid, {...}]` → INVALID | 메뉴 매칭이 `APPLY_TECHNIQUE[lid]`와 불일치 | action name prefix 매칭 (§12.9) |
| `defn["outcome"]` KeyError → segfault | `stage3_action_menu`에서 param_checker 미지원 | param_checker callable 분기 추가 (§12.3) |
| param_checker에 빈 문자열 전달 → FAILURE | `_extract_6dof_json`이 비표준 키 무시 | 일반 JSON fallback regex (§12.10) |
| `DONE_EXPLORING` 파싱 실패 | `[]` 누락 | mock에서 `DONE_EXPLORING[]` 형식 사용 |
| `onfloor` predicate 미지원 | BDDL에 잘못된 predicate | `onfloor` → `ontop` |
| NAVIGATE_TO 피드백 키 없음 → 타겟 미발견 | `exploration_feedbacks`에 NAVIGATE_TO 키 누락 | NAVIGATE_TO 텍스트 피드백 추가 필수 |
| Probe 0 mock 응답 순서 어긋남 | 데모 없으면 Probe 0 skip인데 mock에 응답 있음 | `demo_image_paths: []` 시 Probe 0 응답 제거 |
| `prerequisite` 필드 무시됨 | 플래너가 `requires` 필드 사용 | `"prerequisite"` → `"requires"` |
| 뚜껑이 이미지에서 열려 보임 | 3D 모델 기본 joint 상태 | `joint_pos: [0.0]` 또는 `exploration_no_image: True` |
| 기법 이름이 정답 힌트 | `tilt_rear_then_lift`가 동작 설명 | 중립 이름 `technique_A`~`D` 사용 |

### 12.14. 실행 명령어

```bash
# Mock LLM
python -m omnigibson.examples.cats.run_cats_agent --model mock --task tilt_to_release_bench

# Gemini (with-demo: demo_text_descriptions 자동 사용)
python -m omnigibson.examples.cats.run_cats_agent --model gemini-2.5-pro --task tilt_to_release_bench

# No-demo 실험: task_config에서 demo_text_descriptions를 임시 제거하거나 빈 리스트로
```
