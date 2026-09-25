# Island Days — UI, layout e recursos visuais

> Referência técnica. Island Days não é um backend suportado pelo Days ModToolkit.

## 1. Inventário do Layout

O RomFS original estudado continha:

```text
334 archives DARC
1.351 recursos internos
893 BCLIM
353 BCLYT
104 BCLAN
1 BCFNT
219 texturas candidatas de UI/HUD
```

A heurística de 219 candidatos serviu para localizar elementos com texto; não significa que todos precisaram ser modificados.

---

## 2. Referência inglesa e baseline original

A referência inglesa substituía apenas três archives:

```text
common.arc
name.arc
title.arc
```

Comparação com o original:

### `common.arc`

- 29 arquivos internos;
- 27/29 byte-idênticos;
- alterações da referência concentradas em:
  - `blyt/name_text.bclyt`;
  - `blyt/window_text.bclyt`;
- `font/sample.bcfnt` byte-idêntica ao original.

### `name.arc`

- 4/4 recursos internos modificados pela referência;
- frame de nome alterado de 119×18 para 161×18.

### `title.arc`

- 5/11 recursos internos modificados;
- texturas como NEW GAME/LOAD/OPTION/OMAKE eram texto rasterizado em BCLIM.

Essa comparação mostrou que muita UI de Island Days é imagem, enquanto outras partes dependem de layout e runtime.

---

## 3. `common.arc`

Recursos relevantes observados:

```text
anim/dialog_in.bclan
anim/dialog_out.bclan
blyt/dialog.bclyt
blyt/dialog_text.bclyt
blyt/name_text.bclyt
blyt/window_text.bclyt
blyt/info_text.bclyt
blyt/log_text.bclyt
blyt/omake_text.bclyt
blyt/save_load_text.bclyt
blyt/story_sentaku_text.bclyt
font/sample.bcfnt
timg/dialog.bclim
```

O archive também contém layouts numéricos e de batalha reutilizados por diversas telas.

---

## 4. `name.arc`

Estrutura documentada:

```text
anim/name_frame_in.bclan
anim/name_frame_out.bclan
blyt/name_frame.bclyt
timg/name_frame.bclim
```

O archive é pequeno, mas foi essencial para resolver o truncamento do nameplate.

Veja [NAMEPLATE.md](./NAMEPLATE.md).

---

## 5. `title.arc`

Recursos observados:

```text
blyt/tittle.bclyt
timg/newgame.bclim
timg/continu.bclim
timg/option.bclim
timg/omake.bclim
timg/p_cursor.bclim
timg/tittle.bclim
timg/t_bg.bclim
timg/t_frame.bclim
timg/t_waku.bclim
```

Tradução final do menu principal:

```text
最初から     → NOVO JOGO
続きから     → CONTINUAR
オプション   → OPÇÕES
おまけモード → EXTRAS
```

---

## 6. Rebuild BCLIM

O pipeline de pesquisa reconstruía BCLIM localmente a partir dos assets do próprio usuário.

Garantias adotadas:

- mesmas dimensões;
- mesmo formato;
- mesmo tamanho quando exigido pelo fluxo;
- metadados preservados;
- DARC final validado;
- nenhum archive original redistribuído.

Na fase inicial, 13/13 BCLIM de referência fizeram round-trip byte-idêntico.

O editor visual usou Pillow quando necessário, preservando arte, sprites, screenshots e regiões não textuais.

---

## 7. Fases da UI/HUD

### Fase 1 — v0.9.0

Primeiro archive traduzido:

```text
battle_low_1.arc
```

Primeiros alvos:

- 食料 → `ALIM.`;
- Day → `Dia`;
- st/nd/rd/th → `º`;
- バックログ → `Hist.`;
- オート → `Auto`;
- オートモード中 → `Modo auto`.

O archive reconstruído manteve 312.872 bytes e somente os BCLIM esperados diferiam.

### Fase 2 — v0.9.2

Cobertura:

```text
4 archives
18 BCLIM
```

Archives:

