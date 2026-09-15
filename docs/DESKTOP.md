> Atualização v0.11.1: a tela inicial agora usa GARbro externo e repack por pasta.
> Consulte [GARBRO_REPACK.md](GARBRO_REPACK.md) para o novo fluxo, testes e arquivos.
> O guia abaixo descreve a interface anterior, acessível pelo botão Interface anterior / .sdmod.

# Interface desktop — v0.11

## Abrir e configurar

No Windows 10/11, execute `run_gui.bat`. O launcher configura o `PYTHONPATH` e
usa `py -3` ou `python`. Também é possível executar
`python -m sdhq_toolkit.gui` com `src` no `PYTHONPATH`, ou `sdhq-gui` após
instalar o projeto. A interface usa Tkinter/ttk, com tema nativo Vista quando
disponível, sem bibliotecas externas adicionais.

Na aba **Localizações**, escolha:

1. Instalação legítima de School Days HQ v1.02, com seus executáveis.
2. Pasta **Packs**, contendo os GPKs originais.
3. Workspace existente v0.10 ou um novo diretório de edição.
4. Diretório para logs e relatórios.
5. Diretório de saída para GPKs e pacotes criados.

Workspace, relatórios e saída devem ser separados entre si e de Packs. A
interface salva as preferências em `.sdhq-desktop.json` na raiz do toolkit.
Alterações nas localizações entram em vigor ao clicar em **Detectar GPKs e
abrir workspace**. A chave é obtida dos recursos CIPHERCODE do executável;
a GUI não grava a chave nos relatórios. A versão v1.02 é a instalação alvo,
não uma certificação automática da versão do executável.

## Explorar e selecionar

**Arquivos e GPKs** mostra a árvore de GPKs e pastas obtida dos índices. Não é
necessário extrair todos os arquivos. A lista tem páginas de 500 entradas para
evitar criar dezenas de milhares de widgets de uma só vez.

A detecção lê somente índices e metadata, sem calcular hashes dos arquivos
extraídos. O andamento aparece também na aba Localizações. Entradas já extraídas
aparecem como **não verificado** até usar **Atualizar / validar**. Essa validação
pode levar mais tempo porque lê o conteúdo do workspace.

Ao expandir uma pasta da árvore, os arquivos diretamente contidos nela são
carregados sob a pasta. Você pode selecioná-los ali para extrair, abrir,
consultar especificações ou restaurar. A lista à direita continua mostrando
os arquivos da pasta e de suas subpastas, com os filtros aplicados.
Se essa lista estiver recolhida, use **Mostrar painel de arquivos →** para
restaurar sua largura. Quando um filtro não encontra arquivos, aparece uma
mensagem explicando que é possível usar **Limpar**.

- Selecione um ou vários GPKs/pastas na árvore com Ctrl/Shift para restringir a lista.
- Pesquise partes do nome ou caminho; palavras são combinadas por AND, sem diferenciar maiúsculas.
- Combine a pesquisa com extensão, formato e estado. O formato inicial é inferido pela extensão; a inspeção verifica as propriedades do conteúdo.
- Use Ctrl/Shift na lista para selecionar vários arquivos da página atual.
- **Marcar seleção** acumula arquivos entre páginas. **Marcar filtrados** inclui todas as páginas do filtro atual.
- **Limpar marcas** remove a seleção acumulada; **Limpar** remove filtros e o escopo da árvore.

A prioridade das operações é: arquivos marcados, arquivos selecionados na
lista e, por último, GPKs/pastas selecionados na árvore. Sem seleção, nenhuma
operação é iniciada. **Extrair tudo** e **Repack todos os GPKs** usam todos os
GPKs detectados, independentemente dos filtros.

## Estados e edição externa

| Estado | Significado |
| --- | --- |
| original | SHA-256 igual ao registrado na extração |
| modificado | Hash diferente, sem incompatibilidades detectadas |
| ausente | Entrada registrada como extraída, mas arquivo ausente |
| novo | Arquivo fora do índice ou colocado sobre entrada não extraída sem registro |
| inválido | Alteração ilegível ou incompatível com as propriedades verificadas do original |
| não extraído | Entrada presente no índice, ainda não materializada no workspace |
| não verificado | Registrado como extraído; conteúdo e presença ainda não conferidos nesta abertura |

Use **Extrair seleção**, **Abrir arquivo** ou **Abrir pasta** para editar em
aplicativos associados no Windows. Após salvar no editor, use **Atualizar /
validar**. Esta ação recalcula hashes e compara alterações ao original. Ela
não é um monitor automático de arquivos. A contagem de modificações e os GPKs
afetados aparecem abaixo da lista; erros e avisos aparecem nas especificações
e no relatório. Os arquivos originais são considerados a referência confiável.

