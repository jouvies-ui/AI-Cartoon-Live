"""Versioned character identity, portable templates and private per-instance memory."""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from . import config, personas

ID_PATTERN = r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$'


class CharacterProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(default='小雅', min_length=1, max_length=24)
    personality: str = Field(default='温柔、机灵、有一点俏皮的伙伴。对熟悉的人亲切，会认真记住对方说过的事；遇到难过的事情先共情，不强行卖萌。', min_length=1, max_length=1600)
    speaking_style: str = Field(default='像熟悉的朋友一样，用自然、简短的中文口语回应对方刚说的具体事情。少说“努力不会白费”“我懂你的感受”这类套话，不反复自我介绍、不每句撒娇。需要了解对方时可以追问一句，不每轮强行提问。表情和动作说明不要念出来。', min_length=1, max_length=600)
    voice_template: str = Field(default='', max_length=64, pattern=r'^$|'+ID_PATTERN)
    expression_strength: float = Field(default=0.8, ge=0.2, le=1.0, allow_inf_nan=False)
    auto_gestures: StrictBool = True
    remember: StrictBool = True
    memory_turns: int = Field(default=12, ge=1, le=20, strict=True)


class CharacterTemplate(BaseModel):
    """Deliberately excludes conversations, credentials and machine addresses."""
    model_config = ConfigDict(extra='forbid')
    format: Literal['local-character/v1'] = 'local-character/v1'
    character_id: str = Field(pattern=ID_PATTERN)
    avatar: Literal['whale_girl_v1'] = 'whale_girl_v1'
    profile: CharacterProfile
    voice_reference_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')


def character_id() -> str:
    value = (config.load().get('local_avatar') or {}).get('character_id', 'default')
    if not isinstance(value, str) or not re.fullmatch(ID_PATTERN, value):
        raise ValueError('Invalid character_id')
    return value


def avatar_id() -> str:
    value = (config.load().get('local_avatar') or {}).get('avatar', 'whale_girl_v1')
    if value not in ('whale_girl_v1',):
        raise ValueError('Unknown local avatar')
    return value


def state_dir() -> Path:
    # Renaming never changes the storage key; separate instances never share memory.
    return config.CONF_PATH.parent / 'state' / 'characters' / character_id()


def _write(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_suffix('.tmp')
    with open(temp, 'w', opener=lambda p, flags: os.open(p, flags, 0o600)) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temp, 0o600)
    temp.replace(path)


def _default_profile() -> CharacterProfile:
    conf = config.load()
    values = dict((conf.get('local_avatar') or {}).get('character') or {})
    selected = personas.get((conf.get('llm') or {}).get('persona', ''))
    if selected:
        values.setdefault('name', selected.get('name', '小雅')[:24])
        values.setdefault('personality', selected.get('system_prompt', '')[:1600])
    values.setdefault('voice_template', (conf.get('tts') or {}).get('voice', ''))
    return CharacterProfile.model_validate(values)


def _document():
    path = state_dir() / 'character.json'
    if path.exists():
        data = json.loads(path.read_text())
        if data.get('version') != 2 or data.get('character_id') != character_id():
            raise ValueError('Unknown character profile format')
        return data
    # One-time migration of the previous renderer-specific identity. Leave the
    # original files untouched as a recovery copy; custom instances start fresh.
    value = _default_profile()
    legacy = config.CONF_PATH.parent / 'state' / 'whale_girl_v1'
    if character_id() == 'default':
        if (legacy / 'character.json').exists():
            old = json.loads((legacy / 'character.json').read_text())
            old.setdefault('voice_template', value.voice_template)
            value = CharacterProfile.model_validate(old)
        memory_path = state_dir() / 'memory.json'
        if (legacy / 'memory.json').exists() and not memory_path.exists():
            old_memory = json.loads((legacy / 'memory.json').read_text())
            if old_memory.get('version') != 1 or old_memory.get('avatar') != 'whale_girl_v1':
                raise ValueError('Unknown legacy memory format')
            messages = _validate_messages(old_memory.get('messages', []))
            _write(memory_path, {'version': 2, 'character_id': character_id(),
                                'identity_revision': 1, 'messages': messages if value.remember else []})
    data = {'version': 2, 'character_id': character_id(), 'revision': 1,
            'previous_names': [], 'profile': value.model_dump()}
    _write(path, data)
    return data


