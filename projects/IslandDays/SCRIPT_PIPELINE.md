# Island Days — pipeline de script e texto

> Referência técnica. Esta pipeline não está integrada ao Days ModToolkit.

## 1. Separação entre lógica e texto

O RomFS observado possui:

```text
Script/script/    → 281 TXT de lógica
Script/script_j/  → 282 TXT de texto
```

Comandos observados em `script/`:

- `setname`
- `settext`
- `setchr`
- `setbg`
- `playbgm`
- `bwait`

A maior parte da tradução textual foi concentrada em `script_j`.

---

## 2. Organização de `script_j`

Distribuição documentada:

| Diretório | TXT |
|---|---:|
| `00Common` | 50 |
| `01SK` | 21 |
| `02KT` | 25 |
| `03KK` | 21 |
| `04ST` | 21 |
| `05OT` | 21 |
| `06HK` | 21 |
| `07KR` | 21 |
| `08AI` | 21 |
| `09Battle` | 29 |
| `10morning` | 29 |
| raiz | 2 |

Na raiz:

```text
ev_pr000.txt
namelist.txt
```

`namelist.txt` é tratado separadamente porque serve ao caminho `setname`.

---

## 3. Alinhamento JP ↔ referência

Todos os 282 caminhos de `script_j` do original também existiam na referência inglesa e tinham a mesma contagem de linhas.

Isso permitiu alinhamento determinístico por:

```text
caminho + número da linha
```

sem fuzzy matching.

Estado do corpus:

```text
281 XMLs de tradução
19.401 linhas totais
15.783 linhas traduzíveis
15.783/15.783 source_jp alinhados
0 divergências de contagem
```

Campos usados no XML mestre:

```xml
<source_jp>...</source_jp>
<reference_en>...</reference_en>
<translation_ptbr>...</translation_ptbr>
```

Regra linguística:

1. japonês original = fonte canônica;
2. inglês = apoio;
3. PT-BR = único campo editável.

A referência inglesa era machine translation e não era tratada como autoridade semântica.

---

## 4. Linhas técnicas e integridade

O pipeline preservava:

- números de linha;
- caminho do arquivo;
- JP original;
- EN de referência;
- hashes por entrada em batches;
- comentários/linhas técnicas;
- CRLF.

O merge oficial recusava batches stale e escrevia somente `translation_ptbr`.

Originais nunca eram sobrescritos.

---

## 5. `settext` e fluxo runtime

No build analisado, `settext N`:

1. converte `N` para índice zero-based;
2. busca a linha em `script_j`;
3. usa CRLF como delimitador estrutural;
4. copia a linha para um buffer temporário;
5. converte `br` em `0x0A`;
6. converte multibyte para unidades de 16 bits;
7. envia o resultado ao renderer.

Buffer temporário:

```text
140 bytes
```

Limite conservador adotado:

```text
136 bytes de payload
```

O encoder deve falhar se o texto exceder o limite; truncamento silencioso não é aceitável.

---

## 6. Controle `br`

O corpus japonês continha 1.238 ocorrências de `br` em 1.187 linhas.

A semântica foi confirmada no runtime:

```text
br → 0x0A → U+000A → quebra visual
```

Existe uma particularidade importante: o pré-processador reconhece o primeiro byte ASCII `b` (`0x62`) e consome dois bytes.

Por isso, o codec final evita ASCII visível cru e reserva o par `br` para o controle estrutural.

Na camada editorial, a convenção usada foi:

```text
{br}
```

---

## 7. Por que ASCII cru falhou

O primeiro caminho validou os acentos via doadores Shift_JIS, mas uma tentativa posterior de usar ASCII single-byte normal produziu um resultado diagnóstico:

- letras ASCII desapareceram;
- espaços/pontuação ASCII desapareceram;
- caracteres enviados pelo caminho multibyte continuaram aparecendo.

Conclusão:

> o renderer de diálogo precisa receber os caracteres visíveis pelo caminho multibyte validado.

---

## 8. Plano v3 — 141 doadores

A BCFNT já possuía os glifos necessários.

