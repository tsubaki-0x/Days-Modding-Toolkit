# Ajustar a arte da GUI

Edite `tema.json`, na mesma pasta de `run_gui.bat`, e reabra a interface.

- `imagem`: nome de um PNG/JPG nessa pasta, ou caminho completo. Em caminhos
  Windows use `/` ou `\\` em vez de uma única barra invertida.
- `opacidade`: 0 esconde a arte, 1 mostra totalmente. Exemplo suave: 0.4.
- `zoom`: 1 preenche o painel; 1.3 aproxima; 0.7 afasta. Limite: 0.2 a 3.
- `x`: deslocamento em pixels; positivo move à direita, negativo à esquerda.
- `y`: positivo move para baixo, negativo para cima.

Exemplo: `"x": -100, "y": 40` move a arte 100 pixels à esquerda e 40 abaixo.
O recorte é centralizado antes dos deslocamentos. A imagem original não é alterada.

A arte ocupa o painel lateral direito, suavizada sobre branco; os controles
permanecem sólidos para leitura. Em janelas com menos de 1280 pixels de largura,
o painel é ocultado para preservar os campos. Amplie a janela para vê-lo.

Requer Pillow, já disponível no ambiente usado nesta entrega. Se necessário:
`python -m pip install Pillow`. Sem a biblioteca ou a imagem, o repack continua
funcionando. Não é necessário alterar os GPKs nem extrair a arte do jogo.
