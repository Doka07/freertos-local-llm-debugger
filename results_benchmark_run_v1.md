# Benchmark Evaluation Report
- **Total Cases Evaluated:** 5
- **Failure Class Accuracy:** 40.0%
- **Fault Detection Accuracy:** 100.0%
- **Mean Task Identification (Jaccard):** 0.500
- **Mean Resource Identification (Jaccard):** 0.600
- **Evidence Reference Validity:** 60.0%
- **False Positive Count:** 0

## Case Details
| Case ID | Expected Class | Predicted Class | Match | Task Score | Obj Score | Valid Refs |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| case_001 | `DEADLOCK_LOCK_ORDER` | `DEADLOCK_LOCK_ORDER` | ✅ PASS | 1.0 | 1.0 | True |
| case_002 | `PRIORITY_INVERSION` | `MISSING_MUTEX_RELEASE` | ❌ FAIL | 0.0 | 0.0 | True |
| case_003 | `MISSED_ISR_NOTIFICATION` | `DEADLOCK_LOCK_ORDER` | ❌ FAIL | 0.0 | 0.0 | False |
| case_004 | `MISSING_MUTEX_RELEASE` | `DEADLOCK_LOCK_ORDER` | ❌ FAIL | 0.5 | 1.0 | True |
| case_005 | `NONE` | `NONE` | ✅ PASS | 1.0 | 1.0 | False |