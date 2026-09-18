<img width="1672" height="941" alt="School Days" src="https://github.com/user-attachments/assets/f372b6c5-15a3-4e64-ba90-8981ff755cd6" />

# School Days HQ / Shiny Days Modding Toolkit

Toolkit não oficial para explorar, validar e reconstruir arquivos **GPK/STACK** da família Days, com foco atual em:

- **School Days HQ v1.02**
- **Shiny Days 1.01e** (baseline usado no desenvolvimento)

**GARbro explora e extrai. Você edita. O ModToolkit faz o repack.**

Versão atual: **0.12.0-dev**.

> O repositório continua com o nome histórico `SchoolDaysHQ-Modding-Toolkit`, mas o núcleo GPK agora suporta as variantes confirmadas de School Days HQ e Shiny Days.

## O que mudou na v0.12

O toolkit não depende mais de uma única chave global de PIDX.

Agora ele:

- tenta primeiro a chave fornecida ou extraída por `CIPHERCODE`;
- se ela falhar, autodetecta variantes conhecidas do PIDX por arquivo;
- reconhece a chave de School Days HQ;
- reconhece a chave de Shiny Days;
- preserva no repack a mesma chave que realmente abriu o GPK de referência;
- permite usar o fluxo principal GARbro + pasta externa sem informar manualmente uma chave;
- torna `--key-report` opcional na CLI;
- mantém o fluxo legado, workspaces e pacotes `.sdmod`.

### Chaves confirmadas

School Days HQ:

```text
82 EE 1D B3 57 E9 2C C2 2F 54 7B 10 4C 9A 75 49
```

Shiny Days:

```text
F0 D0 BC 05 54 AC 68 A9 F1 7C 8E 3D 64 0B F3 AA
```

Também permanece reconhecida a variante compatível:

```text
56 7C 1B 90 B6 FE 3F DB B6 06 79 EA CC 11 A0 4F
```

A chave do Shiny Days foi confirmada ao decodificar um PIDX real com zlib válido e também encontrada literalmente em `SHINYDAYS.exe`.

## Status por jogo

### School Days HQ

Baseline principal já amplamente exercitado pelo projeto:

- versão: **v1.02**
- histórico: 29 GPKs
- 69.936 entradas catalogadas
- alterações INI, ORS, CMAP, PNG, OGG e WMV testadas ao longo do desenvolvimento

### Shiny Days

Baseline técnico atual:

- versão usada: **Shiny Days com patch oficial JAST 1.01e aplicado**
- PIDX de Shiny Days suportado por autodetecção
- repack preserva a chave Shiny do arquivo de referência
- mesmo fluxo de GARbro/pasta externa pode ser usado

O suporte ao **container GPK** está implementado. Isso não significa que todo formato de asset interno específico de Shiny Days já foi testado individualmente; o teste final no jogo continua obrigatório.

## Requisitos

- Windows
- Python **3.10+** com Tkinter/Tcl-Tk
- School Days HQ v1.02 ou Shiny Days 1.01e
- [GARbro](https://github.com/morkt/GARbro) para exploração/extração
- Pillow opcional para a arte lateral:

```powershell
python -m pip install Pillow
```

O jogo, GARbro e arquivos proprietários não acompanham o toolkit.

## Fluxo principal

1. Abra o GPK no GARbro.
2. Extraia os arquivos desejados preservando os caminhos internos.
3. Edite em ferramentas externas.
4. Abra `run_gui.bat`.
5. Selecione o **GPK de referência**.
6. Selecione a **pasta com as alterações**.
7. A instalação do jogo é opcional no fluxo principal; quando informada, o toolkit tenta extrair a chave dela primeiro.
8. Clique em **Conferir alterações**.
9. Clique em **Gerar GPK**.

O GPK de referência é a autoridade para:

- nomes;
- ordem;
- offsets/base estrutural;
- flags;
- headers;
- campos desconhecidos;
- proteção do PIDX.

## Autodetecção de PIDX

O núcleo usa:

```python
read_stack_index(archive, key=None)
```

A ordem de tentativa é:

1. chave fornecida/CIPHERCODE, se houver;
2. School Days HQ;
3. variante ALT_56;
4. Shiny Days;
5. PIDX sem XOR como fallback defensivo.

Uma variante só é aceita se:

- o zlib descompactar;
- o tamanho declarado conferir;
- o índice tiver estrutura válida;
- as entradas puderem ser interpretadas com segurança.

O relatório do índice registra:

```text
index_key_name
index_key_hex
index_xor
index_codec
```

## Repack seguro

O writer:

- lê novamente o GPK de referência;
- detecta a chave efetiva daquele arquivo;
- preserva entradas não alteradas;
- recompõe apenas entradas modificadas;
- recria o PIDX;
- usa a **mesma chave efetiva da referência**;
- valida o arquivo temporário antes de publicar a saída.

Assim, um GPK de Shiny Days não é convertido acidentalmente para a chave de School Days HQ.

## CLI

`--key-report` agora é opcional nos comandos GPK principais.

Exemplo:

```powershell
python -m sdhq_toolkit.cli read-index "D:\Shiny Days\Packs\Script.GPK"
```

ou, usando um relatório explícito:

```powershell
python -m sdhq_toolkit.cli read-index "D:\Jogo\Packs\Script.GPK" --key-report reports\ciphercode_report.json
```

A extração de chave também foi ampliada: se o recurso nomeado `CIPHERCODE` não existir, o toolkit procura as chaves conhecidas diretamente nos executáveis.

## Limites atuais

- inclusão de novas entradas no índice ainda não é suportada;
- remoção e renomeação de entradas ainda não são suportadas;
- arquivo ausente na pasta externa mantém a entrada da referência;
- arquivos novos aparecem como **novo — não incluído**;
- validações de assets são preventivas e não substituem teste real;
- compatibilidade do container não implica compatibilidade semântica de todo asset interno;
- não misture GPKs de versões diferentes como referência/extração.

## Shiny Days 1.01e

Para o baseline usado neste projeto, aplique primeiro o patch oficial 1.01e da JAST e só então use os GPKs como referência.

Esse patch corrige, entre outros pontos:

- ending de Minami e crash relacionado;
- nós/percentual do Route Map;
- splash screens ausentes;
- Story Route do Kokoro Bad End;
- uniforme incorreto na rota da Inori;
- pequenos erros de texto.

As próprias notas da JAST informam que o problema de save não é corrigido por esse patch e pode exigir execução como Administrador ou ajuste de permissões da pasta.

## Testes

A suíte existente continua disponível:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -q
```

A v0.12 adiciona testes sintéticos específicos para:

- autodetecção School Days HQ;
- autodetecção Shiny Days;
- fallback quando uma chave errada é fornecida;
- repack Shiny preservando a chave Shiny;
- fluxo principal sem diretório do jogo;
- descoberta literal da chave no executável.

## Documentação

- [GARbro + repack](docs/GARBRO_REPACK.md)
- [Formato GPK](docs/GPK_FORMAT.md)
- [Suporte a Shiny Days](docs/SHINY_DAYS.md)
- [Interface anterior e .sdmod](docs/DESKTOP.md)
- [Workspaces parciais](docs/PARTIAL_WORKSPACES.md)
- [Notas v0.12](docs/RELEASE_v0.12.md)

## Licença e créditos

Código sob [MIT](LICENSE).

School Days, Shiny Days, logos, executáveis e assets pertencem aos respectivos titulares e não são cobertos pela licença MIT deste repositório.

Projeto não oficial, sem vínculo com os titulares das franquias ou com o GARbro.
