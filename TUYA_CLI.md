*[Read in English (US)](TUYA_CLI.en.md)*

# CLI Python + Tuya Cloud API — guia completo

> Este documento é só necessário se você quiser usar o **CLI Python
> deste repositório** com um Hub Smart IR da Tuya (aprender, disparar
> e importar códigos via API Cloud). Se você só quer os códigos IR do
> controle da AUN ET30 pra usar do seu jeito, veja [README.md](README.md)
> — não precisa de nada daqui.

CLI em Python que controla o projetor AUN ET30 através de um Hub
Smart IR da Tuya via **API Cloud**. Suporta três formas de obter um
código IR:

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

Normalmente aparecem dois dispositivos relevantes:
- **Smart IR** — o Hub físico de verdade. O Device ID dele vai em `TUYA_DEVICE_ID`.
- Um controle virtual que o próprio app já criou/aprendeu
  parcialmente (ex: "Projetor"). O Device ID dele é usado como
  `remote_id` na opção **5** do menu (importar códigos já aprendidos
  pelo app).

Se o `TUYA_ENDPOINT` do `.env.example` não bater com o Data Center
escolhido, ajuste conforme a lista de regiões no próprio arquivo.

## 2. Instalação

```bash
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

Se você já tentou aprender botões pelo app Tuya Smart, comece pela
opção **5**. Cole o Device ID desse controle virtual quando pedido. O
script lista cada código salvo, mostra o hex decodificado, e você
mapeia pro botão correspondente. Isso evita reaprender do zero pelo
CLI.

### 4.1 Aprender os botões que funcionam (opção 2)

Fluxo: escolha o botão → aponte o controle físico direto pro Hub →
pressione ENTER → aperte o botão no controle rapidamente. O script
aguarda até 20s por um sinal. O código capturado é decodificado (se
for NEC padrão) e salvo em `codebook.json`.

Use isto para os botões que a importação (opção 5) não trouxe.

### 4.2 Inferir botões fisicamente quebrados (opção 3)

Para botões que não transmitem nada fisicamente, não dá pra
"aprender" — o script gera uma lista de candidatos plausíveis
baseados em padrões de bits observados nos botões vizinhos já
aprendidos/importados e permite testar cada um ao vivo:

1. Escolha o botão quebrado.
2. Para cada candidato, o script pergunta se pode enviar — aponte o
   Hub pro aparelho e observe.
3. Se o aparelho reagir corretamente, confirme com `s`. O código é
   salvo como `inferred_confirmed` no codebook e passa a se comportar
   como qualquer outro código aprendido.
4. Se nenhum candidato funcionar, o script avisa — pode ser
   necessário aprender/importar mais botões vizinhos primeiro (mais
   dados = heurística melhor) ou o protocolo real não ser NEC puro.

**Aviso honesto:** para o controle da AUN ET30 especificamente, essa
heurística de bits **não funcionou** — veja a seção
["Lições da AUN ET30"](#6-lições-da-aun-et30-o-que-realmente-funcionou-e-o-que-não)
abaixo pra entender por quê e o que funcionou de verdade.

### 4.3 Ver status (opção 4)

Mostra, para cada botão, se o código é: aprendido, importado do app,
inferido e confirmado, placeholder (não confirmado) ou ainda sem
código nenhum.

### 4.4 Código manual (opção `m`)

Aceita qualquer código NEC de 32 bits (8 dígitos hex), com ou sem
prefixo `0x` — útil para testar hipóteses rápidas sem passar pelo
fluxo de inferência.

## 5. Solução de problemas

| Sintoma | Causa provável | Solução |
|---|---|---|
| `[ERRO DE AUTENTICAÇÃO]` | Access ID/Secret errados ou endpoint de região errada | Confira a seção Authorization Key e o Data Center do projeto |
| Erro de permissão / "no permission" | Serviço de API não assinado no projeto | Aba Service API → assine "IR Control Hub Open Service" |
| `TUYA_DEVICE_ID` não encontrado / device offline | Hub não vinculado ao projeto ou offline | Refaça o Link Tuya App Account e confirme o Hub online no app |
| Opção 5 (importar) dá erro/lista vazia | O Device ID do controle virtual pode não valer como `remote_id` diretamente | Confirme que colou o Device ID certo; se persistir, ignore a importação e use aprendizado (opção 2) direto |
| `[SEM SINAL]` ao tentar aprender um botão | Botão realmente quebrado, controle fora de alcance, ou pilha fraca | Troque a pilha, aproxime o controle do Hub; se persistir, o botão está morto — use a inferência (opção 3) |
| Comando aceito mas aparelho não reage | Timing NEC incompatível, hub fora do alcance IR, protocolo não é NEC puro, **ou o payload está no formato errado** (ver seção 6) | Aproxime o hub do aparelho; teste `necx2=True` manualmente; para botões aprendidos com `checksum_ok=False`, o sinal pode não ser NEC padrão — nesse caso o reenvio ainda funciona (usa o base64 capturado, não a decodificação) |
| `remote_id` inválido após apagar o controle no app | Cache local desatualizado | O script tenta reprovisionar automaticamente; se não resolver, apague `.tuya_remote_cache.json` |
| Nenhum candidato de inferência funciona | Heurística não bateu com o chip do controle real | Aprenda mais botões vizinhos (mais dados melhoram os candidatos) ou tente valores manuais via opção `m` |

## 6. Lições da AUN ET30: o que realmente funcionou (e o que não)

Esta seção documenta os problemas reais enfrentados ao usar este CLI
contra um Hub de verdade — úteis se você for adaptar este código pra
outro aparelho/Hub, mesmo que os códigos específicos da AUN ET30 não
te interessem.

### 6.1 O bug mais grave: formato de payload errado, falha silenciosa

`nec_encoder.py` originalmente produzia `base64 + FastLZ comprimido`
(o formato documentado em vários projetos de engenharia reversa da
Tuya), mas o endpoint
`POST /v2.0/infrareds/{id}/remotes/{remote_id}/learning-codes`
**deste Hub específico** espera **hex cru** (durações uint16
little-endian, sem compressão e sem base64). O pior: a API **aceita**
o base64 e responde `success: true` — mas o Hub não emite o IR
corretamente. Nenhum erro, nenhum aviso, simplesmente nada acontece
no aparelho.

Como foi diagnosticado: enviando um código **sabidamente funcional**
pelos dois caminhos. Via hex cru o aparelho reagiu; via
`encode_nec()` não aconteceu nada — um teste de controle simples que
deveria ter sido feito desde o início, sempre que um "código correto"
parecer não funcionar.

Correção: `encode_nec()` agora gera hex cru, usando os timings de um
**molde** extraído de um código real capturado pelo app (veja
[README.md](README.md#protocolo)), em vez dos valores "de livro" do
NEC. O encoder antigo continua disponível como
`encode_nec_base64_legacy()`, só para referência — **não use pra
enviar comandos de verdade**.

**Lição pra qualquer Hub IR baseado em Tuya:** antes de assumir que um
código está errado, confirme o formato de payload que o endpoint
específico do seu Hub espera, testando um código *sabidamente
funcional* pelos dois caminhos (síntese vs. captura verbatim).

### 6.2 Outros três bugs reais encontrados

1. **`nec_decoder.py` só sabia decodificar um dos dois formatos que a
   Tuya usa.** `durations_from_tuya_code()` assumia que todo código
   vinha em base64 + FastLZ comprimido. Só que o endpoint
   `GET /remotes/{remote_id}/learning-codes` devolve os códigos em
   **hex cru**. Isso derrubava a opção de importar com uma exceção
   não tratada. Corrigido: agora tenta base64+FastLZ primeiro e cai
   pra hex cru se a descompressão falhar.

2. **`tuya_client.py._provision_remote` lia a resposta errado.**
   Esperava `resp["result"]["remote_id"]`, mas a API devolve
   `resp["result"]` como a própria string do `remote_id` (sem
   aninhamento).

3. **Erro de assinatura (`sign invalid`, code 1004) em
   `enable_learning`/`disable_learning`.** Essas funções chamavam
   `openapi.put(path, {})` passando um dicionário vazio como corpo. A
   lib `requests`, ao receber `json={}` (dict vazio, não `None`),
   serializa e envia `"{}"` como corpo literal — descasando da
   assinatura HMAC calculada pela Tuya (que trata corpo vazio como
   hash de string vazia). Corrigido passando `None` em vez de `{}`.

### 6.3 Botões fisicamente quebrados: quando a inferência por bits não basta

Dois botões do controle da AUN ET30 (Left e Volume-) estavam
fisicamente quebrados e não transmitiam nada. A heurística de
inferência por bits (`inference.py`) parte do princípio de que
controles NEC baratos mapeiam botões fisicamente adjacentes para bits
vizinhos do byte de comando — mas isso **não se confirmou** neste
controle: uma varredura exaustiva de todos os 256 comandos possíveis
não encontrou os valores certos na época, porque o payload gerado
estava no formato errado (seção 6.1). Depois de corrigido o encoder,
os valores corretos foram achados por varredura manual com
confirmação visual a cada disparo — não por heurística.

O padrão real dos comandos (ver tabela em
[README.md](README.md#tabela-de-códigos)) mostra que a numeração das
teclas segue a ordem de varredura da matriz do chip, não a posição
física nem agrupamento lógico dos botões — então pares "óbvios" como
Volume+/Volume- podem estar longe um do outro em termos de bits.

**Cuidado ao testar candidatos:** não injete comandos extras "pra
ajudar a visualizzar" (ex: mandar Volume+ antes de testar um
candidato de Volume- pra abrir a barra na tela) — isso contamina o
teste e pode gerar falsos positivos. Teste sempre um comando isolado
por vez.

### 6.4 Exportar o codebook pro app Tuya Smart

Depois de mapear tudo, dá pra criar um controle virtual **de verdade**
dentro do app Tuya Smart, com todas as teclas persistidas — não só
disparo avulso, aparece lá igual um controle normal.

A pegadinha: o endpoint `POST /v2.0/infrareds/{id}/learning-codes`
(que cria um controle novo e salva a lista de teclas) exige um campo
**`key`** em cada item de `codes` — é obrigatório segundo a
[documentação oficial](https://developer.tuya.com/en/docs/cloud/837dd9e219?id=Kb3oeazmud83g),
mas fácil de não notar porque a API **aceita silenciosamente** um
payload sem ele e responde `success: true` mesmo assim — só que
nenhuma tecla fica salva. `key_name` sozinho não é suficiente; ele é
só um rótulo de exibição opcional.

```python
codes = [{"key": nome, "key_name": nome, "code": entry["code_b64"]}
         for nome, entry in codebook.all_entries().items()]

