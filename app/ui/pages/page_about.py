"""
Módulo para a PageAbout, uma página simples com informações
sobre a aplicação, instruções e créditos.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit

class PageAbout(QWidget):
    def __init__(self):
        super().__init__()
        self.build_ui()

    def build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("Sobre / Instruções")
        title.setObjectName("pageTitle")
        root.addWidget(title)
        
        txt = QTextEdit()
        txt.setReadOnly(True)
        
        about_text = """
        <h2 style="color:#9f7aea;">Sobre o Aplicativo</h2>
        <p>Este aplicativo é uma poderosa ferramenta de automação para tarefas repetitivas. Com ele, você pode criar e gerenciar <b>macros de teclado e mouse</b>, além de utilizar um <b>autoclicker</b> para agilizar ações em jogos, testes de software ou qualquer atividade que exija cliques ou pressionamentos de tecla repetitivos.</p>
        <hr style="border: 1px solid #3c3c52;">
        <h3 style="color:#9f7aea;">Instruções de Uso</h3>
        <ul>
            <li><b>Macros:</b> Clique em "Gravar Macro", realize as ações e pare a gravação.</li>
            <li><b>Autoclicker:</b> Configure delay e repetições, use os botões ou hotkeys.</li>
            <li><b>Perfis:</b> Salve/carregue perfis para usos distintos.</li>
        </ul>
        <hr style="border: 1px solid #3c3c52;">
        <p style="text-align: center; color: #7a7a7a;">
            Versão 3.0 (Refatorada)<br>
            Desenvolvido por Gabriel Alves da Silva Diógenes<br>
            Copyright © 2025
        </p>
        """
        txt.setHtml(about_text)
        
        root.addWidget(txt)
        root.addStretch()