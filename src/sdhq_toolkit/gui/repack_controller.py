"""Settings and external application actions, independently testable without Tk."""
import json
import subprocess
from pathlib import Path


class RepackSettings:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            return {}
        result = json.loads(self.path.read_text(encoding='utf-8'))
        if not isinstance(result, dict):
            raise ValueError('Configuração inválida')
        return result

    def save(self, values):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(self.path)


def garbro_status(value):
    if not value:
        return 'Não configurado'
    path = Path(value)
    return 'GARbro configurado' if path.is_file() and path.suffix.lower() == '.exe' else 'Executável não encontrado'


def launch_garbro(value):
    if garbro_status(value) != 'GARbro configurado':
        raise ValueError('Selecione o GARbro.exe. Mantenha os arquivos que acompanham o programa.')
    path = Path(value).resolve()
    return subprocess.Popen([str(path)], cwd=str(path.parent))
