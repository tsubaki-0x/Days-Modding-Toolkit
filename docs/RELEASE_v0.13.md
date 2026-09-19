# v0.13.0-dev1 — temas multi-game automáticos

## Objetivo

Fazer a interface visual acompanhar o jogo realmente identificado pelo GPK sem misturar apresentação com a lógica do arquivo.

## Mudanças

- projeto rebatizado publicamente como **Days ModToolkit**;
- tema padrão de School Days HQ preservado;
- novo tema de Shiny Days;
- logo específica de Shiny Days;
- arte lateral específica de Shiny Days;
- arte de Shiny Days em 100% de opacidade;
- paleta quente inspirada na logo de Shiny Days;
- ao selecionar um GPK, a GUI usa `index_key_name` para escolher o tema;
- `SCHOOL_DAYS_HQ` ativa School Days HQ;
- `SHINY_DAYS` ativa Shiny Days;
- GPK desconhecido não força tema nem altera o parser;
- título da janela e cabeçalho acompanham o jogo detectado;
- override antigo `tema.json` continua compatível com o tema padrão de School Days.

## Segurança técnica

A mudança de tema ocorre **depois** da identificação técnica do PIDX. Nenhum perfil visual altera chave, codec, flags, offsets ou comportamento do writer.

## Assets dos temas

```text
themes/school_days/
themes/shiny_days/
```

Cada perfil possui `Logo.png`, `Fundo.png` e `tema.json`.

## Baselines

- School Days HQ: v1.02
- Shiny Days: 1.01e

## Hotfix dev1

- corrige colisão com o método interno `tkinter.Misc._root()` no painel de arte;
- evita `TypeError: 'Tk' object is not callable` ao processar eventos da GUI, inclusive no Python 3.14;
- nenhuma lógica de leitura/repack de GPK foi alterada por este hotfix.
