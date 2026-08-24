# Palpite 360

*Seu palpite. Nosso jogo.*

Relatórios comparativos entre duas equipes com base em dados históricos reais
(últimos jogos), **sem assinaturas, sem cobrança e sem indicadores ao vivo**.

## O que faz

- Baixa dados históricos reais de partidas (gratuito, sem chave de API) de
  [football-data.co.uk](https://www.football-data.co.uk/).
- Para cada time, calcula: aproveitamento, gols marcados/sofridos, jogos sem
  sofrer/marcar, % Over 0.5/1.5/2.5/3.5, % ambas marcam, e (quando a liga
  disponibiliza) finalizações, escanteios e cartões — com peso maior para
  jogos mais recentes.
- Cruza os dados das duas equipes (ataque de um vs. defesa do outro) para
  apontar combinações estatisticamente favoráveis.
- Estima gols esperados e probabilidades (1X2, Over/Under, ambas marcam,
  placares mais prováveis) usando distribuição de Poisson — e, quando a liga
  tiver o dado, o mesmo modelo aplicado a escanteios e cartões.
- Calcula um Elo relativo simples entre as equipes (apenas com base nas
  temporadas carregadas, não no histórico completo do clube).
- Classifica os mercados calculados por confiança estatística (🟢 mais
  segura / 🟡 boa para valor / 🔴 arriscada) e sugere uma combinação
  (múltipla) com os melhores mercados de categorias diferentes.
- Dados atualizam sozinhos a cada 6h enquanto o app é usado (cache com TTL),
  e há um botão "🔄 Atualizar agora" para forçar um novo download na hora.

## O que **não** faz (por decisão de escopo ou limitação de dado gratuito)

- Sem dados ao vivo, sem WebSocket, sem "pressão" em tempo real.
- Sem contas de usuário, sem planos pagos, sem admin.
- Sem mercados de jogadores, sem escalação/desfalques confirmados no dia
  (exigiria outra fonte de dados, hoje não integrada).
- Sem cash-out: isso depende da odd ao vivo de uma casa de apostas
  específica, que não temos acesso nem processamos.
- As probabilidades são estimativas estatísticas, nunca certezas — o app
  não processa apostas nem dinheiro, só sugere leituras de confiança.

## Cobertura de dados

- **Ligas com estatísticas completas** (chutes, escanteios, cartões, árbitro),
  via football-data.co.uk, sem chave de API: Inglaterra (4 divisões +
  National League), Escócia (4 divisões), Alemanha, Itália, Espanha, França
  (2 divisões cada), Holanda, Bélgica, Portugal, Turquia, Grécia.
- **Ligas com dados básicos** (só placar, sem chutes/escanteios/cartões), via
  football-data.co.uk, sem chave de API: Áustria, Dinamarca, Finlândia,
  Irlanda, Noruega, Polônia, Romênia, Rússia, Suécia, Suíça (europeias) e
  Brasil, Argentina, China, Japão, México, EUA (fora da Europa).
- **Ligas africanas** (só placar, sem chutes/escanteios/cartões), via
  [API-Football](https://www.api-football.com/) — **exige uma chave gratuita
  própria** (ver seção abaixo): Egito, África do Sul, Marrocos, Tunísia,
  Argélia, Nigéria, Gana, Quênia, Angola, Costa do Marfim, Camarões,
  Tanzânia, Zâmbia, e CAF Champions League.
- **Competições sul-americanas extras** (só placar, sem chutes/escanteios/
  cartões), também via API-Football — **mesma chave gratuita** de cima:
  Brasileirão Série B, Copa Libertadores e Copa Sul-Americana. Confirmamos
  que football-data.co.uk não cobre essas três (só tem o Brasileirão Série A).

O relatório informa claramente quando uma estatística não está disponível.
Isso é uma limitação das fontes gratuitas, não do sistema — dados completos
(chutes/escanteios/cartões) de ligas fora da Europa exigem provedores pagos
(ver observação de viabilidade que fizemos antes de começar o projeto).

### Habilitando as ligas africanas e sul-americanas extras (opcional, gratuito)

1. Crie uma conta grátis em https://dashboard.api-football.com/register
   (plano Free = 100 requisições/dia, mais que suficiente para uso pessoal
   com o cache deste app).
2. Copie sua chave no painel ("API-KEY").
3. Cole a chave em `config/api_football_key.txt` (crie o arquivo a partir de
   `config/api_football_key.txt.example`) **ou** defina a variável de
   ambiente `API_FOOTBALL_KEY`.

A mesma chave libera as duas regiões (África e Sul-Americanas) de uma vez —
não precisa configurar nada separado para cada uma.

Sem essa chave, as ligas europeias e "outras" continuam funcionando
normalmente — só África e Sul-Americanas ficam indisponíveis, com um aviso explicando
o motivo.

**Importante — testado com uma chave real:** o plano **Free** da API-Football
bloqueia buscar jogos por liga + temporada fora de **2022-2024** (temporadas
mais recentes exigem plano pago). As ligas europeias e "outras" via
football-data.co.uk **não** têm essa limitação — lá os dados são sempre da
temporada atual.

### Varredura gradual de jogos atuais (contorno gratuito)

Descobrimos (testando com a chave real) que `/fixtures?date=AAAA-MM-DD` — 
buscar por **data**, em vez de por liga+temporada — devolve os jogos reais
daquele dia em **todas** as ligas, incluindo a temporada em andamento, e
**não** cai no bloqueio do plano Free. O app usa isso: a cada carregamento
de uma liga africana ou sul-americana, ele varre mais alguns dias novos por
trás (poucas chamadas, ~6-8 por vez — não trava a tela nem consome a cota
diária de uma vez), guarda cada dia em cache permanente, e indexa localmente
por liga. Esse "histórico atual" cresce sozinho a cada uso do app — a
interface mostra `varredura de jogos recentes cobre os últimos N dias`.

Enquanto a varredura ainda não tem pelo menos 15 jogos recentes para uma
competição, o app completa a amostra com as temporadas antigas (2022-2024)
para não ficar com dado de menos — e mostra um aviso 📅 quando o jogo mais
recente da amostra é antigo (>20 dias), explicando o motivo.

Isso funciona bem para ligas com jogos toda semana (ex.: Série B, ligas
africanas nacionais). Para competições mais espaçadas (Libertadores e
Sul-Americana, que jogam a cada ~2 semanas e têm pausas longas entre fases),
a varredura ainda funciona, mas leva mais tempo (semanas de uso) até acumular
os últimos 10-20 jogos de um time específico — é uma limitação inerente ao
calendário dessas competições, não um bug.

Não é preciso fazer nada para ativar isso — acontece automaticamente. Só é
mais rápido se você usar o app com frequência (cada carregamento avança a
janela um pouco mais).

## Como rodar

```bash
pip install -r requirements.txt
streamlit run app.py
```

Abra `http://localhost:8501` no navegador (a porta pode variar conforme sua configuração).

## Deploy online (Streamlit Community Cloud, gratuito)

1. Suba este repositório para o GitHub (`git push`).
2. Entre em https://share.streamlit.io com sua conta do GitHub.
3. Clique em **New app**, escolha o repositório, branch `master`/`main` e o
   arquivo principal `app.py`. Clique em **Deploy**.
4. (Opcional, para África/Sul-Americanas) No painel do app, vá em **Settings
   → Secrets** e cole:
   ```toml
   API_FOOTBALL_KEY = "sua_chave_aqui"
   ```
   Salve — o app reinicia sozinho e já lê a chave dali (sem precisar de
   arquivo nenhum no repositório).

**Importante:** no plano gratuito do Streamlit Community Cloud, o app fica
com uma URL pública (`https://SEU-APP.streamlit.app`) — qualquer pessoa com
o link acessa, inclusive a seção de recomendações de apostas. Não há conta
de usuário nem controle de acesso nesta versão. Use com essa consciência
(é adequado para testes e uso pessoal compartilhado com link, não para
divulgação pública ampla).

## Estrutura

```
app.py                          Interface (Streamlit)
src/leagues.py                  Catálogo de campeonatos disponíveis
src/config.py                   Leitura da chave da API-Football (opcional)
src/data_sources.py             Download, cache e normalização (football-data.co.uk)
src/data_sources_api_football.py Download, cache e normalização (API-Football, África)
src/stats.py                    Indicadores históricos por equipe
src/crossing.py                 Cruzamento entre as duas equipes
src/poisson_model.py            Estimativa de gols/escanteios/cartões (Poisson)
src/betting.py                  Classificação de mercados por confiança + combinações
src/elo.py                      Rating Elo simplificado
.streamlit/config.toml          Tema visual (cores, fundo escuro)
assets/logo.png                 Logo da marca (favicon + cabeçalho)
config/api_football_key.txt     Sua chave da API-Football (não versionado)
data/cache/                     Dados baixados (cache local, não versionado)
data/cache/api_football/day_*.json   Varredura por data (jogos atuais, cresce com o uso)
```

## Identidade visual

Marca própria **Palpite 360** ("Seu palpite. Nosso jogo."): fundo preto e
verde-limão (`#96cd14`, extraído da logo em `assets/logo.png`), aplicados em
`.streamlit/config.toml` e no CSS embutido em `app.py`. A logo é usada como
favicon e no cabeçalho do app.

Não reproduzimos o logotipo, o nome ou o layout de nenhuma casa de apostas
real (bet365 ou qualquer outra) — evitamos isso de propósito: replicar a
marca de uma empresa de apostas licenciada, num app que já calcula
probabilidades de jogo, criaria risco de confusão de marca. A identidade
usada aqui é a marca própria do projeto.

## Limitações a ter em mente

- O Elo é calculado só com as temporadas carregadas (geralmente as últimas
  3), não com o histórico completo do clube — serve para comparar as duas
  equipes entre si, não como rating absoluto.
- O modelo de Poisson é uma estimativa simples (sem Dixon-Coles, sem ajuste
  para mando de campo além da média da liga, sem contexto de escalação ou
  desfalques). É um ponto de partida estatístico, não uma previsão precisa.
- Ligas fora da Europa geralmente só têm placar, sem estatísticas avançadas,
  de graça.
- As ligas africanas e as competições sul-americanas extras (Série B,
  Libertadores, Sul-Americana) dependem de uma chave própria e gratuita da
  API-Football (cota de 100 requisições/dia) — os nomes/temporadas exatas
  disponíveis podem variar conforme a cobertura da API para cada competição.
- Libertadores e Sul-Americana são mata-mata + fase de grupos, não pontos
  corridos — "mandante/visitante" nos últimos jogos ainda faz sentido, mas
  finais em campo neutro (se houver no recorte) entram como se o time da
  chave fosse mandante, o que pode distorcer levemente a leitura de
  casa/fora bem no fim da competição.
- A "melhor combinação" multiplica as probabilidades assumindo que os
  mercados são independentes. Na prática, mercados como "over gols" e
  "ambas marcam" são correlacionados — a chance real da combinação dar
  certo tende a ser um pouco menor que o número exibido.
- Cartões não têm um "adversário que reduz" tão direto quanto gols/escanteios
  (não rastreamos cartão sofrido); o cálculo usa a média da liga como
  aproximação da força defensiva, então é o mercado menos preciso do app.
