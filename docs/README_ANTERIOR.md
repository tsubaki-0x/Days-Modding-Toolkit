<!-- Historical README, preserved before publication rewrite. -->
# School Days HQ Modding Toolkit

## v0.11.1 — GARbro externo e repack por pasta

Abra **`run_gui.bat`**. Requer Python 3.10+ com Tkinter.

Para uma instalação limpa, extraia `dist/SchoolDaysHQ-Modding-Toolkit-v0.11.1-completo.zip`
em uma pasta nova. Consulte a [organização dos arquivos](ORGANIZACAO.md).

1. Selecione manualmente o GARbro.exe, mantendo os arquivos que acompanham o programa.
2. Crie uma pasta exclusiva para cada GPK e extraia nela pelo GARbro, preservando
   caminhos e sem converter formatos. O GARbro não precisa criar uma pasta com o nome do GPK.
3. Edite os arquivos. No toolkit, selecione a instalação do jogo (onde fica o EXE),
   o GPK de referência, a pasta de alterações, a saída e os relatórios.
4. Use **Conferir alterações** e **Gerar GPK**.
5. Antes de trocar o GPK em `Packs`, feche o jogo e o GARbro para liberar o arquivo.
   Guarde uma cópia do GPK anterior.

O GPK de referência pode ser original ou modificado. Arquivos ausentes na pasta
são mantidos da referência; metadata de extração não é necessário. Usar o nome
do GPK na pasta ajuda na organização, mas não é obrigatório. Importam os caminhos
**dentro** da pasta selecionada, inclusive arquivos diretamente na raiz.

Avisos de formato permitem montar sem garantia de funcionamento no jogo. Arquivos
novos aparecem como **não incluídos**; inclusão, remoção e renomeação de entradas
estão fora desta entrega. Saídas anteriores são preservadas.

Veja o [guia de uso, escopo e verificação](GARBRO_REPACK.md).
O botão **Interface anterior / .sdmod** e a CLI preservam os recursos existentes
com suas regras anteriores de workspace. Veja o [guia anterior](DESKTOP.md)
e o [metadata parcial](PARTIAL_WORKSPACES.md).

O conteúdo abaixo também documenta os pipelines anteriores; as restrições de
workspace desses comandos não se aplicam ao novo repack por pasta.

Base inicial, não oficial, para pesquisa e desenvolvimento de ferramentas de
modding de **School Days HQ v1.02**.

O objetivo do projeto é permitir o fluxo:

```text
GPK original -> extração -> edição -> repack com referência -> validação
```

Esta versão (`0.11.1-dev`) fornece interface desktop, inventário, leitura do índice Stack,
extração/repack GPK baseado no archive original e pipelines em lote com
progresso, verificação de espaço e retomada por archive concluído. Ela também
inclui relatório compacto de assets, conversão lossless do formato CMAP e um
projeto visual protegido para editar seus mapas de regiões interativas. A v0.9
adiciona uma linha de base limpa e validação pré-repack de PNG, Ogg, WMV/ASF,
CMAP e arquivos de texto. A v0.10 acrescenta projetos e pacotes `.sdmod`, com
somente os arquivos alterados, verificação de hashes, aplicação transacional e
remoção segura no workspace.

O round-trip dos 29 GPKs foi validado manualmente no jogo: 69.936 entradas,
nenhuma falha. GPK, INI, ORS e CMAP possuem suporte confirmado. Uma modificação
real em `STARTSCRIPT.INI`, alterações controladas de ações CMAP e substituições
de PNG, Ogg e WMV também foram reconstruídas e reconhecidas pelo jogo.

## Requisitos

- Windows 10/11 ou Linux
- Python 3.10 ou superior
- Nenhuma dependência externa para os scanners

## Teste rápido no Windows

1. Extraia este projeto.
2. Coloque cópias dos arquivos `.gpk` do jogo em `samples/packs/`.
3. Se você já extraiu algum GPK, coloque a pasta resultante em
   `samples/extracted/NomeDoGPK/`.
4. Execute `run_inventory.bat`.

Os relatórios serão criados em `reports/`:

- `gpk_inventory.json` e `.txt`
- `asset_inventory.json` e `.txt`
- `unknown_formats.txt`

O scanner agora lê também os últimos 32 bytes de cada archive, reconhece o
rodapé `STKFile0PIDX ... STKFile0PACKFILE`, calcula tamanho/offset do índice e
mostra progresso. Use `--skip-hash` para uma nova varredura quase instantânea.

Nenhum arquivo original é alterado.

## Uso pelo terminal

