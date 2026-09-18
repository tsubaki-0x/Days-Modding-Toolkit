# Formato GPK / STACK

Status atual: **leitura e repack confirmados para as variantes usadas por School Days HQ e Shiny Days**.

## Rodapé Stack

Os 32 bytes finais possuem:

```text
0x00  12 bytes  "STKFile0PIDX"
0x0C   4 bytes  tamanho do índice protegido (uint32 little-endian)
0x10  16 bytes  "STKFile0PACKFILE"
```

O índice começa em:

```text
tamanho_do_archive - 32 - tamanho_do_indice
```

## Estrutura do PIDX

Depois de aplicar a chave XOR correta:

```text
uint32 tamanho descompactado
zlib(index)
```

A v0.12 não assume mais uma única chave.

### School Days HQ

```text
82 EE 1D B3 57 E9 2C C2 2F 54 7B 10 4C 9A 75 49
```

### Shiny Days

```text
F0 D0 BC 05 54 AC 68 A9 F1 7C 8E 3D 64 0B F3 AA
```

### Variante adicional

```text
56 7C 1B 90 B6 FE 3F DB B6 06 79 EA CC 11 A0 4F
```

## Autodetecção

`read_stack_index()` aceita uma chave preferencial, mas não depende dela.

Cada candidata só é aceita quando:

1. zlib aceita o stream;
2. o tamanho descompactado confere com o uint32;
3. o índice pode ser parseado;
4. nomes UTF-16LE são válidos;
5. offsets/tamanhos ficam dentro do archive.

O relatório expõe:

```text
index_key_name
index_key_hex
index_xor
index_codec
```

Isso permite ao writer reutilizar exatamente a proteção detectada no GPK de referência.

## Entrada do índice

Estrutura observada:

```text
uint16  name_len
UTF-16LE name
int32   unknown_1
int16   unknown_2
uint32  offset
uint32  stored_size
int32   unknown_3
uint32  unpacked_size
uint8   header_size
header_size bytes header
```

Quando `unpacked_size != 0`, a entrada é tratada como comprimida. Para as entradas DFLT trabalhadas pelo toolkit, o payload usa zlib.

## Repack

O writer preserva prefixo/stub, ordem, nomes, campos desconhecidos, headers, streams não modificados e a chave efetiva do PIDX.

A saída é escrita em temporário, reaberta e validada antes de ser publicada.

## Escopo

O suporte ao container de Shiny Days não implica que cada formato interno do jogo já tenha validação especializada.
