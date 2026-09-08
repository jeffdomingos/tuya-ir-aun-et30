*[Read in English (US)](README.en.md)*

# Códigos IR do controle remoto — Projetor AUN ET30

Mapa completo dos códigos infravermelhos do controle remoto que
acompanha o mini projetor **AUN ET30**. Esses códigos não estavam
documentados em nenhum lugar público antes deste repositório (sem
resultado nos bancos de dados de IR mais conhecidos — irdb,
Flipper-IRDB, RemoteCentral — nem em fóruns) e foram obtidos por
engenharia reversa, com bastante tentativa e erro.

Se seu controle **parece igual** a esse (mesmo layout de botões, mesmo
mini projetor genérico vendido sob marcas diferentes — comum em
projetores baratos de AliExpress/Amazon rebranded) e esses códigos
funcionarem no seu aparelho, **abra uma issue ou PR** contando qual é
a marca/modelo do seu projetor — ajuda a mapear a família de
controles que usa esse mesmo chip. Veja [CONTRIBUTING.md](CONTRIBUTING.md).

## Modelos possivelmente compatíveis (não confirmado)

O único aparelho que eu de fato tenho para testar é o **AUN ET30**,
então os códigos acima são confirmados apenas nele. Porém, encontrei
anúncios de controles remotos de reposição vendidos como compatíveis
com vários modelos ao mesmo tempo, o que sugere que compartilham o
mesmo chip/layout de comandos:

- [Remote Control for AUN ET40C A30 A30C ET40 ET30 ET30S / Artlii YG600 US-YG600B YG620 YG220 (Amazon)](https://www.amazon.com/dp/B0DK75XS2R)
- [Remote Control For AUN ET40C A30 A30C ET40 ET30 ET30S AKEY7 (eBay)](https://www.ebay.com/itm/176633915628)

Modelos citados nesses anúncios: **AUN ET40C, A30, A30C, ET40, ET30S**,
**Artlii YG600, US-YG600B, YG620, YG220**, **AKEY7**. Se você tiver um
desses e os códigos funcionarem (ou não), por favor abra uma issue —
isso confirma (ou descarta) a compatibilidade de verdade.

## Protocolo

- **Protocolo:** NEC padrão, 32 bits (endereço + ~endereço + comando +
  ~comando), portadora de 38 kHz.
- **Endereço:** `0x00` em todos os botões.
- **Timings reais medidos:** leader mark `8889µs`, leader space
  `4513µs`, bit mark `563µs`, space do bit `0` = `563µs`, space do bit
  `1` = `1703µs`, stop mark `563µs`.

> **Nota de aplicabilidade:** os timings "de livro" do NEC
> (9000/4500/560/1690µs) também decodificam esses sinais corretamente
> na maioria dos receptores (a tolerância cobre a diferença), mas
> alguns emissores/receptores mais rígidos só aceitam os timings
> **exatos e medidos** acima. Se sua implementação não reagir com os
> valores padrão, use os valores reais medidos. O encoder de
> referência deste repositório (`nec_encoder.py`) já gera a saída
> correta usando esses timings reais — validado byte a byte contra
> uma captura verbatim do controle físico.

## Tabela de códigos

Todos no endereço `0x00`. Código NEC completo = `00FF` + comando + `~comando`.

| Botão | Comando (hex) | Código NEC completo |
|---|---|---|
| POWER | `0xA8` | `0x00FFA857` |
| VOLTAR (back) | `0xA4` | `0x00FFA45B` |
| OK | `0x9E` | `0x00FF9E61` |
| VOLUME- | `0x9C` | `0x00FF9C63` |
| ESQUERDA (seta esquerda) | `0x9B` | `0x00FF9B64` |
| BAIXO (seta pra baixo) | `0x9A` | `0x00FF9A65` |
| DIREITA (seta direita) | `0x99` | `0x00FF9966` |
| REWIND (retroceder) | `0x98` | `0x00FF9867` |
| INPUT / SOURCE | `0x97` | `0x00FF9768` |
| CIMA (seta pra cima) | `0x95` | `0x00FF956A` |
| PLAY/PAUSE | `0x93` | `0x00FF936C` |
| MENU | `0x91` | `0x00FF916E` |
| VOLUME+ | `0x8C` | `0x00FF8C73` |
| MUTE | `0x88` | `0x00FF8877` |
| FORWARD (avançar) | `0x82` | `0x00FF827D` |

Repare que os comandos não seguem a posição física dos botões nem
agrupamento lógico óbvio — a numeração é a ordem de varredura da
matriz do chip do controle, não algo dedutível de fora.

## Formatos prontos pra usar

- [`AUN_ET30.ir`](AUN_ET30.ir) — formato **Flipper Zero** (protocolo NEC nativo).
- [`AUN_ET30.lircd.conf`](AUN_ET30.lircd.conf) — formato **LIRC** (`lircd.conf`).
- [`codebook.json`](codebook.json) — inclui o hex NEC de cada botão
  mais o payload binário específico da API da Tuya (usado pelo CLI
  deste repositório).

Qualquer ferramenta que aceite NEC cru (Arduino + `IRremote`,
ESPHome, Tasmota, ferramentas de captura/replay genéricas) pode usar
diretamente os valores da tabela acima — endereço `0x00`, comando
conforme a coluna.

## Ferramentas neste repositório

Além do mapa de códigos, este repositório inclui:

- `nec_encoder.py` / `nec_decoder.py` — codificam/decodificam NEC ↔
  formato binário da Tuya, usando os timings reais medidos acima.
  Rode `python3 nec_encoder.py` e `python3 nec_decoder.py` pra ver o
  auto-teste de round-trip.
- Um **CLI Python completo** para quem usa um Hub Smart IR da Tuya
  via Cloud API (aprender, disparar e importar códigos). Não é
  necessário se você só quer os códigos — ver
  [TUYA_CLI.md](TUYA_CLI.md) caso esse seja o seu caso.

## Licença

[MIT](LICENSE).
