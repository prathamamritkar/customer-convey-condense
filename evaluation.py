import json
import logging
from typing import List, Dict

# Scikit-learn is the standard for benchmarking F1/MSE
try:
    from sklearn.metrics import f1_score, mean_squared_error
except ImportError:
    logging.warning("scikit-learn not installed. Run: pip install scikit-learn")

def evaluate_llm_judge(ground_truth_path: str, llm_predictions_path: str):
    """
    Module for HITL (Human-in-the-Loop) Evaluation.
    Compares human-labelled audits to LLM-generated JSON audits.
    """
    try:
        with open(ground_truth_path, 'r', encoding='utf-8') as f:
            y_true_data = json.load(f)
        with open(llm_predictions_path, 'r', encoding='utf-8') as f:
            y_pred_data = json.load(f)
    except FileNotFoundError:
        print("Dataset files not found. Generate LLM predictions first to benchmark.")
        return

    # 1. Prepare classification tracking (String matches) for F1 Score
    # Classes for compliance: "Pass", "Fail", "Partial"
    compliance_true, compliance_pred = [], []
    # Classes for resolution: "Resolved", "Unresolved", "Escalated"
    resolution_true, resolution_pred = [], []

    # 2. Prepare continuous score tracking for MSE
    empathy_true, empathy_pred = [], []
    efficiency_true, efficiency_pred = [], []

    # Map the JSON arrays to parallel validation arrays
    for key in set(y_true_data.keys()).intersection(set(y_pred_data.keys())):
        true_audit = y_true_data[key]
        pred_audit = y_pred_data[key]

        # Categorical
        compliance_true.append(true_audit.get('compliance_status', 'Fail'))
        compliance_pred.append(pred_audit.get('compliance_status', 'Fail'))
        
        resolution_true.append(true_audit.get('resolution_status', 'Unresolved'))
        resolution_pred.append(pred_audit.get('resolution_status', 'Unresolved'))

        # Numerical (1-10)
        empathy_true.append(true_audit.get('empathy_score', 0))
        empathy_pred.append(pred_audit.get('empathy_score', 0))

        efficiency_true.append(true_audit.get('efficiency_score', 0))
        efficiency_pred.append(pred_audit.get('efficiency_score', 0))

    # --- CALCULATE METRICS ---
    
    # We use weighted F1 to gracefully handle class imbalances.
    f1_comp = f1_score(compliance_true, compliance_pred, average='weighted', zero_division=0)
    f1_res = f1_score(resolution_true, resolution_pred, average='weighted', zero_division=0)

    mse_emp = mean_squared_error(empathy_true, empathy_pred)
    mse_eff = mean_squared_error(efficiency_true, efficiency_pred)

    print("="*60)
    print(" 🎯 LLM-AS-A-JUDGE BENCHMARKING REPORT (HITL)")
    print("="*60)
    print(f"Total Call Audits Evaluated: {len(resolution_true)}")
    print("-"*60)
    print("CATEGORICAL CLASSIFICATIONS (Accuracy/Precision/Recall)")
    print(f" • Compliance Status F1 Score:  {f1_comp:.4f}")
    print(f" • Resolution Status F1 Score:  {f1_res:.4f}")
    print("-"*60)
    print("CONTINUOUS METRICS (Mean Squared Error)")
    print(f" • Empathy Score MSE:           {mse_emp:.4f}")
    print(f" • Efficiency Score MSE:        {mse_eff:.4f}")
    print("="*60)

if __name__ == "__main__":
    # Example Usage: Assuming you have JSON banks of data
    # evaluate_llm_judge("data/hitl_human_truth.json", "data/llm_outputs.json")
    print("Evaluation module loaded. Requires scikit-learn and ground truth JSON to execute.")
