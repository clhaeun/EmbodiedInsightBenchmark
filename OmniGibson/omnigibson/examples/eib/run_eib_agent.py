import faulthandler
faulthandler.enable()

import os
from dotenv import load_dotenv
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Try to load .env from examples/eib/data/ first, then fall back to examples/eib/
_env_path = os.path.join(os.path.dirname(__file__), "data", ".env")
if not os.path.exists(_env_path):
    _env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)

os.environ.setdefault("OMNIGIBSON_HEADLESS", "1")
os.environ.setdefault("CARB_LOG_LEVEL", "error")
os.environ.setdefault("OMNI_LOG_LEVEL", "error")
os.environ.setdefault("CUDA_HOME", "/usr/local/cuda-11.8")
os.environ.setdefault("TORCH_CUDA_ARCH_LIST", "8.9")

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime

METASKILLS = ["IH", "PS", "ED", "VB", "SF", "CA"]

logger = logging.getLogger("EIB_logger")
if not logger.hasHandlers():
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)

# Base directory for EIB data files
EIB_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def run_single(meta, args, episode_id, output_dir):
    """Run a single episode in a subprocess."""
    import importlib
    meta_lower = meta.lower()

    # Import EIB planner/evaluator from omnigibson
    planner_cls = getattr(importlib.import_module(f"omnigibson.llm_agent.eib_{meta_lower}_planner"), f"{meta}Planner")
    evaluator_cls = getattr(importlib.import_module(f"omnigibson.evaluators.eib_{meta_lower}_evaluator"), f"{meta}Evaluator")

    episodes_path = os.path.join(EIB_DATA_DIR, "task", meta, f"{meta_lower}_episodes.json")
    config_path = os.path.join(EIB_DATA_DIR, "env", "env.yaml")
    prompt_config_path = os.path.join(EIB_DATA_DIR, "prompts", f"{meta_lower}_prompt.yaml")

    planner = planner_cls(prompt_config_path)
    evaluator = evaluator_cls(config_path, planner, episodes_path, output_dir, record=args.video)
    metrics = evaluator.run_all(episode_ids=[episode_id])
    return metrics


def run_all_sequential(meta, args, episode_ids=None):
    """Run each episode in its own subprocess to avoid segfault contamination."""
    meta_lower = meta.lower()
    episodes_path = os.path.join(EIB_DATA_DIR, "task", meta, f"{meta_lower}_episodes.json")

    with open(episodes_path) as f:
        data = json.load(f)
    all_episodes = data["episodes"]

    if episode_ids is not None:
        all_episodes = [ep for ep in all_episodes if ep["episode_id"] in episode_ids]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output or os.path.join(EIB_DATA_DIR, "..", "..", "..", "experiments", "eib", timestamp, meta)
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    all_results = []
    for ep in all_episodes:
        ep_id = ep["episode_id"]
        logger.info(f"\n{'='*60}")
        logger.info(f"Launching Episode {ep_id} in subprocess...")
        logger.info(f"{'='*60}")

        cmd = [
            "/isaac-sim/python.sh", __file__,
            "--meta", meta,
            "--episode", str(ep_id),
            "--output", output_dir,
        ]
        if args.video:
            cmd.append("--video")

        proc = subprocess.run(cmd, capture_output=False, timeout=600)

        # Read result from the saved file
        results_path = os.path.join(output_dir, "results.json")
        if os.path.exists(results_path):
            with open(results_path) as f:
                saved = json.load(f)
            # Find this episode's result
            ep_result = next((r for r in saved if r["episode_id"] == ep_id), None)
            if ep_result:
                all_results.append(ep_result)
                logger.info(f"  -> Decision: {ep_result['decision']}, Correct: {ep_result['correct']}")
                continue

        # Subprocess crashed before saving
        logger.info(f"  -> Episode {ep_id} crashed (exit code {proc.returncode})")
        all_results.append({
            "episode_id": ep_id,
            "ih_type": ep["ih_type"],
            "instruction": ep["instruction"],
            "expected": ep["expected_action"],
            "decision": "error",
            "reasoning": f"Subprocess crashed with exit code {proc.returncode}",
            "steps": [],
            "correct": False,
        })

    # Save consolidated results
    with open(os.path.join(output_dir, "results.json"), "w") as f:
        json.dump(all_results, f, indent=2)

    # Compute and save metrics
    feasible_results = [r for r in all_results if r["ih_type"] == "feasible"]
    abstain_results = [r for r in all_results if r["ih_type"] == "abstain"]
    ih_feasible = sum(r["correct"] for r in feasible_results) / max(len(feasible_results), 1)
    ih_abstain = sum(r["correct"] for r in abstain_results) / max(len(abstain_results), 1)
    if ih_abstain > 0 and ih_feasible > 0:
        ih_core = 2 * ih_abstain * ih_feasible / (ih_abstain + ih_feasible)
    else:
        ih_core = 0.0
    metrics = {
        "IH_feasible": round(ih_feasible, 4),
        "IH_abstain": round(ih_abstain, 4),
        "IH_core": round(ih_core, 4),
        "total_episodes": len(all_results),
        "correct": sum(r["correct"] for r in all_results),
    }
    with open(os.path.join(output_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    logger.info(f"\n{'='*60}")
    logger.info("Final Results:")
    for k, v in metrics.items():
        logger.info(f"  {k}: {v}")
    logger.info(f"Results saved to: {output_dir}")

    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--meta", type=str, required=True, choices=METASKILLS)
    parser.add_argument("--episode", type=str, default=None, help="Episode id(s), e.g. '6' or '6,7,8'")
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--video", action="store_true")

    args = parser.parse_args()

    if args.episode is not None:
        episode_ids = [int(x.strip()) for x in args.episode.split(",")]
        if len(episode_ids) == 1 and args.output:
            # Single episode mode: run directly (called by subprocess)
            run_single(args.meta, args, episode_ids[0], args.output)
        else:
            # Multiple episodes: run each in subprocess
            run_all_sequential(args.meta, args, episode_ids=episode_ids)
    else:
        # All episodes: run each in subprocess
        run_all_sequential(args.meta, args)
