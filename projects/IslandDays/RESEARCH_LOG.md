# Island Days — research log técnico

> Registro cronológico condensado da engenharia reversa usada no projeto PT-BR. Island Days não é um backend suportado pelo Days ModToolkit.

## v0.1.0 — workspace inicial

Objetivo: criar uma raiz única para a investigação.

Foi definido um workspace cumulativo com áreas separadas para:

- originais;
- referência inglesa;
- tradução;
- layout;
- ferramentas;
- builds;
- relatórios;
- testes;
- documentação.

`ev_pr000` foi escolhido como futuro proof of concept.

---

## v0.2.0 — referência inglesa integrada

Projeto estudado:

```text
Cristonimus/islandays-translation
```

Descobertas:

- Title ID `0004000000120800`;
- 282 TXT em `script_j`;
- 281 XMLs preparados;
- 19.401 linhas;
- 15.783 traduzíveis;
- `common.arc`, `name.arc`, `title.arc`;
- separação entre `script` e `script_j`;
- encoder inglês incompatível com PT-BR sem adaptação.

A referência inglesa foi classificada como apoio, não como fonte canônica.

---

## v0.2.1/v0.2.2 — documentação e Git byte-safe

A documentação passou a fazer parte formal do projeto.

Também foi adotado:

```text
core.autocrlf=false
```

para impedir normalização acidental dos TXT CP932/CRLF.

Originais e builds locais ficaram fora dos snapshots públicos.

---

## v0.3.0 — DARC / BCLIM / BCFNT

Foram criadas ferramentas de investigação de archive/layout.

Resultados:

- `common.arc`, `name.arc`, `title.arc` reconhecidos como DARC;
- BCLIM, BCLYT, BCLAN e BCFNT identificados;
- 13 BCLIM da referência fizeram round-trip byte-idêntico;
- `sample.bcfnt` possui 9.943 codepoints mapeados;
- acentos PT-BR já existem na fonte.

Mudança de hipótese:

> o problema dos acentos não era ausência de glyph; era o caminho de encoding/runtime.

---

## v0.4.0 — original japonês integrado

Inventário:

```text
563 arquivos de Script
334 archives de Layout
1.351 recursos internos
```

Foi confirmado:

- 282 caminhos JP ↔ EN idênticos em `script_j`;
- mesma contagem de linhas;
- CP932/CRLF;
- alinhamento determinístico;
- `namelist.txt` com 12 linhas;
- referência inglesa alterava apenas três archives de Layout.

---

## v0.5.0 — ExeFS e primeiro plano de encoding

O `code.bin` foi analisado localmente.

Descobertas:

- BLZ / Backward LZ77;
- `script_j` lido como multibyte/SJIS;
- conversão para buffer 16-bit;
- CRLF estrutural;
- `br` convertido para U+000A;
- buffer temporário de 140 bytes;
- limite conservador de 136 bytes.

Primeira estratégia:

- usar 46 codepoints CJK doadores;
- remapear CMAP para glyphs PT-BR existentes;
- preservar `code.bin`.

---

## v0.6.0 — primeiro PoC in-game e problema de largura

No Azahar 2126.1.2:

- acentos por doadores funcionaram;
- `{br}` funcionou;
- `code.bin` permaneceu intacto.

Problema:

- fullwidth gerava espaçamento excessivo;
- o wrap nativo podia partir palavras.

Foi iniciada a medição por CWDH/BCLYT.

---

## v0.6.1 — ASCII cru falha

Uma tentativa de usar ASCII normal de um byte falhou visualmente:

- letras desapareceram;
- espaços desapareceram;
- pontuação desapareceu;
- acentos/doadores multibyte continuaram aparecendo.

Essa falha foi decisiva.

Nova solução:

```text
46 doadores de acentos
+ 95 doadores para ASCII U+0020–U+007E
= 141 doadores
```

`{br}` permaneceu como único ASCII cru.

---

## v0.6.2 — baseline textual confirmada

Terceiro PoC no Azahar:

- letras visíveis;
- espaços visíveis;
- dígitos;
- pontuação;
- `b` minúsculo;
- acentos;
- 3 linhas;
- sem quebra de palavra;
- nenhum CJK doador visível.

A estratégia v3 virou baseline de produção.

---

## v0.7.0 — pipeline de produção

Foi criado fluxo auditável:

```text
JP
→ XML master
→ batches
→ tradução
→ merge
→ validação
→ wrap
→ codec
→ RomFS parcial/final
```

