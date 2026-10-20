import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
START = "<!-- METRICS:START -->"
END = "<!-- METRICS:END -->"


def n(value, digits=4, signed=False):
    value = float(value)
    return f"{value:+.{digits}f}" if signed else f"{value:.{digits}f}"


def build(metrics, thresholds):
    h = metrics["headline_metrics"]
    pooled = metrics["pooled_out_of_fold"]
    lines = [
        "| Metric | Value |",
        "|---|---:|",
        f"| Pooled out-of-fold ROC-AUC (patient-cluster 95% CI) | {n(h['pooled_out_of_fold_roc_auc'])} ({n(h['pooled_out_of_fold_roc_auc_patient_cluster_ci95'][0])} to {n(h['pooled_out_of_fold_roc_auc_patient_cluster_ci95'][1])}) |",
        f"| 5-fold mean ROC-AUC +/- SD (separate quantity) | {n(h['five_fold_mean_roc_auc'])} +/- {n(h['five_fold_roc_auc_sd'])} |",
        f"| Pooled out-of-fold PR-AUC | {n(pooled['full']['pr_auc'])} |",
        "",
        "| Operating point | Threshold | Sensitivity | Specificity | Precision | False alerts / patient-week | TP | FP | TN | FN |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in ("moderate", "high"):
        row = thresholds["test_evaluation"][label]
        lines.append(
            f"| {label.title()} | {n(row['threshold'], 2)} | {row['sensitivity']:.1%} | "
            f"{row['specificity']:.1%} | {row['precision']:.1%} | "
            f"{n(row['false_alerts_per_patient_week'], 3)} | {row['tp']} | {row['fp']} | {row['tn']} | {row['fn']} |"
        )
    lines += ["", "| Paired ablation | Fold-mean ROC-AUC difference +/- SD | Fold wins |", "|---|---:|---:|"]
    for row in metrics["paired_differences"].values():
        lines.append(f"| {row['label']} | {n(row['roc_mean'], signed=True)} +/- {n(row['roc_sd'])} | {row['roc_wins']} |")
    lines += [
        "",
        "| BP availability | Fold-mean paired dAUC +/- SD (n=5) | Fold wins | Pooled OOF paired dAUC | Pooled bootstrap mean and patient-cluster 95% CI | Fold t-test p | Conclusion |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    sparse = metrics["sparse_bp_experiment"]["availability_settings"]
    for key in ("daily", "2-3 readings/week", "1 reading/week"):
        gain = sparse[key]["wearable_gain"]
        ci = gain["patient_cluster_bootstrap_ci95"]
        lines.append(
            f"| {sparse[key]['label']} | {n(gain['roc_auc_difference_mean'], signed=True)} +/- {n(gain['roc_auc_difference_sd'])} | "
            f"{gain['wins']} | {n(gain['pooled_oof_roc_auc_difference'], signed=True)} | "
            f"{n(gain['pooled_bootstrap_mean_roc_auc_difference'], signed=True)} "
            f"[{n(ci[0], signed=True)}, {n(ci[1], signed=True)}] | "
            f"{n(gain['fold_one_sample_ttest_p_value'])} | {gain['conclusion']} |"
        )
    lines += ["", "BP history is the consistent gain; sleep/HRV help only when cuff readings are sparse (see table), and not at all in the daily setting."]
    figures = sorted(p for p in (ROOT / "docs" / "figures").glob("*.png") if "calib" in p.name.lower())
    if figures:
        rel = figures[0].relative_to(ROOT).as_posix()
        lines.append(f"\nCalibration figure: ![Calibration plot]({rel})")
    else:
        lines.append("\nCalibration figure: NOT FOUND in docs/figures.")
    return "\n".join(lines)


def main():
    readme_path = README
    text = readme_path.read_text(encoding="utf-8-sig")
    metrics = json.loads((ROOT / "ml/artifacts/metrics.json").read_text(encoding="utf-8"))
    thresholds = json.loads((ROOT / "ml/artifacts/thresholds.json").read_text(encoding="utf-8"))
    block = f"{START}\n{build(metrics, thresholds)}\n{END}"
    if START in text and END in text:
        before, rest = text.split(START, 1)
        _, after = rest.split(END, 1)
        text = before + block + after
    else:
        begin = text.index("| Feature set (pooled out-of-fold)")
        finish = text.index("clinical performance.", begin) + len("clinical performance.")
        text = text[:begin] + block + text[finish:]
    text = re.sub(
        r"Reproduce in Windows PowerShell:.*?same script\.",
        lambda _: "Reproduce in Windows PowerShell with .\\scripts\\evaluate.ps1 or .\\.venv_check\\Scripts\\python.exe -m ml.robustness. GNU make is optional.",
        text,
        count=1,
        flags=re.S,
    )
    text = text.replace(
        "Labels are derived from simulated next-day cuff readings, which in turn are generated from a hidden latent risk score that includes sleep debt, HRV drop, activity and stress terms, so model results measure recovery of the simulator's assumptions and are not evidence on real patients.",
        "Labels are derived from simulated next-day cuff readings, which in turn are generated from a hidden latent risk score that includes sleep debt, HRV drop, activity and stress terms, so model results measure recovery of the simulator's assumptions and are not evidence on real patients.\n\nCGM not included: the target is hypertension, the guidelines list CGM as an example; sleep stages, HRV, steps, resting HR and medication timing are included. Genetic markers are out of scope for this run.",
    )
    text = text.replace(
        "Parts of this project were developed with AI coding assistants; all code was reviewed, tested and is the team's responsibility.",
        "AI assistants were used for coding; human team members specified, reviewed and validated the project.",
    )
    readme_path.write_text(text, encoding="utf-8")
    print("Updated README metrics from ml/artifacts/metrics.json and thresholds.json.")


if __name__ == "__main__":
    main()
