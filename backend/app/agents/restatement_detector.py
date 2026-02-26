"""
RestatementDetector
===================
Analyzes extracted financial figures across multiple years to detect
silent restatements (where a prior year's comparative figure was changed)
and auditor rotations over time.
"""

from typing import Dict, Any, List

class RestatementDetector:
    """
    Compares financial scans year-over-year to flag restatements and auditor changes.
    """
    
    def compare(self, scans: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Takes a dictionary of scans keyed by year (e.g. "FY22", "FY23", "FY24").
        Returns a dict indicating if restatements or auditor changes were found.
        """
        # Sort years to ensure chronological processing (e.g. FY22, FY23, FY24)
        sorted_years = sorted(scans.keys())
        
        restatements = []
        auditor_history = {}
        
        # Build auditor history
        for year in sorted_years:
            yr_data = scans[year]
            aud_data = yr_data.get("Auditor Name")
            if aud_data and aud_data.get("value"):
                auditor_history[year] = aud_data["value"]
                
        # Detect auditor change
        # If there are > 1 unique auditors in the history
        unique_auditors = set(auditor_history.values())
        auditor_changed = len(unique_auditors) > 1

        # Detect restatements
        # Logic: Compare FY_N's "previous_value" with FY_(N-1)'s "value"
        # We assume FinancialExtractor extracts 'previous_value' for the comparative column
        for i in range(1, len(sorted_years)):
            prev_year_key = sorted_years[i-1] # e.g. FY22
            curr_year_key = sorted_years[i]   # e.g. FY23
            
            curr_scan = scans[curr_year_key]
            prev_scan = scans[prev_year_key]
            
            # Check each numeric figure
            for figure in ["Revenue", "EBITDA", "PAT", "Total Debt", "Net Worth"]:
                curr_fig = curr_scan.get(figure)
                prev_fig = prev_scan.get(figure)
                
                if not curr_fig or not prev_fig:
                    continue
                    
                restated_val = curr_fig.get("previous_value")
                original_val = prev_fig.get("value")
                
                if restated_val is not None and original_val is not None and original_val != 0:
                    diff_pct = ((restated_val - original_val) / abs(original_val)) * 100
                    
                    # Flag if differs by more than 2%
                    if abs(diff_pct) > 2.0:
                        restatements.append({
                            "figure": figure,
                            "year_restated": prev_year_key,
                            "original_value": original_val,
                            "restated_value": restated_val,
                            "change_pct": round(diff_pct, 1),
                            "severity": "HIGH" if abs(diff_pct) > 10.0 else "MEDIUM",
                            "finding": (
                                f"{figure} for {prev_year_key} was reported as {curr_fig.get('unit', '')} {original_val} "
                                f"in the {prev_year_key} annual report but restated to {curr_fig.get('unit', '')} {restated_val} "
                                f"in the {curr_year_key} annual report — a {round(diff_pct, 1)}% {'downward' if diff_pct < 0 else 'upward'} revision."
                            )
                        })

        return {
            "restatements_detected": len(restatements) > 0,
            "restatements": restatements,
            "auditor_changed": auditor_changed,
            "auditor_history": auditor_history
        }
