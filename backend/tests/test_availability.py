from app.availability import MODEL_VERSION, estimate, summary
from app.fixtures import acceptance
from fastapi.testclient import TestClient
from app.main import create_app


def test_availability_is_explainable_and_deduplicates_shared_block():
    snapshot = acceptance()
    plan = {
        'id': 'plan-1',
        'assignments': [
            {'task_id': 'A', 'window_id': 'W1', 'start': 130, 'end': 170},
            {'task_id': 'B', 'window_id': 'W1', 'start': 170, 'end': 195},
        ],
        'packages': [{'window_id': 'W1', 'start': 130, 'end': 195}],
    }
    rows = estimate(snapshot, 7, 0, plan)
    row = next(item for item in rows if item.asset_id == 'AS-S1-UP')
    assert row.model_version == MODEL_VERSION
    assert row.scheduled_block_ids == ['W1']
    assert row.scheduled_task_ids == ['A', 'B']
    assert row.baseline_availability < 1
    assert row.downtime_avoided_hours > 0


def test_summary_surfaces_review_required_health():
    result = summary(acceptance(), 7, 0)
    assert result['synthetic'] is True
    assert result['data_quality']['block_new_recommendation'] is True
    assert result['metrics']['critical_assets'] > 0
    assert result['disclaimer'].startswith('Synthetic advisory')


def test_availability_api_returns_plan_comparison(tmp_path):
    with TestClient(create_app('sqlite:///' + str(tmp_path / 'availability.db'))) as client:
        corridor = next(item for item in client.get('/api/context').json()['corridors'] if item['id'] == 'small')
        plan = next(item for item in client.get('/api/context').json()['plans'] if item['corridor'] == 'small')
        response = client.get('/api/availability/summary', params={'snapshot_id': corridor['snapshot_id'], 'plan_id': plan['id']})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body['plan_id'] == plan['id']
        assert body['model_version'] == MODEL_VERSION
        assert body['estimates'][0]['source_record_id'].startswith('SMMS-')
        assert client.get('/api/assets/AS-S1-UP/availability', params={'snapshot_id': corridor['snapshot_id']}).status_code == 200
