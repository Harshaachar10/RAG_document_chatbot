export const RESOLUTION_LABELS: Record<string, string> = {
  linked: 'Linked',
  pending_review: 'Pending review',
  review_required: 'Review required',
  unresolved: 'Unresolved',
  rejected: 'Rejected',
  informational: 'Informational',
  identifier_conflict: 'Identifier conflict',
  duplicate_ingestion: 'Duplicate ingestion',
};

export const REVIEW_STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  deferred: 'Deferred',
  completed: 'Completed',
  resolved: 'Resolved',
  approved: 'Approved',
  rejected: 'Rejected',
};

export const PIPELINE_ACTION_LABELS: Record<string, string> = {
  AUTO_LINK: 'Auto-linked',
  REVIEW: 'Needs review',
  COMPLIANCE_REVIEW: 'Compliance review',
  DEDUPE_REVIEW: 'Deduplicate',
  ASSIGN_NPI: 'Assign NPI',
  NOT_A_PERSON: 'Not a person',
};

export const SEVERITY_LABELS: Record<string, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
};