```powershell
python -m sdhq_toolkit inventory --packs samples\packs --extracted samples\extracted --output reports
python -m sdhq_toolkit inventory --packs "C:\Games\School Days HQ\packs" --output reports --skip-hash
python -m sdhq_toolkit inspect samples\packs\Script.gpk
python -m sdhq_toolkit scan-assets samples\extracted --output reports
python -m sdhq_toolkit compare original.gpk reconstruido.gpk
python pipelines\extract_ciphercode.py "C:\Games\School Days HQ" --output reports\ciphercode_report.json
python pipelines\read_gpk_index.py "C:\Games\School Days HQ\Packs\Ini.GPK" --key-report reports\ciphercode_report.json
python pipelines\unpack_gpk.py "C:\Games\School Days HQ\Packs\Ini.GPK" --key-report reports\ciphercode_report.json --workspace workspace
python pipelines\repack_gpk.py workspace\Ini --reference "C:\Games\School Days HQ\Packs\Ini.GPK" --key-report reports\ciphercode_report.json --output output
python pipelines\unpack_all_gpk.py "C:\Games\School Days HQ\Packs" --key-report reports\ciphercode_report.json --workspace workspace
python pipelines\repack_all_gpk.py workspace --references "C:\Games\School Days HQ\Packs" --key-report reports\ciphercode_report.json --output output
python pipelines\summarize_assets.py reports\asset_inventory.json --output reports
python pipelines\verify_cmap.py workspace\System --output reports\cmap_roundtrip.json
python pipelines\export_cmap_project.py workspace\System --output cmap_project
python pipelines\build_cmap_project.py cmap_project --output cmap_staged
python pipelines\create_asset_baseline.py workspace --output reports\asset_baseline.json
python pipelines\validate_assets.py workspace --baseline reports\asset_baseline.json --output reports\asset_validation.json
python pipelines\create_mod_project.py "mods\meu-mod" --id "autor.meu-mod" --name "Meu Mod" --author "Autor" --archives System
python pipelines\build_mod_package.py "mods\meu-mod" --workspace workspace --output dist --asset-baseline reports\asset_baseline.json
python pipelines\inspect_mod_package.py "dist\autor.meu-mod-1.0.0.sdmod"
python pipelines\apply_mod_package.py "dist\autor.meu-mod-1.0.0.sdmod" --workspace workspace
python pipelines\remove_mod.py "autor.meu-mod" --workspace workspace
```

## Criação e distribuição de mods

A v0.10 distribui alterações em um `.sdmod`, sem incluir GPKs completos ou
assets inalterados. O criador informa os GPKs-alvo, edita o workspace e executa
o build. O usuário inspeciona o pacote, aplica-o sobre uma extração limpa e
reconstrói somente os GPKs afetados usando seus próprios originais.

Pacotes adulterados e versões incompatíveis são recusados. A aplicação cria
backup antes de qualquer substituição e bloqueia conflitos com outras edições.
Consulte `docs/MOD_PACKAGES.md` para o fluxo completo.

## Validação de assets

Com o `workspace` restaurado e sem alterações, crie a referência local uma vez:

```powershell
py -3 pipelines\create_asset_baseline.py "workspace" --output "reports\asset_baseline.json" --progress-every 500
```

O comando compara cada arquivo com o hash registrado durante a extração. Se
algum arquivo estiver ausente ou já tiver sido modificado, a linha de base fica
com `FAIL` e não pode ser usada.

Depois de editar os assets, valide somente o que mudou:

```powershell
py -3 pipelines\validate_assets.py "workspace" --baseline "reports\asset_baseline.json" --output "reports\asset_validation.json" --progress-every 500
```

A validação integral verifica CRC/chunks e propriedades de PNG, CRC/páginas e
parâmetros de Ogg Vorbis/Opus, além da estrutura e streams de WMV/ASF. CMAP
preserva dimensões e IDs conhecidos; ORS, INI e TXT precisam continuar em
UTF-8. Arquivos desconhecidos modificados são bloqueados por padrão.

Para tornar a validação uma etapa obrigatória do repack, acrescente:

```powershell
--asset-baseline "reports\asset_baseline.json"
```

Consulte `docs/ASSET_VALIDATION.md` para a política completa.

## Resumo compacto dos assets

Se `asset_inventory.json` já foi gerado, não é necessário examinar novamente os
69 mil arquivos. Reclassifique o relatório existente:

```powershell
py -3 pipelines\summarize_assets.py "reports\asset_inventory.json" --output "reports"
```

Isso gera `asset_summary.json` e `asset_summary.txt`, com totais por GPK e por
formato. O detector reconhece PNG, Ogg, ORS, ASF/WMV, CMAP, INI, TXT e DS_Store.

## CMAP

Os 137 CMAPs de `System.GPK` possuem cabeçalho little-endian com largura e
altura, seguido por exatamente um byte por pixel. Para validar todos:

```powershell
py -3 pipelines\verify_cmap.py "workspace\System" --output "reports\cmap_roundtrip.json"
```