**Extrair seleção** mostra quantos arquivos foram extraídos agora e quantos já
existiam e foram preservados, além da pasta de destino. Não inicia validação
automática depois de concluir. Para substituir uma edição pelo original, use
**Restaurar arquivo**. O botão de extração preserva as edições já existentes.

O alvo da operação aparece acima dos filtros: marcas, arquivos da lista ou
GPKs/pastas da árvore. Clique no nome do GPK na árvore para selecioná-lo; apenas
expandir sua seta não é uma seleção. Quando não há alvo, a interface avisa.
Durante uma operação, os botões de trabalho ficam desabilitados e **Cancelar**
permanece disponível. O andamento aparece na própria página de arquivos.

**Atualizar / validar** verifica os GPKs que contêm a seleção atual; sem seleção,
verifica todos. O repack também valida somente os GPKs solicitados. A seleção,
as pastas expandidas e a página da lista são preservadas ao atualizar os dados.

Selecione um arquivo e clique em **Especificações**, ou dê duplo clique. A GUI
extrai somente o original selecionado para uma pasta temporária isolada e
mostra suas propriedades, mesmo quando o workspace ainda não contém o arquivo.
Quando há arquivo no workspace, mostra também as propriedades atuais:

- PNG: dimensões, transparência, profundidade e tipo de cor.
- Ogg: codec, canais, frequência e informações disponíveis de duração.
- WMV/ASF: streams, codecs, resolução e duração; mudança de duração gera aviso.
- CMAP: dimensões e IDs; IDs novos são rejeitados.
- ORS/INI/TXT: codificação inferida, seções, chaves, linhas e convenção de quebra de linha.
- Desconhecidos: assinatura hexadecimal, tamanho e aviso de compatibilidade não verificada.

A inferência de texto reconhece BOM UTF-8/UTF-16 e tenta UTF-8 e CP932. Sem BOM,
codificações podem ser ambíguas. A validação de ORS verifica estrutura textual;
não interpreta a semântica dos comandos nem garante o comportamento do script.
As validações de mídia usam os leitores existentes e não substituem uma
decodificação completa por um player. Os fluxos já validados no jogo até v0.10
permanecem registrados; não é necessário repeti-los para instalar a atualização.

**Restaurar arquivo** solicita confirmação porque descarta as edições daquele
arquivo e recupera seu conteúdo diretamente do GPK original. As demais entradas
do workspace são preservadas. Se um mod instalado controla o arquivo, sua
remoção posterior reconhece que ele já foi restaurado.

## Repack e extração parcial

**Repack GPKs selecionados** reconstrói os GPKs que contêm a seleção. Inclui
todas as alterações presentes nesses GPKs, não apenas os arquivos selecionados.
Primeiro valida alterações com o mesmo modo escolhido em **Atualizar / validar**.
Editar o conteúdo ou aumentar/diminuir o tamanho de um arquivo é permitido;
as restrições de formato são avaliadas separadamente da montagem do GPK.

Na própria página de arquivos, escolha o modo em **Validação / repack**:

- **Estrito:** bloqueia incompatibilidades detectadas em PNG, OGG, WMV/ASF,
  CMAP e texto. Formatos desconhecidos modificados precisam da opção
  **Permitir formatos desconhecidos**, disponível nessa página e na aba de pacotes.
- **Experimental:** permite repack dos bytes editados mesmo com problemas de
  formato ou formatos desconhecidos. Esses problemas continuam visíveis como
  avisos. Não remove bytes extras, não converte o arquivo e não comprova que
  o jogo aceitará a alteração. É uma opção para mudanças intencionais que
  ultrapassam as verificações implementadas.

Nos dois modos, continuam bloqueados referência incompatível, arquivos
extraídos ausentes, arquivos novos sem entrada correspondente e alterações
concorrentes durante o repack. Adicionar, remover ou renomear entradas do índice
GPK ainda não é suportado. Arquivos auxiliares do editor devem ficar fora da
pasta extraída desse GPK.

A validação mostra **APROVADO**, **COM AVISOS** ou **BLOQUEADO**, com contagem e
lista dos problemas. O status do relatório acompanha o resultado: `PASS`,
`WARN` ou `FAIL`. Concluir a varredura não significa aprovar arquivos inválidos.
O repack repete as mesmas regras para detectar edições feitas após a validação.

As entradas não extraídas são copiadas do GPK de referência. Não representam
remoções. Extrações completas da v0.10 e extrações parciais podem ser usadas
juntas. Arquivos novos no GPK continuam não suportados. A GUI nunca publica os
GPKs em Packs. Se já existir uma saída com o nome de algum GPK solicitado,
todo o novo lote vai para uma subpasta `repack-<data-hora>` da saída configurada.
A interface e o relatório mostram o caminho efetivo. Os resultados anteriores
são preservados, permitindo editar e gerar novamente sem removê-los.

