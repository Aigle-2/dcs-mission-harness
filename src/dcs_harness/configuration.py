"""Private local paths in an ignored dotenv file; no shell evaluation."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess

from .core import HarnessError, result

KEYS = ('DCS_HARNESS_DCS_PATH', 'DCS_HARNESS_SAVED_GAMES_PATH',
        'DCS_HARNESS_REFERENCE_ROOTS', 'DCS_HARNESS_PRIVATE_ROOT')


def read_env(repo: Path) -> dict[str, str]:
    path = repo / '.env'
    if path.is_symlink():
        raise HarnessError('UNSAFE_LOCAL_ENV', 'BLOCKED')
    if not path.exists():
        return {}
    if path.is_symlink() or path.stat().st_size > 64_000:
        raise HarnessError('UNSAFE_LOCAL_ENV', 'BLOCKED')
    values = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        key, separator, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if not separator or key not in KEYS:
            continue
        if key in values:
            raise HarnessError('DUPLICATE_LOCAL_SETTING', 'BLOCKED')
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except ValueError:
                raise HarnessError('INVALID_LOCAL_ENV', 'BLOCKED') from None
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        if not isinstance(value, str):
            raise HarnessError('INVALID_LOCAL_ENV', 'BLOCKED')
        values[key] = value
    return values


def load_env(repo: Path) -> None:
    for key, value in read_env(repo).items():
        if value:
            os.environ.setdefault(key, value)


def directory(value: str, code: str) -> Path:
    path = Path(value)
    if not value or any(ord(c) < 32 for c in value) or not path.is_absolute() or not path.is_dir():
        raise HarnessError(code, 'BLOCKED')
    resolved = path.resolve()
    if resolved == Path(resolved.anchor) or resolved == Path.home().resolve():
        raise HarnessError(code, 'BLOCKED')
    return resolved


@dataclass(frozen=True)
class Settings:
    dcs: Path
    saved_games: Path
    references: tuple[Path, ...]


def settings(repo: Path) -> Settings:
    values = {**read_env(repo), **{k: os.environ[k] for k in KEYS if k in os.environ}}
    configured = settings_values(values)
    if configured.saved_games.is_relative_to(repo.resolve()):
        raise HarnessError('SAVED_GAMES_INSIDE_CHECKOUT', 'BLOCKED')
    return configured


def settings_values(values: dict[str, str]) -> Settings:
    if not all(values.get(k) for k in KEYS[:2]):
        raise HarnessError('LOCAL_SETUP_REQUIRED', 'BLOCKED')
    dcs = directory(values[KEYS[0]], 'DCS_PATH_INVALID')
    if not any((dcs / binary / 'DCS.exe').is_file() for binary in ('bin', 'bin-mt')):
        raise HarnessError('DCS_INSTALLATION_NOT_FOUND', 'BLOCKED')
    saved = directory(values[KEYS[1]], 'SAVED_GAMES_PATH_INVALID')
    if not (saved / 'Config').is_dir() and not saved.name.lower().startswith('dcs'):
        raise HarnessError('SAVED_GAMES_PROFILE_NOT_FOUND', 'BLOCKED')
    try:
        refs = json.loads(values.get(KEYS[2], '[]'))
    except ValueError:
        raise HarnessError('REFERENCE_ROOTS_INVALID', 'BLOCKED') from None
    if not isinstance(refs, list) or any(not isinstance(v, str) for v in refs):
        raise HarnessError('REFERENCE_ROOTS_INVALID', 'BLOCKED')
    roots = tuple(directory(v, 'REFERENCE_ROOT_INVALID') for v in refs)
    if len(set(roots)) != len(roots):
        raise HarnessError('DUPLICATE_REFERENCE_ROOT', 'BLOCKED')
    return Settings(dcs, saved, roots)


def ignored_env(repo: Path) -> None:
    try:
        tracked = subprocess.run(['git', 'ls-files', '--error-unmatch', '--', '.env'], cwd=repo,
                                 capture_output=True, timeout=10)
        ignored = subprocess.run(['git', 'check-ignore', '-q', '--', '.env'], cwd=repo,
                                 capture_output=True, timeout=10)
    except OSError:
        raise HarnessError('LOCAL_ENV_IGNORE_NOT_VERIFIED', 'BLOCKED') from None
    if tracked.returncode == 0 or ignored.returncode != 0:
        raise HarnessError('LOCAL_ENV_MUST_BE_GITIGNORED', 'BLOCKED')


def initialize(repo: Path, dcs: Path | None, saved: Path | None,
               references: list[Path] | None, private: Path | None) -> dict:
    values = {**read_env(repo), **{k: os.environ[k] for k in KEYS if k in os.environ}}
    if dcs is not None: values[KEYS[0]] = str(dcs.resolve())
    if saved is not None: values[KEYS[1]] = str(saved.resolve())
    if references is not None: values[KEYS[2]] = json.dumps([str(p.resolve()) for p in references])
    if private is not None: values[KEYS[3]] = str(private.resolve())
    missing = [k for k in KEYS[:2] if not values.get(k)]
    if missing:
        return result('BLOCKED', 'init', findings=[{'code': 'LOCAL_SETUP_REQUIRED'}],
                      missing=missing, next_skill='environment-setup',
                      skill_file='.agents/skills/environment-setup/SKILL.md',
                      agent_action='Ask the user for the DCS installation, Saved Games/DCS and optional reference directories. Save with init.')
    if not values.get(KEYS[2]):
        values[KEYS[2]] = '[]'
    if not values.get(KEYS[3]):
        values[KEYS[3]] = str((repo.parent / f'{repo.name}-private').resolve())
    # Validate the exact candidates, independent of existing process overrides.
    configured = settings_values(values)
    if configured.saved_games.is_relative_to(repo.resolve()):
        raise HarnessError('SAVED_GAMES_INSIDE_CHECKOUT', 'BLOCKED')
    private_path = Path(values[KEYS[3]])
    if (not private_path.is_absolute() or private_path.resolve() == Path.home().resolve()
            or private_path.resolve() == Path(private_path.anchor)
            or private_path.resolve().is_relative_to(repo.resolve())
            or repo.resolve().is_relative_to(private_path.resolve())):
        raise HarnessError('PRIVATE_ROOT_OVERLAPS_CHECKOUT', 'BLOCKED')
    ignored_env(repo)
    path = repo / '.env'
    previous = path.read_text(encoding='utf-8-sig').splitlines() if path.exists() else []
    retained = [line for line in previous if line.partition('=')[0].strip() not in KEYS]
    body = '\n'.join([*retained, *(f'{k}={json.dumps(values[k], ensure_ascii=False)}' for k in KEYS)]) + '\n'
    temporary = repo / '.env.pending'
    if temporary.is_symlink():
        raise HarnessError('UNSAFE_LOCAL_ENV', 'BLOCKED')
    with temporary.open('x', encoding='utf-8') as stream:
        stream.write(body)
    temporary.replace(path)
    return result('PASS', 'init', configured=True, reference_roots=len(configured.references),
                  config_file='.env', private_values='NOT_EMITTED', runtime='NOT_TESTED')
