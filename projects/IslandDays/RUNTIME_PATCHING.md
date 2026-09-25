# Island Days — ExeFS, runtime e code.ips

> Referência técnica. Island Days não é um backend suportado pelo Days ModToolkit.

## 1. Por que o ExeFS precisou ser estudado

Mesmo com os 281 XMLs de `script_j` completos, ainda apareciam textos japoneses em:

- choices do Dia 2;
- batalha detalhada;
- prompt diário;
- speaker do prompt;
- nomes de fases;
- finais;
- galeria;
- descrições inferiores;
- Save/Load;
- Batalha Livre.

Isso provou que parte da UI e da lógica textual está embutida no executável.

---

## 2. Build analisado

```text
code.bin comprimido
tamanho: 1.120.648 bytes
SHA-256:
c9e7b22eabc505764086df1001c59063ae6de40423c54baf07ce3b8adeebe151

compressão:
BLZ / Backward LZ77

.code descomprimido
tamanho: 1.961.984 bytes
SHA-256:
82ca029205c72942a1f6e39e26007410f5dc4d34f87aace6a1102405982e3581

base de carregamento observada:
0x00100000
```

O executável original nunca foi incluído nos snapshots públicos.

---

## 3. Fluxo `settext`

Endereços do build analisado:

| Função | VA |
|---|---:|
| loader de Script | `0x00218FC8` |
| file loader | `0x001C219C` |
| parser de comandos | `0x002156C4` |
| handler `settext` | `0x0021658C` |
| busca/pré-processamento de `script_j` | `0x0018D1C4` |
| multibyte → 16 bits | `0x0018D2EC` |
| passo da conversão multibyte | `0x001C9B84` |
| acesso à tabela/locale | `0x001C9E3C` |

Fluxo:

```text
settext
→ linha CP932/SJIS
→ buffer temporário
→ br → 0x0A
→ conversão multibyte
→ buffer 16-bit
→ renderer
```

Offsets observados no objeto:

```text
script_j base: +0xD94
cursor atual:  +0xDB8
índice linha:  +0xDC0
buffer 16-bit: +0xDC6
```

---

## 4. Choices dinâmicas — v0.9.1

O playtest encontrou frases como:

```text
世界とコテージを探索する
刹那とコテージを探索する
乙女とコテージを探索する
心とコテージを探索する
```

Elas não existiam nos 281 XMLs.

Foi localizado um pool UTF-16LE:

```text
offset: 0x185020–0x185582
capacidade: 1.378 bytes
rótulos: 60
referências absolutas: 124
```

O prompt:

```text
何をしようか？
```

aparecia separadamente em:

```text
0x12E8FC
```

O builder de pesquisa:

1. validava o `code.bin` conhecido;
2. descomprimia BLZ em memória;
3. recompunha os 60 rótulos;
4. atualizava 124 ponteiros;
5. mantinha o tamanho do `.code`;
6. gerava apenas `exefs/code.ips`.

Uso final dessa região na v0.9.1:

```text
1.344 / 1.378 bytes
```

Maior rótulo PT-BR:

```text
15 caracteres
```

O primeiro `code.ips` dessa fase tinha 2.528 bytes no build conhecido.

As 60 choices e o prompt foram confirmados in-game no Azahar 2126.1.2.

---

## 5. Abreviações das choices

Para manter o pool dentro da região original, algumas choices usaram siglas curtas.

Casos observados:

```text
Se
Kt
Ko
St
Ot
Hi
Ka
Ai
```

Os rótulos de cabana do caso crítico observado no Dia 2 usaram nomes completos.

A decisão foi conservar o `.code` sem crescimento e evitar alocação nova.

---

## 6. Runtime de batalha — v0.9.2

Outro pool UTF-16LE foi localizado:

```text
0x18670A–0x1868D8
capacidade: 462 bytes
strings: 31
```

Cinco efeitos adicionais foram realocados na sobra do mesmo pool:

```text
貫通 → Perf
対空 → AA
予備 → Res
爆風 → Exp
鈍足 → Lent
```

Uso após repack:

```text
456 / 462 bytes
```

Estado runtime v2:

```text
60 choices
31 strings de batalha
5 efeitos
162 ponteiros absolutos
```

Essa camada foi confirmada visualmente in-game.

