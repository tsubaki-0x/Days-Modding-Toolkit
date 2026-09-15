> Atualização v0.11.1: a tela inicial agora usa GARbro externo e repack por pasta.
> Consulte [GARBRO_REPACK.md](GARBRO_REPACK.md) para o novo fluxo, testes e arquivos.
> O guia abaixo descreve a interface anterior, acessível pelo botão Interface anterior / .sdmod.

# v0.11 — 14 de setembro de 2026

Interface desktop Windows separada do núcleo, navegação pelos índices GPK,
extração/repack parciais e operações `.sdmod` com prévia verificável.
Versões técnicas: `0.11.0-dev` / `0.11.0.dev0`.

Os fluxos já validados no jogo na v0.10 permanecem como referência: 29 GPKs,
69.936 entradas, edição dos formatos suportados, pacotes com múltiplos GPKs e
restauração do workspace. Não foram repetidos testes no jogo nem alterados
os arquivos proprietários ou os workspaces existentes durante esta implementação.

## Arquivos novos — 15

- `ATUALIZACAO_v0.10_PARA_v0.11.txt`
- `run_gui.bat`
- `docs/DESKTOP.md`
- `docs/PARTIAL_WORKSPACES.md`
- `docs/RELEASE_v0.11.md`
- `src/sdhq_toolkit/core/desktop.py`
- `src/sdhq_toolkit/core/operations.py`
- `src/sdhq_toolkit/core/partial.py`
- `src/sdhq_toolkit/gui/__init__.py`
- `src/sdhq_toolkit/gui/__main__.py`
- `src/sdhq_toolkit/gui/app.py`
- `src/sdhq_toolkit/gui/controller.py`
- `tests/test_gui_controller.py`
- `tests/test_gui_actions.py`
- `tests/test_partial.py`

## Arquivos alterados — 13

- `README.md`
- `pyproject.toml`
- `src/sdhq_toolkit/__init__.py`
- `src/sdhq_toolkit/cli.py`
- `src/sdhq_toolkit/core/asset_validation.py`
- `src/sdhq_toolkit/core/batch.py`
- `src/sdhq_toolkit/core/extractor.py`
- `src/sdhq_toolkit/core/mods.py`
- `src/sdhq_toolkit/core/repacker.py`
- `src/sdhq_toolkit/formats/gpk/reader.py`
- `src/sdhq_toolkit/formats/gpk/writer.py`
- `src/sdhq_toolkit/utils/hashing.py`
- `src/sdhq_toolkit/utils/streams.py`

## Verificações executadas

| Verificação | Resultado |
| --- | --- |
| Suíte existente antes das alterações | 46 testes, todos passaram |
| Suíte padrão: `python -m unittest discover -s tests -q` | 82 passaram; 14 testes gráficos opcionais ignorados; 1,748 s |
| Novos testes de operações parciais | 14 testes, todos passaram |
| Novos testes de serviços/controladores desktop | 22 testes, todos passaram |
| Testes dos botões Tk com `SDHQ_GUI_TESTS=1` | 14 testes, todos passaram; 4,036 s |
| `python -m compileall -q src tests` | Sem erros |
| Importação de `sdhq_toolkit.gui.app` | Sucesso; Tk 9.0 disponível |
| CLI `--help` e `unpack --help` | Sucesso; `--member` disponível |

Os testes novos usam GPKs e arquivos sintéticos. Cobrem preservação das entradas
não extraídas, conteúdo comprimido e sem compressão, extração incremental,
metadata legado, rejeição de referência incorreta, arquivos ausentes/novos,
restauração individual, cancelamento/retomada, filtros e seleção, estados,
especificações, proteção de Packs, prévia de pacote e alterações posteriores à
validação. Cobrem também aplicação com extração automática dos alvos, rollback
na aplicação cancelada e retomada de remoção cancelada.

