import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory


class LabError(Exception):
    def __init__(self, code, status=503):
        self.code, self.status = code, status
        super().__init__(code)


@dataclass(frozen=True)
class Settings:
    api_key: str = field(default='', repr=False)
    enabled: bool = False
    host: str = ''
    username: str = field(default='', repr=False)
    password: str = field(default='', repr=False)
    domain_dn: str = 'DC=lab,DC=example,DC=test'
    ou_name: str = 'Portal-Test'
    ca_file: str = ''

    @classmethod
    def from_env(cls):
        flag = os.getenv('LAB_EXECUTION_ENABLED', 'false').lower()
        if flag not in ('true', 'false'):
            raise ValueError('LAB_EXECUTION_ENABLED must be true or false')
        return cls(api_key=os.getenv('LAB_API_KEY', ''), enabled=flag == 'true',
                   host=os.getenv('LAB_HOST', ''), username=os.getenv('LAB_USERNAME', ''),
                   password=os.getenv('LAB_PASSWORD', ''),
                   domain_dn=os.getenv('LAB_DOMAIN_DN', 'DC=lab,DC=example,DC=test'),
                   ou_name=os.getenv('LAB_OU_NAME', 'Portal-Test'),
                   ca_file=os.getenv('LAB_CA_FILE', ''))

    def validate(self):
        if len(self.api_key) < 32:
            raise LabError('api_key_not_configured')
        if not self.enabled:
            raise LabError('execution_disabled')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', self.host):
            raise LabError('invalid_lab_host')
        if not self.username or not self.password:
            raise LabError('credentials_not_configured')
        if not re.fullmatch(r'DC=[A-Za-z0-9-]+(?:,DC=[A-Za-z0-9-]+)+', self.domain_dn):
            raise LabError('invalid_domain_dn')
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9-]{0,47}', self.ou_name):
            raise LabError('invalid_ou_name')
        if self.ca_file and not Path(self.ca_file).is_file():
            raise LabError('ca_file_not_found')


class LabService:
    def __init__(self, settings, runner=None):
        self.settings = settings
        self.runner = runner
        self.lock = threading.Lock()

    def execute(self, operation):
        if operation not in ('connection', 'test_ou'):
            raise LabError('unknown_operation', 400)
        self.settings.validate()
        if not self.lock.acquire(blocking=False):
            raise LabError('lab_busy', 409)
        try:
            return self._execute(operation)
        finally:
            self.lock.release()

    def _execute(self, operation):
        s = self.settings
        inventory = {'all': {'children': {'windows_lab': {'hosts': {'lab_dc': {
            'ansible_host': s.host, 'ansible_user': s.username,
            'ansible_password': s.password, 'ansible_connection': 'winrm',
            'ansible_port': 5986, 'ansible_winrm_scheme': 'https',
            'ansible_winrm_transport': 'ntlm',
            'ansible_winrm_server_cert_validation': 'validate',
            'ansible_winrm_operation_timeout_sec': 20,
            'ansible_winrm_read_timeout_sec': 30,
            **({'ansible_winrm_ca_trust_path': s.ca_file} if s.ca_file else {})
        }}}}}}
        try:
            runner = self.runner
            if runner is None:
                import ansible_runner
                runner = ansible_runner.run
            project = Path(__file__).resolve().parents[2] / 'automation'
            with TemporaryDirectory(prefix='iac-lab-') as work:
                result = runner(private_data_dir=work, project_dir=str(project),
                    playbook=f'playbooks/{operation}.yml', inventory=inventory,
                    extravars={'lab_domain_dn': s.domain_dn, 'lab_ou_name': s.ou_name},
                    envvars={'ANSIBLE_CONFIG': str(project / 'ansible.cfg'),
                             'ANSIBLE_ROLES_PATH': str(project / 'roles'),
                             'ANSIBLE_DISPLAY_ARGS_TO_STDOUT': 'false',
                             'ANSIBLE_NOCOLOR': 'true'},
                    settings={'job_timeout': 120}, quiet=True)
                if result.rc != 0 or result.status != 'successful':
                    raise LabError('automation_failed', 502)
        except LabError:
            raise
        except Exception:
            raise LabError('automation_unavailable', 503) from None
        return {'operation': operation, 'status': 'succeeded'}
