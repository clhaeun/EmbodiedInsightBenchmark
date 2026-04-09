#!/usr/bin/env bash
# Benchmark runner for LLM agent on BEHAVIOR-1K tasks.
#
# Usage:
#   ./run_benchmark.sh                          # all tiers, gpt-4o
#   ./run_benchmark.sh --tier easy              # easy only
#   ./run_benchmark.sh --tier hard --model claude-sonnet-4-20250514
#   ./run_benchmark.sh --robot Fetch --model gemini/gemini-2.0-flash
#   ./run_benchmark.sh --symbolic               # use symbolic (teleport) primitives
#   ./run_benchmark.sh --dry-run                # print commands only

set -euo pipefail

# ---------- defaults ----------
MODEL="gpt-4o"
ROBOT="Tiago"
TIER="all"
MAX_STEPS=50
DRY_RUN=false
SYMBOLIC=false

# ---------- parse args ----------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --model)   MODEL="$2";     shift 2 ;;
        --robot)   ROBOT="$2";     shift 2 ;;
        --tier)    TIER="$2";      shift 2 ;;
        --max-steps) MAX_STEPS="$2"; shift 2 ;;
        --symbolic) SYMBOLIC=true;  shift ;;
        --dry-run) DRY_RUN=true;   shift ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# ---------- benchmark tasks: "task_name scene_model" ----------
EASY_TASKS=(
    "turning_on_radio Rs_int"
    "bringing_newspaper_in Rs_garden"
    "store_honey Rs_int"
    "installing_a_fax_machine Pomaria_0_int"
    "donating_toys Wainscott_0_int"
    "composting_waste Rs_int"
    "put_togethera_basic_pruning_kit house_single_floor"
)

MEDIUM_TASKS=(
    "bringing_in_mail Rs_garden"
    "picking_up_trash Wainscott_0_int"
    "bag_groceries grocery_store_convenience"
    "dispose_of_a_pizza_box Rs_int"
    "loading_the_car house_single_floor"
    "preparing_lunch_box Wainscott_0_int"
    "packing_moving_van Rs_garden"
)

HARD_TASKS=(
    "outfit_a_basic_toolbox house_single_floor"
    "putting_food_in_fridge Wainscott_0_int"
    "clean_up_your_desk Merom_1_int"
    "putting_away_tools house_single_floor"
    "clearing_food_from_table_into_fridge Rs_int"
    "boxing_books_up_for_storage Benevolence_1_int"
    "setting_the_table Wainscott_0_int"
    "setup_a_bar_for_a_cocktail_party restaurant_brunch"
)

# ---------- select tiers ----------
TASKS=()
case "$TIER" in
    easy)   TASKS=("${EASY_TASKS[@]}") ;;
    medium) TASKS=("${MEDIUM_TASKS[@]}") ;;
    hard)   TASKS=("${HARD_TASKS[@]}") ;;
    all)    TASKS=("${EASY_TASKS[@]}" "${MEDIUM_TASKS[@]}" "${HARD_TASKS[@]}") ;;
    *)      echo "Unknown tier: $TIER (choose: easy, medium, hard, all)"; exit 1 ;;
esac

TOTAL=${#TASKS[@]}
echo "========================================"
echo "  LLM Agent Benchmark"
echo "  Model: $MODEL"
echo "  Robot: $ROBOT"
echo "  Tier:  $TIER ($TOTAL tasks)"
echo "  Symbolic: $SYMBOLIC"
echo "========================================"

PASS=0
FAIL=0

for i in "${!TASKS[@]}"; do
    ENTRY="${TASKS[$i]}"
    TASK=$(echo "$ENTRY" | awk '{print $1}')
    SCENE=$(echo "$ENTRY" | awk '{print $2}')
    N=$((i + 1))

    echo ""
    echo "[$N/$TOTAL] $TASK  (scene: $SCENE)"
    echo "----------------------------------------"

    CMD="python -m omnigibson.examples.llm_agent.run_llm_agent \
        --model $MODEL \
        --robot $ROBOT \
        --task $TASK \
        --scene $SCENE \
        --max-steps $MAX_STEPS"

    if $SYMBOLIC; then
        CMD="$CMD --symbolic"
    fi

    if $DRY_RUN; then
        echo "  (dry-run) $CMD"
        continue
    fi

    if eval "$CMD"; then
        echo "  => PASSED"
        PASS=$((PASS + 1))
    else
        echo "  => FAILED (exit code $?)"
        FAIL=$((FAIL + 1))
    fi
done

if ! $DRY_RUN; then
    echo ""
    echo "========================================"
    echo "  Results: $PASS passed, $FAIL failed / $TOTAL total"
    echo "========================================"
fi