def profile() -> CharacterProfile:
    return CharacterProfile.model_validate(_document()['profile'])


def identity_context(value: CharacterProfile) -> str:
    doc = _document()
    return ('这是当前已经保存的人设，优先于旧对话和personality中的旧名字。'
            'name是你现在的名字，不是用户的名字；旧回复中的自我介绍、声线、性格不代表现在。'
            '用户的称呼、偏好、经历和关系仍然有效；不要删除或混淆。临时扮演不写入默认设置。\n'
            + json.dumps({'revision': doc['revision'], 'current_profile': value.model_dump(),
                          'previous_character_names': doc['previous_names']}, ensure_ascii=False))


def save_profile(value: CharacterProfile):
    doc = _document()
    old = CharacterProfile.model_validate(doc['profile'])
    if old == value:
        return
    if old.name != value.name:
        doc['previous_names'] = [*doc['previous_names'], old.name][-20:]
    doc.update(revision=doc['revision'] + 1, profile=value.model_dump())
    _write(state_dir() / 'character.json', doc)


def revision() -> int:
    return _document()['revision']


def _validate_messages(history):
    if not isinstance(history, list) or len(history) % 2:
        raise ValueError('Invalid conversation memory')
    for i, item in enumerate(history):
        if (not isinstance(item, dict) or item.get('role') != ('user' if i % 2 == 0 else 'assistant')
                or not isinstance(item.get('content'), str) or len(item['content']) > 2000):
            raise ValueError('Invalid conversation memory entry')
    return [{'role': x['role'], 'content': x['content']} for x in history]


def load_memory(value: CharacterProfile) -> list[dict]:
    if not value.remember:
        return []
    _document()
    path = state_dir() / 'memory.json'
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    if data.get('version') != 2 or data.get('character_id') != character_id():
        raise ValueError('Unknown character memory format')
    return _validate_messages(data.get('messages', []))[-value.memory_turns * 2:]


def save_memory(history, value: CharacterProfile):
    messages = _validate_messages(list(history)[-value.memory_turns * 2:]) if value.remember else []
    _write(state_dir() / 'memory.json', {'version': 2, 'character_id': character_id(),
                                      'identity_revision': revision(), 'messages': messages})


def clear_memory():
    save_memory([], profile())


def voice_catalog(voices: dict) -> list[dict]:
    # Only stable reference voices are character templates. Parameter-designed
    # random voices are not a reproducible character identity.
    out = []
    for key, preset in voices.items():
        if not re.fullmatch(ID_PATTERN, key):
            continue
        if preset.get('engine') == 'hojo':
            from .tts.hojo import scan_voices
            installed = scan_voices(config.load().get('tts') or {}).get(key)
            if installed and preset.get('reference_sha256') == installed['reference_sha256']:
                out.append({'id': key, 'label': preset.get('label', key),
                            **{field: installed[field] for field in ('language', 'gender', 'category', 'preview_text')},
                            'reference_sha256': installed['reference_sha256']})
            continue
        if preset.get('kind') != 'clone':
            continue
        path = Path(preset.get('ref_audio', ''))
        if not path.is_file():
            continue
        out.append({'id': key, 'label': preset.get('label', key),
                    'reference_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return out


def validate_voice(value: CharacterProfile, catalog: list[dict]):
    if value.voice_template not in {v['id'] for v in catalog}:
        raise ValueError('声线模板在当前语音引擎中未安装，请从已安装固定声线中选择。')


def export_template(value: CharacterProfile, catalog: list[dict]) -> CharacterTemplate:
    validate_voice(value, catalog)
    voice = next(v for v in catalog if v['id'] == value.voice_template)
    return CharacterTemplate(character_id=character_id(), avatar=avatar_id(), profile=value,
                             voice_reference_sha256=voice['reference_sha256'])


def validate_template(value: CharacterTemplate, catalog: list[dict]):
    validate_voice(value.profile, catalog)
    voice = next(v for v in catalog if v['id'] == value.profile.voice_template)
    if voice['reference_sha256'] != value.voice_reference_sha256:
        raise ValueError('本机同名声线的音频或模型版本与角色模板不同，请先安装匹配的声线素材。')
