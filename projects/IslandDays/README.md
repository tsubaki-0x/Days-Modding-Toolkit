# Island Days — documentação técnica para modders

## Status no Days ModToolkit

> **Island Days não é suportado pelo Days ModToolkit.**
>
> Esta pasta existe somente como **documentação técnica e referência de pesquisa** para modders futuros. O jogo não possui backend, aba de GUI, comandos de CLI, pipeline integrada ou garantia de compatibilidade dentro do toolkit.

Island Days é um título de **Nintendo 3DS** com uma arquitetura muito diferente dos backends atuais do projeto:

```text
School Days HQ / Shiny Days → GPK/STACK
Summer Days                 → CRio
Island Days                 → RomFS/ExeFS de Nintendo 3DS
                              DARC + BCLIM/BCLYT/BCLAN/BCFNT
                              Script/script + Script/script_j
                              .code + code.ips
```

Por esse motivo, a pesquisa de Island Days é preservada aqui como documentação, mas **não foi incorporada ao núcleo do Days ModToolkit**.

A tradução PT-BR e a pipeline pública de diálogos ficam no repositório separado:

**[Days-Series-PTBR — Island Days](https://github.com/tsubaki-0x/Days-Series-PTBR/tree/main/IslandDays)**

---

## 1. Identificação

```text
Jogo: Island Days
Plataforma: Nintendo 3DS
Title ID observado: 0004000000120800
Ambiente principal de teste: Azahar 2126.1.2
Workspace de pesquisa: IslandDays_PTBR_Workspace
Último estado técnico documentado: v0.10.2
```

O projeto de tradução investigou tanto o **RomFS** quanto o **ExeFS** e terminou com uma build local composta por:

```text
romfs/
exefs/
└── code.ips
```

Arquivos originais do jogo, RomFS, ExeFS, `code.bin`, fontes completas e assets proprietários **não devem ser adicionados a este repositório**.

---

## 2. Mapa geral da arquitetura

### RomFS

```text
Script/
├── script/      → lógica/comandos de evento
└── script_j/    → falas, escolhas e textos exibidos

Layout/
└── *.arc        → archives DARC
    ├── BCLIM    → texturas
    ├── BCLYT    → layouts
    ├── BCLAN    → animações
    └── BCFNT    → fonte
```

Inventário consolidado do RomFS estudado:

```text
Script: 563 arquivos
  281 TXT em Script/script/
  282 TXT em Script/script_j/

Layout:
  334 archives DARC válidos
  1.351 recursos internos
  893 BCLIM
  353 BCLYT
  104 BCLAN
  1 BCFNT
```

### ExeFS

O `code.bin` analisado usa BLZ / Backward LZ77. Depois de descomprimido, foram encontradas strings UTF-16LE e tabelas usadas por partes da interface que **não vivem em `script_j`**.

A pesquisa encontrou no ExeFS:

- 60 choices dinâmicas;
- 31 strings de batalha;
- 5 tipos de efeito;
- 90 strings residuais de UI;
- mensagens locais de Save/Load/Inicialização;
- prompt diário e speaker;
- ponteiros absolutos que precisaram ser atualizados;
- textos finais como `Selecione a fase.`, `Jogo salvo.` e `Excluído.`.

O formato distribuível usado pela tradução é `exefs/code.ips`; o `code.bin` original nunca é redistribuído.

---

## 3. Corpus de script

O corpus textual de `Script/script_j` foi alinhado por **caminho + número da linha**, sem fuzzy matching.

Estado consolidado:

```text
282 TXT em script_j
281 arquivos convertidos para XML
19.401 linhas indexadas
15.783 linhas traduzíveis
15.783/15.783 source_jp alinhados
0 divergências de contagem JP ↔ referência
namelist.txt separado: 12 linhas, CP932/CRLF
```

A separação observada é importante:

- `Script/script/` contém comandos como `setname`, `settext`, `setchr`, `setbg`, `playbgm` e `bwait`;
- `Script/script_j/` contém o texto consumido pelo runtime.

A tradução pública usa o japonês original como fonte canônica e a tradução inglesa apenas como referência auxiliar.

Detalhes: **[SCRIPT_PIPELINE.md](./SCRIPT_PIPELINE.md)**.

---

## 4. Encoding e renderer

A pesquisa mostrou que o caminho de diálogo não aceita simplesmente ASCII visível single-byte.

Fluxo observado:

```text
settext
  ↓
linha CP932/Shift_JIS de script_j
  ↓
pré-processamento
  ↓
conversão multibyte
  ↓
buffer 16-bit
  ↓
renderer
```

Pontos confirmados:

- CRLF é estrutural;
- `br` é convertido para U+000A;
- buffer temporário: 140 bytes;
- limite conservador adotado: 136 bytes;
- o primeiro PoC mostrou que ASCII cru visível desaparecia;
- a solução final usa **141 doadores Shift_JIS**:
  - 46 para caracteres PT-BR acentuados;
  - 95 para ASCII imprimível U+0020–U+007E;
- `{br}` é o único controle que produz ASCII cru;
- a BCFNT original já possui os glifos PT-BR necessários.

O layout real do diálogo foi medido pela fonte:

```text
TextBox_00
280 × 54 px
fonte 14 × 18
máximo: 3 linhas
largura segura do projeto: 272 px
payload conservador: 136 bytes
```

O word-wrap usa `CWDH.char_width`, não contagem simples de caracteres.

Detalhes: **[FILE_FORMATS.md](./FILE_FORMATS.md)** e **[SCRIPT_PIPELINE.md](./SCRIPT_PIPELINE.md)**.

---

## 5. Choices

Island Days possui duas classes diferentes de escolhas.

### Choices estáticas

Vivem nos scripts e são detectáveis por blocos `; ●selection N`.

```text
125 blocos selection
286 opções
limite empírico confirmado: 22 caracteres visíveis
108 overflows antes da correção
0 overflows depois da revisão
```

Esse limite é independente da caixa normal de diálogo.

### Choices dinâmicas

As 60 choices dinâmicas não estavam nos 281 XMLs. Elas foram encontradas como UTF-16LE no ExeFS `.code`, com 124 referências absolutas.

Detalhes: **[RUNTIME_PATCHING.md](./RUNTIME_PATCHING.md)**.

---

## 6. UI, HUD e batalha

A interface não está concentrada em um único lugar. Ela mistura:

- BCLIM em archives DARC;
- parâmetros e panes em BCLYT;
- animações BCLAN;
- `namelist.txt`;
- strings UTF-16LE do ExeFS.

A pesquisa cobriu:

- Title;
- Options;
- Save/Load;
- Extras/Omake;
- Window/Day;
- HUD;
- preparação de batalha;
- INFORMATION;
- menu de comandos;
- resultado/MVP;
- pause;
- guide;
- 17 telas de tips;
- Batalha Livre;
- residuais em runtime.

Cobertura visual final documentada:

```text
33 archives
109 BCLIM modificados/reconstruídos
```

Detalhes gerais: **[UI_LAYOUT.md](./UI_LAYOUT.md)**.  
Batalha: **[BATTLE_SYSTEM.md](./BATTLE_SYSTEM.md)**.

---

## 7. Nameplate

O nameplate revelou que `setname` usa um caminho diferente de `settext`.

A solução final exigiu:

```text
namelist.txt: CP932 fullwidth / CRLF / 12 rótulos

common.arc/blyt/name_text.bclyt
  largura: 70 → 112 px
  capacidade txt1: 12 → 18 bytes

name.arc/timg/name_frame.bclim
  119×18 → 161×18

name.arc/blyt/name_frame.bclyt
  X: -261 → -282
  largura: 119 → 161

name_frame_in.bclan / name_frame_out.bclan
  animação ajustada ao frame ampliado
```

Detalhes: **[NAMEPLATE.md](./NAMEPLATE.md)**.

---

## 8. Runtime patch final

A camada runtime evoluiu em várias etapas.

Estado consolidado do runtime v6:

```text
60 choices dinâmicas
31 strings de batalha
5 efeitos
90 strings residuais realocadas
14 mensagens locais
253 ponteiros absolutos atualizados
```

A auditoria final encontrou **25 frases de gameplay/menu em japonês** no `.code` original; todas passaram a ser cobertas pelo patch. O japonês restante no executável foi classificado como créditos, charset ou identificadores técnicos e não foi tratado como texto de gameplay.

Detalhes: **[RUNTIME_PATCHING.md](./RUNTIME_PATCHING.md)**.

---

## 9. Arquivos desta documentação

| Documento | Conteúdo |
|---|---|
| [FILE_FORMATS.md](./FILE_FORMATS.md) | RomFS, ExeFS, DARC, BCLIM, BCLYT, BCLAN, BCFNT, encoding |
| [SCRIPT_PIPELINE.md](./SCRIPT_PIPELINE.md) | script_j, XML, alinhamento, codec, wrap, static choices |
| [UI_LAYOUT.md](./UI_LAYOUT.md) | inventário, UI geral, DARC/BCLIM e reconstrução |
| [RUNTIME_PATCHING.md](./RUNTIME_PATCHING.md) | `.code`, pools UTF-16LE, ponteiros, code.ips, residuais |
| [BATTLE_SYSTEM.md](./BATTLE_SYSTEM.md) | HUD, batalha, INFORMATION, results, pause e tips |
| [NAMEPLATE.md](./NAMEPLATE.md) | `setname`, namelist, pane, frame e animação |
| [RESEARCH_LOG.md](./RESEARCH_LOG.md) | cronologia completa das descobertas e correções |

---

## 10. O que NÃO faz parte do Days ModToolkit

Esta pasta **não adiciona**:

- parser de Island Days ao toolkit;
- writer/repacker de DARC na GUI;
- suporte a BCLIM/BCLYT/BCLAN/BCFNT na GUI;
- backend de `script_j`;
- editor de `.code`;
- gerador de `code.ips`;
- autodetecção de Island Days;
- tema de GUI;
- comandos CLI oficiais;
- garantia de funcionamento com qualquer dump/revisão.

As ferramentas usadas durante o projeto de tradução pertenciam ao workspace de pesquisa de Island Days. Esta pasta preserva **o conhecimento técnico**, não transforma o jogo em um backend suportado.

---

## 11. Princípios para pesquisa futura

Um modder que continuar esta investigação deve manter as mesmas regras de segurança:

1. preservar RomFS/ExeFS originais;
2. nunca trabalhar sobre o único backup;
3. tratar JP original como baseline;
4. preservar CP932/CRLF dos scripts;
5. validar DARC/BCLIM após qualquer rebuild;
6. medir texto por CWDH/BCLYT;
7. distinguir `settext`, `setname` e strings do ExeFS;
8. nunca redistribuir `code.bin` original;
9. gerar patches diferenciais como `code.ips`;
10. confirmar alterações in-game, porque validação estrutural não substitui teste no runtime.

---

## 12. Créditos da pesquisa

**SUZU / tsubaki-0x** — direção da tradução PT-BR, testes, pesquisa, documentação e validação in-game.  
**OpenAI / Google Gemini** — apoio em análise, debugging, scripts, tradução e documentação.  
**Cristonimus / islandays-translation** — referência inglesa estudada durante a fase inicial; usada apenas como apoio, não como fonte canônica.  
**0verflow** — desenvolvimento de Island Days e propriedade intelectual original.

## Aviso legal

Esta documentação descreve engenharia reversa e observações obtidas sobre uma cópia legal do jogo.

Não incluir neste repositório ROM, CIA, CXI, RomFS, ExeFS, `code.bin`, fonte completa, scripts originais ou assets proprietários de Island Days.
