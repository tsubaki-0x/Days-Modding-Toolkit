# GARbro + ModToolkit — v0.12.0-dev

O GARbro continua sendo o explorador/extrator externo. O ModToolkit reconstrói o GPK de referência usando os arquivos da pasta escolhida.

A v0.12 amplia esse fluxo para **School Days HQ v1.02** e **Shiny Days 1.01e**.

## Preparação e uso

1. Abra o GPK no GARbro.
2. Extraia tudo ou somente o que pretende editar.
3. Preserve os caminhos internos e não converta os formatos.
4. Abra `run_gui.bat`.
5. Selecione o GPK de referência.
6. Selecione a pasta com as alterações.
7. Selecione saída e relatórios.
8. A instalação do jogo agora é **opcional** no fluxo principal.
9. Clique em **Conferir alterações**.
10. Clique em **Gerar GPK**.

Quando uma instalação é informada, o toolkit tenta primeiro localizar uma chave via `CIPHERCODE` ou por varredura literal conhecida. Mesmo assim, o próprio GPK continua sendo a autoridade final: se a chave fornecida falhar, o índice tenta as variantes conhecidas.

## Shiny Days

O baseline usado no projeto é Shiny Days após o patch oficial JAST 1.01e.

A chave PIDX confirmada é:

```text
F0 D0 BC 05 54 AC 68 A9 F1 7C 8E 3D 64 0B F3 AA
```

No repack, essa mesma chave é preservada automaticamente.

## Regras da montagem

- uma referência por operação;
- arquivo igual mantém os bytes da referência;
- arquivo diferente substitui a entrada correspondente;
- arquivo ausente mantém a referência;
- entrada nova fora do índice não é inserida;
- inclusão/remoção/renomeação continuam fora do escopo;
- saída sempre separada da referência/pasta editada;
- cancelamento remove temporários;
- o GPK gerado é reaberto e validado antes de ser publicado.

## Segurança multi-game

O writer não usa mais cegamente uma chave global.

```text
GPK de referência
    ↓
detectar PIDX
    ↓
registrar chave efetiva
    ↓
rebuild
    ↓
criptografar PIDX com a mesma chave
    ↓
reabrir e validar
```

Assim um GPK de Shiny Days permanece Shiny Days no nível do PIDX.

## Teste no jogo

Compatibilidade estrutural não garante que todo asset modificado seja aceito pela engine.

Faça:

```text
1 edição
1 repack
1 backup
1 teste
```

Feche o jogo e o GARbro antes de trocar arquivos em `Packs`.
