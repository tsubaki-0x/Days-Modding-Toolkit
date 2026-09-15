# Preparar o repositório e a release

## Arquivos para o GitHub

Mantenha README.md, RELEASES.md, LICENSE, pyproject.toml, .gitignore, launchers,
tema.example.json, src/, docs/, pipelines/ e tests/. Não envie __pycache__ ou .pyc.

README.md é a página principal; RELEASES.md contém o texto da release.
docs/README_ANTERIOR.md preserva a documentação antiga de comandos e pesquisa.
A versão do código continua 0.11.1-dev; a tag proposta é v0.11.1-dev.

## Dados locais

Não enviar .sdhq-repack.json, .sdhq-desktop.json, tema.json, Fundo.png, GPKs,
pacotes de mod pessoais, workspace, backups, amostras do jogo, relatórios ou outputs.
Use tema.example.json como configuração pública; cada pessoa escolhe sua imagem.
A logo tem origem documentada em src/sdhq_toolkit/gui/assets/README.md.

O .gitignore evita adicionar esses caminhos normalmente, mas não remove arquivos
que já tenham sido versionados. Confira os arquivos selecionados antes do envio.

## Pacote da release

Monte um ZIP completo a partir dos arquivos públicos, incluindo os PNGs da GUI.
Não use o manifesto da distribuição extraída como se ele representasse o código
atual: ele foi criado antes das mudanças no tema e no layout.

Recrie os hashes do pacote final e teste em uma pasta nova. Os arquivos PNG da
logo são dados do pacote Python; Pillow é opcional para a arte lateral.
Não inclua a imagem pessoal de fundo por acidente; o programa funciona sem ela.

Nada foi enviado ao GitHub por estas alterações. O repositório e a publicação
da release continuam sob controle do autor.
