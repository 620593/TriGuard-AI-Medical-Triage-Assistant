"""
History Retrieval Tool for Long-Term Memory (V6)
Queries MongoDB for past reports.
"""
from backend.src.tools.mongodb_tool import _get_db

async def get_relevant_history(user_id: str, current_symptoms: list, current_intent: str, limit: int = 3) -> str:
    db = _get_db()
    
    # Query last 30 reports for this user
    cursor = db.reports.find({"report.user_id": str(user_id)}).sort("created_at", -1).limit(30)
    user_reports = []
    async for doc in cursor:
        user_reports.append(doc)
    
    if not user_reports:
        return ""
        
    relevant_reports = []
    
    for report_doc in user_reports:
        report = report_doc.get("report", {})
        
        # Check intent match OR symptom overlap
        report_intent = report.get("intent", "")
        report_symptoms = report.get("symptoms", [])
        
        has_symptom_overlap = any(sym.lower() in [rs.lower() for rs in report_symptoms] for sym in current_symptoms)
        has_intent_match = (report_intent == current_intent) and current_intent != "casual"
        
        if has_symptom_overlap or has_intent_match:
            relevant_reports.append(report_doc)
            
        if len(relevant_reports) >= limit:
            break
            
    if not relevant_reports:
        return ""
        
    formatted_str = "=== RELEVANT PRIOR HISTORY ===\n"
    for report_doc in relevant_reports:
        report = report_doc.get("report", {})
        
        date_str = str(report_doc.get("created_at", "Unknown date"))
        if " " in date_str:
            date_str = date_str.split(" ")[0]
        elif "T" in date_str:
            date_str = date_str.split("T")[0]
            
        risk = report.get("risk_level", "unknown")
        symps = ", ".join(report.get("symptoms", []))
        
        # Depending on how it's stored, use clinical_summary or summary
        summary = ""
        if "clinical_summary" in report:
            summary = report["clinical_summary"]
        elif "summary" in report:
            summary = report["summary"]
        elif "llm_output" in report and isinstance(report["llm_output"], dict):
            summary = report["llm_output"].get("clinical_summary", "No summary available.")
        else:
            summary = "No summary available."
            
        formatted_str += f"[{date_str}] Risk: {risk} | Symptoms: {symps}\n"
        formatted_str += f"Summary: {summary}\n---\n"
        
    formatted_str += "=== END PRIOR HISTORY ==="
    
    return formatted_str
