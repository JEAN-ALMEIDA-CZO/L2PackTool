# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['motor', 'l2npc', 'gui_npc', 'idioma', 'ajuda', 'gui_arquivos', 'l2anim', 'l2mapa', 'l2seq', 'l2criar', 'gui_video', 'l2conferir', 'gui_conferir', 'l2item', 'gui_item', 'rolagem', 'manual', 'l2skill', 'gui_skill', 'l2icone', 'gui_icone', 'l2servidor', 'l2mundo', 'gui_mundo', 'gui_arma', 'l2glow', 'gui_glow', 'l2env', 'l2multisell', 'gui_multisell', 'l2mob', 'gui_mob', 'tema', 'projeto', 'gui_projeto', 'versao']
hiddenimports += collect_submodules('PIL')


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[('motor.py', '.'), ('l2npc.py', '.'), ('l2chaves.py', '.'), ('l2texto.py', '.'), ('l2cronica.py', '.'), ('l2compat.py', '.'), ('l2ia.py', '.'), ('l2anima.py', '.'), ('l2cripto.py', '.'), ('l2protecao.py', '.'), ('gui_protecao.py', '.'), ('gui_ia.py', '.'), ('gui_npc.py', '.'), ('gui_arquivos.py', '.'), ('gui_video.py', '.'), ('l2anim.py', '.'), ('l2mapa.py', '.'), ('l2seq.py', '.'), ('l2criar.py', '.'), ('l2conferir.py', '.'), ('gui_conferir.py', '.'), ('l2item.py', '.'), ('gui_item.py', '.'), ('rolagem.py', '.'), ('manual.py', '.'), ('l2skill.py', '.'), ('gui_skill.py', '.'), ('l2icone.py', '.'), ('gui_icone.py', '.'), ('l2servidor.py', '.'), ('l2mundo.py', '.'), ('gui_mundo.py', '.'), ('gui_arma.py', '.'), ('l2glow.py', '.'), ('gui_glow.py', '.'), ('l2env.py', '.'), ('l2multisell.py', '.'), ('gui_multisell.py', '.'), ('l2mob.py', '.'), ('gui_mob.py', '.'), ('tema.py', '.'), ('projeto.py', '.'), ('gui_projeto.py', '.'), ('versao.py', '.'), ('idioma.py', '.'), ('ajuda.py', '.'), ('recursos', 'recursos'), ('idiomas', 'idiomas'), ('ferramentas', 'ferramentas')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='L2PackTool-Completo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='recursos/versao/L2PackTool-Completo.txt',
    icon=['recursos/icone.ico'],
)
