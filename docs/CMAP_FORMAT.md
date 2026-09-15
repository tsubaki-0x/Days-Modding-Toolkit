# Formato CMAP

O formato CMAP de School Days HQ é um mapa raster simples de 8 bits usado como
mapa de regiões interativas da interface.

## Estrutura confirmada

| Offset | Tamanho | Tipo | Campo |
|---:|---:|---|---|
| `0x00` | 4 bytes | `uint32 LE` | largura |
| `0x04` | 4 bytes | `uint32 LE` | altura |
| `0x08` | `largura × altura` | bytes | valores do mapa |

O tamanho válido é sempre:

```text
8 + largura × altura
```

Essa fórmula foi confirmada nas 137 amostras presentes em `System.GPK`.

O relatório real confirmou valores consecutivos entre `0` e `44`. A forte
evidência atual indica que `0` é a área inativa e `1..N` são IDs de regiões ou
controles. Exemplos: `OPTION_SOUND.CMAP` usa `0..44`, enquanto
`SELECT_1_FULL.CMAP` contém somente o ID `1`.

## Conversão

O exportador cria PNG grayscale de 8 bits, sem entrelaçamento. Cada byte CMAP é
armazenado como um pixel de mesmo valor, portanto o round-trip é lossless.

```powershell
py -3 pipelines\cmap_to_png.py arquivo.CMAP --output arquivo.png
py -3 pipelines\png_to_cmap.py arquivo.png --output reconstruido.CMAP
```

O importador aceita PNG 8-bit grayscale e também RGB/RGBA quando todos os
canais de cor são iguais e o alpha é totalmente opaco. PNG colorido,
transparência parcial, bit depth diferente de 8 e imagens entrelaçadas são
recusados para evitar conversões ambíguas.

Os arquivos de saída nunca substituem arquivos existentes.

## Projeto visual colorido

O modo recomendado representa cada byte CMAP por uma cor única e reversível:

```powershell
py -3 pipelines\export_cmap_project.py workspace\System --output cmap_project
```

Estrutura criada:

```text
cmap_project/
  editable/          PNGs coloridos que podem ser alterados
  overlays/          visualizações sobre os PNGs da interface
  palette_legend.html legenda visual dos IDs realmente utilizados
  cmap_project.json  manifesto, hashes, dimensões e paleta
```

O PNG editável contém um marcador `SDHQ-CMAP-Palette=v1`. A importação aceita
somente as 256 cores exatas registradas. Cores produzidas por antialiasing,
transparência, mudanças de dimensão e fontes CMAP alteradas após a exportação
são recusadas.

Por padrão, o build também recusa IDs que não existiam naquele CMAP original.
Um novo ID não possui necessariamente uma ação associada no jogo. O parâmetro
experimental `--allow-new-ids` remove somente esse bloqueio; ele não garante
que o jogo atribuirá uma função à nova região.

```powershell
py -3 pipelines\build_cmap_project.py cmap_project --output cmap_staged
```

Somente CMAPs cujo conteúdo realmente mudou são escritos em `cmap_staged`.
O relatório fica em `cmap_staged.build.json`, fora da árvore de assets.

Alguns editores removem metadados PNG. Nessa situação o modo explícito abaixo
permite a leitura sem o marcador, mas todas as cores e dimensões continuam
sendo rigorosamente verificadas:

```powershell
py -3 pipelines\build_cmap_project.py cmap_project --output cmap_staged --allow-missing-marker
```

Esse parâmetro deve ser usado apenas quando o editor realmente removeu o
marcador e todas as cores foram mantidas sem suavização.

## Validação completa

```powershell
py -3 pipelines\verify_cmap.py workspace\System --output reports\cmap_roundtrip.json
```

O relatório testa `CMAP -> PNG -> CMAP` em memória e exige igualdade byte a
byte. Ele também registra dimensões e contagem de cada valor encontrado nos
mapas, necessária para documentar sua semântica.
