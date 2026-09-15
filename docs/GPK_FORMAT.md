# Formato GPK

Status: **leitura do rodapé confirmada no GARbro; índice em pesquisa**.

## Rodapé Stack

Os 32 bytes finais possuem a estrutura:

```text
0x00  12 bytes  "STKFile0PIDX"
0x0C   4 bytes  tamanho do índice (uint32 little-endian)
0x10  16 bytes  "STKFile0PACKFILE"
```

O índice começa em `tamanho_do_archive - 32 - tamanho_do_indice`. Seu conteúdo
é protegido por XOR com a chave `CIPHERCODE` e depois usa Zlib.

## Fluxo planejado

1. Ler o archive original.
2. Preservar header, ordem, flags e campos ainda desconhecidos.
3. Extrair cada entrada para uma pasta com o mesmo nome do GPK.
4. Registrar metadados em `.sdhq/archive.json`.
5. Reconstruir usando o GPK original como referência.
6. Validar offsets, tamanhos, contagem e compatibilidade no jogo.
