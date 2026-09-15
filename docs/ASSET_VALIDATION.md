# Validação de assets

A v0.9 introduz uma verificação de compatibilidade entre os arquivos originais
extraídos e os arquivos editados pelo modder. Ela é uma barreira preventiva:
detecta danos e mudanças estruturais conhecidas antes de construir o GPK, mas o
teste final dentro do jogo continua obrigatório.

## 1. Criar a linha de base

Restaure primeiro o `workspace` ao estado extraído. Em seguida execute:

```powershell
py -3 pipelines\create_asset_baseline.py "workspace" --output "reports\asset_baseline.json" --progress-every 500
```

Cada arquivo precisa possuir o mesmo SHA-256 registrado em
`.sdhq/archive.json`. Isso impede que uma pasta já modificada seja aceita por
engano como original. O relatório contém hashes e propriedades técnicas, mas
não contém os assets do jogo.

## 2. Validar as alterações

Para todo o workspace:

```powershell
py -3 pipelines\validate_assets.py "workspace" --baseline "reports\asset_baseline.json" --output "reports\asset_validation.json" --progress-every 500
```

Também é possível validar apenas um archive:

```powershell
py -3 pipelines\validate_assets.py "workspace\System" --baseline "reports\asset_baseline.json" --output "reports\System.asset_validation.json"
```

Um arquivo com o mesmo hash é contado como `unchanged` e não precisa passar
novamente pela análise completa. O relatório detalha os arquivos modificados e
os motivos de cada bloqueio.

## Política de compatibilidade

| Formato | Validação integral da edição | Mudanças bloqueadas |
|---|---|---|
| PNG | assinatura, chunks, CRC, zlib, filtros e tamanho das scanlines | dimensões, bit depth, interlace e modelo de cor incompatível |
| Ogg | páginas, lacing, sequência, CRC e identificação do codec | codec, canais ou sample rate diferentes |
| WMV/ASF | objetos do cabeçalho, tamanho declarado e streams | quantidade/tipo de streams, codec, dimensões, canais ou sample rate diferentes |
| CMAP | estrutura completa, pixels e IDs | dimensões diferentes ou IDs novos |
| ORS/INI/TXT | leitura integral | texto que deixou de ser UTF-8 |
| DAT/desconhecido | hash | qualquer modificação sem autorização explícita |

Mudanças de bitrate, duração ou modelo RGB/RGBA compatível podem gerar
`warning`, sem bloquear automaticamente.

## Formatos desconhecidos

`FONTDATA.DAT`, `FONTDATA_ENG.DAT` e outros formatos não documentados são
bloqueados se forem alterados. Para uma pesquisa consciente, é possível usar:

```powershell
--allow-unknown
```

Essa opção apenas libera a passagem; ela não prova compatibilidade.

## Preflight integrado ao repack

Archive individual:

```powershell
py -3 pipelines\repack_gpk.py "workspace\System" --reference "C:\Games\School Days HQ\Packs\System.GPK" --key-report "reports\ciphercode_report.json" --output "output" --asset-baseline "reports\asset_baseline.json"
```

Todos os archives:

```powershell
py -3 pipelines\repack_all_gpk.py "workspace" --references "C:\Games\School Days HQ\Packs" --key-report "reports\ciphercode_report.json" --output "output_all" --asset-baseline "reports\asset_baseline.json"
```

Se houver arquivo incompatível, ausente, extra ou desconhecido modificado, o
GPK não é construído e o caminho do relatório de diagnóstico é exibido.
