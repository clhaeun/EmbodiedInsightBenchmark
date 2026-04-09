---
name: Context Adaptability Research
description: CA 연구 전체 맥락 — Phase 1 (body CA, 6 tasks 완료) → Phase 2 (CATS, 2개 task 구현, raw 센서 피드백·demo 라벨 제거 설계 확정)
type: project
---

## Phase 1 — Body Context Adaptability (완료)

양손→단일팔 전환 시 passive fixture 활용. Fetch 로봇, single-arm. **6개 태스크 완료, heat_frozen_pancake 폐기.**

| 태스크 | 핵심 전략 | 상태 |
|--------|----------|------|
| spread_butter_on_toast | rubber_mat 미끄럼 방지 | 완료 |
| spread_jam_on_cracker | rubber_mat 미끄럼 방지 | 완료 |
| draw_a_line_on_paper | 무거운 물체로 ruler 고정 | 완료 |
| tear_paper_along_a_ruler | stapler로 ruler 고정 | 완료 |
| hammer_nail | PIERCE+PLACE_AGAINST+3 heavy objects | 완료 |
| sweep_dustpan | 벽/계단 활용 (2가지 방법) | 완료 |

## Phase 2 — CATS (Context-Adaptive Tool Selection)

**논문 근거:** Johnson, Karimi, Bengio et al. — CA는 perspectival metacognition의 핵심 구성요소.

**기술 스택:** Tiago (dual-arm) 로봇, IsaacSim/OmniGibson, 실제 촬영 영상 데모, success rate 주 평가

**핵심 설계 원칙 (v2 — 2026-03-27 확정):**
- Exploration feedback: **raw 센서 데이터** (tactile array, force, physical properties). 자연어 해석을 주지 않고 에이전트가 수치에서 추론
- Demo 전달: **라벨 없음** — 에이전트가 영상에서 직접 도구/원리 식별 (CA 순도 향상)
- 평가 2단계 분리: Tool Selection accuracy (1차) + Execution success (2차)
- CUT 전처리 지원: planner_ca.py에 CUT 액션 추가

**구현된 태스크:**

| Task | Level | 정답 도구 | CA tools | 특이사항 | 상태 |
|------|-------|----------|----------|---------|------|
| retrieve_egg_from_gap | 2.3 | spatula | 5개 | 좁은 틈에서 egg 꺼내기 | 구현+실험 완료 |
| micro_glass_shard_pickup | 2.3 | potato | 6개 (broom 포함) | CUT 전처리, raw 센서, demo 라벨 제거 | 구현 완료, 테스트 필요 |

**상세 가이드:** `project_cats_task_guide.md`, `project_cats_retrieve_egg_implementation.md`, `project_cats_glass_shard_task.md`
