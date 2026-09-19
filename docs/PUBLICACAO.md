# Publicação do Days ModToolkit

## Distribuição

O projeto **não utiliza GitHub Releases**.

A distribuição pública é feita diretamente pela branch principal:

```text
days-modtoolkit
```

O usuário baixa o estado atual pelo botão:

```text
Code → Download ZIP
```

Assim, o conteúdo da branch principal é a própria distribuição do toolkit.

## Nome do repositório

Identidade pública atual:

```text
Days-Modding-Toolkit
```

Nome do projeto exibido na documentação e na GUI:

```text
Days ModToolkit
```

O namespace Python histórico `sdhq_toolkit` e os entry points `sdhq`/`sdhq-gui` permanecem por compatibilidade.

## O que deve existir na branch principal

Mantenha:

- `README.md`
- `LICENSE`
- `pyproject.toml`
- `.gitignore`
- launchers `.bat`
- `themes/school_days/`
- `themes/shiny_days/`
- `src/`
- `docs/`
- `pipelines/`
- `tests/`

Os perfis oficiais de tema devem acompanhar a branch principal para que o ZIP baixado por **Code → Download ZIP** funcione imediatamente.

## Não publicar

Não versionar:

- `.sdhq-repack.json`
- `.sdhq-desktop.json`
- overrides pessoais `tema.json`/`Fundo.png` na raiz;
- GPKs originais;
- mods pessoais;
- workspaces;
- backups;
- relatórios e outputs locais;
- `__pycache__`;
- arquivos `.pyc`.

## Atualizações

Novas versões são publicadas atualizando a própria branch `days-modtoolkit`.

O número da versão continua registrado no código e no README para diagnóstico, mas não é necessário criar uma Release ou anexar ZIP manualmente.

Antes de atualizar a branch principal:

1. valide a GUI;
2. valide a autodetecção School Days HQ/Shiny Days;
3. teste o repack;
4. confira os assets dos temas;
5. execute a suíte de testes aplicável;
6. só então atualize `days-modtoolkit`.

O botão **Code → Download ZIP** passa automaticamente a entregar esse novo estado.
