# Fechamento funcional — v0.11.1-dev

Escopo consolidado: GARbro externo explora e extrai; seleção manual do EXE.
Toolkit faz repack de uma referência original ou modificada e uma pasta externa,
sem metadata obrigatório. Ausências mantêm a referência. Validação de formatos
informa sem bloquear. Arquivos novos são explicitamente não incluídos.

Implementação funcional concluída. Inclusão, remoção e renomeação de entradas
estão fora desta entrega. CLI, workspace e interface anterior/.sdmod preservados,
com suas regras anteriores. Próxima etapa prevista: personalização visual da GUI,
sem alterar essas regras, quando solicitada pelo usuário.

Em 14/09/2026, o usuário confirmou INI.gpk: extração pelo GARbro, edição,
substituições identificadas pelo toolkit e GPK remontado carregando a alteração
pretendida no jogo. Registro por relato do usuário; não repetido pelo assistente.

Orientações adicionadas: criar pasta exclusiva por GPK; nome igual é recomendado,
não obrigatório; preservar arquivos na raiz e subpastas; fechar jogo e GARbro
antes de substituir GPK em Packs e guardar cópia anterior.

Verificação de fechamento: 110 testes descobertos, 94 passaram na suíte normal,
16 de janela opcionais. A execução de fechamento de *gui*.py passou nos 38 testes,
incluindo os 16 de janela; 110 testes distintos aprovados. Compileall aprovado.
Dois novos testes cobrem
arquivos na raiz com nome de pasta independente e cancelamento durante a escrita.
Corrigidos acentos danificados nos trechos recentes da documentação.

ZIP incremental: dist/SchoolDaysHQ-Modding-Toolkit-v0.10-to-v0.11-incremental.zip.
Somente allowlist de código, testes, launcher e documentação; sem dados do jogo.
Não refazer os testes já validados no jogo nem ler relatórios enormes para retomar.

Organização posterior: nove instruções antigas movidas da raiz para docs/historico.
docs/ORGANIZACAO.md classifica código, manutenção e dados locais. Nenhum dado do jogo,
mod, backup ou resultado foi apagado. Pastas output_*/cmap_* mantidas nos caminhos
atuais enquanto a preferência do usuário sobre arquivamento não estiver definida.
Preferências salvas das duas interfaces preservadas.

Distribuição completa nova: dist/SchoolDaysHQ-Modding-Toolkit-v0.11.1-completo.zip,
com manifesto SHA-256. Extraída em pasta temporária isolada: 94 testes passaram,
16 opcionais de janela não executados novamente; CLI --help passou.
ZIP completo não depende de dados/versões anteriores. Incremental também atualizado.

## Tema visual em andamento — pasta nova

ATUALIZAÇÃO MAIS RECENTE: usuário forneceu a arte local
`ChatGPT Imdage 14 de set. de 2026, 21_56_01.png`. Adicionado gui/background.py:
painel lateral direito com imagem suavizada por opacidade, zoom e deslocamentos
x/y controlados por tema.json na raiz. Instruções em docs/FUNDO_GUI.md.
Usa Pillow disponível localmente, sem modificar a imagem original. Janela padrão
1460x900; painel ocultado abaixo de 1280 de largura para preservar controles.
Três testes da GUI passaram após integração. Não atualizado ZIP/manifesto nesta
etapa curta a pedido de economia de sessão. Registros de pendência da arte abaixo
são históricos e foram resolvidos pelo arquivo local; apresentação atual é lateral,
não por trás de campos transparentes. Próxima revisão visual pode ajustar isso.

Trabalho atual em SchoolDaysHQ-Modding-Toolkit-v0.11.1-completo. Usuário solicitou
economia de sessão e forneceu a paleta #5FA8E8, #A9D7F5, #F7F7F2, #17283B,
#101820, #C9363E. Aplicada por gui/theme.py à tela principal, sem mudanças no core.
Logo PNG fornecida pelo usuário baixada do Wikimedia, aplicada no canto superior
esquerdo; origem em gui/assets/README.md. pyproject inclui assets PNG no pacote.
Guias de layout, cabeçalho, botões e tabela tematizados. Três testes da nova GUI
passaram, incluindo logo e espaço mínimo 980x800; primeiro ajuste de espaçamento
foi corrigido após teste. Não repetir suíte inteira por mudanças só visuais.

PENDENTE: usuário deve informar caminho local da arte de fundo desejada. Ele
forneceu link interno autenticado do ChatGPT; não registrar nem redistribuir sua
URL assinada. Pergunta enviada, aguardando resposta. Não substituir a arte por
outra. Ao receber o arquivo: inspecionar e integrar ao fundo com opacidade suave,
preservando legibilidade. Distribuição e manifesto só devem ser atualizados após
finalizar a arte. O manifesto atual corresponde ao ZIP extraído antes do tema.


Correção de layout em 15/09/2026: GUI principal usa Panedwindow vertical, com
configuração rolável (gui/scroll_form.py) e resultados separados, mais rolagem
horizontal da tabela. Tamanho inicial limitado à tela; mínimo 760x540. Quatro
testes GUI passaram, incluindo 760x540, 1024x650, 1366x700 e 1460x900. Nenhuma
mudança no core ou cores. Usuário quer instruções para mudar painéis brancos para
azul-marinho por conta própria. ZIP/manifesto ainda não atualizados com tema/layout.


Documentação para GitHub preparada: README.md reescrito para o fluxo atual;
RELEASES.md com texto da release v0.11.1-dev; docs/PUBLICACAO.md com conteúdo
público e exclusões; docs/README_ANTERIOR.md preserva o README antigo;
tema.example.json é o exemplo público. .gitignore protege tema.json, Fundo.png,
preferências e dados locais. Nenhum envio ao GitHub foi feito. Código não mudou.
ZIP/manifesto ainda precisam ser regenerados para incluir tema/layout atuais.


ZIP final atualizado na raiz: SchoolDaysHQ-Modding-Toolkit-v0.11.1-completo.zip.
Inclui tema escuro, layout adaptável, logo, documentação GitHub e tema.example.json.
Não inclui tema.json, Fundo.png, preferências pessoais nem dados do jogo.
MANIFESTO_DISTRIBUICAO.json regenerado com hashes dos arquivos públicos.
Verificação da distribuição em pasta temporária, sem usar o workspace pessoal.
