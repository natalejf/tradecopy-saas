# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('frontend', 'frontend'), ('core', 'core'), ('routers', 'routers'), ('services', 'services'), ('main.py', '.')],
    hiddenimports=['uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan', 'uvicorn.lifespan.on', 'fastapi', 'fastapi.middleware', 'fastapi.middleware.cors', 'fastapi.staticfiles', 'fastapi.responses', 'fastapi.routing', 'fastapi.security', 'fastapi.security.http', 'pydantic', 'pydantic.deprecated', 'pydantic.v1', 'jwt', 'multipart', 'python_multipart', 'websockets', 'anyio', 'anyio.streams.memory', 'anyio._backends', 'anyio._backends._asyncio', 'starlette', 'starlette.routing', 'starlette.middleware', 'starlette.middleware.cors', 'starlette.staticfiles', 'starlette.responses', 'starlette.websockets', 'starlette.applications', 'starlette.requests', 'click', 'h11', 'httptools', 'watchfiles', 'core.database', 'core.auth', 'core.websocket_manager', 'routers.accounts', 'routers.trades', 'routers.subscriptions', 'routers.webhooks', 'routers.admin', 'services.trade_sync'],
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
    name='TradeCopy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