`ev_pr000`:

```text
1.244 textos
13 lotes
```

---

## v0.8.0 — tradução principal completa

Resultado:

```text
15.783/15.783
281/281 XMLs
0 pendências
0 erros
0 avisos
```

Depois do baseline técnico, 413 entradas em 161 XMLs ainda receberam revisão contextual.

---

## v0.8.1 — limite próprio das choices

Playtest revelou truncamento acima de 22 caracteres.

Inventário:

```text
125 blocos
286 opções
108 overflows iniciais
0 overflows finais
```

Conclusão:

> choices estáticas possuem gate próprio, separado do diálogo.

---

## v0.9.0 — primeira fase de UI/HUD

Inventário total:

```text
334 DARC
1.351 recursos
893 BCLIM
353 BCLYT
104 BCLAN
1 BCFNT
219 candidatos de UI/HUD
```

`battle_low_1.arc` virou o primeiro alvo visual.

Também foi tentada a primeira integração de nomes.

---

## v0.9.1 — choices dinâmicas no ExeFS

Mesmo com `script_j` completo, o Dia 2 ainda mostrava choices JP.

Foi localizado:

```text
0x185020–0x185582
60 labels UTF-16LE
124 referências
```

Prompt separado:

```text
0x12E8FC
何をしようか？
```

Foi criado `code.ips` diferencial.

As 60 choices e `O quê?` foram confirmados in-game.

---

## v0.9.2 — nameplate e batalha detalhada

Novas descobertas:

- `setname` usa `namelist.txt` fullwidth;
- `name_text.bclyt` original = 70×18;
- `battle_low_2` contém labels/status;
- `battle_jyunbi` contém Save/Info;
- `battle_window` contém Return;
- `.code` contém 31 strings de batalha + 5 efeitos.

Estado:

```text
4 archives / 18 BCLIM
runtime: 60 choices + 31 battle + 5 effects
162 pointers
```

---

## v0.9.3 — correção real do nameplate

Playtest mostrou:

```text
Makoto → Makot
speaker diário → 誠
```

A hipótese “aumentar só o pane” foi descartada.

Correção:

```text
name pane: 70→112
txt1: 12→18 bytes
frame: 119→161
BCLYT/BCLAN ajustados
speaker/prompt realocados no .code
```

UI de batalha:

```text
27 archives
62 BCLIM
17 tips
```

---

## v0.10.0 — interface geral

Entraram:

- Title;
- Options;
- Save/Load;
- Extras;
- Window;
- Day.

Cobertura:

```text
33 archives
108 BCLIM
```

Playtest confirmou nameplate, speaker, atalhos, INFORMATION, battle result/MVP e pause.

---

## v0.10.1 — residuais do runtime

A interface parecia pronta, mas o playtest revelou textos ainda fora dos BCLIM.

Tabela residual:

```text
0x185582–0x185BEC
90 strings
```

Como o PT-BR era maior:

```text
novo pool em padding zero:
0x187060
0x2000 bytes reservados
```

Ponteiros:

```text
91 novos
253 totais
```

Também:

- 11 mensagens locais in-place;
- `back.bclim` da Batalha Livre → `Voltar`;
- total visual → 33 archives / 109 BCLIM.

---

## v0.10.2 — último residual e auditoria final

Playtest encontrou:

```text
プレイするステージを選んでください。
```

em:

```text
0x0DBE4C
```

Tradução:

```text
Selecione a fase.
```

Depois, auditoria integral de UTF-16LE encontrou ainda:

```text
0x11C69C
セーブが完了しました。
→ Jogo salvo.

0x0DB17C
データを削除しました。
→ Excluído.
```

Estado runtime final:

```text
formato v6
60 choices
31 battle
5 effects
90 residuals
14 local messages
253 pointers
```

A auditoria classificou 25 frases japonesas de gameplay/menu no executável original e todas ficaram cobertas.

O japonês restante pertencia a créditos, charset e identificadores técnicos.

---

## Conclusão da pesquisa

A investigação terminou mostrando que Island Days distribui texto por várias camadas:

```text
script_j
namelist.txt
BCLIM
BCLYT
BCLAN
BCFNT
.code UTF-16LE
```

Nenhuma dessas camadas, isoladamente, representa “todo o texto do jogo”.

Essa é a principal razão para a documentação ser preservada mesmo sem integrar Island Days ao Days ModToolkit.
