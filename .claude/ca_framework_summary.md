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
