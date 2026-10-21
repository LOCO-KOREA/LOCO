"""Build a portable Windows x64 Electron + frozen Python + model directory.

No system installation, registry writes or existing DB copying. Each build has
a new output directory so a running/previous package is never overwritten.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_SHA = '0fac2226112d0371903ca86e3853cec24ef603a0b2f96f589b180f0ebdd135ab'


def set_executable_icon(executable, icon):
    """Update only the new output copy, including its existing icon languages."""
    import pefile
    from PyInstaller.utils.win32.icon import IconFile, win32api
    source = IconFile(str(icon))
    with pefile.PE(str(executable), fast_load=True) as image:
        image.parse_data_directories(directories=[2])
        directory = getattr(image, 'DIRECTORY_ENTRY_RESOURCE', None)
        groups = [(name.id if name.name is None else str(name.name), language.id)
                  for entry in (directory.entries if directory else []) if entry.id == 14
                  for name in entry.directory.entries for language in name.directory.entries]
    handle = win32api.BeginUpdateResource(str(executable), False)
    try:
        for group_id, language in groups or [(1, 0)]:
            win32api.UpdateResource(handle, 14, group_id, source.grp_icon_dir() + source.grp_icondir_entries(1), language)
            for index, data in enumerate(source.images, 1):
                win32api.UpdateResource(handle, 3, index, data, language)
    except Exception:
        win32api.EndUpdateResource(handle, True)
        raise
    win32api.EndUpdateResource(handle, False)


def main():
    if sys.platform != 'win32' or sys.version_info[:2] != (3, 12):
        raise SystemExit('Build with CPython 3.12 x64 on Windows.')
    model = ROOT / 'models' / 'movenet_lightning.tflite'
    if not model.is_file() or hashlib.sha256(model.read_bytes()).hexdigest() != MODEL_SHA:
        raise SystemExit('Run scripts/download_movenet.ps1 to obtain the verified official model.')
    electron = ROOT / 'frontend' / 'node_modules' / 'electron' / 'dist'
    if not (electron / 'electron.exe').is_file():
        raise SystemExit('Run npm --prefix frontend ci and initialize Electron first.')
    icon = ROOT / 'frontend' / 'assets' / 'app-icon.ico'
    if not icon.is_file():
        raise SystemExit('Missing LOCO Windows icon: frontend/assets/app-icon.ico')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    work = ROOT / 'build' / ('windows-' + stamp)
    work.mkdir(parents=True)
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onedir', '--name', 'loco-service',
        '--paths', str(ROOT), '--collect-all', 'ai_edge_litert',
        '--add-data', str(ROOT / 'ergo' / 'db' / 'schema_v1.sql') + ';ergo/db',
        '--distpath', str(work / 'backend'), '--workpath', str(work / 'freeze'),
        '--specpath', str(work), str(ROOT / 'ergo' / 'service' / 'json_lines.py'),
    ], cwd=ROOT, check=True)
    output = ROOT / 'dist' / ('LOCO-2.0-windows-x64-' + stamp)
    shutil.copytree(electron, output)
    (output / 'electron.exe').rename(output / 'LOCO.exe')
    set_executable_icon(output / 'LOCO.exe', icon)
    resources = output / 'resources'
    app = resources / 'app'
    frontend = app / 'frontend'
    shutil.copytree(ROOT / 'frontend', frontend, ignore=shutil.ignore_patterns('node_modules', '.local', 'package-lock.json'))
    (app / 'package.json').write_text(json.dumps(dict(name='loco', version='2.0.0', main='frontend/electron/main.cjs')), encoding='utf-8')
    guide = app / 'docs' / 'ui'; guide.mkdir(parents=True)
    shutil.copy2(ROOT / 'docs' / 'ui' / 'loco-guide.js', guide)
    shutil.copytree(work / 'backend', resources / 'backend')
    (resources / 'models').mkdir()
    shutil.copy2(model, resources / 'models' / model.name)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True))
    manifest = dict(version='2.0', build_utc=stamp, source_commit=commit, source_has_local_changes=dirty,
                    python=sys.version, model_sha256=MODEL_SHA,
                    default_db=r'%LOCALAPPDATA%\LOCO\loco_demo.db',
                    external_validation=['real GPT account', 'clean separate Windows PC', 'user legacy DB', 'field study'])
    manifest['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                               for base in ('ergo','frontend') for p in (ROOT/base).rglob('*')
                               if p.is_file() and not any(part in ('node_modules','.local','__pycache__') for part in p.parts)
                               and p.suffix in ('.py','.js','.cjs','.html','.css','.sql','.json','.svg','.png','.ico')}
    manifest['source_sha256']['docs/ui/loco-guide.js']=hashlib.sha256((ROOT/'docs/ui/loco-guide.js').read_bytes()).hexdigest()
    manifest['contract_version']='2.0'
    manifest['electron']=json.loads((ROOT/'frontend/node_modules/electron/package.json').read_text(encoding='utf-8'))['version']
    (output / 'build-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / '실행안내.txt').write_text(
        'LOCO 2.0 Windows x64 포터블\n\n폴더 전체를 유지한 채 LOCO.exe를 실행하세요. Python/Node 설치가 필요하지 않습니다.\n'
        'DB 기본 경로: %LOCALAPPDATA%\\LOCO\\loco_demo.db\n사진은 원본 경로로 연결되므로 원본 파일을 보존하세요.\n'
        'GPT를 사용하려면 앱 실행 환경에 OPENAI_API_KEY를 설정하고 설정 화면에서 모델과 사용 여부를 확인하세요.\n'
        '키는 패키지에 포함되지 않습니다. 설정이 없으면 로컬 대체 설명을 사용합니다.\n'
        '이 빌드는 개발 PC 검증용이며 별도 PC/현장/실제 GPT 계정 검증 상태는 검증 보고서를 따릅니다.\n', encoding='utf-8')
    print(str(output), flush=True)
    (ROOT / '.local').mkdir(exist_ok=True)
    (ROOT / '.local' / 'latest-package.txt').write_text(str(output), encoding='utf-8')


if __name__ == '__main__':
    main()
