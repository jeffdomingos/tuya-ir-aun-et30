*[Read in English (US)](IR_CODES.en.md)*

# Códigos IR do controle remoto — AUN ET30 (e possíveis modelos irmãos)

Referência standalone dos códigos infravermelhos do controle remoto
que acompanha o mini projetor **AUN ET30**. Esses códigos **não
estavam documentados em nenhum lugar público** até este repositório
(sem resultado nos bancos de dados de IR mais conhecidos — irdb,
Flipper-IRDB, RemoteCentral — nem em fóruns) — foram descobertos por
engenharia reversa através de um Hub Smart IR da Tuya, com bastante
tentativa e erro. Veja [README.md](README.md) pela história completa
de como cada um foi descoberto (alguns por captura real, outros por
varredura de força bruta).

Se seu controle **parece igual** a esse (mesmo layout de botões,
mesmo mini projetor genérico vendido sob marcas diferentes — comum em
projetores baratos de AliExpress/Amazon rebranded) e esses códigos
funcionarem no seu aparelho, **abra uma issue ou PR** contando qual é
a marca/modelo do seu projetor — ajuda a mapear a família de
controles que usa esse mesmo chip.

## Protocolo

- **Protocolo:** NEC padrão, 32 bits (endereço + ~endereço + comando
  + ~comando), portadora de 38 kHz.
- **Endereço:** `0x00` em todos os botões confirmados.
- **Timings reais medidos** (fora do "livro" do NEC — veja nota
  abaixo): leader mark `8889µs`, leader space `4513µs`, bit mark
  `563µs`, space do bit `0` = `563µs`, space do bit `1` = `1703µs`,
  stop mark `563µs`.

> **Nota importante para quem for reimplementar isso:** os timings
> "de livro" do NEC (9000/4500/560/1690µs) também decodificam esses
> sinais corretamente (a tolerância de qualquer receptor IR cobre a
> diferença), mas alguns emissores/receptores específicos (como o Hub
> usado aqui) só aceitam os timings **exatos e medidos**, não os
> valores padrão. Se seus testes com os timings de livro não
> funcionarem, use os valores reais acima.

## Tabela de códigos

Todos no endereço `0x00`. Código NEC completo = `00FF` + comando + `~comando`.

| Botão | Comando (hex) | Código NEC completo | Origem |
|---|---|---|---|
| FORWARD (avançar) | `0x82` | `0x00FF827D` | capturado (aprendizado real) |
| MUTE | `0x88` | `0x00FF8877` | importado do app Tuya Smart |
| VOLUME+ | `0x8C` | `0x00FF8C73` | importado do app Tuya Smart |
| MENU | `0x91` | `0x00FF916E` | importado do app Tuya Smart |
| PLAY/PAUSE | `0x93` | `0x00FF936C` | capturado (aprendizado real) |
| CIMA (seta pra cima) | `0x95` | `0x00FF956A` | importado do app Tuya Smart |
| INPUT / SOURCE | `0x97` | `0x00FF9768` | importado do app Tuya Smart |
| REWIND (retroceder) | `0x98` | `0x00FF9867` | capturado (aprendizado real) |
| DIREITA (seta direita) | `0x99` | `0x00FF9966` | importado do app Tuya Smart |
| BAIXO (seta pra baixo) | `0x9A` | `0x00FF9A65` | importado do app Tuya Smart |
| ESQUERDA (seta esquerda) | `0x9B` | `0x00FF9B64` | importado do app Tuya Smart |
| VOLUME- | `0x9C` | `0x00FF9C63` | varredura + confirmação ao vivo |
| OK | `0x9E` | `0x00FF9E61` | importado do app Tuya Smart |
| VOLTAR (back) | `0xA4` | `0x00FFA45B` | importado do app Tuya Smart |
| POWER | `0xA8` | `0x00FFA857` | importado do app Tuya Smart |

Repare que os comandos não seguem a posição física dos botões nem
agrupamento lógico óbvio (POWER e VOLTAR estão isolados longe dos
outros; o bloco `0x98`–`0x9C` concentra REWIND/DIREITA/BAIXO/
ESQUERDA/VOLUME- só por coincidência de varredura da matriz do chip).
Detalhes de como cada valor foi encontrado estão no
[README.md, seção 9](README.md#9-como-esquerda-e-volume--foram-resolvidos).

## Formatos prontos pra usar

- [`AUN_ET30.ir`](AUN_ET30.ir) — formato **Flipper Zero** (protocolo NEC nativo).
- [`AUN_ET30.lircd.conf`](AUN_ET30.lircd.conf) — formato **LIRC** (`lircd.conf`).
- [`codebook.json`](codebook.json) — formato usado pelo CLI deste
  repositório (inclui o payload binário específico da API da Tuya,
  além do hex NEC puro).

Qualquer ferramenta que aceite NEC cru (Arduino + `IRremote`,
ESPHome, Tasmota, ferramentas de captura/replay genéricas) pode usar
diretamente os valores da tabela acima — endereço `0x00`, comando
conforme a coluna.
