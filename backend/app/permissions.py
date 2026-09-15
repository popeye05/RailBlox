"""Explicit, fail-closed access policy for the four division roles."""
import re

ROLES = {'viewer': 0, 'planner': 1, 'officer': 2, 'admin': 3}
CAPABILITIES = [
    {'id': 'read', 'label': 'View schedules, train movements and evidence', 'role': 'viewer'},
    {'id': 'export', 'label': 'Export records and reports', 'role': 'viewer'},
    {'id': 'prepare', 'label': 'Maintain tasks, import data and resolve mappings', 'role': 'planner'},
    {'id': 'plan', 'label': 'Generate proposals and test disruptions', 'role': 'planner'},
    {'id': 'analyse', 'label': 'Run analysis and prepare report drafts', 'role': 'planner'},
    {'id': 'validate', 'label': 'Validate plans and run benchmarks', 'role': 'officer'},
    {'id': 'review', 'label': 'Approve, reject and revise commitments', 'role': 'officer'},
    {'id': 'outcomes', 'label': 'Finalize cycles and record actual outcomes', 'role': 'officer'},
    {'id': 'users', 'label': 'Invite colleagues and manage division access', 'role': 'admin'},
    {'id': 'configure', 'label': 'Configure automation and review the audit trail', 'role': 'admin'},
]

# A new write endpoint must be assigned a policy deliberately.
WRITE_RULES = [
    ('POST', r'/api/tasks', 'planner'),
    ('PATCH', r'/api/tasks/[^/]+', 'planner'),
    ('POST', r'/api/plans/generate', 'planner'),
    ('POST', r'/api/plans/[^/]+/opportunities', 'planner'),
    ('POST', r'/api/plans/[^/]+/(validate|revise|approve|finalize)', 'officer'),
    ('POST', r'/api/scenarios', 'planner'),
    ('POST', r'/api/scenarios/[^/]+/repair', 'planner'),
    ('POST', r'/api/imports/preview', 'planner'),
    ('POST', r'/api/imports/[^/]+/commit', 'planner'),
    ('POST', r'/api/mappings/[^/]+/resolve', 'planner'),
    ('POST', r'/api/benchmarks', 'officer'),
    ('POST', r'/api/intelligence/(evidence|recommend|reports)', 'planner'),
    ('POST', r'/api/intelligence/nlp/[^/]+', 'planner'),
    ('POST', r'/api/intelligence/recommendations/[^/]+/(decision|outcomes)', 'officer'),
    ('POST', r'/api/intelligence/reports/[^/]+/review', 'officer'),
    ('POST', r'/api/ai/recommendations/[^/]+/explain', 'planner'),
    ('POST', r'/api/ai/reports/[^/]+/summary', 'planner'),
    ('POST', r'/api/ai/nlp/[^/]+', 'planner'),
    ('POST', r'/api/ai/models/[^/]+/train', 'planner'),
]


def required_role(method, path):
    path = path.rstrip('/')
    if path == '/api/admin' or path.startswith('/api/admin/'):
        return 'admin'
    if method in {'GET', 'HEAD', 'OPTIONS'}:
        return 'viewer'
    return next((role for verb, pattern, role in WRITE_RULES
                 if method == verb and re.fullmatch(pattern, path)), None)


def capabilities(role):
    return [item['id'] for item in CAPABILITIES if ROLES.get(role, -1) >= ROLES[item['role']]]
