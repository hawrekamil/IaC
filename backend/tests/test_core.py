from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import pytest
from app.core import LabError, LabService, Settings


def configured():
    return Settings(api_key='k' * 32, enabled=True, host='dc01.lab.test',
                    username='LAB\\operator', password='unit-test-only')


def test_disabled_never_runs():
    called = []
    service = LabService(replace(configured(), enabled=False), lambda **kw: called.append(kw))
    with pytest.raises(LabError, match='execution_disabled'):
        service.execute('connection')
    assert not called


@pytest.mark.parametrize('changes', [
    {'api_key': ''}, {'host': '{{bad}}'}, {'username': ''}, {'password': ''},
    {'domain_dn': 'invalid'}, {'ou_name': 'bad,OU=x'}, {'ca_file': '/missing/ca.pem'}
])
def test_invalid_config(changes):
    with pytest.raises(LabError):
        replace(configured(), **changes).validate()


def test_unknown_operation():
    with pytest.raises(LabError, match='unknown_operation'):
        LabService(configured()).execute('shell')


def test_success_uses_only_fixed_target_and_verified_tls():
    captured = {}
    def runner(**kwargs):
        captured.update(kwargs)
        assert Path(kwargs['private_data_dir']).is_dir()
        assert Path(kwargs['project_dir'], kwargs['playbook']).is_file()
        return SimpleNamespace(rc=0, status='successful')
    result = LabService(configured(), runner).execute('test_ou')
    host = captured['inventory']['all']['children']['windows_lab']['hosts']['lab_dc']
    assert host['ansible_winrm_server_cert_validation'] == 'validate'
    assert host['ansible_host'] == 'dc01.lab.test'
    assert captured['settings']['job_timeout'] == 120
    assert not Path(captured['private_data_dir']).exists()
    assert result == {'operation': 'test_ou', 'status': 'succeeded'}


def test_failure_is_generic_and_releases_lock():
    service = LabService(configured(), lambda **kw: (_ for _ in ()).throw(RuntimeError('secret')))
    with pytest.raises(LabError, match='automation_unavailable') as error:
        service.execute('connection')
    assert 'secret' not in str(error.value)
    assert not service.lock.locked()


def test_busy_target_is_rejected():
    service = LabService(configured())
    service.lock.acquire()
    with pytest.raises(LabError, match='lab_busy'):
        service.execute('connection')
    service.lock.release()


def test_unsuccessful_runner():
    service = LabService(configured(), lambda **kw: SimpleNamespace(rc=1, status='failed'))
    with pytest.raises(LabError, match='automation_failed'):
        service.execute('connection')
