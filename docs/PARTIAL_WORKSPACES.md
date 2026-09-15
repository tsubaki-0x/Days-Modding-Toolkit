# Workspaces parciais — v0.11

O metadata continua em `<workspace>/<GPK>/.sdhq/archive.json`. A v0.11 mantém
`entries` com todas as entradas do índice na ordem original e acrescenta:

```json
{
  "metadata_version": 2,
  "reference_index_sha256": "hash do índice estrutural",
  "extraction_complete": false,
  "entries": [
    {"path": "INI/ONE.INI", "extracted": true, "extracted_sha256": "hash do original extraído"},
    {"path": "INI/TWO.INI", "extracted": false}
  ]
}
```

O exemplo omite os demais campos do índice e de origem por brevidade. O hash
estrutural valida nomes, posições, tamanhos, cabeçalhos e campos desconhecidos;
não é um hash de todo o conteúdo do GPK. Os GPKs originais devem permanecer
imutáveis. Metadata da v0.10 sem `extracted` é interpretado como extração completa.

O hash `extracted_sha256` sempre descreve o original extraído; atualizar a GUI
não redefine a linha de base. A seleção rejeita caminhos ausentes do índice,
colisões e arquivos não registrados já existentes. Extrações posteriores não
sobrescrevem edições. Restauração é uma operação explícita por entrada.

No repack:

- `extracted=false` e arquivo inexistente: reutiliza os bytes originais.
- `extracted=false` e arquivo existente: erro de arquivo não registrado.
- `extracted=true` e arquivo inexistente: erro de arquivo ausente.
- `extracted=true` e hash igual: reutiliza os bytes originais.
- `extracted=true` e hash diferente: reconstrói a entrada com a lógica existente.
- Arquivo fora do índice: erro; adição e remoção de entradas não são suportadas.

As gravações de cada entrada usam um temporário no mesmo volume e substituição
após leitura completa. Ao terminar, falhar ou cancelar cooperativamente, o
metadata é gravado por substituição atômica. Arquivos concluídos são preservados.
O repack é publicado apenas após reconstrução e validação do índice temporário.

## API e CLI

```python
from sdhq_toolkit.core.partial import extract_selection, restore_entry
from sdhq_toolkit.core.repacker import repack_archive

extract_selection(archive, workspace / archive.stem, key, ["INI/ONE.INI"])
restore_entry(archive, workspace / archive.stem, key, "INI/ONE.INI")
repack_archive(workspace / archive.stem, archive, output, key)
```

`paths=None` seleciona todas as entradas e `paths=[]` cria somente metadata.
`cancel` aceita `CancellationToken`; `progress` recebe contagem, total, caminho
e informação adicional. Os parâmetros novos são opcionais.

```powershell
python pipelines\unpack_gpk.py "C:\Games\School Days HQ\Packs\Ini.GPK" --workspace workspace --key-report reports\ciphercode_report.json --member "INI/ONE.INI" --member "INI/TWO.INI"
python pipelines\repack_gpk.py workspace\Ini --reference "C:\Games\School Days HQ\Packs\Ini.GPK" --key-report reports\ciphercode_report.json --output output_v011
```

Use caminhos que realmente existam no índice. `unpack` sem `--member` e
`unpack-all` completam uma extração parcial existente sem sobrescrever edições.
O repack detecta automaticamente o metadata parcial. A criação de `.sdmod`
ignora apenas entradas explicitamente não extraídas e inexistentes; não ignora
arquivos extraídos ausentes. Baselines de assets criados a partir de um workspace
parcial cobrem somente as entradas extraídas naquele momento; refaça a baseline
em estado limpo ao ampliar sua cobertura. A GUI compara diretamente ao GPK
original e não depende de uma baseline externa.
