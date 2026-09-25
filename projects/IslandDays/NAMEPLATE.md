# Island Days — nameplate, setname e nomes de personagem

> Referência técnica. Island Days não é um backend suportado pelo Days ModToolkit.

## 1. Descoberta principal

O nameplate não usa o mesmo caminho de texto do diálogo principal.

```text
settext → script_j → codec v3 / diálogo
setname → namelist.txt → CP932 fullwidth / pane próprio
```

Tentar tratar os dois caminhos como equivalentes leva a resultados incorretos.

---

## 2. `namelist.txt`

Características confirmadas:

```text
encoding: CP932
EOL: CRLF
linhas: 12
```

Lista PT-BR usada no projeto:

```text
Makoto
Sekai
Kotonoha
Kokoro
Setsuna
Otome
Hikari
Karen
Ai
Garota
Todos
Voz
```

O caminho `setname` usa ASCII fullwidth CP932.

Ele **não** reutiliza o codec v3 de 141 doadores do `settext`.

---

## 3. Primeira correção incompleta — v0.9.2

A primeira hipótese foi aumentar apenas o pane:

```text
common.arc/blyt/name_text.bclyt
70×18 → 112×18
```

O playtest mostrou que `Makoto` ainda aparecia como:

```text
Makot
```

Isso provou que a largura do pane não era a única limitação.

---

## 4. Causa real do truncamento

Duas limitações adicionais foram identificadas:

1. capacidade curta no `txt1`;
2. frame/animação de `name.arc` ainda dimensionados para o original.

Portanto, corrigir somente `common.arc` não bastava.

---

## 5. Solução final — v0.9.3

### `common.arc/blyt/name_text.bclyt`

```text
pane:
70×18 → 112×18

capacidade interna txt1:
12 → 18 bytes
```

### `name.arc/timg/name_frame.bclim`

```text
119×18 → 161×18
```

O frame PT-BR foi reconstruído a partir do original japonês, estendendo o miolo e sem redistribuir asset da referência inglesa.

### `name.arc/blyt/name_frame.bclyt`

```text
X:
-261 → -282

largura:
119 → 161
```

### BCLAN

Também foram ajustados:

```text
name_frame_in.bclan
name_frame_out.bclan
```

para acompanhar o frame ampliado.

---

## 6. Validação

Gates documentados:

```text
12/12 nomes codificáveis
pane: 112 px
buffer: 18 bytes
frame: 161 px
DARC válido
```

Depois do ajuste completo, o playtest confirmou nomes como:

- Makoto;
- Kotonoha;
- Setsuna;

sem truncamento.

---

## 7. Prompt diário — caso especial

Ainda existia um caso em que o speaker `誠` aparecia acima do prompt:

```text
何をしようか？
```

Esse caso não vinha simplesmente de `namelist.txt`.

O runtime v3 tratou os dois elementos no ExeFS:

```text
O quê? → 0x12E948
Makoto → 0x12E8FC
```

Uma cópia de `map_flag_1_0%d` em `0x12F63C` foi reutilizada e três instruções ARM foram ajustadas.

O `.code` manteve o mesmo tamanho.

O resultado `Makoto` acima de `O quê?` foi confirmado in-game.

---

## 8. Relação com a referência inglesa

A referência inglesa já ampliava alguns componentes do nameplate, o que ajudou a indicar a direção da pesquisa.

Mas a solução PT-BR final:

- foi validada contra os arquivos originais;
- reconstruiu o frame a partir do original japonês;
- não depende de copiar o asset inglês;
- documentou a capacidade interna e as animações que também precisavam mudar.

---

## 9. Lição para modders

Um texto truncado em UI de Nintendo 3DS pode envolver mais de uma camada:

```text
texto
+ encoding
+ capacidade do pane
+ dimensão do frame
+ posição
+ animação
```

No caso de Island Days, todas essas camadas precisaram ser consideradas para o nameplate ficar correto.
