# Island Days — formatos e arquitetura de arquivos

> Documento de referência. Island Days não é um backend suportado pelo Days ModToolkit.

## 1. Visão geral

A pesquisa separou o jogo em duas áreas principais:

```text
RomFS
├── Script/
│   ├── script/
│   └── script_j/
└── Layout/
    └── *.arc (DARC)

ExeFS
└── code.bin
    └── .code descomprimido
        └── strings/tabelas UTF-16LE
```

O Title ID observado no projeto foi:

```text
0004000000120800
```

---

## 2. RomFS / Script

Inventário integrado:

```text
Script total: 563 arquivos
Script/script/:   281 TXT
Script/script_j/: 282 TXT
```

### `Script/script/`

Contém lógica/comandos de evento. Comandos observados:

- `setname`
- `settext`
- `setchr`
- `setbg`
- `playbgm`
- `bwait`

### `Script/script_j/`

Contém falas, choices e outros textos exibidos.

Todos os 282 TXT estudados são CP932/CRLF.

`namelist.txt` também é CP932/CRLF, possui 12 linhas e usa um caminho de renderização diferente do diálogo principal.

---

## 3. DARC

O `Layout/` original estudado contém:

```text
334 archives .arc
334/334 reconhecidos como DARC válidos
1.351 recursos internos
```

A ferramenta de pesquisa validou e extraiu esses archives sem sobrescrever os originais.

Três archives foram especialmente estudados no início:

| Archive | Entradas | Arquivos internos |
|---|---:|---:|
| `common.arc` | 35 | 29 |
| `name.arc` | 9 | 4 |
| `title.arc` | 15 | 11 |

Tipos internos observados:

```text
BCLIM → textura
BCLYT → layout
BCLAN → animação
BCFNT → fonte
```

A pesquisa pública do workspace não formalizou uma especificação binária completa de DARC além do parser/rebuilder validado; portanto, esta documentação evita inventar campos não registrados nos relatórios.

---

## 4. BCLIM

Inventário total:

```text
893 BCLIM
```

Formatos exercitados pela ferramenta de pesquisa:

- L8
- RGB565
- RGBA5551
- RGBA4
- RGBA8

Regras usadas no rebuild:

- preservar dimensões lógicas;
- preservar metadados/footer;
- preservar padding;
- reconstruir a partir do archive original;
- validar o DARC de saída.

Na fase inicial, 13/13 BCLIM da referência inglesa fizeram round-trip decode → encode **byte-idêntico**.

Exemplos de recursos estudados:

```text
common.arc/timg/dialog.bclim   → 304×96 RGBA5551
name.arc/timg/name_frame.bclim → frame do nameplate
title.arc/timg/newgame.bclim   → 102×18 RGBA4
title.arc/timg/continu.bclim    → 102×18 RGBA4
title.arc/timg/option.bclim     → 102×18 RGBA4
title.arc/timg/omake.bclim      → 102×18 RGBA4
```

---

## 5. BCLYT

Inventário total:

```text
353 BCLYT
```

BCLYT controla panes, posições, dimensões e capacidades usadas por partes da UI.

### Caixa de diálogo

`common.arc/blyt/dialog_text.bclyt` possui o pane `txt1` `TextBox_00`:

```text
largura: 280.0
altura: 54.0
font size X: 14.0
font size Y: 18.0
capacidade derivada: 3 linhas
largura segura adotada: 272 px
```

### Nameplate

`common.arc/blyt/name_text.bclyt`:

```text
original: 70×18
PT-BR:    112×18
capacidade txt1: 12 → 18 bytes
```

`name.arc/blyt/name_frame.bclyt`:

```text
X:       -261 → -282
largura:  119 → 161
```

---

## 6. BCLAN

Inventário total:

```text
104 BCLAN
```

BCLAN é usado para animações de layout.

No nameplate, os recursos relevantes são:

```text
name.arc/anim/name_frame_in.bclan
name.arc/anim/name_frame_out.bclan
```

