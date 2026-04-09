---
name: CATS Task 2.3-D micro_glass_shard_pickup 구현 완료
description: micro_glass_shard_pickup 최종 구현 — raw 센서 피드백, demo 라벨 제거, broom 추가, 2단계 평가(tool selection vs execution), CUT 전처리, 7개 handler
type: project
---

# CATS Task 2.3-D: micro_glass_shard_pickup 구현 기록

## 구현 상태

- **TASK_CONFIG, BDDL, Mock LLM, __init__.py, available_tasks.yaml, planner_ca.py (CUT 추가)**: 완료
- **Scene template JSON**: 미생성 (생성 스크립트만 있음 — `create_micro_glass_shard_pickup_template.py` 실행 필요)
- **데모 영상**: 미확보 (placeholder 경로만)

## 확정된 설계 결정

1. **CUT 액션** (SLICE 아님): 형식 `CUT[target, tool]`. planner_ca.py `_ACTION_PRIMITIVE_MAP`에 전역 추가
2. **demo_labels 제거**: 에이전트가 영상에서 직접 도구/원리를 식별해야 함 (CA 순도 향상)
3. **Exploration feedback → raw 센서 데이터**:
   - NAVIGATE_TO: 이미지 + 짧은 시각 설명 (기존과 동일)
   - TOUCH: tactile 4x4 pressure array (kPa) + normal force + temperature
   - PUSH: before/after tactile 비교 + "Particles displaced: 0"
   - PICK_UP: mass, grip force, hardness (Shore A), friction, moisture
4. **broom 추가**: CA tool 6개 (potato, lettuce, broccoli, vacuum, sponge, broom) + knife(일반도구)
5. **2단계 평가 분리**:
   - **Tool Selection accuracy (1차)**: correct_tool="potato" → "potato" 선택 = 정답
   - **Execution success (2차)**: CUT 후 half_potato 사용 = SUCCESS, 통감자 = FAILURE
   - 통감자 FAILURE 시 "You need to cut the potato" 힌트 제공 → 재시도 가능
6. **broken_glass 8개**: scale 0.1, kinematic=True 권장, beltgg/rvpgpt 교차
7. **vacuum**: 대형 그대로 (handheld 삭제)
8. **Probe 0**: 유지 (데모 파일 없으면 자동 skip)
9. **NEW_ACTION handler 7개**: half_potato(SUCCESS), potato(FAILURE), lettuce/broccoli/vacuum/sponge/broom(FAILURE)
10. **handler dict 순서**: half_potato → potato (fuzzy matching first-match 보장)
11. **성공 구현**: broken_glass를 z=-10 텔레포트
12. **Object IDs**: potato_701~sponge_705, broom_706, carving_knife_707, broken_glass_711~718

## 파일 목록

### 생성 (5개)
- `omnigibson/llm_agent/cats_tasks/micro_glass_shard_pickup.py`
- `bddl3/bddl/activity_definitions/micro_glass_shard_pickup/problem0.bddl`
- `datasets/.../create_micro_glass_shard_pickup_template.py`
- `omnigibson/llm_agent/configs/llm_mock_cats_micro_glass_shard_pickup.yaml`
- `omnigibson/examples/cats/demos/micro_glass_shard_pickup/README.md`

### 수정 (3개)
- `omnigibson/llm_agent/cats_tasks/__init__.py` — CATS_TASK_REGISTRY에 등록
- `joylo/sampled_task/available_tasks.yaml` — task 엔트리 추가
- `omnigibson/llm_agent/planner_ca.py` — _ACTION_PRIMITIVE_MAP에 CUT 추가

## Exploration Primitive → Raw 센서 데이터 형식

| Primitive | 반환 형식 | 핵심 수치 | 에이전트 해석 포인트 |
|-----------|----------|----------|-------------------|
| NAVIGATE_TO | 이미지 + 시각 설명 | — | 파편 위치, 도구 후보 확인 |
| TOUCH[floor, spill_area] | 4x4 tactile kPa array | 대부분 0, 3셀에서 5.7~9.1 스파이크 | 미세 날카로운 이물질 산재 |
| PUSH[hand, floor_surface] | pre/post tactile 비교 | 전후 거의 동일 + displaced=0 | 닦기 무효, 박혀있음 |
| PICK_UP[potato] | mass, hardness, moisture | Shore A 78, moisture 0.02 | 딱딱+건조 → 잘라야 함 |

## Mock LLM 실행

```bash
python -m omnigibson.examples.cats.run_cats_agent --model mock --task micro_glass_shard_pickup
```

## 남은 작업
- Scene template JSON 생성: `create_micro_glass_shard_pickup_template.py` 실행
- broken_glass kinematic 설정
- 데모 영상 6개 확보 (라벨 없이 제공)
- 시뮬레이터 테스트 (카메라 앵글, 센서 데이터 수치 미세 조정)