A solução final reservou codepoints CJK válidos em Shift_JIS, ausentes do corpus original, e redirecionou seus CMAPs para glyphs já existentes.

```text
46 doadores → acentos PT-BR
95 doadores → ASCII imprimível U+0020–U+007E
141 doadores no total
```

Fluxo:

```text
caractere PT-BR
   ↓
codepoint doador Shift_JIS
   ↓
conversão multibyte original
   ↓
codepoint doador em 16 bits
   ↓
CMAP redirecionado
   ↓
glyph PT-BR/ASCII proporcional
```

A BCFNT mantém o mesmo tamanho.

`{br}` é o único ASCII cru permitido no payload.

O PoC v3 foi confirmado in-game no Azahar 2126.1.2.

---

## 9. Métricas de layout

`dialog_text.bclyt`:

```text
TextBox_00
280×54
fonte 14×18
3 linhas
```

Margem conservadora:

```text
280 - 8 = 272 px úteis
```

O wrapper usa `CWDH.char_width`.

Regras de produção:

- máximo 3 linhas;
- cada linha <= 272 px;
- payload <= 136 bytes;
- sem CR/LF literal no campo editorial;
- `{br}` para quebra;
- sem `errors=replace`;
- todos os caracteres precisam ser representáveis pelo plano.

---

## 10. Batches

O primeiro arquivo usado como prova de produção foi `ev_pr000.xml`:

```text
1.244 textos
13 lotes
12 × 100
1 × 44
```

O objetivo dos batches era permitir tradução auditável sem perder o vínculo com o XML mestre.

Fluxo do workspace de pesquisa:

```text
JP original
  ↓
XML mestre
  ↓
batch
  ↓
translation_ptbr
  ↓
merge
  ↓
validação
  ↓
wrap CWDH/BCLYT
  ↓
codec v3
  ↓
TXT CP932/CRLF
  ↓
RomFS overlay
```

Build parcial podia usar japonês original como fallback nas linhas pendentes.

Build final exigia tudo preenchido.

---

## 11. Tradução completa

Estado final do corpus principal:

```text
281/281 XMLs completos
15.783/15.783 traduções
0 pendências
0 erros
0 avisos no gate final
```

A revisão contextual final alterou 413 entradas em 161 XMLs depois do primeiro baseline tecnicamente limpo.

---

## 12. Choices estáticas

Blocos de choice são identificáveis por:

```text
; ●selection N
```

As N linhas `kind=text` seguintes são opções.

Inventário:

```text
125 blocos
286 opções
```

Playtest revelou um limite próprio:

```text
máximo empírico: 22 caracteres visíveis
≈ 44 bytes no codec v3
```

Antes da correção:

```text
108 opções > 22 caracteres
```

Depois:

```text
286/286 válidas
max = 22
overflow = 0
```

Esse gate é independente do limite normal de diálogo.

---

## 13. Choices dinâmicas não pertencem a esta pipeline

O fato de `script_j` estar 100% traduzido não eliminou escolhas em japonês no Dia 2.

Isso levou à descoberta de **60 choices dinâmicas no ExeFS**.

Portanto:

```text
choices estáticas → script_j
choices dinâmicas → .code / ExeFS
```

Veja [RUNTIME_PATCHING.md](./RUNTIME_PATCHING.md).

---

## 14. Round-trip e pipeline pública

Depois da conclusão do projeto, uma pipeline pública de diálogo foi separada no repositório Days-Series-PTBR.

Ela foi validada com:

```text
TXT original
→ XML
→ TXT reconstruído
→ 281/281 scripts byte-idênticos
```

e também com teste real:

```text
XML com tradução
→ RomFS parcial
→ Azahar
→ texto PT-BR exibido in-game
```

Essa pipeline pública é propositalmente limitada ao **diálogo/script**. Ela não reconstrói automaticamente toda a UI, runtime ou `code.ips`.

---

## 15. Nota para modders futuros

Não suponha que “tradução completa de script” significa “tradução completa do jogo”.

Island Days distribui texto entre:

```text
script_j
namelist.txt
BCLIM
BCLYT
.code UTF-16LE
```

O projeto só chegou à cobertura total depois de testar cada camada separadamente.
