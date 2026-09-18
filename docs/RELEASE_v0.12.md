# v0.12.0-dev — suporte multi-game GPK

## Objetivo

Expandir o núcleo GPK do toolkit para suportar School Days HQ e Shiny Days sem exigir uma chave global fixa.

## Principais mudanças

- chave Shiny Days adicionada;
- autodetecção por arquivo;
- fallback quando CIPHERCODE está ausente ou incorreto;
- varredura literal de executáveis para chaves conhecidas;
- writer preserva a chave efetiva da referência;
- fluxo principal GARbro não exige mais instalação do jogo;
- CLI aceita `--key-report` opcional;
- labels da GUI atualizados;
- testes sintéticos multi-game adicionados.

## Chave Shiny Days

```text
F0 D0 BC 05 54 AC 68 A9 F1 7C 8E 3D 64 0B F3 AA
```

## Baseline

- School Days HQ: v1.02
- Shiny Days: 1.01e

## Cobertura adicionada

`tests/test_multigame_gpk.py` cobre:

- detecção School;
- detecção Shiny;
- fallback de chave;
- repack preservando SHINY_DAYS;
- fluxo principal sem diretório do jogo;
- descoberta da chave dentro de um EXE sintético.

## Observação

A compatibilidade adicionada é da camada GPK/STACK. Formatos internos específicos de Shiny Days ainda devem ser testados caso a caso no jogo.
