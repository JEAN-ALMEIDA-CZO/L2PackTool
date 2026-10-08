# -*- mode: python ; coding: utf-8 -*-
# A copia que o INSTALADOR instala: o mesmo programa do -Completo, mas em
# pasta (o .exe e o _internal\ ao lado), e nao num arquivo unico.
#
# O arquivo unico se descompacta inteiro -- 300 MB -- na pasta temporaria a
# cada vez que abre, e o antivirus varre tudo de novo: eram uns oito segundos
# so com a imagem da abertura na tela. Em pasta nao ha o que descompactar.
# Quem baixa o .exe solto continua tendo o arquivo unico.
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['motor', 'l2npc', 'gui_npc', 'idioma', 'ajuda', 'gui_arquivos', 'l2anim', 'l2mapa', 'l2seq', 'l2criar', 'gui_video', 'l2conferir', 'gui_conferir', 'l2item', 'gui_item', 'rolagem', 'manual', 'l2skill', 'gui_skill', 'l2icone', 'gui_icone', 'l2servidor', 'l2mundo', 'gui_mundo', 'gui_arma', 'l2glow', 'gui_glow', 'l2env', 'l2multisell', 'gui_multisell', 'l2mob', 'gui_mob', 'tema', 'projeto', 'gui_projeto', 'versao', 'l2conjunto', 'l2mensagem', 'gui_texto', 'l2atualizar', 'gui_atualizar', 'l2win10', 'abertura']
hiddenimports += collect_submodules('PIL')


a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[('motor.py', '.'), ('l2npc.py', '.'), ('l2chaves.py', '.'), ('l2texto.py', '.'), ('l2cronica.py', '.'), ('l2compat.py', '.'), ('l2ia.py', '.'), ('l2anima.py', '.'), ('l2cripto.py', '.'), ('l2protecao.py', '.'), ('gui_protecao.py', '.'), ('gui_ia.py', '.'), ('gui_npc.py', '.'), ('gui_arquivos.py', '.'), ('gui_video.py', '.'), ('l2anim.py', '.'), ('l2mapa.py', '.'), ('l2seq.py', '.'), ('l2criar.py', '.'), ('l2conferir.py', '.'), ('gui_conferir.py', '.'), ('l2item.py', '.'), ('gui_item.py', '.'), ('rolagem.py', '.'), ('manual.py', '.'), ('l2skill.py', '.'), ('gui_skill.py', '.'), ('l2icone.py', '.'), ('gui_icone.py', '.'), ('l2servidor.py', '.'), ('l2mundo.py', '.'), ('gui_mundo.py', '.'), ('gui_arma.py', '.'), ('l2glow.py', '.'), ('gui_glow.py', '.'), ('l2env.py', '.'), ('l2multisell.py', '.'), ('gui_multisell.py', '.'), ('l2mob.py', '.'), ('gui_mob.py', '.'), ('tema.py', '.'), ('projeto.py', '.'), ('gui_projeto.py', '.'), ('versao.py', '.'), ('idioma.py', '.'), ('ajuda.py', '.'), ('l2conjunto.py', '.'), ('l2mensagem.py', '.'), ('gui_texto.py', '.'), ('recursos', 'recursos'), ('idiomas', 'idiomas'), ('ferramentas', 'ferramentas')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# A imagem de abertura que o executavel mostra enquanto se descompacta, antes
# de o Python existir. Desenhada por arte_da_abertura.py a cada compilacao.
# Sem `text_pos`: com ele o PyInstaller escreve na imagem o nome de cada
# arquivo que vai extraindo -- ruido para quem so quer o programa aberto. O
# "Carregando o sistema..." ja vem desenhado na propria imagem.
splash = Splash(
    'recursos/abertura.png',
    binaries=a.binaries,
    datas=a.datas,
    minify_script=True,
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    splash,
    [],
    exclude_binaries=True,
    name='L2PackTool-Completo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='recursos/versao/L2PackTool-Completo.txt',
    icon=['recursos/icone.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    splash.binaries,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='L2PackTool-instalado',
)
