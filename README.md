*[Read in English (US)](README.en.md)*

# Tuya IR CLI — Controle do Projetor AUN ET30

CLI em Python que controla o projetor AUN ET30 através de um Hub
Smart IR da Tuya via **API Cloud**. Suporta três formas de obter um
código IR:

**Status: projeto completo.** Os 15 botões do controle (13 físicos +
os 2 quebrados por corrosão de pilha, ESQUERDA e VOLUME-) estão
mapeados, confirmados ao vivo no projetor e salvos em `codebook.json`.
Veja a seção [8. Bugs reais encontrados e corrigidos](#8-bugs-reais-encontrados-e-corrigidos)
e [9. Como ESQUERDA e VOLUME- foram resolvidos](#9-como-esquerda-e-volume--foram-resolvidos)
pra entender o que não estava óbvio na implementação original.

1. **Aprendizado real** — aponta o controle físico pro Hub e captura
   o sinal de verdade. Use para os botões que ainda funcionam no seu
   controle.
2. **Inferência assistida** — para botões fisicamente quebrados (que
   nunca vão transmitir nada), gera candidatos plausíveis a partir de
   botões vizinhos já aprendidos e deixa você testar cada um ao vivo,
   apontando o Hub pro projetor, até confirmar o que funciona.
3. **Placeholder sintético** — códigos de exemplo gerados
   algoritmicamente (protocolo NEC padrão), usados só como fallback
   antes de qualquer aprendizado real.

## Como isso funciona de verdade

A API Cloud da Tuya não tem um endpoint que aceite "hex NEC cru" nem
"aprender e reenviar em tempo real" como uma coisa só. Os comandos de
IR passam pela família de endpoints `learning-codes`:

- `PUT /v2.0/infrareds/{id}/learning-state?state=true` — liga o modo
  de aprendizado no Hub.
- `GET /v2.0/infrareds/{id}/learning-codes?learning_time=...` —
  consulta se algo foi capturado (usado para aprender códigos reais
  do controle físico).
- `POST /v2.0/infrareds/{id}/learning-codes` — salva um código e
  gera um `remote_id` ("controle virtual").
- `POST /v2.0/infrareds/{id}/remotes/{remote_id}/learning-codes` —
  dispara um código (aprendido ou gerado) em tempo real.
- `GET /v2.0/infrareds/{id}/remotes/{remote_id}/learning-codes` —
  lista todos os códigos já salvos para um remote_id (usado para
  importar o que já foi aprendido pelo app Tuya Smart/Smart Life).

Tanto os códigos aprendidos quanto os sintéticos usam o mesmo formato
binário: uma string base64 com a lista de durações de pulso (mark/
space, em microssegundos), comprimida com uma variante do FastLZ. Por
isso o projeto tem duas peças complementares:

- `nec_encoder.py` — gera esse formato a partir de um código NEC
  hexadecimal (usado nos placeholders e nos candidatos de inferência).
- `nec_decoder.py` — faz o caminho inverso: decodifica o que o Hub
  captura do controle físico de volta para hex NEC legível (usado no
  aprendizado e na importação, para você ver e conferir o código real
  de cada botão).

Ambos foram validados byte a byte (round-trip encode → decode) contra
o algoritmo documentado publicamente por engenharia reversa do
formato da Tuya, usado também por projetos como tinytuya e IRTuya.

## 1. Passo a passo no portal da Tuya

> O portal foi renomeado — hoje é **platform.tuya.com** (o link antigo
> `iot.tuya.com` pode não carregar mais dependendo da rede/DNS).

### 1.1 Criar conta e projeto Cloud
1. Acesse [platform.tuya.com](https://platform.tuya.com) e crie/entre na conta de desenvolvedor.
2. Vá em **Cloud** (menu lateral) → **Create Cloud Project**.
3. Preencha:
   - **Project Name**: qualquer nome, ex. `IR Projetor AUN ET30`.
   - **Industry**: `Smart Home`.
   - **Development Method**: `Custom Development` (é o que dá acesso à Cloud API com Access ID/Secret).
   - **Data Center**: escolha a região onde seu app Tuya Smart/Smart Life está cadastrado (precisa bater, senão o dispositivo não aparece para vincular). No Brasil, geralmente é **Western America Data Center**.

### 1.2 Pegar Access ID e Access Secret
1. Abra o projeto criado → aba **Overview**.
2. Na seção **Authorization Key** você verá:
   - **Access ID / Client ID** → vai em `TUYA_ACCESS_KEY`
   - **Access Secret / Client Secret** → clique em "Show" → vai em `TUYA_SECRET_KEY`

### 1.3 Habilitar os serviços de API necessários
1. Na mesma página do projeto, vá na aba **Service API**.
2. Confirme que os seguintes serviços estão **assinados/habilitados**
   (senão as chamadas retornam erro de permissão):
   - **IoT Core**
   - **Authorization** (Authentication)
   - **IR Control Hub Open Service** (ou "Infrared Control Hub" /
     "Universal Infrared Open Service", o nome varia por região)
3. Se algum não estiver na lista, use **Go to Subscribe** para adicioná-lo (gratuito no plano Trial/Basic).

### 1.4 Vincular seu Hub IR ao projeto e pegar o Device ID
1. Ainda no projeto, vá em **Devices → Link Tuya App Account** (ou "Link My App").
2. Escaneie o QR code com o app **Tuya Smart** (Me → ícone de scan no topo).
3. Depois de vinculado, seus dispositivos aparecem na lista **All Devices**.

No seu caso, apareceram dois dispositivos:
- **Smart IR** — o Hub físico de verdade. O Device ID dele vai em `TUYA_DEVICE_ID`.
- **Projetor** — um controle virtual que o próprio app já criou/aprendeu
  parcialmente. O Device ID dele é usado como `remote_id` na opção **5**
  do menu (importar códigos já aprendidos pelo app).

Se o `TUYA_ENDPOINT` do `.env.example` não bater com o Data Center
escolhido, ajuste conforme a lista de regiões no próprio arquivo.

## 2. Instalação

```bash
cd tuya_ir_cli
python3 -m venv .venv && source .venv/bin/activate   # opcional, mas recomendado
pip install -r requirements.txt
```

## 3. Configuração

```bash
cp .env.example .env
# edite o .env com TUYA_ACCESS_KEY, TUYA_SECRET_KEY, TUYA_ENDPOINT, TUYA_DEVICE_ID
```

Se alguma variável estiver faltando, o script pergunta interativamente
no terminal na hora de rodar (menos prático para uso repetido — prefira o `.env`).

## 4. Uso

```bash
python3 main.py
```

Menu principal:

```
1) Enviar comando
2) Aprender código de um botão (controle físico -> Hub)
3) Inferir + testar código de um botão quebrado
4) Ver status dos códigos (codebook)
5) Importar códigos de um controle virtual já existente (app)
m) Enviar código NEC manual (hex)
q) Sair
```

### 4.0 Importar o que o app já aprendeu (opção 5) — comece por aqui

Se você já tentou aprender botões pelo app Tuya Smart (como foi o seu
caso, com o controle "Projetor"), comece pela opção **5**. Cole o
Device ID desse controle virtual quando pedido. O script lista cada
código salvo, mostra o hex decodificado, e você mapeia pro botão
correspondente do nosso projeto (Power, Cima, Baixo, etc.). Isso evita
reaprender do zero pelo CLI.

### 4.1 Aprender os botões que funcionam (opção 2)

Botões suportados para aprendizado: `POWER`, `MUTE`, `REWIND`,
`PLAY/PAUSE`, `FORWARD`, `CIMA`, `DIREITA`, `BAIXO`, `OK`, `VOLTAR`,
`MENU`, `INPUT`, `VOLUME+`.

Fluxo: escolha o botão → aponte o controle físico direto pro Hub →
pressione ENTER → aperte o botão no controle rapidamente. O script
aguarda até 20s por um sinal. O código capturado é decodificado (se
for NEC padrão) e salvo em `codebook.json`.

Use isto para os botões que a importação (opção 5) não trouxe.

### 4.2 Inferir os botões quebrados: ESQUERDA e VOLUME- (opção 3)

Como esses botões não transmitem nada fisicamente, não dá pra
"aprender" — o script gera uma lista de candidatos plausíveis
baseados em padrões de bits observados nos botões vizinhos já
aprendidos/importados (ex: a diferença de bit entre CIMA/BAIXO é
testada também em DIREITA e VOLUME+) e permite testar cada um ao vivo:

1. Escolha `ESQUERDA` ou `VOLUME -`.
2. Para cada candidato, o script pergunta se pode enviar — aponte o
   Hub pro projetor e observe.
3. Se o projetor reagir corretamente (mover o cursor pra esquerda /
   abaixar volume), confirme com `s`. O código é salvo como
   `inferred_confirmed` no codebook e passa a se comportar como
   qualquer outro código aprendido.
4. Se nenhum candidato funcionar, o script avisa — pode ser
   necessário aprender/importar mais botões vizinhos primeiro (mais
   dados = heurística melhor) ou o protocolo real não ser NEC puro.

**Pré-requisitos da inferência:**
- Para `ESQUERDA`: tenha `CIMA`, `BAIXO` e/ou `DIREITA` primeiro.
- Para `VOLUME -`: tenha `VOLUME+` primeiro (e de preferência
  `CIMA`/`BAIXO` também, para reaproveitar o padrão de bits).

### 4.3 Ver status (opção 4)

Mostra, para cada um dos 15 botões, se o código é: aprendido,
importado do app, inferido e confirmado, placeholder (não confirmado)
ou ainda sem código nenhum.

### 4.4 Código manual (opção `m`)

Aceita qualquer código NEC de 32 bits (8 dígitos hex), com ou sem
prefixo `0x` — útil para testar hipóteses rápidas sem passar pelo
fluxo de inferência.

## 5. Estrutura do projeto

```
tuya_ir_cli/
├── .env.example         # modelo das variáveis de ambiente
├── requirements.txt
├── config.py             # carrega/valida config do .env
├── nec_encoder.py         # converte hex NEC -> formato binário Tuya
├── nec_decoder.py         # converte formato binário Tuya -> hex NEC
├── codebook.py            # persiste códigos por botão (codebook.json)
├── inference.py           # heurísticas de inferência p/ botões quebrados
├── tuya_client.py         # autenticação, envio, aprendizado, importação
├── main.py                # CLI interativa
├── codebook.json          # criado automaticamente (códigos por botão)
└── .tuya_remote_cache.json  # criado automaticamente (cache do remote_id)
```

## 6. Solução de problemas

| Sintoma | Causa provável | Solução |
|---|---|---|
| `[ERRO DE AUTENTICAÇÃO]` | Access ID/Secret errados ou endpoint de região errada | Confira a seção Authorization Key e o Data Center do projeto |
| Erro de permissão / "no permission" | Serviço de API não assinado no projeto | Aba Service API → assine "IR Control Hub Open Service" |
| `TUYA_DEVICE_ID` não encontrado / device offline | Hub não vinculado ao projeto ou offline | Refaça o Link Tuya App Account e confirme o Hub online no app |
| Opção 5 (importar) dá erro/lista vazia | O Device ID do "Projetor" pode não valer como `remote_id` diretamente | Confirme que colou o Device ID certo; se persistir, ignore a importação e use aprendizado (opção 2) direto |
| `[SEM SINAL]` ao tentar aprender um botão | Botão realmente quebrado, controle fora de alcance, ou pilha fraca | Troque a pilha, aproxime o controle do Hub; se persistir, o botão está morto — use a inferência (opção 3) |
| Comando aceito mas projetor não reage | Timing NEC incompatível, hub fora do alcance IR, ou protocolo não é NEC puro | Aproxime o hub do projetor; teste `necx2=True` manualmente; para botões aprendidos com `checksum_ok=False`, o sinal pode não ser NEC padrão — nesse caso o reenvio ainda funciona (usa o base64 capturado, não a decodificação) |
| `remote_id` inválido após apagar o controle no app | Cache local desatualizado | O script tenta reprovisionar automaticamente; se não resolver, apague `.tuya_remote_cache.json` |
| Nenhum candidato de inferência funciona | Heurística não bateu com o chip do controle real | Aprenda mais botões vizinhos (mais dados melhoram os candidatos) ou tente valores manuais via opção `m` |

## 7. Notas sobre a inferência

A inferência **não é uma leitura real** — é um chute educado baseado
em como controles remotos NEC baratos costumam mapear botões
fisicamente adjacentes para bits do byte de comando. Ela só fica
disponível para teste ao vivo, nunca é aplicada "no escuro": você
sempre confirma visualmente no projetor antes de qualquer código ser
salvo como definitivo.

Na prática, pra esse controle específico, a inferência por heurística
de bits **não bateu** — o chip não segue um padrão simples e previsível
(ver seção 9 abaixo pra saber o que funcionou de verdade).

## 8. Bugs reais encontrados e corrigidos

Durante os testes contra o Hub de verdade (nunca validados antes,
só contra mocks), apareceram quatro bugs reais na implementação
original — sendo o primeiro deles grave o bastante para invalidar
horas de testes:

0. **`nec_encoder.py` gerava o formato errado — falha silenciosa.**
   O encoder produzia `base64 + FastLZ comprimido` (formato
   documentado em vários projetos de engenharia reversa da Tuya), mas
   o endpoint
   `POST /v2.0/infrareds/{id}/remotes/{remote_id}/learning-codes`
   **deste Hub** espera **hex cru** (durações uint16 little-endian,
   sem compressão e sem base64). O pior: a API **aceita** o base64 e
   responde `success: true` — mas o Hub não emite o IR corretamente.
   Nenhum erro, nenhum aviso, simplesmente nada acontece no aparelho.

   Consequência: toda a varredura de força bruta feita para descobrir
   os botões quebrados era inútil. O código correto do botão ESQUERDA
   (`0x00FF9B64`) chegou a ser testado individualmente e "não
   funcionou" — quando na verdade o payload é que estava no formato
   errado. O mesmo código, enviado verbatim em hex cru, funciona
   perfeitamente.

   Como foi diagnosticado: enviando um código **sabidamente
   funcional** (BAIXO, `0x00FF9A65`) pelos dois caminhos. Via hex cru
   o cursor desceu; via `encode_nec()` não aconteceu nada. Teste de
   controle simples que deveria ter sido feito no começo.

   Correção: `encode_nec()` agora gera hex cru, usando os timings de
   um **molde** extraído de um código real capturado pelo app
   (`8889 / 4513 / 563 / 1703`, em vez dos valores "de livro"
   `9000 / 4500 / 560 / 1690`). Gerar `0x00FF9B64` com esse molde
   produz um payload **byte a byte idêntico** ao do app — validado por
   comparação exata, e o `__main__` do módulo roda esse assert. O
   encoder antigo continua disponível como
   `encode_nec_base64_legacy()`, só para referência.

Os outros três:

1. **`nec_decoder.py` só sabia decodificar um dos dois formatos que a
   Tuya usa.** `durations_from_tuya_code()` assumia que todo código
   vinha em base64 + FastLZ comprimido (formato que `nec_encoder.py`
   produz, usado ao *provisionar* um controle virtual novo). Só que o
   endpoint `GET /remotes/{remote_id}/learning-codes` — usado tanto
   pra importar códigos do app quanto pra listar o que já foi
   aprendido — devolve os códigos em **hex cru** (durações não
   comprimidas, sem base64). Isso derrubava a opção de importar com
   uma exceção não tratada. Corrigido: agora tenta base64+FastLZ
   primeiro e cai pra hex cru se a descompressão falhar.

2. **`tuya_client.py._provision_remote` lia a resposta errado.**
   Esperava `resp["result"]["remote_id"]`, mas a API devolve
   `resp["result"]` como a própria string do `remote_id` (sem
   aninhamento). Toda vez que o script provisionava um controle
   virtual novo, quebrava com `TypeError: string indices must be
   integers`.

3. **Erro de assinatura (`sign invalid`, code 1004) em `enable_learning`/
   `disable_learning`.** Essas funções chamavam `openapi.put(path, {})`
   passando um dicionário vazio como corpo. A biblioteca da Tuya
   calcula a assinatura HMAC tratando corpo vazio como hash de uma
   string vazia, mas a lib `requests`, ao receber `json={}` (dict
   vazio, não `None`), serializa e envia `"{}"` como corpo literal —
   descasando do que foi assinado. Resultado: toda tentativa de
   aprendizado real (opção 2) falhava com erro de assinatura. Corrigido
   passando `None` em vez de `{}`.

## 9. Como ESQUERDA e VOLUME- foram resolvidos

**ESQUERDA:** a heurística de inferência por bits não encontrou o
código certo — na verdade, uma varredura exaustiva de **todos os 256
comandos possíveis** no endereço `0x00` (o mesmo dos outros 13
botões) não encontrou nada, mesmo o código certo (`0x9B`) estando
tecnicamente dentro dessa faixa e tendo sido testado individualmente
na época. O que resolveu: o usuário conseguiu cadastrar o botão Left
diretamente no **app Tuya Smart**, no fluxo de "combinar código" do
template do controle "Projetor". Isso ficou visível via API
(`GET /remotes/{remote_id}/learning-codes` no `remote_id` do
"Projetor") como uma nova entrada `key_name='navigate_left'`.

Curiosamente, reenviar o mesmo código de 4 bytes (`0x00FF9B64`)
**resintetizado do zero** por `nec_encoder.encode_nec()` não fazia o
projetor reagir — só funcionou reenviando o payload **verbatim**
(a string exata que a API devolveu, sem recodificar). Ou seja, pra
esse controle específico, a codificação NEC "por livro" do encoder
não reproduz 100% o que o hardware espera (provavelmente alguma
nuance de timing); o valor real de 4 bytes bate, mas os pulsos
sintetizados não são bit-a-bit idênticos aos originais.

**VOLUME- (`0x00FF9C63`):** resolvido por varredura manual depois que
o bug do encoder (item 0 acima) foi corrigido. O valor `0x9C` já tinha
sido testado logo no começo do projeto — e "falhou", porque o payload
saía no formato errado.

Uma tentativa intermediária chegou a dar `0x00FF8B74` como confirmado,
mas era **falso positivo**: o script de teste da época mandava um
`VOLUME+` antes de cada candidato "pra abrir a barra de volume na
tela", e o que se via subindo era esse `VOLUME+`, não o candidato.
Lição: script de teste não deve injetar comandos que o usuário não
pediu — contamina o experimento.

### O padrão real dos códigos

Com os 15 botões mapeados, dá pra ver como o chip do controle numera
as teclas — e por que as heurísticas de inferência falharam:

| cmd | botão | | cmd | botão |
|---|---|---|---|---|
| `0x82` | FORWARD | | `0x99` | DIREITA |
| `0x88` | MUTE | | `0x9A` | BAIXO |
| `0x8C` | VOLUME+ | | `0x9B` | ESQUERDA |
| `0x91` | MENU | | `0x9C` | VOLUME- |
| `0x93` | PLAY_PAUSE | | `0x9E` | OK |
| `0x95` | CIMA | | `0xA4` | VOLTAR |
| `0x97` | INPUT | | `0xA8` | POWER |
| `0x98` | REWIND | | | |

Observações que quebram as suposições "óbvias":

- **Pares funcionais não são numericamente vizinhos.** FORWARD
  (`0x82`) e REWIND (`0x98`) são o par mais óbvio do controle e estão
  a 22 valores de distância. Por isso procurar VOLUME- ao lado de
  VOLUME+ (`0x8C`) nunca fez sentido — ele está em `0x9C`.
- **VOLUME+ e VOLUME- diferem por exatamente 1 bit** (`0x8C` vs
  `0x9C`, bit 4). A heurística de "inverter um bit" existia no
  `inference.py`, mas só era aplicada aos bits 0 e 1 — nunca aos bits
  altos.
- **O bloco `0x98`–`0x9C` é contíguo**: REWIND, DIREITA, BAIXO,
  ESQUERDA, VOLUME-. Os dois botões quebrados eram vizinhos diretos
  um do outro, o que só ficou visível depois de descobrir os dois.
- A numeração não segue nem a posição física dos botões nem
  agrupamento por função — é a ordem de varredura da matriz do chip,
  que não dá pra deduzir de fora.

**Conclusão honesta sobre a inferência:** para este controle, nenhuma
heurística de bits teria acertado. O que resolveu foi (a) consertar o
formato do payload e (b) varredura exaustiva com confirmação visual a
cada disparo. O valor do `inference.py` acabou sendo mais o de ordenar
os candidatos do que o de adivinhar o certo.

## 10. Exportar o codebook pro app Tuya Smart

Depois de mapear tudo, dá pra criar um controle virtual **de verdade**
dentro do app Tuya Smart, com todas as 15 teclas persistidas — não só
disparo avulso, aparece lá igual um controle normal.

A pegadinha: o endpoint `POST /v2.0/infrareds/{id}/learning-codes`
(que cria um controle novo e salva a lista de teclas) exige um campo
**`key`** em cada item de `codes` — é obrigatório segundo a
[documentação oficial](https://developer.tuya.com/en/docs/cloud/837dd9e219?id=Kb3oeazmud83g),
mas fácil de não notar porque a API **aceita silenciosamente** um
payload sem ele e responde `success: true` mesmo assim — só que
nenhuma tecla fica salva. `key_name` sozinho (o que a gente vinha
usando) não é suficiente; ele é só um rótulo de exibição opcional.

```python
codes = [{"key": nome, "key_name": nome, "code": entry["code_b64"]}
         for nome, entry in codebook.all_entries().items()]

body = {
    "category_id": 6,      # Projector, na taxonomia da Tuya
    "brand_id": 999999,    # "Outro" / genérico
    "remote_name": "Projetor AUN ET30 (CLI)",
    "codes": codes,
}
client.openapi.post(f"/v2.0/infrareds/{device_id}/learning-codes", body)
```

O controle virtual gerado assim aparece no app Tuya Smart como
qualquer outro, com as 15 teclas prontas pra usar por lá também — sem
depender do CLI.

### 10.1 Os ícones do app (setas, OK, volume, etc.) — o campo `id` importa

Criar o controle com o `key` certo (ex: `navigate_up`, `volume_down`,
`power`) já é suficiente pra API aceitar e a tecla aparecer com o
nome certo — mas os **ícones gráficos** do app (o D-pad, os botões de
energia/volume/mute) ficam **desabilitados** se o campo `id` de cada
código não bater com o ID padrão do catálogo interno da Tuya. Sem um
`id` explícito, a API auto-gera um contador sequencial (1, 2, 3...)
que não corresponde a nada — o app aceita e mostra a tecla na lista
"Mais" (extras), mas não liga ela ao ícone.

IDs padrão descobertos comparando com um controle que o próprio app
Tuya já tinha montado corretamente (uma marca gravada como "Outro",
categoria 6 = Projetor):

| `key` | `id` | função |
|---|---|---|
| `power` | 1 | Energia |
| `ok` | 42 | OK |
| `menu` | 45 | Menu |
| `navigate_up` | 46 | Cima |
| `navigate_down` | 47 | Baixo |
| `navigate_left` | 48 | Esquerda |
| `navigate_right` | 49 | Direita |
| `volume_up` | 50 | Volume+ |
| `volume_down` | 51 | Volume- |
| `mute` | 106 | Mudo |
| `back` | 116 | Voltar |

Botões sem ícone padrão (ex: Input, Rewind, Forward, Play/Pause) não
têm `id` fixo — usam um número qualquer, único, fora dessa faixa
(ex: `900001`, `900002`...), e continuam acessíveis pela lista "Mais"
do app, exatamente como no controle original.

**Cuidado com colisão de `id`:** se algum código no lote não tiver
`id` explícito, a API auto-gera um sequencial (1, 2, 3...) que pode
colidir com um `id` fixo usado por outro código do mesmo lote — quem
processa por último "vence" e o outro código **desaparece
silenciosamente** (nem erro, nem aviso; a contagem final de chaves
salvas só fica menor que o esperado). Sempre informe um `id` explícito
e exclusivo pra cada código do lote, mesmo os sem ícone padrão.

**Scripts auxiliares criados durante essa investigação** (ficam na
raiz do projeto, não fazem parte do fluxo principal do `main.py`):

- `scan_missing_buttons.py` / `remote_voldown.py` — varredura em lote
  ou testes numerados de candidatos, pra rodar localmente sem o
  limite de tempo por comando que uma sessão de agente tem.
- `test_candidates_interactive.py` — menu interativo pra testar e
  salvar candidatos um a um.
- `remote.py` — "controle remoto" no terminal (Windows, via
  `msvcrt`): aperta uma tecla e o comando dispara na hora, sem ENTER,
  pra testar rapidamente todos os botões já mapeados.
