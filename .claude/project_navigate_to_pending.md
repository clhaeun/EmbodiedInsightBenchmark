---
name: NAVIGATE_TO mock LLM 보류 태스크
description: hammer_nail mock LLM에 NAVIGATE_TO 추가 보류 — movable object navigate 정책 결정 필요
type: project
---

hammer_nail mock LLM에 NAVIGATE_TO 추가가 보류 상태.

sweep_dustpan은 해결됨 (2026-03-24): 두 mock 파일 모두 movable object 직접 navigate 방식으로 NAVIGATE_TO 추가 완료.

**Why:** NAVIGATE_TO 프롬프트는 "fixed objects only"로 안내하지만, 코드(`_navigate_to_obj`)는 movable도 내부적으로 처리함. hammer_nail에서 물체가 이동하며(countertop→wall 왕복) 적절한 고정 타깃이 없음.

**How to apply:** movable object에 대한 NAVIGATE_TO 정책을 결정한 후:
- hammer_nail: countertop ↔ wall 왕복 시 NAVIGATE_TO 타깃 확정