body = {
    "category_id": 6,      # Projector, na taxonomia da Tuya
    "brand_id": 999999,    # "Outro" / genérico
    "remote_name": "Meu Controle Custom",
    "codes": codes,
}
client.openapi.post(f"/v2.0/infrareds/{device_id}/learning-codes", body)
```

#### Os ícones do app (setas, OK, volume, etc.) — o campo `id` importa

Criar o controle com o `key` certo (ex: `navigate_up`, `volume_down`,
`power`) já é suficiente pra API aceitar e a tecla aparecer com o
nome certo — mas os **ícones gráficos** do app (o D-pad, os botões de
energia/volume/mute) ficam **desabilitados** se o campo `id` de cada
código não bater com o ID padrão do catálogo interno da Tuya. Sem um
`id` explícito, a API auto-gera um contador sequencial (1, 2, 3...)
que não corresponde a nada — o app aceita e mostra a tecla na lista
"Mais" (extras), mas não liga ela ao ícone.

IDs padrão descobertos comparando com um controle que o próprio app
Tuya já tinha montado corretamente (categoria 6 = Projetor):

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
do app.

**Cuidado com colisão de `id`:** se algum código no lote não tiver
`id` explícito, a API auto-gera um sequencial (1, 2, 3...) que pode
colidir com um `id` fixo usado por outro código do mesmo lote — quem
processa por último "vence" e o outro código **desaparece
silenciosamente** (nem erro, nem aviso). Sempre informe um `id`
explícito e exclusivo pra cada código do lote, mesmo os sem ícone
padrão.

## 7. Estrutura do projeto

```
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
