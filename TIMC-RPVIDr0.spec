# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(['TIMC-RPVIDr0.py'],
             pathex=['C:\\Users\\isi\\PycharmProjects\\TIMC-RPVID2'],
             binaries=[
             (r'C:\Program Files (x86)\Galil\gclib\dll\x64\libcrypto-3.dll','gclib\dll\\x64'),
             (r'C:\Program Files (x86)\Galil\gclib\dll\x64\libssl-3.dll','gclib\dll\\x64'),
             (r'C:\Program Files (x86)\Galil\gclib\dll\x64\gclib.dll','gclib\dll\\x64'),
             (r'C:\Program Files (x86)\Galil\gclib\dll\x64\gclibo.dll','gclib\dll\\x64'),
             (r'C:\Program Files (x86)\Galil\gclib\dll\x64\libcrypto-1_1-x64.dll','gclib\dll\\x64'),
             (r'C:\Program Files (x86)\Galil\gclib\dll\x64\libssl-1_1-x64.dll','gclib\dll\\x64'),],
             datas=[
             ('gamepad.png','.'),
             ('xbox_gamepad.jpg','.'),
             ('MainGUIr0.ui','.'),
             ('serial_communication.dmc','.'),
             ('minus.ico','.'),
             ('plus.ico','.'),
             ('cw.ico','.'),
             ('ccw.ico','.'),
             ('down-arrow.ico','.'),
             ('down-left-arrow.ico','.'),
             ('down-right-arrow.ico','.'),
             ('left-arrow.ico','.'),
             ('right-arrow.ico','.'),
             ('up-arrow.ico','.'),
             ('up-left-arrow.ico','.'),
             ('up-right-arrow.ico','.'),
             ],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='TIMC-RPVIDr0',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True,
          icon='C:\\Users\\isi\\PycharmProjects\\TIMC-RPVID2\\icon.ico'
          )
