# Suporte a Shiny Days

## Baseline

O suporte foi desenvolvido usando **Shiny Days com o patch oficial JAST 1.01e aplicado**.

Para manter os testes reproduzíveis, use GPKs extraídos dessa base.

## PIDX

Chave confirmada:

```text
F0 D0 BC 05 54 AC 68 A9 F1 7C 8E 3D 64 0B F3 AA
```

Ela foi encontrada em `SHINYDAYS.exe` e validada contra um PIDX real:

- XOR produz prefixo coerente;
- stream zlib válido;
- tamanho descompactado confere;
- índice contém nomes UTF-16LE válidos.

## Como o toolkit usa isso

Não é necessário escolher Shiny Days manualmente.

`read_stack_index()` tenta a chave fornecida primeiro e, se necessário, as variantes conhecidas de School Days HQ, ALT_56 e Shiny Days.

O writer usa a chave efetivamente detectada no GPK de referência.

## Patch 1.01e

Página oficial:

https://help.jastusa.com/en/knowledgebase/article/shiny-days-patch-1-01e-and-bugfixes

Segundo as notas da JAST, o patch corrige:

- ending de Minami, incluindo novos créditos e crash;
- nós do Route Map e percentual;
- splash screens ausentes;
- Story Route do Kokoro Bad End;
- uniforme na rota da Inori;
- pequenos erros de texto.

O problema geral de save não é resolvido pelo patch e pode depender das permissões da pasta de instalação.

## Escopo atual

A camada GPK/STACK está suportada.

Isso não significa que todos os formatos internos exclusivos de Shiny Days já tenham validadores especializados. Para formatos desconhecidos, use o modo Experimental com cautela e teste no jogo.

## Tema automático da GUI

Na linha v0.13, a identificação `SHINY_DAYS` também controla a apresentação visual: ao selecionar um GPK reconhecido como Shiny Days, a GUI troca automaticamente logo, arte lateral, paleta, cabeçalho e título.

A arte usa `opacidade: 1.0`, sem esmaecimento. A paleta usa laranja/amarelo/creme inspirados na identidade visual do jogo.

Essa troca é somente visual; a detecção e o repack continuam usando o GPK como autoridade técnica.