---

## 7. Prompt diário e speaker — v0.9.3

Depois da v0.9.2, o prompt ainda mostrava o speaker `誠` e o nameplate visual precisava de correção.

O runtime v3 realocou:

```text
O quê? → 0x12E948
Makoto → 0x12E8FC
```

Para liberar/organizar os slots, uma string local:

```text
map_flag_1_0%d
```

passou a reutilizar uma cópia idêntica já existente em:

```text
0x12F63C
```

Também foram ajustadas três instruções ARM.

Garantias:

- `.code` não cresceu;
- as 60 choices foram preservadas;
- o battle pool foi preservado;
- os 162 ponteiros anteriores permaneceram válidos.

O prompt `Makoto / O quê?` foi confirmado in-game.

---

## 8. Strings residuais — v0.10.1

Depois de Title/Options/Save/Load/Extras estarem traduzidos, o playtest ainda mostrou rodapés e nomes em japonês.

Foi localizada uma tabela UTF-16LE:

```text
0x185582–0x185BEC
90 strings
todas com referências absolutas
```

Cobertura:

- Fase 1–10;
- rótulos especiais de Batalha Livre;
- 21 nomes de finais desbloqueáveis;
- títulos de CG/eventos da galeria;
- descrições inferiores de Extras;
- descrições inferiores de Options;
- mensagens/prompts relacionados a dados.

As traduções PT-BR eram maiores que o pool japonês. Em vez de aumentar o `.code`, o patch usou padding zero validado:

```text
novo pool PT-BR: 0x187060
reserva: 0x2000 bytes
```

Ponteiros:

```text
91 ponteiros residuais
+ 162 anteriores
= 253 ponteiros absolutos
```

Além disso, 11 mensagens locais de Save/Load/Inicialização foram traduzidas in-place.

---

## 9. Últimos residuais — v0.10.2

### Batalha Livre

String:

```text
プレイするステージを選んでください。
```

Local:

```text
0x0DBE4C
```

Tradução:

```text
Selecione a fase.
```

Ela não fazia parte da tabela residual de 90 strings e foi substituída in-place.

### Save concluído

```text
0x11C69C
セーブが完了しました。
→ Jogo salvo.
```

### Delete concluído

```text
0x0DB17C
データを削除しました。
→ Excluído.
```

Todas cabiam nos slots originais em UTF-16LE e não aumentaram o `.code`.

---

## 10. Estado final — runtime v6

```text
60 choices dinâmicas
31 strings de batalha
5 efeitos
90 strings residuais realocadas
14 mensagens locais
253 ponteiros absolutos atualizados
Makoto + O quê? preservados
```

A numeração v6 representa a evolução do formato interno do patch de runtime durante o projeto.

---

## 11. Auditoria final de japonês

Foi feita uma varredura alinhada das strings UTF-16LE do `.code` original.

Método:

1. extrair strings UTF-16LE;
2. filtrar hiragana/katakana/kanji/pontuação japonesa;
3. classificar gameplay/menu vs créditos/charset/identificadores;
4. comparar com pools e patches já conhecidos.

Resultado:

```text
25 frases de gameplay/menu em japonês encontradas
25/25 cobertas pelo patch final
```

Japonês intencionalmente preservado:

- créditos originais;
- nomes de staff/cast;
- tabelas de charset;
- caminhos;
- identificadores internos;
- nomes técnicos de recursos.

Esses itens não foram tratados como residual de localização.

---

## 12. Filosofia do patch

O projeto evitou redistribuir o executável.

Regra:

```text
code.bin original local
      ↓
validação por hash
      ↓
descompressão em memória
      ↓
patches/repoint
      ↓
diff
      ↓
exefs/code.ips
```

Nenhuma etapa pública deve incluir o `code.bin` original.

---

## 13. Cuidados para pesquisa futura

Não reutilize offsets cegamente em outro build.

Os endereços desta página pertencem ao build conhecido com os hashes documentados.

Antes de aplicar qualquer patch:

1. validar hash;
2. confirmar compressão;
3. confirmar tamanho descomprimido;
4. localizar os pools;
5. validar referências;
6. garantir que a saída não cresça de forma não planejada;
7. testar no jogo.

Um patch estruturalmente válido pode ainda falhar semanticamente no runtime.