Para converter um arquivo sem tocar no original:

```powershell
py -3 pipelines\cmap_to_png.py "workspace\System\TITLE\TITLE.CMAP" --output "cmap_edit\TITLE.png"
py -3 pipelines\png_to_cmap.py "cmap_edit\TITLE.png" --output "cmap_rebuilt\TITLE.CMAP"
```

O PNG grayscale preserva os bytes, mas os IDs baixos ficam quase pretos. Para
edição visual segura, exporte o projeto colorido completo:

```powershell
py -3 pipelines\export_cmap_project.py "workspace\System" --output "cmap_project"
```

Ele cria `editable/` com uma cor exata por ID, `overlays/` com as regiões sobre
os PNG correspondentes, `palette_legend.html` com a legenda dos IDs e
`cmap_project.json` com hashes e metadados. Edite somente os PNG de
`editable/`, sem antialiasing, transparência ou novas cores.

Para reconstruir apenas os CMAP realmente modificados em uma pasta separada:

```powershell
py -3 pipelines\build_cmap_project.py "cmap_project" --output "cmap_staged"
```

O build verifica marcador, paleta, dimensões, IDs e hash do CMAP de origem.
Nenhum arquivo do `workspace` é sobrescrito. Consulte `docs/CMAP_FORMAT.md`.

## Extração de todos os GPKs

```powershell
py -3 pipelines\unpack_all_gpk.py "D:\SCHOOL DAYS HQ\Overflow\SCHOOLDAYS HQ\Packs" --key-report "reports\ciphercode_report.json" --workspace "workspace"
```

Antes de começar, a pipeline lê os índices e compara a estimativa de tamanho
extraído com o espaço livre. Durante o processo, mostra o GPK atual e uma
entrada a cada 100 arquivos. Para outra frequência, use, por exemplo:

```powershell
--progress-every 25
```

Ao executar novamente o mesmo comando, archives que possuem um
`.sdhq/archive.json` completo e compatível são ignorados. Uma pasta existente
sem esse marcador é tratada como parcial e nunca é sobrescrita automaticamente.
O relatório incremental fica em `reports/unpack_all_report.json`.

## Repack em lote

```powershell
py -3 pipelines\repack_all_gpk.py "workspace" --references "D:\SCHOOL DAYS HQ\Overflow\SCHOOLDAYS HQ\Packs" --key-report "reports\ciphercode_report.json" --output "output_all"
```

Cada pasta concluída do workspace é associada ao GPK original de mesmo nome.
O writer processa arquivos em blocos de 1 MiB, preserva entradas inalteradas e
recomprime somente as modificadas. Resultados existentes só são ignorados
quando o relatório `*.build.json` ainda corresponde ao estado atual do
workspace; caso contrário, a pipeline interrompe aquele archive sem apagar
nada.

O núcleo GPK foi validado nos 29 archives da instalação analisada. Mesmo assim,
mantenha backups fora da pasta `Packs` e teste mods novos de forma controlada.

Se o Python não encontrar o pacote, use os scripts de `pipelines/`, que já
configuram o caminho automaticamente:

```powershell
python pipelines\inventory_pipeline.py --packs samples\packs --extracted samples\extracted --output reports
```

## Estrutura

```text
src/sdhq_toolkit/       código estável do toolkit
pipelines/              entradas prontas para pesquisa/teste
research/               scripts e anotações experimentais
tests/                  testes automatizados
samples/packs/          cópias locais dos GPKs (ignoradas pelo Git)
samples/extracted/      conteúdo extraído (ignorado pelo Git)
workspace/              área editável futura
output/                 GPKs reconstruídos
reports/                inventários gerados
backups/                backups manuais do usuário
mods/                   projetos locais de mod
dist/                   pacotes .sdmod gerados
```

## Segurança e direitos autorais

Este repositório não inclui arquivos do jogo. Use apenas arquivos de uma cópia
legítima de School Days HQ. As pastas de amostras, relatórios e resultados são
ignoradas pelo Git para reduzir o risco de publicar conteúdo proprietário.

## Limites atuais

- O repack exige o GPK original como referência.
- Adição e remoção de entradas ainda não são suportadas.
- Archives concluídos são retomados; uma entrada interrompida no meio é
  reprocessada quando a pasta parcial for movida ou removida pelo usuário.
- A instalação automática no diretório do jogo ainda não está disponível; a
  aplicação de `.sdmod` modifica apenas o workspace extraído.
- Mods não podem adicionar/remover entradas nem sobrepor alterações no mesmo
  arquivo nesta versão.
- A validação estrutural não substitui o teste manual de cada mod no jogo.
- `FONTDATA.DAT` e `FONTDATA_ENG.DAT` ainda não possuem conversor.
