# Fluxo de trabalho

## Inventário

```powershell
run_inventory.bat
```

A pipeline apenas lê os arquivos e gera relatórios.

## Extração em lote

```powershell
py -3 pipelines\unpack_all_gpk.py "C:\Games\School Days HQ\Packs" --key-report reports\ciphercode_report.json --workspace workspace
```

O comando:

1. encontra os GPKs sem depender de letras maiúsculas/minúsculas;
2. lê todos os índices e estima o espaço extraído;
3. bloqueia o início se não houver espaço suficiente;
4. extrai cada entrada em blocos de 1 MiB;
5. atualiza `reports/unpack_all_report.json` após cada archive;
6. ignora archives já concluídos quando for executado novamente.

Se existir `workspace/NomeDoGPK` sem um `.sdhq/archive.json` completo, a pasta é
considerada parcial. Ela não será sobrescrita. Mova-a para outro local antes de
reiniciar a extração daquele archive.

## Round-trip controlado

```text
packs/Script.gpk
        -> workspace/Script/
        -> edição do modder
        -> output/Script.gpk (usando original como referência)
        -> validação
        -> teste manual no jogo
```

O toolkit nunca deverá sobrescrever o GPK original no comando `repack`.

## Linha de base dos assets

Depois de extrair todos os GPKs e antes de editar qualquer arquivo, crie uma
linha de base limpa:

```powershell
py -3 pipelines\create_asset_baseline.py workspace --output reports\asset_baseline.json --progress-every 500
```

O resultado esperado na instalação validada é `69936 passed, 0 failed`. O
processo lê e calcula hashes dos aproximadamente 12 GB extraídos, portanto pode
levar alguns minutos. Ele mostra progresso e não escreve dentro do workspace.

Depois das edições:

```powershell
py -3 pipelines\validate_assets.py workspace --baseline reports\asset_baseline.json --output reports\asset_validation.json --progress-every 500
```

O relatório lista somente arquivos alterados, ausentes ou extras; arquivos
inalterados entram apenas no contador. Consulte `ASSET_VALIDATION.md`.

## Repack em lote

```powershell
py -3 pipelines\repack_all_gpk.py workspace --references "C:\Games\School Days HQ\Packs" --key-report reports\ciphercode_report.json --output output_all
```

Para bloquear o repack quando a validação de assets falhar:

```powershell
py -3 pipelines\repack_all_gpk.py workspace --references "C:\Games\School Days HQ\Packs" --key-report reports\ciphercode_report.json --output output_all --asset-baseline reports\asset_baseline.json
```

Arquivos inalterados são copiados do GPK de referência em streaming. Arquivos
alterados são lidos e recomprimidos em streaming. Cada saída recebe seu próprio
`Nome.gpk.build.json`, e o resumo fica em `reports/repack_all_report.json`.

O comando nunca substitui um resultado existente que não corresponda ao
workspace atual. Use um novo diretório `--output` para uma nova rodada.

## Formatos internos

Gere o resumo compacto a partir do inventário já existente:

```powershell
py -3 pipelines\summarize_assets.py reports\asset_inventory.json --output reports
```

Antes de modificar mapas CMAP, valide todas as amostras originais:

```powershell
py -3 pipelines\verify_cmap.py workspace\System --output reports\cmap_roundtrip.json
```

Somente depois de um relatório com `status: PASS`, crie o projeto visual:

```powershell
py -3 pipelines\export_cmap_project.py workspace\System --output cmap_project
```

Use `cmap_project\overlays` para localizar os IDs sobre a interface e edite
apenas `cmap_project\editable`. Cada cor representa exatamente um ID de região.
Não use pincel com antialiasing, transparência, blur ou redimensionamento.

Reconstrua as alterações em staging:

```powershell
py -3 pipelines\build_cmap_project.py cmap_project --output cmap_staged
```

Arquivos inalterados não são copiados. O relatório é criado ao lado da pasta,
em `cmap_staged.build.json`, para impedir que seja confundido com um asset do
jogo. O comando nunca grava diretamente no `workspace`.
