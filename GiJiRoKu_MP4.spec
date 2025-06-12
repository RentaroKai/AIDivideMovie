# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        ('resources/ffmpeg/ffmpeg.exe', 'resources/ffmpeg'),  # FFmpegを正しいディレクトリに配置
        ('resources/ffmpeg/ffprobe.exe', 'resources/ffmpeg'),  # ffprobe を追加
    ],
    datas=[
        ('src/ui', 'src/ui'),
        ('src/utils', 'src/utils'),
        ('src/prompts', 'src/prompts'),
        ('config', 'config'),
        ('icon.ico', '.'),
    ],
    hiddenimports=[
        'pydub',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[ 'hooks/ffmpeg_hook.py' ],
    excludes=[
        'numpy',
        'pandas',
        'pyarrow',
        'matplotlib',
        'scipy',
        'PIL',
        'pygame',
        'google.cloud',          # 使っていなければ
        'google.protobuf.pyext', # C 拡張
        'rich', 'pygments',      # カラフル出力; GUI なら不要
        'pytest', 'unittest',    # テスト専用
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='GiJiRoKu_MP4',
    debug=False,  # デバッグモードを有効化
    bootloader_ignore_signals=False,
    strip=False,  # デバッグ情報を保持
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # コンソールウィンドウを表示
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico'
)