## Pacotes .sdmod

1. Use **Novo projeto** para informar ID, nome, autor e versão em uma pasta vazia,
   ou selecione um projeto v0.10 existente com `mod.json`.
2. Clique em **Prévia exata**. A lista inclui os caminhos, GPKs, tamanhos e hashes
   dos arquivos que serão incluídos; arquivos originais/não extraídos não entram.
3. Confira a lista e clique em **Criar pacote da prévia**. Se os arquivos mudarem
   desde a prévia, a criação é bloqueada até gerar outra prévia. O projeto pode
   restringir GPKs pelo campo `target_archives` no seu `mod.json`.
4. Selecione um `.sdmod` e use **Inspecionar pacote** para verificar manifesto e
   hashes, ou **Aplicar no workspace**. A GUI extrai previamente apenas os alvos
   necessários, quando ainda não extraídos. Conflitos com edições são bloqueados.
5. Use **Listar instalados**, selecione o ID e clique em **Remover e restaurar**.
   Os backups são locais ao workspace e o fluxo existente de remoção é reutilizado.

Aplicação e remoção alteram o workspace. Depois gere os GPKs pela ação de repack.
Não há cópia automática para a instalação.

O modo Experimental se aplica à validação/repack GPK da página de arquivos.
A criação de pacotes `.sdmod` mantém a validação estrita, com a opção separada
para autorizar formatos desconhecidos.

## Referência trocada durante a sessão

A interface confere tamanho, datas e identidade do arquivo de referência antes
das operações. Se o GPK mudou, recarrega o índice antes de comparar com o
metadata; assim não usa offsets antigos após uma troca e nova extração.
Se o GPK atual realmente não corresponder ao workspace, a operação continua
bloqueada e informa o caminho e os tamanhos registrado/atual. Selecione o GPK
usado naquela extração, ou extraia o novo GPK em outro workspace preservando as
edições existentes. Não é necessário editar o metadata manualmente.

## Operações, cancelamento e relatórios

Um worker executa uma operação por vez. As telas não executam leitura/escrita
de GPK. A interface recebe progresso por polling e continua respondendo.
**Cancelar** solicita parada cooperativa; fechar a janela durante uma operação
solicita cancelamento e aguarda o worker encerrar com segurança.

- Extração: remove o arquivo temporário em andamento e salva no metadata as
  entradas concluídas. Repetir a seleção ou extrair tudo retoma o trabalho.
- Repack: descarta o GPK temporário da operação interrompida. Em lotes, GPKs já
  concluídos ficam na saída, cada um com seu relatório `.build.json`.
- Criação: descarta o pacote temporário caso seja interrompida antes de publicar.
- Aplicação: o mecanismo existente restaura os arquivos aplicados se ocorrer
  cancelamento dentro da transação. Extrações preparatórias concluídas permanecem.
- Remoção: para entre arquivos. Mantém o estado instalado até concluir; repetir
  a remoção reconhece os arquivos já restaurados e termina com segurança.

Extração, hashing e repack verificam cancelamento por bloco. Algumas rotinas de
inspeção e operações de pacote aguardam o término do arquivo em processamento.
Após cancelamento, **Atualizar / validar** mostra o estado persistido. Não
encerre o processo à força se quiser aguardar a gravação do metadata.

Cada operação registra status, resultado ou erro em `gui-<data-hora>.json`, além
de `desktop.log` na pasta configurada. A aba **Logs e relatórios** permite abrir
a pasta e o último relatório. Relatórios são locais e não entram no ZIP de atualização.

## Arquitetura e verificação

`core/partial.py` implementa seleção, retomada e restauração usando `GPKReader`.
`GPKWriter` reconstrói a partir da referência. `core/desktop.py` orquestra
formatos, estados e pacotes. `gui/controller.py` controla seleção e worker sem
Tk; `gui/app.py` contém somente apresentação e ligações com os serviços.

Execute `run_tests.bat` ou `python -m unittest discover -s tests -v` com `src`
no `PYTHONPATH`. A execução padrão usa arquivos sintéticos sem abrir janelas.
Os testes adicionais dos próprios widgets ficam desabilitados por padrão.
Para executá-los no Windows com uma janela oculta:

```powershell
$env:PYTHONPATH = "src"
$env:SDHQ_GUI_TESTS = "1"
python -m unittest discover -s tests -p test_gui_actions.py -v
Remove-Item Env:SDHQ_GUI_TESTS
```

Esses testes acionam os botões, processam os eventos do Tk e verificam resultados
em diretórios temporários. Os comandos de abrir aplicativos são interceptados.
Não acessam dados proprietários nem repetem validações manuais no jogo.
