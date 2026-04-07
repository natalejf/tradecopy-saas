"""
TradeCopy Local — Launcher
"""
import os
import sys
import time
import threading
import webbrowser

PORT = 8000
URL = f"http://localhost:{PORT}"


def get_base_dir():
    """Obtener directorio base correcto dentro o fuera del .exe"""
    if getattr(sys, 'frozen', False):
        # Dentro del .exe — PyInstaller extrae todo a _MEIPASS
        return sys._MEIPASS
    else:
        # En desarrollo — directorio del script
        return os.path.dirname(os.path.abspath(__file__))


def open_browser():
    time.sleep(3)
    webbrowser.open(URL)


def run_server():
    base_dir = get_base_dir()

    # Cambiar al directorio base Y agregarlo al Python path
    os.chdir(base_dir)
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    print(f"📁 Directorio base: {base_dir}")
    print(f"📄 Archivos: {os.listdir(base_dir)}")

    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        log_level="info"
    )


if __name__ == "__main__":
    print("=" * 50)
    print("   TradeCopy Local v2.0")
    print("   Copiador de trades MT5")
    print("=" * 50)
    print(f"\n🚀 Iniciando servidor en {URL}...")

    threading.Thread(target=open_browser, daemon=True).start()
    run_server()