# Preparar o repositório e a release

## Nome público

O projeto passa a usar **Days ModToolkit** como identidade pública.

Nome recomendado do repositório:

```text
Days-ModToolkit
```

O namespace Python histórico `sdhq_toolkit` e os entry points `sdhq`/`sdhq-gui` permanecem por compatibilidade.

## Arquivos para o GitHub

Mantenha:

- `README.md`
- `RELEASES.md`
- `LICENSE`
- `pyproject.toml`
- `.gitignore`
- launchers
- `tema.example.json`
- `themes/school_days/`
- `themes/shiny_days/`
- `src/`
- `docs/`
- `pipelines/`
- `tests/`

Não envie `__pycache__`, `.pyc`, GPKs ou dados pessoais de workspace.

## Dados locais

Não publicar:

- `.sdhq-repack.json`
- `.sdhq-desktop.json`
- overrides pessoais `tema.json`/`Fundo.png` da raiz;
- GPKs;
- mods pessoais;
- workspace;
- backups;
- relatórios ou outputs locais.

## Pacote da release

A linha atual é **v0.13.0-dev1**.

Monte um ZIP completo a partir dos arquivos públicos e teste em uma pasta nova antes de publicar. Os perfis oficiais em `themes/school_days/` e `themes/shiny_days/` devem acompanhar a distribuição.

Pillow continua opcional para a arte lateral, mas é recomendado para recorte e escala de melhor qualidade.
