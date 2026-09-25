# Island Days — sistema de batalha e HUD

> Referência técnica. Island Days não é um backend suportado pelo Days ModToolkit.

## 1. Por que batalha virou uma área própria

Depois da tradução do corpus `script_j`, vários rótulos de batalha permaneceram em japonês porque a interface de batalha combina:

- BCLIM;
- BCLYT;
- `namelist.txt`;
- strings UTF-16LE do ExeFS;
- valores dinâmicos.

Por isso, a batalha foi tratada em fases independentes.

---

## 2. `battle_low_1.arc`

HUD base.

Traduções documentadas:

```text
食料         → ALIM.
Day          → Dia
st/nd/rd/th  → º
バックログ   → Hist.
オート       → Auto
オートモード中 → Modo auto
ウェーブ     → Onda:
敵           → Inim:
```

O archive da fase inicial manteve 312.872 bytes e somente os BCLIM alvo diferiam.

---

## 3. `battle_low_2.arc`

Labels:

```text
活躍   → Ação:
武器   → Arma:
攻撃   → ATQ:
速度   → Vel.
範囲   → Alc.
特殊   → Esp.
必殺技 → Golpe:
```

`l_name.bclim` contém atlas com 9 nomes completos romanizados.

---

## 4. `battle_jyunbi.arc`

Preparação:

```text
バトル開始     → Iniciar
ウェーブ数     → Ondas:
マップイメージ → Mapa
セーブ         → Salvar
情報           → Info
```

Na fase residual também foi tratado:

```text
戻る → Voltar
```

Esse `back.bclim` separado apareceu no fluxo de Batalha Livre.

---

## 5. `battle_window.arc`

```text
戻る → Voltar
```

---

## 6. `info.arc`

INFORMATION/status:

```text
体力   → HP:
信頼   → Conf.:
愛情   → Afeto:
不満   → Insat.:
攻撃   → ATQ:
範囲   → Alc.:
ランク → Rank:
速度   → Vel.:
特性   → Traço:
必殺技 → Golpe:
武器   → Arma:
切り替え → Trocar
```

`info_l_name.bclim` contém atlas com 9 nomes completos.

---

## 7. `battle_com_menu.arc`

```text
レベルアップ → Subir Nv.
武器チェンジ → Trocar Arma
必殺技       → Golpe
撤退         → Recuar
```

---

## 8. Resultado / MVP

### `result_up.arc`

```text
奪われた食糧 → Alim. roub.
消費BP       → BP gasto
活躍度       → Desemp.
```

Também inclui lista de nomes.

### `result_mvp.arc`

Inclui nomes completos do MVP em alfabeto latino.

---

## 9. Guide

`guide.arc`:

```text
Y:セーブ X:情報
→ Y:Salvar X:Info
```

---

## 10. Pause

`battle_pause.arc`:

```text
タイトルに戻る   → Voltar ao título
リトライ         → Repetir
再開する         → Continuar
バトルスキップ   → Pular batalha
```

---

## 11. Tips

Archives:

```text
tips00.arc ... tips16.arc
```

Cada tela principal foi tratada como BCLIM 400×240.

Cobertura:

1. Regras do jogo
2. Posicionar unidades
3. Subir de nível
4. Trocar arma
5. Tipos de arma
6. Golpe
7. Recuar
8. Inimigo: Rato
9. Inimigo: Cobra
10. Inimigo: Cão
11. Inimigo: Macaco
12. Inimigo: Corvo
13. Inimigo: Toupeira
14. Inimigo: Javali
15. Inimigo: Gato-selvagem
16. Inimigo: Lagarto gigante
17. Inimigo: Urso

Estratégia visual:

- preservar moldura;
- preservar logo;
- preservar flores;
- preservar screenshots;
- preservar sprites;
- apagar apenas área textual necessária;
- redesenhar PT-BR;
- manter DARC válido.

---

## 12. Strings de batalha no ExeFS

Nem tudo era textura.

Pool encontrado:

```text
0x18670A–0x1868D8
31 strings
462 bytes
```

Cinco efeitos adicionais:

```text
貫通 → Perf
対空 → AA
予備 → Res
爆風 → Exp
鈍足 → Lent
```

Uso final:

```text
456 / 462 bytes
```

Na v0.9.2, o runtime totalizava:

```text
60 choices
31 battle strings
5 effects
162 pointers
```

A camada de batalha runtime foi confirmada in-game.

---

## 13. Fases de cobertura

### v0.9.0

Primeiro HUD.

### v0.9.2

```text
4 archives
18 BCLIM
```

### v0.9.3

```text
27 archives
62 BCLIM
17 tips
```

Incluiu preparação, INFORMATION, power-up, result/MVP, guide e pause.

### v0.10.0/v0.10.1

A interface geral elevou o builder para:

```text
33 archives
109 BCLIM
```

Esse total já inclui UI fora da batalha.

---

## 14. Archives raros revisados

Foram auditados:

```text
battle_start.arc
battle_clear.arc
battle_defeat.arc
battle_speed.arc
battle_unit_menu.arc
battle_weapon_menu.arc
wave.arc
battle_cutin_1.arc ... battle_cutin_9.arc
```

Nos recursos visualmente auditados, não havia rótulos japoneses adicionais relevantes que exigissem outra tradução rasterizada.

---

## 15. Batalha Livre e runtime residual

O playtest final encontrou a descrição:

```text
プレイするステージを選んでください。
```

no `.code` em:

```text
0x0DBE4C
```

Tradução in-place:

```text
Selecione a fase.
```

Esse caso é importante porque prova novamente que um texto visualmente associado à batalha pode não estar no DARC correspondente.

---

## 16. Conclusão para modders

Para modificar batalha de Island Days, trate como um sistema composto:

```text
BCLIM     → labels rasterizados
BCLYT     → layouts
namelist  → nomes
.code     → valores/strings dinâmicas
script_j  → texto narrativo e choices estáticas
```

Não há um único archive que concentre toda a UI de batalha.
