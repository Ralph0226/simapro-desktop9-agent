"""Guarded SimaPro 9 GUI assist on Windows; no claim of calculation from clicks."""
import hashlib
import json
import os
import re
from datetime import datetime,timezone
from pathlib import Path
from .core import safe_path


def _is_simapro_window(window):
    if window.class_name()=='TApplication':return False
    import win32api
    import win32process
    try:
        handle=win32api.OpenProcess(0x0410,False,window.process_id())
        try:
            executable=win32process.GetModuleFileNameEx(handle,0)
        finally:
            handle.Close()
    except Exception:
        return False
    return Path(executable).name.casefold()=='simapro.exe'


def _app():
    if os.name!='nt':raise RuntimeError('GUI assistance requires local Windows desktop session')
    try:
        from pywinauto import Desktop
    except ImportError as exc:
        raise RuntimeError('Install requirements-windows-gui.txt in the LOCAL Windows venv') from exc
    desk=Desktop(backend='win32')
    wins=[w for w in desk.windows() if 'simapro' in w.window_text().lower() and w.is_visible() and _is_simapro_window(w)]
    if len(wins)!=1:
        raise RuntimeError(f'Expected exactly one visible SimaPro main window; found {len(wins)}')
    return wins[0]


def inspect_gui(max_controls: int=100):
    if not 1<=max_controls<=500:raise ValueError('max_controls out of bounds')
    app=_app()
    res=[]
    for c in app.descendants()[:max_controls]:
        try:
            res.append({'text':c.window_text()[:160],'class':c.class_name(),
                        'control_id':c.control_id(),'enabled':c.is_enabled()})
        except Exception:pass
    return {'ok':True,'window':app.window_text(),'process_id':app.process_id(),'controls':res,'read_only':True}


def gui_step(action: str, control_text: str='', key_sequence: str='', expected_window: str='',
             approval_token: str=''):
    if os.environ.get('SIMAPRO_GUI_ENABLED','0')!='1':
        raise RuntimeError('GUI actions disabled: set SIMAPRO_GUI_ENABLED=1 explicitly in local MCP env')
    if approval_token!='I_APPROVE_GUI_STEP':
        raise ValueError('Explicit approval_token required for each action; screenshot and review first')
    if action not in ('click_control','type_keys','screenshot'):
        raise ValueError('Allowed actions: click_control,type_keys,screenshot')
    app=_app()
    if action!='screenshot' and not expected_window:
        raise ValueError('Exact expected_window title is required for GUI input')
    if expected_window and expected_window!=app.window_text():
        raise RuntimeError('Expected window title mismatch; abort')
    if action=='type_keys' and (not key_sequence or len(key_sequence)>200):
        raise ValueError('Shortcut/typed text is missing or too long')
    if action=='click_control' and not control_text:
        raise ValueError('Select an exact visible control title before clicking')
    p=safe_path('outputs/gui_audit',True)
    p.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    before=p / f'{stamp}_before.png'
    after=p / f'{stamp}_after.png'
    app.capture_as_image().save(before)
    try:
        if action=='click_control':
            targets=[c for c in app.descendants() if c.window_text()==control_text and c.is_visible() and c.is_enabled()]
            if len(targets)!=1:raise RuntimeError(f'Exactly one matching visible enabled control required; got {len(targets)}')
            targets[0].click_input()
        elif action=='type_keys':
            # Restricted typed-key execution; operator controls the foreground window.
            app.set_focus()
            app.type_keys(key_sequence,with_spaces=True,set_foreground=True)
        after_app=_app()
        after_app.capture_as_image().save(after)
    except Exception:
        raise RuntimeError(f'GUI step stopped. Inspect pre-action screenshot: {before}')
    event={'time':stamp,'action':action,'control_text':control_text,'key_sequence_sha256':hashlib.sha256(key_sequence.encode()).hexdigest(),
           'before':str(before),'after':str(after),'claim':'UI input performed; model or calculation NOT verified'}
    (p / f'{stamp}_audit.json').write_text(json.dumps(event,indent=2),encoding='utf-8')
    return {'ok':True,**event}


def capture_results_clipboard(output_tsv: str):
    """Read a text table the user has already copied from SimaPro result window.

    The OS cannot attest clipboard origin. Therefore output is NEVER auto-labelled as LCIA.
    """
    _app()  # confirm a SimaPro GUI exists; does not establish clipboard provenance
    try:
        import win32clipboard as clip
        import win32con
    except ImportError as exc:
        raise RuntimeError('Install pywin32 for clipboard capture on Windows') from exc
    clip.OpenClipboard()
    try:
        if not clip.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            raise RuntimeError('Windows clipboard does not contain plain Unicode text')
        raw=clip.GetClipboardData(win32con.CF_UNICODETEXT)
    finally:
        clip.CloseClipboard()
    if not raw.strip() or len(raw.splitlines())<2:
        raise ValueError('Clipboard does not look like a nonempty table: copy SimaPro results first')
    if len(raw)>2_000_000:raise ValueError('Clipboard text too large (max 2 million characters)')
    path=safe_path(output_tsv,True)
    if path.exists():raise FileExistsError(f'File exists: {path}')
    path.write_text(raw,encoding='utf-8-sig')
    return {'ok':True,'file':str(path),'rows':len(raw.splitlines()),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'origin':'USER_COPIED_CLIPBOARD_ORIGIN_NOT_ATTESTED',
            'next':'Inspect columns and normalize_exported_lcia with delimiter="\t" and actual field names.'}
