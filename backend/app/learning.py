"""Small auditable ridge-regression experiment trained only on completed outcomes."""
import numpy as np
from datetime import datetime
from .domain import utcnow
from uuid import uuid4


def features(record):
    return [1., record['planned_minutes'] / 60.,
            float(record['weather'] in ('rain', 'heavy rain', 'storm')),
            float(record['weather'] in ('heat', 'fog'))]


def train(history, cutoff, snapshot_id):
    # Group equal completion timestamps into the same side of the split.
    records = sorted({r['id']: r for r in history if datetime.fromisoformat(r['completed_at']) <= cutoff}.values(),
                     key=lambda r: (datetime.fromisoformat(r['completed_at']), r['id']))
    if len(records) < 30:
        raise ValueError('At least 30 completed outcomes are required for the duration experiment')
    boundary = datetime.fromisoformat(records[int(len(records) * .7)]['completed_at'])
    training = [r for r in records if datetime.fromisoformat(r['completed_at']) < boundary]
    testing = [r for r in records if datetime.fromisoformat(r['completed_at']) >= boundary]
    if len(training) < 20 or len(testing) < 10:
        raise ValueError('Need at least 20 earlier training records and 10 later holdout records')
    x = np.array([features(r) for r in training]); y = np.array([r['actual_minutes'] for r in training])
    penalty = np.eye(4) * .01; penalty[0, 0] = 0
    weights = np.linalg.solve(x.T @ x + penalty, x.T @ y)
    predicted = np.maximum(1, np.array([features(r) for r in testing]) @ weights)
    truth = np.array([r['actual_minutes'] for r in testing])
    baseline = np.array([r['planned_minutes'] for r in testing])
    return {'id': str(uuid4()), 'created_at': utcnow(), 'snapshot_id': snapshot_id,
            'algorithm': 'Ridge regression; planned duration and observed weather features',
            'coefficients': weights.tolist(), 'cutoff': cutoff.isoformat(),
            'training_ids': [r['id'] for r in training], 'holdout_ids': [r['id'] for r in testing],
            'mae_minutes': round(float(np.mean(np.abs(predicted - truth))), 2),
            'engineering_baseline_mae': round(float(np.mean(np.abs(baseline - truth))), 2),
            'status': 'evaluation only',
            'limitation': 'Retrospective observed weather is not a forecast. No live accuracy, calibrated risk or safety claim. Does not replace the scheduler duration policy.'}