- `battle_low_1.arc`;
- `battle_low_2.arc`;
- `battle_jyunbi.arc`;
- `battle_window.arc`.

Também entrou a primeira versão do nameplate PT-BR.

### Fase 3 — v0.9.3

Depois do playtest, a cobertura passou para:

```text
27 archives
62 BCLIM
```

Incluiu:

- INFORMATION;
- menu de comandos;
- resultado/MVP;
- guide;
- pause;
- 17 tips 400×240;
- nameplate corrigido;
- speaker diário corrigido no runtime.

### Fase 4 — v0.10.0

Seis archives gerais entraram no builder:

```text
title.arc
option.arc
save_load.arc
omake.arc
window.arc
day.arc
```

Novos recursos:

```text
46 BCLIM
```

Total:

```text
33 archives
108 BCLIM
```

### Fase 5 — v0.10.1

Foi adicionado:

```text
battle_jyunbi.arc/back.bclim → Voltar
```

Total visual final:

```text
33 archives
109 BCLIM
```

A partir daí, o restante importante de japonês estava principalmente no runtime, não em novas texturas.

---

## 8. Options

Cobertura documentada:

- volumes BGM/SE/Voz;
- presets `Alto / Médio / Baixo / OFF`;
- velocidade `Lenta / Normal / Rápida`;
- `Sim / Não`;
- `Voltar`;
- excluir dados;
- inicializar dados;
- header `OPÇÕES`.

Descrições inferiores de algumas dessas opções vieram do ExeFS e foram tratadas depois pelo runtime patch.

---

## 9. Save/Load

Texturas traduzidas:

- `SALVAR`;
- `CARREGAR`;
- `APAGAR DADOS`;
- `Slot 1–8`;
- `SEM DADOS`;
- `Dia`;
- `ALIM.`;
- `Sim / Não`.

Mensagens de conclusão/confirmação não estavam todas em BCLIM; parte delas foi localizada no `.code`.

Veja [RUNTIME_PATCHING.md](./RUNTIME_PATCHING.md).

---

## 10. Extras / Omake

Cobertura visual:

- `EXTRAS`;
- `FINAIS`;
- `BATALHA LIVRE`;
- `GALERIA`;
- `Lista de finais`;
- `Batalha livre`;
- `Galeria`;
- `Voltar`;
- `PÁG.`;
- `Pontos:`.

Nomes desbloqueáveis de finais, títulos de galeria, fases e descrições inferiores vieram de strings runtime e precisaram de outra camada.

---

## 11. Window / Day

Traduções documentadas:

```text
B Voltar
Day → Dia
st/nd/rd/th → º
```

---

## 12. Archives raros auditados

Os seguintes archives foram inspecionados e não exigiram texto PT-BR adicional nas texturas auditadas:

```text
battle_start.arc
battle_clear.arc
battle_defeat.arc
battle_speed.arc
battle_unit_menu.arc
battle_weapon_menu.arc
wave.arc
battle_cutin_1.arc ... battle_cutin_9.arc
bg_low_scroll.arc
sentaku.arc
```

Eles eram essencialmente gráficos, ícones ou elementos sem rótulos japoneses relevantes nas texturas inspecionadas.

---

## 13. Tips

As 17 telas:

```text
tips00.arc ... tips16.arc
```

foram tratadas como BCLIM 400×240.

Estratégia:

1. usar o asset original local;
2. remover texto japonês da área adequada;
3. preservar moldura, logo, flores, screenshots e sprites;
4. redesenhar PT-BR;
5. reempacotar;
6. validar DARC/BCLIM.

As tips são detalhadas em [BATTLE_SYSTEM.md](./BATTLE_SYSTEM.md).

---

## 14. Regra central da UI

Em Island Days, “UI” pode significar quatro coisas diferentes:

```text
texto rasterizado → BCLIM
geometria/pane   → BCLYT
animação         → BCLAN
texto dinâmico   → .code / UTF-16LE
```

Traduzir apenas imagens não fecha a interface inteira.

Essa foi uma das principais conclusões da pesquisa.