Além dos testes sem interface, os botões foram exercitados automaticamente em
uma janela Tkinter oculta, usando GPKs sintéticos e interceptando abertura de
aplicativos externos. Foram verificados detecção, extração, seleção, filtros,
paginação, marcas, validação, especificações, restauração, repack, abertura de
arquivos/pastas, cancelamento e recuperação após erro de callback. Os 96 testes
executados nas duas modalidades passaram. Não houve avaliação visual manual.
A validação de
ORS é estrutural, não semântica; a codificação sem BOM é inferida. Consulte as
limitações e os pontos de cancelamento em [DESKTOP.md](DESKTOP.md).

## Distribuição incremental

Correção da abertura: Detectar GPKs agora lê índices e metadata sem validar todo
o conteúdo do workspace antes de exibir a lista. O progresso também aparece na
aba Localizações e o botão fica desabilitado durante operações. Arquivos já
extraídos recebem estado **não verificado** até a validação explícita.
Foi conferida a detecção nas localizações salvas: 29 GPKs e 69.936 entradas em
74,17 segundos, sem extração, repack ou alterações nos dados do jogo.

Correção da página de arquivos: a extração/restauração termina com um resumo
de arquivos novos, já extraídos e restaurados, sem iniciar uma validação global.
Validação e repack restringem a leitura aos GPKs da seleção. Os botões indicam
quando falta uma seleção e ficam desabilitados durante tarefas. O andamento
aparece na página, e seleção/paginação são preservadas. Exceções de callbacks
são exibidas sem interromper permanentemente o processamento dos eventos.

Correção de referências e navegação: o índice em memória é invalidado quando
o GPK em disco muda, evitando erros falsos após troca e nova extração. Uma
incompatibilidade real continua bloqueada, com mensagem contendo caminho e
tamanhos. Foi confirmada a compatibilidade do índice atual de System.gpk com
seu metadata (327.083.389 bytes, 252 entradas), somente por leitura.
As pastas da árvore agora exibem seus arquivos ao expandir; seleção múltipla
de arquivos na árvore funciona mesmo com paginação na lista. Há indicação de
filtros sem resultados e botão para recuperar a largura do painel de arquivos.
Os testes cobrem cache após troca, incompatibilidade real, troca com mesmo
tamanho, expansão, seleção e layout da lista no tamanho mínimo da janela.

Correção da aprovação de assets: terminar a varredura não é mais reportado como
PASS quando há bloqueios. Validação e repack usam o mesmo resumo e as mesmas
regras, com resultados APROVADO, COM AVISOS ou BLOQUEADO. Foi acrescentado um
modo Experimental explícito, que conserva os bytes modificados no GPK e registra
incompatibilidades de formato como avisos. As restrições da estrutura GPK
continuam ativas. A autorização de formatos desconhecidos também aparece na
página de arquivos. Saídas existentes são preservadas e novos repacks usam
uma subpasta datada quando necessário.

Os testes adicionais verificam PNG/texto válidos com tamanhos diferentes,
repack experimental preservando exatamente CMAP/PNG inválidos e dados de formato
desconhecido, bloqueio de entradas ausentes/novas mesmo no modo Experimental,
status de validação sem falso PASS e geração repetida sem sobrescrever a saída.

Artefato: `dist/SchoolDaysHQ-Modding-Toolkit-v0.10-to-v0.11-incremental.zip`.

O ZIP é montado comparando SHA-256 dos arquivos com um inventário capturado
antes das edições. Contém exatamente os 28 arquivos novos/alterados acima,
com caminhos relativos à raiz do toolkit. Não contém GPKs, workspace,
backups, relatórios gerados, outputs, caches Python ou arquivos proprietários.
O ZIP é aberto novamente para verificar integridade e igualdade de conteúdo
com os arquivos da pasta.

Para instalar, extraia na raiz da v0.10 substituindo os arquivos correspondentes
e execute `run_gui.bat`. Não é necessário recriar os workspaces já extraídos.
