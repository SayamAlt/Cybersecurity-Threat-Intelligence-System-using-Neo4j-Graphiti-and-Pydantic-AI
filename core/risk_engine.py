def compute_risk_score(cvss):
    cvss = float(cvss) if cvss else 5.0
    
    if cvss >= 9.0:
        return "CRITICAL"
    elif cvss >= 7.0:
        return "HIGH"
    elif cvss >= 4.0:
        return "MEDIUM"
    else:
        return "LOW"