Eles precisaram ser ajustados quando o frame foi ampliado de 119 px para 161 px.

---

## 7. BCFNT

O arquivo de fonte observado é:

```text
common.arc/font/sample.bcfnt
```

Inventário/auditoria:

```text
1 BCFNT
42 blocos CMAP
9.943 codepoints mapeados
CWDH cobrindo glyph indices 0–9942
FINF nominal: 18×14
```

A BCFNT original e a BCFNT da referência inglesa eram byte-idênticas.

O intervalo U+00A0–U+0101 está coberto e os acentos PT-BR auditados já possuem glifos.

Consequência importante:

> o problema não era desenhar novos acentos; era fazer o runtime chegar aos codepoints corretos.

### CWDH

Cada entrada CWDH estudada possui:

- `left` (s8);
- `glyph_width` (u8);
- `char_width` (u8).

O wrapper usa `char_width` como avanço proporcional.

---

## 8. CP932 / Shift_JIS

Os scripts game-ready são byte-sensíveis.

Regras confirmadas:

- `script_j` usa CP932/Shift_JIS;
- EOL é CRLF;
- o runtime procura `0x0D` e avança dois bytes;
- `br` é um controle estrutural convertido para LF/U+000A;
- normalização automática de EOL deve ser evitada.

No workspace de pesquisa, arquivos game-ready eram tratados como bytes e o Git local usava `core.autocrlf=false`.

---

## 9. ExeFS / `code.bin`

Build analisado:

```text
code.bin comprimido:
1.120.648 bytes
SHA-256:
c9e7b22eabc505764086df1001c59063ae6de40423c54baf07ce3b8adeebe151

compressão:
BLZ / Backward LZ77

.code descomprimido:
1.961.984 bytes
SHA-256:
82ca029205c72942a1f6e39e26007410f5dc4d34f87aace6a1102405982e3581

base de carregamento observada:
0x00100000
```

Endereços documentados no build estudado:

| Função/estrutura | VA |
|---|---:|
| loader de Script | `0x00218FC8` |
| file loader | `0x001C219C` |
| parser de comandos | `0x002156C4` |
| handler `settext` | `0x0021658C` |
| busca/pré-processamento `script_j` | `0x0018D1C4` |
| multibyte → 16 bits | `0x0018D2EC` |
| passo da conversão multibyte | `0x001C9B84` |
| acesso a tabela/locale | `0x001C9E3C` |

Offsets observados no objeto de evento:

```text
script_j base: +0xD94
cursor atual:  +0xDB8
índice linha:  +0xDC0
buffer 16-bit: +0xDC6
```

---

## 10. Strings UTF-16LE no runtime

Alguns textos da UI não vêm de `script_j`.

Foram encontrados no `.code` descomprimido:

- choices dinâmicas;
- strings de batalha;
- efeitos;
- nomes de fases/finais/galeria;
- descrições inferiores;
- mensagens de dados;
- prompt/speaker diário.

Esses textos foram tratados por patch diferencial e distribuídos como:

```text
exefs/code.ips
```

O `code.bin` original nunca deve ser distribuído.

Detalhes: [RUNTIME_PATCHING.md](./RUNTIME_PATCHING.md).

---

## 11. Build local observado

O pipeline de pesquisa produzia localmente:

```text
07_BUILD/PTBR_PRODUCTION/
├── romfs/
└── exefs/
    └── code.ips
```

Essa árvore é uma saída de pesquisa/tradução, **não um recurso do Days ModToolkit**.

---

## 12. Resumo para modders

Ao investigar Island Days, não trate tudo como “texto do script”.

```text
script_j      → diálogo/choices estáticas
namelist.txt  → nameplate / setname
BCLIM         → texto rasterizado da UI
BCLYT         → panes/dimensões/capacidades
BCLAN         → animações
BCFNT         → glyphs/CMAP/CWDH
.code         → choices dinâmicas + runtime UI
```

Essa separação foi uma das descobertas centrais do projeto.
