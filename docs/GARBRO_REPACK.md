# GARbro + ModToolkit — v0.11.1-dev

O GARbro é um aplicativo separado. Ele explora, visualiza e extrai os arquivos.
O novo fluxo principal do ModToolkit reconstrói um GPK usando uma pasta externa.
Não exige metadata de extração nem cadastro de workspace.

## Preparação e uso

1. Extraia a distribuição completa do GARbro onde preferir. Não copie apenas o EXE.
2. Abra `run_gui.bat` e use **Selecionar…** no campo **GARbro.exe (opcional)**.
   A configuração é manual, salva em `.sdhq-repack.json`; não há detecção automática.
3. Clique em **Abrir GARbro**. No aplicativo separado, abra seu GPK e extraia
   tudo ou apenas os arquivos desejados. Preserve caminhos e formatos, sem conversão.
4. Edite os arquivos nos programas de sua preferência.
5. Selecione a instalação do jogo (para obter CIPHERCODE), o **GPK de referência**,
   a **pasta com as alterações**, a **saída** e os **relatórios**.
6. Clique em **Conferir alterações** para ver substituições, arquivos iguais e avisos.
7. Clique em **Gerar GPK**. A comparação é refeita para incluir as edições mais recentes.
   O resultado informa o destino e se houve avisos. Teste o GPK no jogo por sua conta.

Exemplo: para a entrada `INI/ONE.INI`, se o arquivo editado está em
`D:\Mods\System\INI\ONE.INI`, selecione `D:\Mods\System` como pasta de alterações.
Não selecione a subpasta INI nem uma pasta que englobe vários GPKs.

Crie uma pasta exclusiva para cada GPK antes de extrair. O GARbro pode extrair
diretamente no destino escolhido, sem criar uma pasta com o nome do GPK.
Usar nomes como `INI` e `System` é recomendado para organização, não obrigatório.
Se o índice contém `ONE.INI` diretamente na raiz, o arquivo deve ficar em
`D:\Mods\INI\ONE.INI` e a pasta selecionada deve ser `D:\Mods\INI`.
Se o índice contém subpastas, mantenha essas subpastas dentro do destino escolhido.

Antes de substituir o GPK em `Packs`, feche o jogo e o GARbro: o GPK aberto no
GARbro pode estar bloqueado para substituição. Guarde uma cópia da versão anterior
e copie manualmente o resultado da saída. O toolkit não faz essa troca automaticamente.

## Regras da montagem

- O GPK escolhido pode ser original ou modificado. Seu índice é lido a cada operação.
- Arquivo presente e diferente substitui a entrada correspondente.
- Arquivo igual mantém os dados armazenados na referência.
- Arquivo ausente mantém a entrada da referência; ausência nunca significa remoção.
- Metadata `.sdhq` existente é ignorado neste fluxo e não é alterado.
- Arquivos novos fora do índice aparecem como **novo — não incluído**, com aviso.
  Não são inseridos no GPK. Adicionar, excluir ou renomear entradas exige suporte futuro.
- Diferenças de PNG, OGG, ASF/WMV, CMAP, textos e formatos desconhecidos geram avisos,
  sem autorização adicional nem bloqueio de compatibilidade. Não há reparo automático.
- Falhas de leitura/escrita, índice impossível de interpretar ou arquivos sendo
  alterados durante a montagem podem impedir a operação; a GUI informa a falha.
- A saída fica separada da pasta de alterações e da pasta do GPK de referência.
  Quando o destino já existe, é criada uma subpasta com data/hora.
- Cancelamento remove o GPK temporário. O GPK de referência e as edições não são escritos.

O serviço usa temporariamente uma entrada original por vez para comparar seu conteúdo
e suas propriedades. Não extrai todo o GPK para o workspace do modder.
O botão GARbro apenas inicia o executável; não controla seus cliques nem monitora a extração.
O repack funciona sem GARbro configurado se os arquivos já estiverem extraídos.

## Feedback e ferramentas anteriores

A tela mostra início, progresso, cancelamento, resultado e erros. A tabela apresenta
os arquivos presentes e os avisos; entradas ausentes são resumidas no total mantido.
Selecione uma linha para ler seu aviso completo no painel inferior. **Relatórios**
abre a pasta com JSON detalhado e `desktop.log`; **Abrir saída** abre o resultado.

**Interface anterior / .sdmod** abre o aplicativo anterior em um processo separado.
Seus recursos de pacotes, extração e CLI foram preservados, inclusive suas regras de
workspace e validação. A política informativa descrita aqui pertence ao novo fluxo.

## Verificação desta entrega

- Suíte normal de fechamento: 110 testes descobertos, 94 passaram, 16 de janela ignorados por opção.
- Suíte `*gui*.py` com `SDHQ_GUI_TESTS=1`, repetida no fechamento: 38 passaram, incluindo os 16 testes de janela.
- `python -m compileall -q src tests`: aprovado.
- 110 testes distintos passaram entre as duas execuções.
- Novos testes nesta reformulação: 12 de serviço/configuração sem janelas e 2 da interface com janela oculta.
  O fechamento acrescentou cobertura para arquivos na raiz, nome livre da pasta
  e cancelamento durante a escrita com remoção do temporário e preservação dos dados.
- A primeira execução conjunta expôs coleta de objetos Tk fora da thread principal
  nos testes. O encerramento dos testes foi corrigido; a repetição conjunta passou.
- GPKs sintéticos usados nos testes; não repetidos os testes já concluídos no jogo.
- Início real do GARbro não testado: o launcher foi verificado com processo simulado.

Em 14/09/2026, o usuário confirmou o fluxo com **INI.gpk**: extraiu pelo GARbro,
editou os arquivos, conferiu as substituições, gerou o repack e carregou no jogo
a alteração pretendida. Esse resultado é um relato do usuário, registrado sem
repetir o teste. Não representa certificação de qualquer edição possível.

O escopo funcional desta entrega está fechado: uma referência por operação e
substituição de entradas existentes. Inclusão, remoção e renomeação não fazem parte
desta versão. A próxima etapa prevista é a personalização visual da GUI.

## Arquivos desta reformulação

Novos: `core/folder_repack.py`, `gui/repack_app.py`, `gui/repack_controller.py`
(dentro de `src/sdhq_toolkit`), `tests/test_folder_repack.py`,
`tests/test_repack_gui.py`, `docs/GARBRO_REPACK.md`, `docs/CONTINUIDADE.md`.

Alterados: `.gitignore`, `README.md`, `pyproject.toml`,
`ATUALIZACAO_v0.10_PARA_v0.11.txt`, `docs/DESKTOP.md`, `docs/RELEASE_v0.11.md`,
`src/sdhq_toolkit/__init__.py`, `src/sdhq_toolkit/formats/gpk/writer.py`,
`src/sdhq_toolkit/gui/app.py`, `src/sdhq_toolkit/gui/__main__.py`,
`tests/test_gui_actions.py`.

No fechamento, nenhum arquivo novo: atualizados `README.md`,
`ATUALIZACAO_v0.10_PARA_v0.11.txt`, `docs/GARBRO_REPACK.md`, `docs/CONTINUIDADE.md`,
`docs/DESKTOP.md`, `docs/RELEASE_v0.11.md`, `src/sdhq_toolkit/gui/repack_app.py`
e `tests/test_folder_repack.py`. O núcleo de repack não foi alterado nesta etapa.
