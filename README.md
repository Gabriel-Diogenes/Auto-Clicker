# Auto Clicker + Macro Recorder

Um **auto clicker e gravador de macros** em Python com interface moderna usando **CustomTkinter** e captura de teclado com **pynput**. Ideal para automatizar tarefas repetitivas.

## Funcionalidades
- Gravação e execução de macros do teclado (pressão e liberação de teclas).  
- Número de repetições definido ou **modo infinito**.  
- Controle de **velocidade de execução**.  
- Salvamento e carregamento de macros em JSON.  
- Atalhos: `F6` → Iniciar, `F7` → Parar.

## Como usar
1. Clique **Gravar Macro** para iniciar a gravação.  
2. Pressione **Parar Gravação** ao finalizar.  
3. Ajuste **velocidade** e **repetições**.  
4. Clique **Executar Macro** para rodar.  
5. Use **Parar Macro** para interromper.  
6. Salve e carregue macros com **Salvar Macro** e **Carregar Macro**.

## Requisitos
- Python 3.8+  
- Bibliotecas:
```bash
pip install customtkinter pynput
