import sys
import ctypes
from PySide6.QtWidgets import QApplication

# Importa a nossa MainWindow, o coração da aplicação
from app.ui.main_window import MainWindow

def main():
    # Tenta definir o DPI awareness para melhor resolução em telas HiDPI
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except AttributeError:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except AttributeError:
            print("AVISO: Não foi possível definir o DPI awareness.")

    app = QApplication(sys.argv)

    # Carrega a folha de estilos do arquivo externo que criamos
    try:
        with open("app/assets/styles.qss", "r") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print("AVISO: Arquivo de estilos 'styles.qss' não encontrado.")

    # Cria e exibe a janela principal
    win = MainWindow()
    win.show()
    
    # Inicia o loop de eventos da aplicação
    sys.exit(app.exec())

if __name__ == "__main__":
    main()